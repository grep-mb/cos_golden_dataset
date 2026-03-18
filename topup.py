import json
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from scraper import (
    BASE_URL,
    JSONL_PATH,
    STATE_PATH,
    _dismiss_cookie_banner,
    _scroll_to_load_products,
    append_jsonl,
    download_images,
    extract_product_id,
    generate_csv,
    log,
    random_delay,
    scrape_product,
)


def get_current_counts():
    men = women = 0
    scraped_ids = set()
    if JSONL_PATH.exists():
        with open(JSONL_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                scraped_ids.add(r["source_product_id"])
                if r["section"] == "men":
                    men += 1
                else:
                    women += 1
    return men, women, scraped_ids


def discover_extra_urls(page, section, scraped_ids, needed, already_discovered):
    """Find product URLs not yet scraped from deeper subcategories."""
    known_ids = set(scraped_ids) | set(extract_product_id(u) for u in already_discovered if extract_product_id(u))

    # Subcategories to try (different from the ones already exhausted)
    extra_subcats = {
        "men": [
            "knitwear",
            "coats-and-jackets",
            "jeans",
            "shoes",
            "suits",
            "polo-shirts",
            "sweatshirts",
            "underwear",
            "co-ords",
            "accessories-all",
            "bags-and-wallets",
            "belts",
            "hats-scarves-and-gloves",
            "jewellery",
            "linen-collection",
            "wardrobe-essentials",
        ],
        "women": [
            "dresses",
            "skirts",
            "knitwear",
            "coats-and-jackets",
            "jeans",
            "shoes",
            "tops",
            "accessories-all",
            "bags-and-wallets",
            "jewellery",
            "swimwear",
            "lingerie",
            "co-ords",
            "shorts",
        ],
    }

    new_urls = []
    for subcat in extra_subcats.get(section, []):
        if len(new_urls) >= needed * 3:  # gather extra in case some lack "Style with"
            break

        cat_url = f"{BASE_URL}/{section}/{subcat}"
        log.info("Discovering extras from %s", cat_url)
        try:
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(2, 3)
            _dismiss_cookie_banner(page)
            _scroll_to_load_products(page, max_scrolls=10)

            links = page.query_selector_all('a[href*="/product/"]')
            for link in links:
                href = link.get_attribute("href")
                if not href:
                    continue
                full_url = urljoin(BASE_URL, href)
                pid = extract_product_id(full_url)
                if pid and pid not in known_ids:
                    known_ids.add(pid)
                    new_urls.append(full_url)
        except PlaywrightTimeout:
            log.warning("Timeout on %s, skipping", cat_url)
        except Exception as e:
            log.warning("Error on %s: %s", cat_url, e)

        random_delay(1, 2)

    log.info("Found %d new candidate URLs for %s (need %d)", len(new_urls), section, needed)
    return new_urls


def main():
    men_count, women_count, scraped_ids = get_current_counts()
    men_needed = max(0, 100 - men_count)
    women_needed = max(0, 100 - women_count)
    log.info("Current: men=%d, women=%d. Need: men=+%d, women=+%d", men_count, women_count, men_needed, women_needed)

    if men_needed == 0 and women_needed == 0:
        log.info("Already at 100+100, nothing to do")
        return

    # Load existing discovered URLs to avoid re-visiting
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    already_discovered = {}
    for section in ["men", "women"]:
        already_discovered[section] = state.get("discovered_urls", {}).get(section, [])

    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_vendor_override="Google Inc.",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB")
        stealth.apply_stealth_sync(context)
        page = context.new_page()

        for section, needed in [("men", men_needed), ("women", women_needed)]:
            if needed <= 0:
                continue

            log.info("=== Top-up: need %d more for %s ===", needed, section)
            extra_urls = discover_extra_urls(
                page,
                section,
                scraped_ids,
                needed,
                already_discovered[section],
            )

            scraped_this = 0
            for url in extra_urls:
                if scraped_this >= needed:
                    break

                pid = extract_product_id(url)
                if not pid or pid in scraped_ids:
                    continue

                record = scrape_product(page, url, section)
                if record is None:
                    random_delay(1, 2)
                    continue

                download_images(context, record["source_product_id"], record["source_product_images"])
                append_jsonl(record)
                scraped_ids.add(pid)
                scraped_this += 1
                log.info("  [%s] top-up %d/%d done", section, scraped_this, needed)
                random_delay(2, 4)

            if scraped_this < needed:
                log.warning("Could only add %d/%d for %s", scraped_this, needed, section)

        browser.close()

    # Update state with new scraped IDs
    state["scraped_ids"] = list(scraped_ids)
    STATE_PATH.write_text(json.dumps(state, indent=2))

    # Regenerate CSV
    generate_csv()

    men_final, women_final, _ = get_current_counts()
    log.info("Final: men=%d, women=%d, total=%d", men_final, women_final, men_final + women_final)


if __name__ == "__main__":
    main()

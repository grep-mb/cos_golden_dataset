"""Top-up script to fill gaps and reach 100 men + 100 women products.

Run after the main scraper to discover additional products from deeper
subcategories and scrape them until the target counts are met.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from browser_utils import (
    dismiss_cookie_banner,
    managed_browser,
    random_delay,
    scroll_to_load_products,
)
from dataset import (
    STATE_PATH,
    append_record,
    generate_csv,
    load_records,
    load_state,
    save_state,
)
from scraper import BASE_URL, download_images, extract_product_id, scrape_product

log = logging.getLogger(__name__)


def get_current_counts() -> tuple[int, int, set[str]]:
    """Return (men_count, women_count, scraped_ids) from the current JSONL."""
    records = load_records()
    men_count = sum(1 for r in records if r.section == "men")
    women_count = sum(1 for r in records if r.section == "women")
    scraped_ids = {r.source_product_id for r in records}
    return men_count, women_count, scraped_ids


def discover_extra_urls(
    page: Page,
    section: str,
    scraped_ids: set[str],
    needed: int,
    already_discovered: list[str],
) -> list[str]:
    """Find product URLs not yet scraped from deeper subcategories."""
    known_ids = set(scraped_ids) | {
        pid for u in already_discovered if (pid := extract_product_id(u))
    }

    extra_subcats: dict[str, list[str]] = {
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

    new_urls: list[str] = []
    for subcat in extra_subcats.get(section, []):
        if len(new_urls) >= needed * 3:
            break

        cat_url = f"{BASE_URL}/{section}/{subcat}"
        log.info(f"Discovering extras from {cat_url}")
        try:
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(2, 3)
            dismiss_cookie_banner(page)
            scroll_to_load_products(page, max_scrolls=10)

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
            log.warning(f"Timeout on {cat_url}, skipping")
        except Exception as exc:
            log.warning(f"Error on {cat_url}: {exc}")

        random_delay(1, 2)

    log.info(f"Found {len(new_urls)} new candidate URLs for {section} (need {needed})")
    return new_urls


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    men_count, women_count, scraped_ids = get_current_counts()
    men_needed = max(0, 100 - men_count)
    women_needed = max(0, 100 - women_count)
    log.info(
        f"Current: men={men_count}, women={women_count}. "
        f"Need: men=+{men_needed}, women=+{women_needed}"
    )

    if men_needed == 0 and women_needed == 0:
        log.info("Already at 100+100, nothing to do")
        return

    state = load_state()
    already_discovered: dict[str, list[str]] = {}
    for section in ["men", "women"]:
        already_discovered[section] = state.discovered_urls.get(section, [])

    with sync_playwright() as pw, managed_browser(pw) as (browser, context, page):
        for section, needed in [("men", men_needed), ("women", women_needed)]:
            if needed <= 0:
                continue

            log.info(f"=== Top-up: need {needed} more for {section} ===")
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

                download_images(context, record.source_product_id, record.source_product_images)
                append_record(record)
                scraped_ids.add(pid)
                scraped_this += 1
                log.info(f"  [{section}] top-up {scraped_this}/{needed} done")
                random_delay(2, 4)

            if scraped_this < needed:
                log.warning(f"Could only add {scraped_this}/{needed} for {section}")

    # Update state with new scraped IDs
    state.scraped_ids = list(scraped_ids)
    save_state(state)

    generate_csv()

    men_final, women_final, _ = get_current_counts()
    log.info(f"Final: men={men_final}, women={women_final}, total={men_final + women_final}")


if __name__ == "__main__":
    main()

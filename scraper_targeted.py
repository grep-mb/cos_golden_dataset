"""Targeted COS scraper for products in recommendations.csv.

Crawls COS category pages to discover product URLs, filters them against
the product IDs in recommendations.csv, and scrapes "Style With" data only
for matching products.  This ensures the golden dataset overlaps with the
baseline recommendations pipeline.

Target: 150 men + 150 women products.

Usage:
    python scraper_targeted.py [--max-per-section 150] [--no-resume]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from browser_utils import (
    dismiss_cookie_banner,
    extract_style_with_products,
    managed_browser,
    random_delay,
    scroll_page,
)
from dataset import (
    DATA_DIR,
    IMAGES_DIR,
    JSONL_PATH,
    append_record,
    generate_csv,
    load_records,
    save_state,
)
from models import CrawlState, SourceProduct
from scraper import (
    BASE_URL,
    _build_recommendations,
    _extract_from_jsonld,
    _extract_product_name_from_h1,
    download_images,
    extract_product_id,
)

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent
RECOMMENDATIONS_CSV = _ROOT.parent / "cos-catalog" / "recommendations.csv"
STATE_PATH = _ROOT / "crawl_state_targeted.json"

# Subcategories to crawl for product discovery (per section).
# Ordered roughly by catalog size to maximise product coverage early.
_SUBCATEGORIES: dict[str, list[str]] = {
    "men": [
        "view-all",
        "new-arrivals",
        "trousers",
        "t-shirts",
        "knitwear",
        "shirts",
        "coats-and-jackets",
        "jeans",
        "polo-shirts",
        "co-ords",
        "sweatshirts",
        "suits",
        "shoes",
        "bags-and-wallets",
        "accessories-all",
    ],
    "women": [
        "view-all",
        "new-arrivals",
        "dresses",
        "trousers",
        "tops",
        "knitwear",
        "skirts",
        "coats-and-jackets",
        "jeans",
        "shoes",
        "co-ords",
        "bags-and-wallets",
        "accessories-all",
        "jewellery",
    ],
}


# ---------------------------------------------------------------------------
# State persistence (separate file from the category-based scraper)
# ---------------------------------------------------------------------------


def _load_state(resume: bool) -> CrawlState:
    if resume and STATE_PATH.exists():
        return CrawlState.from_dict(json.loads(STATE_PATH.read_text()))
    return CrawlState()


def _save_state(state: CrawlState) -> None:
    save_state(state, path=STATE_PATH)


# ---------------------------------------------------------------------------
# Step 1: Load target product IDs from recommendations.csv
# ---------------------------------------------------------------------------


def load_target_ids(csv_path: Path = RECOMMENDATIONS_CSV) -> dict[str, set[str]]:
    """Return ``{product_id: set_of_genders}`` from *recommendations.csv*.

    Strips the ``product#`` prefix from ``sourceItemId`` and collects all
    gender values for each product.
    """
    targets: dict[str, set[str]] = {}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row["sourceItemId"]
            product_id = raw_id.removeprefix("product#")
            gender = row["gender"].strip().lower()
            targets.setdefault(product_id, set()).add(gender)
    log.info(
        f"Loaded {len(targets)} unique product IDs from {csv_path.name} "
        f"(man-only: {sum(1 for g in targets.values() if g == {'man'})}, "
        f"woman-only: {sum(1 for g in targets.values() if g == {'woman'})}, "
        f"both: {sum(1 for g in targets.values() if g == {'man', 'woman'})})"
    )
    return targets


# ---------------------------------------------------------------------------
# Step 2: Discover product URLs from category pages
# ---------------------------------------------------------------------------


def _gentle_scroll(page: Page, scrolls: int = 12) -> None:
    """Scroll the page to trigger lazy-loaded product cards.

    Uses a try/except per scroll step so that a mid-scroll navigation
    (common in COS's Next.js SPA) doesn't kill the entire discovery loop.
    """
    for _ in range(scrolls):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
        except Exception:
            break
        time.sleep(0.8)


def _extract_product_links(page: Page) -> dict[str, str]:
    """Return ``{product_id: full_url}`` for all ``/product/`` links on page."""
    found: dict[str, str] = {}
    try:
        links = page.query_selector_all('a[href*="/product/"]')
    except Exception:
        return found
    for link in links:
        href = link.get_attribute("href")
        if not href:
            continue
        full_url = urljoin(BASE_URL, href)
        pid = extract_product_id(full_url)
        if pid:
            found[pid] = full_url
    return found


def discover_target_urls(
    page: Page,
    section: str,
    target_ids: set[str],
    already_scraped: set[str],
) -> list[str]:
    """Crawl category pages for *section* and return URLs whose product IDs
    are in *target_ids* (minus *already_scraped*).
    """
    wanted = target_ids - already_scraped
    found: dict[str, str] = {}  # pid → url

    for subcat in _SUBCATEGORIES.get(section, []):
        if not wanted - found.keys():
            log.info(f"[{section}] All target IDs discovered, stopping category crawl")
            break

        cat_url = f"{BASE_URL}/{section}/{subcat}"
        log.info(
            f"[{section}] Crawling {subcat} "
            f"(found {len(found)}/{len(wanted)} target products so far)"
        )

        try:
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(2, 4)
            dismiss_cookie_banner(page)

            # Gentle scroll to trigger lazy-loaded product cards
            _gentle_scroll(page)

            page_products = _extract_product_links(page)
            for pid, url in page_products.items():
                if pid in wanted and pid not in found:
                    found[pid] = url

            log.info(
                f"[{section}] {subcat}: {len(page_products)} products on page, "
                f"{len(found)} target matches total"
            )

        except PlaywrightTimeout:
            log.warning(f"Timeout loading {cat_url}, skipping")
        except Exception as exc:
            log.warning(f"Error crawling {cat_url}: {exc}")

        random_delay(1, 3)

    urls = list(found.values())
    random.shuffle(urls)
    log.info(
        f"[{section}] Discovery complete: {len(urls)} target products found "
        f"out of {len(wanted)} wanted"
    )
    return urls


# ---------------------------------------------------------------------------
# Step 3: Scrape a single product page
# ---------------------------------------------------------------------------


def scrape_product(page: Page, url: str, section: str) -> SourceProduct | None:
    """Navigate to *url*, extract product data and Style-With recommendations."""
    pid = extract_product_id(url)
    if not pid:
        log.warning(f"Cannot extract product ID from {url}")
        return None

    log.info(f"Scraping product {pid}: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        random_delay(2, 4)
        dismiss_cookie_banner(page)
    except PlaywrightTimeout:
        log.warning(f"Timeout loading product page {url}")
        return None
    except Exception as exc:
        log.warning(f"Error loading product page {url}: {exc}")
        return None

    if "Access Denied" in (page.title() or ""):
        log.warning(f"Access Denied on {url}, skipping")
        return None

    scroll_page(page)

    product_name, source_images = _extract_from_jsonld(page)
    log.info(f"  Name: {product_name}")
    log.info(f"  Found {len(source_images)} images from JSON-LD")

    if not product_name:
        product_name = _extract_product_name_from_h1(page)

    raw_items = extract_style_with_products(page, pid)
    if not raw_items:
        log.info(f"  No 'Style with' section found for {pid} — saving with empty recs")

    recommended = _build_recommendations(raw_items, pid) if raw_items else []
    log.info(f"  Found {len(recommended)} recommended products")

    return SourceProduct(
        source_product_id=pid,
        source_product_name=product_name,
        source_product_url=url,
        source_product_images=source_images,
        section=section,
        recommended_products=recommended,
    )


# ---------------------------------------------------------------------------
# Step 4: Count existing records by section
# ---------------------------------------------------------------------------


def _count_by_section() -> tuple[int, int]:
    """Return ``(men_count, women_count)`` from existing JSONL records."""
    records = load_records()
    men = sum(1 for r in records if r.section == "men")
    women = sum(1 for r in records if r.section == "women")
    return men, women


def _section_from_url(url: str, gender_hint: set[str]) -> str:
    """Determine section (men/women) from the product URL path or gender hint."""
    if "/men/" in url:
        return "men"
    if "/women/" in url:
        return "women"
    if "man" in gender_hint and "woman" not in gender_hint:
        return "men"
    if "woman" in gender_hint and "man" not in gender_hint:
        return "women"
    return "women"


# ---------------------------------------------------------------------------
# Step 5: Main orchestration
# ---------------------------------------------------------------------------


def run(max_per_section: int = 150, resume: bool = True) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if not resume and JSONL_PATH.exists():
        JSONL_PATH.unlink()
        log.info("Cleared existing JSONL (--no-resume)")

    target_ids = load_target_ids()
    state = _load_state(resume)
    scraped = set(state.scraped_ids)

    men_count, women_count = _count_by_section()
    log.info(
        f"Starting counts — men: {men_count}/{max_per_section}, "
        f"women: {women_count}/{max_per_section}"
    )

    # Build the set of target IDs we care about, split by section preference
    men_target_ids: set[str] = set()
    women_target_ids: set[str] = set()
    for pid, genders in target_ids.items():
        if "man" in genders:
            men_target_ids.add(pid)
        if "woman" in genders:
            women_target_ids.add(pid)

    with sync_playwright() as pw, managed_browser(pw) as (browser, context, page):
        # --- Discovery phase ---
        # Use cached discovered URLs on resume, otherwise crawl category pages.
        for section, section_target, section_count in [
            ("men", men_target_ids, men_count),
            ("women", women_target_ids, women_count),
        ]:
            if section_count >= max_per_section:
                log.info(f"[{section}] Already at target, skipping discovery")
                continue

            cached = state.discovered_urls.get(section, [])
            if cached and resume:
                log.info(f"[{section}] Using {len(cached)} cached discovery URLs")
            else:
                cached = discover_target_urls(page, section, section_target, scraped)
                state.discovered_urls[section] = cached
                _save_state(state)

        # --- Scraping phase ---
        for section in ["men", "women"]:
            current_count = men_count if section == "men" else women_count
            if current_count >= max_per_section:
                continue

            product_urls = state.discovered_urls.get(section, [])
            scraped_this_section = current_count
            log.info(
                f"[{section}] Scraping: {len(product_urls)} URLs discovered, "
                f"{scraped_this_section}/{max_per_section} already done"
            )

            for url in product_urls:
                pid = extract_product_id(url)
                if not pid or pid in scraped:
                    continue
                if scraped_this_section >= max_per_section:
                    break

                record = scrape_product(page, url, section)
                if record is None:
                    # Still mark as scraped so we don't retry on resume
                    scraped.add(pid)
                    state.scraped_ids = list(scraped)
                    _save_state(state)
                    random_delay(1, 2)
                    continue

                download_images(context, record.source_product_id, record.source_product_images)
                append_record(record)
                scraped.add(pid)
                state.scraped_ids = list(scraped)
                _save_state(state)

                scraped_this_section += 1
                log.info(
                    f"  [{section}] {scraped_this_section}/{max_per_section} products scraped"
                )
                random_delay(2, 5)

            # Update counts for final log
            if section == "men":
                men_count = scraped_this_section
            else:
                women_count = scraped_this_section

    generate_csv()
    log.info(f"Done! men={men_count}, women={women_count}. Dataset in {DATA_DIR}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="COS targeted scraper — scrapes products from recommendations.csv"
    )
    parser.add_argument(
        "--max-per-section",
        type=int,
        default=150,
        help="Target count per gender section (default: 150)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="Start fresh, clearing existing state and data",
    )
    args = parser.parse_args()

    run(
        max_per_section=args.max_per_section,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()

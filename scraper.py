"""
COS Golden Dataset Scraper

Scrapes the COS website (cos.com/en-gb) to build a golden dataset for
Shop-the-Look. Extracts source products and their "Style with" recommended
products, along with product images.

Uses Playwright with real Chrome (headed mode) + stealth patches since the
site's Akamai WAF blocks headless browsers.

Usage:
    python scraper.py [--max-products-per-section N] [--no-resume]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from urllib.parse import urljoin

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from browser_utils import (
    dismiss_cookie_banner,
    extract_style_with_products,
    managed_browser,
    random_delay,
    scroll_page,
    scroll_to_load_products,
)
from dataset import (
    DATA_DIR,
    IMAGES_DIR,
    append_record,
    generate_csv,
    load_state,
    save_state,
)
from models import CrawlState, RecommendedProduct, SourceProduct

log = logging.getLogger(__name__)

BASE_URL = "https://www.cos.com/en-gb"
SECTIONS = ["men", "women"]
PRODUCT_ID_RE = re.compile(r"(\d{10,})$")


def extract_product_id(url: str) -> str | None:
    match = PRODUCT_ID_RE.search(url.rstrip("/"))
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Category crawling
# ---------------------------------------------------------------------------

# Subcategories that typically contain product listings
PRIORITY_SUBCATEGORIES = [
    "view-all",
    "new-arrivals",
    "t-shirts",
    "shirts",
    "trousers",
    "knitwear",
    "coats-and-jackets",
    "jeans",
    "shoes",
    "dresses",
    "skirts",
    "tops",
    "bags-and-wallets",
    "accessories-all",
    "sweatshirts",
    "suits",
    "polo-shirts",
]


def discover_product_urls(page: Page, section: str, max_products: int) -> list[str]:
    """Navigate category pages for a section and collect product URLs."""
    section_url = f"{BASE_URL}/{section}"
    log.info(f"Discovering products for section: {section}")

    page.goto(section_url, wait_until="domcontentloaded", timeout=30000)
    random_delay(3, 5)
    dismiss_cookie_banner(page)

    subcategory_urls = _extract_subcategory_urls(page, section)
    log.info(f"Found {len(subcategory_urls)} subcategory URLs for {section}")

    product_urls: dict[str, str] = {}  # id -> url

    for cat_url in subcategory_urls:
        if len(product_urls) >= max_products:
            break

        log.info(f"Crawling category: {cat_url} (have {len(product_urls)}/{max_products})")
        try:
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(2, 4)
            dismiss_cookie_banner(page)
            scroll_to_load_products(page)

            links = page.query_selector_all('a[href*="/product/"]')
            for link in links:
                href = link.get_attribute("href")
                if not href:
                    continue
                full_url = urljoin(BASE_URL, href)
                pid = extract_product_id(full_url)
                if pid and pid not in product_urls:
                    product_urls[pid] = full_url
                    if len(product_urls) >= max_products:
                        break

        except PlaywrightTimeout:
            log.warning(f"Timeout loading {cat_url}, skipping")
        except Exception as exc:
            log.warning(f"Error crawling {cat_url}: {exc}")

        random_delay(1, 3)

    urls = list(product_urls.values())
    log.info(f"Discovered {len(urls)} unique product URLs for {section}")
    return urls[:max_products]


def _extract_subcategory_urls(page: Page, section: str) -> list[str]:
    """Extract subcategory listing URLs from the section landing page."""
    subcats: list[str] = []
    seen: set[str] = set()

    links = page.query_selector_all(f'a[href*="/en-gb/{section}/"]')
    for link in links:
        href = link.get_attribute("href")
        if not href:
            continue
        full_url = urljoin(BASE_URL, href)

        if "/product/" in full_url:
            continue
        if not full_url.startswith("http"):
            continue
        if f"/en-gb/{section}/" not in full_url:
            continue
        if full_url in seen:
            continue

        seen.add(full_url)
        subcats.append(full_url)

    def sort_key(url: str) -> int:
        for i, cat in enumerate(PRIORITY_SUBCATEGORIES):
            if f"/{cat}" in url:
                return i
        return len(PRIORITY_SUBCATEGORIES)

    subcats.sort(key=sort_key)
    return subcats


# ---------------------------------------------------------------------------
# Product page scraping
# ---------------------------------------------------------------------------


def scrape_product(page: Page, url: str, section: str) -> SourceProduct | None:
    """Scrape a single product page and return the record."""
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

    # Scroll to ensure "Style with" section loads
    scroll_page(page)

    # --- Extract product data from JSON-LD ---
    product_name, source_images = _extract_from_jsonld(page)
    log.info(f"  Name: {product_name}")
    log.info(f"  Found {len(source_images)} images from JSON-LD")

    if not product_name:
        product_name = _extract_product_name_from_h1(page)

    # --- Style-With section (single JS call) ---
    raw_items = extract_style_with_products(page, pid)
    if not raw_items:
        log.info("  No 'Style with' section found, skipping product")
        return None

    recommended = _build_recommendations(raw_items, pid)
    log.info(f"  Found {len(recommended)} recommended products")

    return SourceProduct(
        source_product_id=pid,
        source_product_name=product_name,
        source_product_url=url,
        source_product_images=source_images,
        section=section,
        recommended_products=recommended,
    )


def _build_recommendations(raw_items: list[dict], source_pid: str) -> list[RecommendedProduct]:
    """Convert raw JS extraction results into typed RecommendedProduct list.

    Handles deduplication, name cleaning, and URL-based fallback naming.
    """
    seen: set[str] = {source_pid}
    result: list[RecommendedProduct] = []

    for item in raw_items:
        pid = item.get("product_id", "")
        if pid in seen:
            continue
        seen.add(pid)

        name = _clean_product_name(item.get("text", ""))
        href = item.get("href", "")
        if not name and href:
            name = _name_from_url(href)

        result.append(
            RecommendedProduct(
                product_id=pid,
                product_name=name,
                product_url=href,
                product_images=item.get("images", []),
            )
        )

    return result


def _extract_from_jsonld(page: Page) -> tuple[str, list[str]]:
    """Extract product name and image URLs from JSON-LD structured data."""
    try:
        jsonld_blocks = page.evaluate(
            """() => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return [...scripts].map(s => s.textContent);
        }"""
        )

        for block_text in jsonld_blocks:
            try:
                data = json.loads(block_text)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("@type") == "Product":
                name = data.get("name", "")
                images = data.get("image", [])
                if isinstance(images, str):
                    images = [images]
                return name, images
    except Exception as exc:
        log.debug(f"JSON-LD extraction failed: {exc}")

    return "", []


def _extract_product_name_from_h1(page: Page) -> str:
    """Fallback: extract product name from h1 tag."""
    try:
        el = page.query_selector("h1")
        if el:
            text = el.inner_text().strip()
            if text and len(text) < 200:
                return text
    except Exception as exc:
        log.debug(f"h1 extraction failed: {exc}")
    return ""


def _name_from_url(url: str) -> str:
    """Derive a product name from the URL slug (fallback when link has no text).

    Example: '.../product/polished-leather-loafers-black-1326192001'
    -> 'Polished Leather Loafers Black'
    """
    match = re.search(r"/product/(.+)-\d{10,}$", url)
    if not match:
        return ""
    slug = match.group(1)
    return slug.replace("-", " ").title()


def _clean_product_name(text: str) -> str:
    """Clean up scraped product name text (may contain price, badges, etc.)."""
    if not text:
        return ""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines:
        if line.startswith(("£", "$", "€")):
            continue
        if re.match(r"^[+\d.,\s]+$", line):
            continue
        if line in ("NEW", "SALE", "NEW IN", "BESTSELLER"):
            continue
        if len(line) < 3:
            continue
        return line
    return lines[0] if lines else ""


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------


def download_images(context: BrowserContext, product_id: str, image_urls: list[str]) -> None:
    """Download product images using the browser context's API request."""
    if not image_urls:
        return

    product_dir = IMAGES_DIR / product_id
    product_dir.mkdir(parents=True, exist_ok=True)

    for i, img_url in enumerate(image_urls):
        dest = product_dir / f"{i}.jpg"
        if dest.exists():
            continue

        try:
            response = context.request.get(img_url, timeout=15000)
            if response.ok:
                dest.write_bytes(response.body())
                log.debug(f"  Downloaded image {i} for {product_id}")
            else:
                log.debug(f"  Image {i} failed (status {response.status})")
        except Exception as exc:
            log.debug(f"  Error downloading image {i}: {exc}")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def run(max_products_per_section: int = 100, resume: bool = True) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state() if resume else CrawlState()
    scraped_ids = set(state.scraped_ids)

    with sync_playwright() as pw, managed_browser(pw) as (browser, context, page):
        for section in SECTIONS:
            # --- Discovery phase ---
            cached_urls = state.discovered_urls.get(section, [])
            if cached_urls and resume:
                log.info(f"Using {len(cached_urls)} cached URLs for {section}")
                product_urls = cached_urls
            else:
                product_urls = discover_product_urls(page, section, max_products_per_section)
                state.discovered_urls[section] = product_urls
                save_state(state)

            # --- Scraping phase ---
            scraped_count = sum(1 for url in product_urls if extract_product_id(url) in scraped_ids)
            log.info(
                f"Section {section}: {len(product_urls)} URLs discovered, "
                f"{scraped_count} already scraped"
            )

            products_scraped_this_section = scraped_count
            for url in product_urls:
                pid = extract_product_id(url)
                if not pid or pid in scraped_ids:
                    continue
                if products_scraped_this_section >= max_products_per_section:
                    break

                record = scrape_product(page, url, section)
                if record is None:
                    random_delay(1, 2)
                    continue

                download_images(context, record.source_product_id, record.source_product_images)

                append_record(record)
                scraped_ids.add(pid)
                state.scraped_ids = list(scraped_ids)
                save_state(state)

                products_scraped_this_section += 1
                log.info(
                    f"  [{section}] {products_scraped_this_section}/"
                    f"{max_products_per_section} products scraped"
                )

                random_delay(2, 4)

    generate_csv()
    log.info(f"Done! Dataset saved to {DATA_DIR}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="COS Golden Dataset Scraper")
    parser.add_argument(
        "--max-products-per-section",
        type=int,
        default=100,
        help="Max products to scrape per section (default: 100)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="Start fresh, ignoring any saved state",
    )
    args = parser.parse_args()

    run(
        max_products_per_section=args.max_products_per_section,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()

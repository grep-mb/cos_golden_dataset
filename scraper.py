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

import argparse
import csv
import json
import logging
import re
import time
import random
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

BASE_URL = "https://www.cos.com/en-gb"
SECTIONS = ["men", "women"]
PRODUCT_ID_RE = re.compile(r"(\d{10,})$")

DATA_DIR = Path(__file__).parent / "data"
IMAGES_DIR = DATA_DIR / "images"
JSONL_PATH = DATA_DIR / "golden_dataset.jsonl"
CSV_PATH = DATA_DIR / "golden_dataset.csv"
STATE_PATH = Path(__file__).parent / "crawl_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def random_delay(lo=2.0, hi=4.0):
    time.sleep(random.uniform(lo, hi))


def extract_product_id(url: str) -> str | None:
    match = PRODUCT_ID_RE.search(url.rstrip("/"))
    return match.group(1) if match else None


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"discovered_urls": {}, "scraped_ids": []}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def append_jsonl(record: dict):
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def generate_csv():
    """Convert the JSONL file into a CSV summary."""
    if not JSONL_PATH.exists():
        return

    records = []
    with open(JSONL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "section",
            "source_product_id",
            "source_product_name",
            "source_product_url",
            "source_image_urls",
            "recommended_product_ids",
            "recommended_product_names",
            "recommended_product_urls",
        ])
        for r in records:
            rec_products = r.get("recommended_products", [])
            writer.writerow([
                r.get("section", ""),
                r.get("source_product_id", ""),
                r.get("source_product_name", ""),
                r.get("source_product_url", ""),
                "|".join(r.get("source_product_images", [])),
                "|".join(p.get("product_id", "") for p in rec_products),
                "|".join(p.get("product_name", "") for p in rec_products),
                "|".join(p.get("product_url", "") for p in rec_products),
            ])

    log.info("CSV written to %s (%d records)", CSV_PATH, len(records))


def _dismiss_cookie_banner(page):
    """Try to accept/dismiss cookie consent banner."""
    try:
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("ACCEPT")',
            '[id*="cookie"] button',
            '[class*="cookie"] button',
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                log.info("Dismissed cookie banner")
                random_delay(0.5, 1.0)
                return
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Category crawling
# ---------------------------------------------------------------------------

# Subcategories that typically contain product listings
PRIORITY_SUBCATEGORIES = [
    "view-all", "new-arrivals", "t-shirts", "shirts", "trousers",
    "knitwear", "coats-and-jackets", "jeans", "shoes", "dresses",
    "skirts", "tops", "bags-and-wallets", "accessories-all",
    "sweatshirts", "suits", "polo-shirts",
]


def discover_product_urls(page, section: str, max_products: int) -> list[str]:
    """Navigate category pages for a section and collect product URLs."""
    section_url = f"{BASE_URL}/{section}"
    log.info("Discovering products for section: %s", section)

    page.goto(section_url, wait_until="domcontentloaded", timeout=30000)
    random_delay(3, 5)
    _dismiss_cookie_banner(page)

    # Gather subcategory links from the landing page
    subcategory_urls = _extract_subcategory_urls(page, section)
    log.info("Found %d subcategory URLs for %s", len(subcategory_urls), section)

    product_urls: dict[str, str] = {}  # id -> url

    for cat_url in subcategory_urls:
        if len(product_urls) >= max_products:
            break

        log.info(
            "Crawling category: %s (have %d/%d)",
            cat_url, len(product_urls), max_products,
        )
        try:
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(2, 4)
            _dismiss_cookie_banner(page)

            # Scroll to load lazy-loaded products
            _scroll_to_load_products(page)

            # Extract product links
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
            log.warning("Timeout loading %s, skipping", cat_url)
        except Exception as e:
            log.warning("Error crawling %s: %s", cat_url, e)

        random_delay(1, 3)

    urls = list(product_urls.values())
    log.info("Discovered %d unique product URLs for %s", len(urls), section)
    return urls[:max_products]


def _extract_subcategory_urls(page, section: str) -> list[str]:
    """Extract subcategory listing URLs from the section landing page."""
    subcats = []
    seen = set()

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

    # Sort: prioritize broad listing categories first
    def sort_key(url):
        for i, cat in enumerate(PRIORITY_SUBCATEGORIES):
            if f"/{cat}" in url:
                return i
        return len(PRIORITY_SUBCATEGORIES)

    subcats.sort(key=sort_key)
    return subcats


def _scroll_to_load_products(page, max_scrolls=15):
    """Scroll down to trigger lazy loading of product cards."""
    for i in range(max_scrolls):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(0.8)

        # Check for "load more" / "show more" button
        for selector in [
            'button:has-text("Load more")',
            'button:has-text("Show more")',
            'button:has-text("LOAD MORE")',
            'button:has-text("SHOW MORE")',
            '[data-testid*="load-more"]',
        ]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    log.info("Clicked 'load more' button (scroll %d)", i)
                    time.sleep(1.5)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Product page scraping
# ---------------------------------------------------------------------------

def scrape_product(page, url: str, section: str) -> dict | None:
    """Scrape a single product page and return the record."""
    pid = extract_product_id(url)
    if not pid:
        log.warning("Cannot extract product ID from %s", url)
        return None

    log.info("Scraping product %s: %s", pid, url)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        random_delay(2, 4)
        _dismiss_cookie_banner(page)
    except PlaywrightTimeout:
        log.warning("Timeout loading product page %s", url)
        return None
    except Exception as e:
        log.warning("Error loading product page %s: %s", url, e)
        return None

    # Check for access denied
    if "Access Denied" in (page.title() or ""):
        log.warning("Access Denied on %s, skipping", url)
        return None

    # Scroll down to ensure "Style with" section loads
    for _ in range(8):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(0.6)
    time.sleep(1)

    # --- Extract product data from JSON-LD ---
    product_name, source_images = _extract_from_jsonld(page)
    log.info("  Name: %s", product_name)
    log.info("  Found %d images from JSON-LD", len(source_images))

    # Fallback: get name from h1 if JSON-LD didn't have it
    if not product_name:
        product_name = _extract_product_name_from_h1(page)

    # --- STYLE WITH section ---
    recommended = _extract_style_with(page, pid)
    if not recommended:
        log.info("  No 'Style with' section found, skipping product")
        return None

    log.info("  Found %d recommended products", len(recommended))

    return {
        "source_product_id": pid,
        "source_product_name": product_name,
        "source_product_url": url,
        "source_product_images": source_images,
        "section": section,
        "recommended_products": recommended,
    }


def _extract_from_jsonld(page) -> tuple[str, list[str]]:
    """Extract product name and image URLs from JSON-LD structured data."""
    try:
        jsonld_blocks = page.evaluate("""() => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return [...scripts].map(s => s.textContent);
        }""")

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
    except Exception as e:
        log.debug("JSON-LD extraction failed: %s", e)

    return "", []


def _extract_product_name_from_h1(page) -> str:
    """Fallback: extract product name from h1 tag."""
    try:
        el = page.query_selector("h1")
        if el:
            text = el.inner_text().strip()
            if text and len(text) < 200:
                return text
    except Exception:
        pass
    return ""


def _extract_style_with(page, source_pid: str) -> list[dict]:
    """Extract recommended products from the 'Style with' section.

    DOM structure (observed):
      <p class="mb-4 font_small_xs_regular">Style with</p>
      <div>  ← siblings contain product cards with <a href="/product/...">
      </div>
    All inside a parent <div class="col-span-full ..."> that contains only
    the "Style with" heading + its recommendation cards.
    """
    recommended = []
    seen_ids = set()
    seen_ids.add(source_pid)  # exclude the source product itself

    try:
        result = page.evaluate("""(sourcePid) => {
            // Find the "Style with" text element
            const candidates = document.querySelectorAll('p, h2, h3, h4, span');
            let styleEl = null;
            for (const el of candidates) {
                const t = el.textContent.trim();
                if (t === 'Style with' || t === 'STYLE WITH' || t === 'Style With') {
                    styleEl = el;
                    break;
                }
            }
            if (!styleEl) return [];

            // Walk up the DOM to find the nearest container with product links
            // Level 0 parent is typically <div class="col-span-full ..."> which
            // contains only the style-with recommendations
            let container = styleEl.parentElement;
            for (let i = 0; i < 6; i++) {
                if (!container) break;
                const links = container.querySelectorAll('a[href*="/product/"]');
                const unique = {};
                for (const a of links) {
                    const href = a.href;
                    const match = href.match(/(\\d{10,})$/);
                    if (match) {
                        const pid = match[1];
                        if (pid !== sourcePid && !unique[pid]) {
                            // Get text - first meaningful line
                            const text = a.textContent.trim();
                            // Extract image URLs from this product card
                            const cardImages = [];
                            const imgs = a.querySelectorAll('img');
                            for (const img of imgs) {
                                const src = img.src || img.getAttribute('data-src') || '';
                                if (src && src.startsWith('http')) {
                                    cardImages.push(src);
                                }
                            }
                            unique[pid] = {href, text, images: cardImages};
                        }
                    }
                }
                const results = Object.entries(unique);
                if (results.length > 0) {
                    return results.map(([pid, info]) => ({
                        product_id: pid,
                        href: info.href,
                        text: info.text,
                        images: info.images
                    }));
                }
                container = container.parentElement;
            }
            return [];
        }""", source_pid)

        for item in result:
            pid = item.get("product_id", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            name = _clean_product_name(item.get("text", ""))
            href = item.get("href", "")
            # Fallback: derive name from URL slug if link had no text
            if not name and href:
                name = _name_from_url(href)
            images = item.get("images", [])
            recommended.append({
                "product_id": pid,
                "product_name": name,
                "product_url": href,
                "product_images": images,
            })

    except Exception as e:
        log.debug("Style with extraction failed: %s", e)

    return recommended


def _name_from_url(url: str) -> str:
    """Derive a product name from the URL slug (fallback when link has no text).

    Example: '.../product/polished-leather-loafers-black-1326192001'
    → 'Polished Leather Loafers Black'
    """
    # Extract the slug between /product/ and the product ID
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
        # Skip price lines
        if line.startswith(("£", "$", "€")):
            continue
        # Skip lines that are just numbers or "+N" color counts
        if re.match(r"^[+\d.,\s]+$", line):
            continue
        # Skip badges like "NEW", "SALE"
        if line in ("NEW", "SALE", "NEW IN", "BESTSELLER"):
            continue
        # Skip very short lines
        if len(line) < 3:
            continue
        return line
    return lines[0] if lines else ""


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

def download_images(context, product_id: str, image_urls: list[str]):
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
                log.debug("  Downloaded image %d for %s", i, product_id)
            else:
                log.debug("  Image %d failed (status %d)", i, response.status)
        except Exception as e:
            log.debug("  Error downloading image %d: %s", i, e)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(max_products_per_section: int = 100, resume: bool = True):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state() if resume else {"discovered_urls": {}, "scraped_ids": []}
    scraped_ids = set(state.get("scraped_ids", []))

    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_vendor_override="Google Inc.",
    )

    with sync_playwright() as p:
        # Must use headed mode (headless=False) + real Chrome channel to
        # bypass Akamai WAF. Headless Chromium gets 403 Access Denied.
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-GB",
        )
        stealth.apply_stealth_sync(context)
        page = context.new_page()

        for section in SECTIONS:
            # --- Discovery phase ---
            cached_urls = state["discovered_urls"].get(section, [])
            if cached_urls and resume:
                log.info("Using %d cached URLs for %s", len(cached_urls), section)
                product_urls = cached_urls
            else:
                product_urls = discover_product_urls(
                    page, section, max_products_per_section
                )
                state["discovered_urls"][section] = product_urls
                save_state(state)

            # --- Scraping phase ---
            scraped_count = sum(
                1 for url in product_urls
                if extract_product_id(url) in scraped_ids
            )
            log.info(
                "Section %s: %d URLs discovered, %d already scraped",
                section, len(product_urls), scraped_count,
            )

            products_scraped_this_section = scraped_count
            for url in product_urls:
                pid = extract_product_id(url)
                if not pid:
                    continue
                if pid in scraped_ids:
                    continue
                if products_scraped_this_section >= max_products_per_section:
                    break

                record = scrape_product(page, url, section)
                if record is None:
                    random_delay(1, 2)
                    continue

                # Download source product images
                download_images(
                    context,
                    record["source_product_id"],
                    record["source_product_images"],
                )

                # Save record
                append_jsonl(record)
                scraped_ids.add(pid)
                state["scraped_ids"] = list(scraped_ids)
                save_state(state)

                products_scraped_this_section += 1
                log.info(
                    "  [%s] %d/%d products scraped",
                    section,
                    products_scraped_this_section,
                    max_products_per_section,
                )

                random_delay(2, 4)

        browser.close()

    # Generate CSV at the end
    generate_csv()
    log.info("Done! Dataset saved to %s", DATA_DIR)


def main():
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

"""
Patch script: revisit product pages that have recommendations without images,
extract recommendation images from the 'Style with' section, and update the JSONL.
"""

import json
import logging
import time
import random
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

JSONL_PATH = Path(__file__).parent / "data" / "golden_dataset.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def random_delay(lo=2.0, hi=4.0):
    time.sleep(random.uniform(lo, hi))


def dismiss_cookie_banner(page):
    try:
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            '[id*="cookie"] button',
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                random_delay(0.5, 1.0)
                return
    except Exception:
        pass


def extract_rec_images(page, source_pid):
    """Extract recommendation product images from the Style With section."""
    try:
        result = page.evaluate("""(sourcePid) => {
            const candidates = document.querySelectorAll('p, h2, h3, h4, span');
            let styleEl = null;
            for (const el of candidates) {
                const t = el.textContent.trim();
                if (t === 'Style with' || t === 'STYLE WITH' || t === 'Style With') {
                    styleEl = el;
                    break;
                }
            }
            if (!styleEl) return {};

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
                            const cardImages = [];
                            const imgs = a.querySelectorAll('img');
                            for (const img of imgs) {
                                const src = img.src || img.getAttribute('data-src') || '';
                                if (src && src.startsWith('http')) {
                                    cardImages.push(src);
                                }
                            }
                            unique[pid] = cardImages;
                        }
                    }
                }
                if (Object.keys(unique).length > 0) {
                    return unique;
                }
                container = container.parentElement;
            }
            return {};
        }""", source_pid)
        return result
    except Exception as e:
        log.debug("Extraction failed: %s", e)
        return {}


def run():
    # Load all records
    records = []
    with open(JSONL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Find records that need updating
    to_update = []
    for i, rec in enumerate(records):
        has_empty = any(
            not rp.get("product_images")
            for rp in rec["recommended_products"]
        )
        if has_empty:
            to_update.append(i)

    log.info("Found %d products needing recommendation image update", len(to_update))
    if not to_update:
        return

    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_vendor_override="Google Inc.",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-GB",
        )
        stealth.apply_stealth_sync(context)
        page = context.new_page()

        updated = 0
        for count, idx in enumerate(to_update):
            rec = records[idx]
            pid = rec["source_product_id"]
            url = rec["source_product_url"]

            log.info("[%d/%d] Visiting %s (%s)", count + 1, len(to_update), pid, url)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeout:
                pass  # networkidle timeout is OK, continue anyway
            except Exception as e:
                log.warning("Error loading %s: %s", pid, e)
                continue

            random_delay(2.0, 3.5)

            dismiss_cookie_banner(page)

            if "Access Denied" in (page.title() or ""):
                log.warning("Access Denied on %s, skipping", pid)
                continue

            # Scroll to load Style With section
            try:
                for _ in range(8):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    time.sleep(0.5)
                time.sleep(0.5)
            except Exception as e:
                log.warning("Scroll error on %s: %s, skipping", pid, e)
                continue

            # Extract images keyed by product_id
            try:
                image_map = extract_rec_images(page, pid)
            except Exception as e:
                log.warning("Extraction error on %s: %s, skipping", pid, e)
                image_map = {}

            # Update recommendation records
            patched = 0
            for rp in rec["recommended_products"]:
                if not rp.get("product_images"):
                    images = image_map.get(rp["product_id"], [])
                    if images:
                        rp["product_images"] = images
                        patched += 1

            if patched > 0:
                updated += 1
                log.info("  Patched %d recommendations with images", patched)
            else:
                log.info("  No images found for recommendations")

            random_delay(1.0, 2.5)

        browser.close()

    # Write updated JSONL
    with open(JSONL_PATH, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    log.info("Done! Updated %d products. JSONL rewritten.", updated)


if __name__ == "__main__":
    run()

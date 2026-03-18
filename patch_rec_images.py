"""Patch script: revisit product pages that have recommendations without images,
extract recommendation images from the 'Style with' section, and update the JSONL.
"""

from __future__ import annotations

import logging
import time

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from browser_utils import (
    dismiss_cookie_banner,
    extract_style_with_products,
    managed_browser,
    random_delay,
    scroll_page,
)
from dataset import load_records, write_records
from models import SourceProduct

log = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    records = load_records()

    # Find records that need updating
    to_update: list[int] = []
    for i, rec in enumerate(records):
        if any(not rp.product_images for rp in rec.recommended_products):
            to_update.append(i)

    log.info(f"Found {len(to_update)} products needing recommendation image update")
    if not to_update:
        return

    with sync_playwright() as pw, managed_browser(pw) as (browser, context, page):
        updated = 0
        for count, idx in enumerate(to_update):
            rec = records[idx]
            pid = rec.source_product_id
            url = rec.source_product_url

            log.info(f"[{count + 1}/{len(to_update)}] Visiting {pid} ({url})")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeout:
                pass  # networkidle timeout is OK, continue anyway
            except Exception as exc:
                log.warning(f"Error loading {pid}: {exc}")
                continue

            random_delay(2.0, 3.5)
            dismiss_cookie_banner(page)

            if "Access Denied" in (page.title() or ""):
                log.warning(f"Access Denied on {pid}, skipping")
                continue

            # Scroll to load Style With section
            try:
                scroll_page(page, delay=0.5)
            except Exception as exc:
                log.warning(f"Scroll error on {pid}: {exc}, skipping")
                continue

            # Extract images keyed by product_id
            raw_items = extract_style_with_products(page, pid)
            image_map = {item["product_id"]: item["images"] for item in raw_items}

            # Update recommendation records
            patched = 0
            for rp in rec.recommended_products:
                if not rp.product_images:
                    images = image_map.get(rp.product_id, [])
                    if images:
                        rp.product_images = images
                        patched += 1

            if patched > 0:
                updated += 1
                log.info(f"  Patched {patched} recommendations with images")
            else:
                log.info("  No images found for recommendations")

            random_delay(1.0, 2.5)

    # Write updated JSONL
    write_records(records)
    log.info(f"Done! Updated {updated} products. JSONL rewritten.")


if __name__ == "__main__":
    run()

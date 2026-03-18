"""Shared browser utilities for COS scraper modules.

Provides common Playwright helpers: browser lifecycle management, cookie
dismissal, scrolling, and Style-With section extraction.
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from playwright_stealth import Stealth

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def random_delay(lo: float = 2.0, hi: float = 4.0) -> None:
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Cookie banner
# ---------------------------------------------------------------------------


def dismiss_cookie_banner(page: Page) -> None:
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
    except Exception as exc:
        log.debug(f"Cookie banner dismissal failed: {exc}")


# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------


def scroll_to_load_products(page: Page, max_scrolls: int = 15) -> None:
    for i in range(max_scrolls):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(0.8)

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
                    log.info(f"Clicked 'load more' button (scroll {i})")
                    time.sleep(1.5)
            except Exception as exc:
                log.debug(f"Load-more click failed: {exc}")


def scroll_page(page: Page, scrolls: int = 8, delay: float = 0.6) -> None:
    for _ in range(scrolls):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(delay)
    time.sleep(max(delay, 0.5))


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------


@contextmanager
def managed_browser(pw: Playwright) -> Generator[tuple[Browser, BrowserContext, Page], None, None]:
    """Launch headed Chrome with stealth patches; ensures ``browser.close()`` on exit.

    Uses headed mode (``headless=False``) + real Chrome channel to bypass
    Akamai WAF.  Headless Chromium gets 403 Access Denied.
    """
    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_vendor_override="Google Inc.",
    )
    browser = pw.chromium.launch(headless=False, channel="chrome")
    try:
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-GB",
        )
        stealth.apply_stealth_sync(context)
        page = context.new_page()
        yield browser, context, page
    finally:
        browser.close()


# ---------------------------------------------------------------------------
# Style-With extraction
# ---------------------------------------------------------------------------


def extract_style_with_products(page: Page, source_pid: str) -> list[dict]:
    """Extract recommended products from the Style-With section.

    Returns a list of dicts, each with keys:
    ``product_id``, ``href``, ``text``, ``images``.

    A single JS evaluation retrieves all data needed by both ``scraper.py``
    (which also needs text/href for name cleaning) and ``patch_rec_images.py``
    (which only needs the image map).
    """
    try:
        return page.evaluate(
            """(sourcePid) => {
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
                            const text = a.textContent.trim();
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
        }""",
            source_pid,
        )
    except Exception as exc:
        log.debug(f"Style-with extraction failed: {exc}")
        return []

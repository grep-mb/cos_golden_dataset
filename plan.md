# Plan: Re-scrape COS for 150+150 Baseline-Matched Products

## Problem

The current golden dataset (298 products: 149 men + 149 women) has only **10 products overlapping** with the 1,149 source product IDs in the baseline STL CSV. We need a new golden dataset of **300 products (150 men + 150 women)** where every product's ID appears in the baseline CSV.

## Key challenge

We only have product IDs from the baseline CSV (e.g. `1245722001`), not full COS URLs. The scraper needs URLs to visit product pages. Two-phase approach:

1. **Discovery**: Crawl COS category pages broadly, match discovered URLs against the 1,149 baseline IDs
2. **Direct lookup fallback**: For remaining unmatched IDs, attempt COS search (`cos.com/en-gb/search?q={product_id}`) to find their URLs

## New file: `scrape_baseline.py`

A new targeted scraper that reuses existing `browser_utils`, `dataset`, and `models` modules.

### Flow

```
1. Load baseline product IDs from CSV (1,149 IDs)
2. Subtract already-scraped IDs (from existing JSONL)
3. Phase 1 — Category discovery:
   - Crawl ALL men + women subcategories (deeper than original scraper)
   - For every product URL found, check if its ID is in the baseline set
   - Build a map: {product_id -> url} for matched products
4. Phase 2 — Search fallback (for IDs still unmatched after discovery):
   - Visit cos.com/en-gb/search?q={product_id}
   - Extract the first product link matching the ID
5. Phase 3 — Scrape matched products:
   - Visit each matched URL, extract product data + "Style With" recs
   - Determine section (men/women) from URL path
   - Skip if no Style With section found
   - Download product images
   - Stop when we reach 150 men + 150 women
6. Save state after each product (resumable)
7. Regenerate CSV at the end
```

### CLI interface

```bash
python scrape_baseline.py --baseline-csv /path/to/cos_baseline.csv
python scrape_baseline.py --baseline-csv /path/to/cos_baseline.csv --no-resume
```

### Output

Writes to the same `data/golden_dataset.jsonl` (appending). The `--no-resume` flag starts fresh with a new JSONL.

### State file

Uses `baseline_crawl_state.json` (separate from the original scraper's `crawl_state.json`) with:
- `discovered_urls`: `{product_id: url}` map from category crawling
- `scraped_ids`: list of already-scraped product IDs
- `search_attempted`: list of IDs that were tried via search (to avoid re-searching)

## Changes to existing files

**None.** All existing scripts (`scraper.py`, `topup.py`, etc.) stay untouched. The new script imports shared utilities from `browser_utils.py`, `dataset.py`, and `models.py`.

## CLAUDE.md update

Add `scrape_baseline.py` to the project structure and running instructions.

## Risks / notes

- Some baseline products may no longer exist on COS (seasonal rotation). With 1,149 candidates and 300 needed, there's margin.
- We don't know the men/women split in the baseline CSV upfront. If the split is heavily skewed, we may not reach exactly 150+150. The script will report the final counts and keep scraping as long as either section needs more.
- COS Akamai WAF: same headed Chrome + stealth approach as the existing scraper.
- Search fallback may not work for all IDs (search might return no results for discontinued products).

# CLAUDE.md — cos_golden_dataset

## Project Purpose

Builds a golden dataset for evaluating Shop-the-Look (outfit recommendation) quality. Scrapes [cos.com/en-gb](https://www.cos.com/en-gb) to collect source products paired with their "Style with" recommended products, including product images. Target: 100 men + 100 women products.

## Project Structure

```
cos_golden_dataset/
├── scraper.py            # Main scraper (discovery + product scraping)
├── topup.py              # Fills gaps to reach 100+100 target
├── patch_rec_images.py   # Backfills missing recommendation images
├── requirements.txt      # Python deps (playwright, playwright-stealth)
├── crawl_state.json      # Resume state (gitignored)
├── data/
│   ├── golden_dataset.jsonl   # Primary output (one record per source product)
│   ├── golden_dataset.csv     # CSV summary (auto-generated)
│   └── images/               # Downloaded product images (gitignored)
└── explorer/             # React + Vite dataset browser (deployed on Netlify)
    ├── src/
    │   ├── components/   # App, ProductList, ProductDetail, Sidebar, etc.
    │   └── data/         # golden_dataset.json (converted from JSONL at build)
    └── scripts/
        └── convert-data.js  # Converts JSONL → JSON, rewrites CDN URLs to local
```

## Environment Setup

```bash
# Python venv (Python 3.14)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
playwright install chrome
```

## Running the Scraper

```bash
# Full scrape (with resume support)
python scraper.py

# Limit products per section
python scraper.py --max-products-per-section 50

# Start fresh, ignoring saved state
python scraper.py --no-resume

# Top up to reach 100+100 (run after main scraper)
python topup.py

# Backfill recommendation images that were missed
python patch_rec_images.py
```

## Important: Headed Browser Required

The scraper uses **headed Chrome** (`headless=False, channel="chrome"`) with `playwright-stealth`. COS uses Akamai WAF which blocks headless Chromium with 403 Access Denied. Do not switch to headless mode.

## Dataset Format

Each record in `golden_dataset.jsonl`:
```json
{
  "source_product_id": "1234567890",
  "source_product_name": "Product Name",
  "source_product_url": "https://www.cos.com/en-gb/...",
  "source_product_images": ["https://..."],
  "section": "men|women",
  "recommended_products": [
    {
      "product_id": "0987654321",
      "product_name": "Recommended Name",
      "product_url": "https://www.cos.com/en-gb/...",
      "product_images": ["https://..."]
    }
  ]
}
```

## Explorer App

React + Vite app for browsing the dataset locally or via Netlify.

```bash
cd explorer
npm install
npm run dev    # Starts at http://localhost:5173
               # predev script auto-converts JSONL → JSON
npm run build  # Production build (deployed via Netlify from explorer/dist)
```

The `scripts/convert-data.js` prebuild step reads `../data/golden_dataset.jsonl`, rewrites CDN image URLs to local `/images/` paths, and writes `src/data/golden_dataset.json`. During dev, a Vite plugin serves `../data/images/` at `/images/`.

## Scraper Flow

1. **Discovery**: Visits section landing pages (men, women), extracts subcategory URLs sorted by priority (view-all, new-arrivals, t-shirts, etc.), scrolls each to load lazy products, collects product URLs.
2. **Scraping**: For each product URL, extracts name + images from JSON-LD, scrolls to load the "Style with" section, extracts recommended product links and thumbnail images.
3. **State**: Saves progress to `crawl_state.json` after each product so runs are resumable.
4. **Output**: Appends to `data/golden_dataset.jsonl` and regenerates `data/golden_dataset.csv` at the end.

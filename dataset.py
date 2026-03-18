"""Dataset I/O: JSONL, CSV, crawl state persistence, and path constants."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from models import CrawlState, SourceProduct

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (relative to this file's parent directory)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent
DATA_DIR = _ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
JSONL_PATH = DATA_DIR / "golden_dataset.jsonl"
CSV_PATH = DATA_DIR / "golden_dataset.csv"
STATE_PATH = _ROOT / "crawl_state.json"


# ---------------------------------------------------------------------------
# JSONL
# ---------------------------------------------------------------------------


def load_records(path: Path = JSONL_PATH) -> list[SourceProduct]:
    """Read all records from the JSONL file."""
    if not path.exists():
        return []
    records: list[SourceProduct] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(SourceProduct.from_dict(json.loads(line)))
    return records


def append_record(record: SourceProduct, path: Path = JSONL_PATH) -> None:
    """Append a single record to the JSONL file."""
    with open(path, "a") as f:
        f.write(json.dumps(record.to_dict()) + "\n")


def write_records(records: list[SourceProduct], path: Path = JSONL_PATH) -> None:
    """Overwrite the JSONL file with a full list of records."""
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict()) + "\n")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def generate_csv(jsonl_path: Path = JSONL_PATH, csv_path: Path = CSV_PATH) -> None:
    """Regenerate the CSV summary from the JSONL file."""
    records = load_records(jsonl_path)
    if not records:
        return

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "section",
                "source_product_id",
                "source_product_name",
                "source_product_url",
                "source_image_urls",
                "recommended_product_ids",
                "recommended_product_names",
                "recommended_product_urls",
            ]
        )
        for rec in records:
            writer.writerow(
                [
                    rec.section,
                    rec.source_product_id,
                    rec.source_product_name,
                    rec.source_product_url,
                    "|".join(rec.source_product_images),
                    "|".join(rp.product_id for rp in rec.recommended_products),
                    "|".join(rp.product_name for rp in rec.recommended_products),
                    "|".join(rp.product_url for rp in rec.recommended_products),
                ]
            )

    log.info(f"CSV written to {csv_path} ({len(records)} records)")


# ---------------------------------------------------------------------------
# Crawl state
# ---------------------------------------------------------------------------


def load_state(path: Path = STATE_PATH) -> CrawlState:
    """Load crawl state from disk, or return a fresh state."""
    if path.exists():
        return CrawlState.from_dict(json.loads(path.read_text()))
    return CrawlState()


def save_state(state: CrawlState, path: Path = STATE_PATH) -> None:
    """Persist crawl state to disk."""
    path.write_text(json.dumps(state.to_dict(), indent=2))

from __future__ import annotations

import csv
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .config import settings
from .seed_data import FRUIT_CSV_ROWS, FRUIT_DB_ROWS, ORDER_DB_ROWS, SUPPLIER_DB_ROWS

DATA_DIR = settings.data_dir
DB_PATH = settings.db_path

FX_PAIRS = [
    ("GBP", "INR", 129.62),
    ("USD", "INR", 83.51),
    ("EUR", "INR", 111.22),
    ("GBP", "USD", 1.55),
    ("EUR", "GBP", 0.858),
    ("EUR", "USD", 1.33),
    ("USD", "GBP", 0.645),
    ("GBP", "EUR", 1.166),
    ("AUD", "INR", 55.10),
    ("CAD", "INR", 61.25),
    ("SGD", "INR", 64.70),
    ("AED", "INR", 22.74),
]


def ensure_seed_data() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_csvs()
    write_sqlite()


def _current_fx_rows():
    csv_rows = []
    db_rows = []
    for idx, (base, quote, rate) in enumerate(FX_PAIRS):
        pair = f"{base}_{quote}"
        csv_rows.append({
            "pair_code": pair,
            "value": f"{rate * (0.985 + (idx % 3) * 0.002):.4f}",
            "decimals": "4",
            "updated_at": "2026-05-01T09:00:00Z",
        })
        db_rows.append((pair, round(rate * (0.997 + (idx % 2) * 0.001), 4), 4, "2026-05-09T18:00:00Z"))
    return csv_rows, db_rows


def _fx_history_rows():
    csv_rows = []
    db_rows = []
    start = date(2021, 1, 1)
    end = date(2025, 12, 31)
    total_days = (end - start).days + 1
    for pair_idx, (base, quote, base_rate) in enumerate(FX_PAIRS):
        pair = f"{base}_{quote}"
        for offset in range(total_days):
            dt = start + timedelta(days=offset)
            wave = math.sin((offset + pair_idx * 17) / 45.0) * 0.018
            seasonal = math.cos((offset + pair_idx * 11) / 180.0) * 0.012
            drift = (offset / total_days - 0.5) * 0.035
            reference = base_rate * (1 + wave + seasonal + drift)
            csv_rate = round(reference * (0.998 + ((offset + pair_idx) % 5) * 0.0004), 4)
            db_rate = round(reference * (1.000 + ((offset + pair_idx) % 7 - 3) * 0.00015), 4)
            record_id = f"{pair}_{dt.isoformat()}"
            csv_rows.append({
                "record_id": record_id,
                "date": dt.isoformat(),
                "pair": pair,
                "base": base,
                "quote": quote,
                "rate": f"{csv_rate:.4f}",
                "provider": "historical_csv_upload",
                "quality_tier": "standard",
                "freshness_days": "30",
            })
            db_rows.append((record_id, dt.isoformat(), pair, base, quote, db_rate, "official_reference_history", "reference", 2))
    return csv_rows, db_rows


def write_csvs() -> None:
    fx_current_csv, _ = _current_fx_rows()
    fx_history_csv, _ = _fx_history_rows()
    _write_csv(DATA_DIR / "fruits.csv", FRUIT_CSV_ROWS)
    _write_csv(DATA_DIR / "fx_rates.csv", fx_current_csv)
    _write_csv(DATA_DIR / "fx_history.csv", fx_history_csv)

def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite() -> None:
    _, fx_current_db = _current_fx_rows()
    _, fx_history_db = _fx_history_rows()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS fruit_prices;
        CREATE TABLE fruit_prices (
            fruit_name TEXT PRIMARY KEY,
            cost_gbp REAL,
            quality_band TEXT,
            supplier_code TEXT,
            last_sync TEXT
        );
        DROP TABLE IF EXISTS fx_official_rates;
        CREATE TABLE fx_official_rates (
            currency_pair TEXT PRIMARY KEY,
            official_rate REAL,
            scale INTEGER,
            published_at TEXT
        );
        DROP TABLE IF EXISTS fx_history_reference;
        CREATE TABLE fx_history_reference (
            record_id TEXT PRIMARY KEY,
            observed_date TEXT,
            currency_pair TEXT,
            base_currency TEXT,
            quote_currency TEXT,
            official_rate REAL,
            provider TEXT,
            quality_tier TEXT,
            freshness_days INTEGER
        );
        DROP TABLE IF EXISTS orders;
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            region TEXT,
            email TEXT,
            total REAL,
            score REAL
        );
        DROP TABLE IF EXISTS suppliers;
        CREATE TABLE suppliers (
            supplier_id TEXT PRIMARY KEY,
            supplier_name TEXT,
            country TEXT,
            rating REAL
        );
        CREATE INDEX IF NOT EXISTS idx_fruit_prices_supplier ON fruit_prices(supplier_code);
        CREATE INDEX IF NOT EXISTS idx_orders_region ON orders(region);
        CREATE INDEX IF NOT EXISTS idx_fx_history_pair_date ON fx_history_reference(currency_pair, observed_date);
        """
    )
    cur.executemany("INSERT INTO fruit_prices VALUES (?, ?, ?, ?, ?)", FRUIT_DB_ROWS)
    cur.executemany("INSERT INTO fx_official_rates VALUES (?, ?, ?, ?)", fx_current_db)
    cur.executemany("INSERT INTO fx_history_reference VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", fx_history_db)
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", ORDER_DB_ROWS)
    cur.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?)", SUPPLIER_DB_ROWS)
    con.commit()
    con.close()

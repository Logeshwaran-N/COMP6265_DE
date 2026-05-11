from __future__ import annotations

import csv
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .config import settings

DATA_DIR = settings.data_dir
DB_PATH = settings.db_path

FX_PAIRS = [
    ("GBP_INR", "GBP", "INR", 108.40),
    ("USD_INR", "USD", "INR", 83.47),
    ("EUR_INR", "EUR", "INR", 91.82),
    ("GBP_USD", "GBP", "USD", 1.29),
    ("EUR_GBP", "EUR", "GBP", 0.84),
    ("EUR_USD", "EUR", "USD", 1.09),
    ("USD_GBP", "USD", "GBP", 0.78),
    ("GBP_EUR", "GBP", "EUR", 1.18),
]
FX_HISTORY_START = date(2023, 5, 1)
FX_HISTORY_END = date(2026, 4, 30)


def ensure_seed_data() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_csvs()
    write_sqlite()


def _fx_rate(pair: str, base_rate: float, day: date, quality: str = "official") -> float:
    days = (day - FX_HISTORY_START).days
    seasonal = math.sin(days / 37.0) * 0.012
    trend = (days / 1095.0) * 0.018
    weekly = math.sin(days / 7.0) * 0.003
    multiplier = 1.0 + seasonal + trend + weekly
    if quality == "manual":
        # Manual CSV feed is intentionally stale/noisier to support trust/conflict demos.
        multiplier *= 0.986 + (math.sin(days / 17.0) * 0.004)
    return round(base_rate * multiplier, 4 if base_rate > 10 else 6)


def _iter_fx_history(quality: str = "official") -> list[dict]:
    rows: list[dict] = []
    d = FX_HISTORY_START
    while d <= FX_HISTORY_END:
        for pair, base, quote, base_rate in FX_PAIRS:
            rows.append({
                "history_id": f"{pair}-{d.isoformat()}",
                "date": d.isoformat(),
                "pair": pair,
                "base": base,
                "quote": quote,
                "rate": _fx_rate(pair, base_rate, d, quality),
                "provider": "manual_uploaded_rates" if quality == "manual" else "gov_authorised_server",
                "quality_tier": "manual" if quality == "manual" else "official",
            })
        d += timedelta(days=1)
    return rows


def write_csvs() -> None:
    fruits = [
        {"fruit": "apple", "price": "10.00", "grade": "B", "supplier": "S1", "updated": "2026-04-20"},
        {"fruit": "banana", "price": "4.10", "grade": "A", "supplier": "S2", "updated": "2026-04-20"},
        {"fruit": "orange", "price": "6.25", "grade": "B", "supplier": "S3", "updated": "2026-04-20"},
        {"fruit": "mango", "price": "9.80", "grade": "C", "supplier": "S4", "updated": "2026-04-20"},
        {"fruit": "grapes", "price": "5.70", "grade": "B", "supplier": "S2", "updated": "2026-04-20"},
        {"fruit": "pear", "price": "3.20", "grade": "B", "supplier": "S5", "updated": "2026-04-20"},
        {"fruit": "kiwi", "price": "7.40", "grade": "A", "supplier": "S4", "updated": "2026-04-20"},
    ]
    stale_day = FX_HISTORY_END - timedelta(days=14)
    fx = [
        {
            "pair_code": pair,
            "value": str(_fx_rate(pair, base_rate, stale_day, "manual")),
            "decimals": "4",
            "updated_at": stale_day.isoformat(),
        }
        for pair, _, _, base_rate in FX_PAIRS
    ]
    _write_csv(DATA_DIR / "fruits.csv", fruits)
    _write_csv(DATA_DIR / "fx_rates.csv", fx)
    _write_csv(DATA_DIR / "fx_history.csv", _iter_fx_history("manual"))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite() -> None:
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
            history_id TEXT PRIMARY KEY,
            observation_date TEXT,
            currency_pair TEXT,
            base_currency TEXT,
            quote_currency TEXT,
            official_rate REAL,
            provider TEXT,
            quality_tier TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fx_history_pair_date ON fx_history_reference(currency_pair, observation_date);
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
        """
    )
    cur.executemany("INSERT INTO fruit_prices VALUES (?, ?, ?, ?, ?)", [
        ("apple", 12.00, "A", "S1", "2026-05-05"),
        ("banana", 4.35, "A", "S2", "2026-05-05"),
        ("orange", 5.95, "A", "S3", "2026-05-05"),
        ("mango", 10.20, "B", "S4", "2026-05-05"),
        ("grapes", 5.30, "B", "S2", "2026-05-05"),
        ("pear", 3.45, "B", "S5", "2026-05-05"),
        ("kiwi", 7.10, "A", "S4", "2026-05-05"),
    ])
    official_day = FX_HISTORY_END
    cur.executemany("INSERT INTO fx_official_rates VALUES (?, ?, ?, ?)", [
        (pair, _fx_rate(pair, base_rate, official_day, "official"), 4, f"{official_day.isoformat()}T09:00:00Z")
        for pair, _, _, base_rate in FX_PAIRS
    ])
    history = _iter_fx_history("official")
    cur.executemany(
        "INSERT INTO fx_history_reference VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (r["history_id"], r["date"], r["pair"], r["base"], r["quote"], r["rate"], r["provider"], r["quality_tier"])
            for r in history
        ],
    )
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
        ("O-1001", "South East", "asha@example.com", 148.20, 0.84),
        ("O-1002", "London", "ben@example.com", 249.99, 0.91),
        ("O-1003", "Midlands", "chitra@example.com", 72.40, 0.62),
        ("O-1004", "Scotland", "david@example.com", 310.00, 0.88),
        ("O-1005", "Wales", "ella@example.com", 42.50, 0.51),
        ("O-1006", "South West", "faisal@example.com", 133.10, 0.74),
        ("O-1007", "North West", "gina@example.com", 91.80, 0.68),
        ("O-1008", "London", "hari@example.com", 420.00, 0.95),
    ])
    cur.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?)", [
        ("S1", "GreenFarm UK", "UK", 4.7),
        ("S2", "SunGrow Co", "Spain", 4.4),
        ("S3", "Citrus Direct", "Morocco", 4.5),
        ("S4", "Tropical Bridge", "India", 4.0),
        ("S5", "Orchard Lane", "UK", 4.2),
    ])
    con.commit()
    con.close()

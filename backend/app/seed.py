from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "warehouse.db"


def ensure_seed_data() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_csvs()
    write_sqlite()


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
    fx = [
        {"pair_code": "GBP_INR", "value": "105.20", "decimals": "2", "updated_at": "2026-04-18"},
        {"pair_code": "USD_INR", "value": "83.10", "decimals": "2", "updated_at": "2026-04-18"},
        {"pair_code": "EUR_INR", "value": "90.50", "decimals": "2", "updated_at": "2026-04-18"},
        {"pair_code": "GBP_USD", "value": "1.21", "decimals": "2", "updated_at": "2026-04-18"},
        {"pair_code": "EUR_GBP", "value": "0.86", "decimals": "2", "updated_at": "2026-04-18"},
    ]
    _write_csv(DATA_DIR / "fruits.csv", fruits)
    _write_csv(DATA_DIR / "fx_rates.csv", fx)


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
    cur.executemany("INSERT INTO fx_official_rates VALUES (?, ?, ?, ?)", [
        ("GBP_INR", 108.40, 4, "2026-05-06T09:00:00Z"),
        ("USD_INR", 83.47, 4, "2026-05-06T09:00:00Z"),
        ("EUR_INR", 91.82, 4, "2026-05-06T09:00:00Z"),
        ("GBP_USD", 1.29, 4, "2026-05-06T09:00:00Z"),
        ("EUR_GBP", 0.84, 4, "2026-05-06T09:00:00Z"),
    ])
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

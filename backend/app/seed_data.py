from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

FRUIT_ROW_COUNT = 1000
ORDER_ROW_COUNT = 5000
SUPPLIER_ROW_COUNT = 120

_GRADES = ["A", "A", "A", "B", "B", "C"]
_COUNTRIES = ["UK", "Spain", "Morocco", "India", "Netherlands", "France", "Italy", "Brazil", "South Africa", "Egypt"]
_REGIONS = ["London", "South East", "South West", "Midlands", "North West", "North East", "Scotland", "Wales", "Northern Ireland", "East Anglia"]
_FRUIT_FAMILIES: List[Tuple[str, float, List[str]]] = [
    ("apple", 2.85, ["gala", "braeburn", "pink_lady", "granny_smith", "cox", "red_delicious"]),
    ("banana", 1.18, ["cavendish", "organic", "fairtrade", "mini", "premium"]),
    ("orange", 2.20, ["valencia", "navel", "blood", "seville", "easy_peel"]),
    ("mango", 5.40, ["alphonso", "kesar", "kent", "honey", "ripe_pack"]),
    ("grapes", 4.35, ["red", "green", "black", "seedless", "premium"]),
    ("pear", 2.55, ["conference", "comice", "anjou", "packham", "rocha"]),
    ("kiwi", 3.70, ["green", "gold", "organic", "large", "zespri"]),
    ("strawberry", 4.65, ["uk", "spanish", "large", "organic", "premium"]),
    ("blueberry", 6.25, ["standard", "jumbo", "organic", "premium", "family_pack"]),
    ("pineapple", 2.95, ["whole", "sweet", "extra_sweet", "prepared", "gold"]),
    ("watermelon", 3.80, ["whole", "mini", "seedless", "slice_pack", "premium"]),
    ("raspberry", 5.90, ["standard", "uk", "organic", "premium", "large_pack"]),
    ("cherry", 7.10, ["standard", "sweet", "premium", "large", "turkish"]),
    ("plum", 2.70, ["victoria", "red", "black", "organic", "ripe"]),
    ("peach", 3.20, ["yellow", "white", "flat", "ripe", "premium"]),
    ("apricot", 3.85, ["standard", "ripe", "organic", "premium", "family_pack"]),
    ("papaya", 4.70, ["ripe", "green", "large", "premium", "tropical"]),
    ("pomegranate", 3.60, ["standard", "large", "premium", "prepared", "imported"]),
    ("lime", 2.10, ["standard", "large", "organic", "net", "premium"]),
    ("lemon", 2.25, ["standard", "large", "unwaxed", "organic", "net"]),
]


def _supplier_rows() -> List[Tuple[str, str, str, float]]:
    rows = []
    for i in range(1, SUPPLIER_ROW_COUNT + 1):
        country = _COUNTRIES[(i * 7) % len(_COUNTRIES)]
        rating = round(3.7 + ((i * 13) % 14) / 10, 1)
        rows.append((f"S{i:03d}", f"Supplier {i:03d} {country}", country, min(rating, 5.0)))
    return rows


def _fruit_entities() -> List[Dict[str, Any]]:
    rng = random.Random(6265)
    rows = []
    core = [
        ("apple", 2.85),
        ("banana", 1.18),
        ("orange", 2.20),
        ("mango", 5.40),
        ("grapes", 4.35),
        ("pear", 2.55),
        ("kiwi", 3.70),
        ("strawberry", 4.65),
        ("blueberry", 6.25),
        ("pineapple", 2.95),
    ]
    for idx, (name, price) in enumerate(core, 1):
        rows.append({"name": name, "base_price": price, "supplier_id": f"S{idx:03d}", "grade": _GRADES[idx % len(_GRADES)]})
    counter = 1
    while len(rows) < FRUIT_ROW_COUNT:
        family, base_price, varieties = _FRUIT_FAMILIES[(counter - 1) % len(_FRUIT_FAMILIES)]
        variety = varieties[(counter * 3) % len(varieties)]
        pack = ["single", "kg", "box", "premium", "value", "organic", "family"][(counter * 5) % 7]
        name = f"{family}_{variety}_{pack}_{counter:04d}"
        if any(r["name"] == name for r in rows):
            counter += 1
            continue
        seasonal = 1 + (((counter * 17) % 41) - 20) / 1000
        premium = 1 + ((counter * 11) % 23) / 100
        base = round(max(0.65, base_price * seasonal * premium), 2)
        supplier_id = f"S{((counter * 7) % SUPPLIER_ROW_COUNT) + 1:03d}"
        rows.append({"name": name, "base_price": base, "supplier_id": supplier_id, "grade": rng.choice(_GRADES)})
        counter += 1
    return rows


def get_fruit_rows() -> tuple[list[dict[str, str]], list[tuple[Any, ...]], list[dict[str, Any]]]:
    csv_rows: list[dict[str, str]] = []
    db_rows: list[tuple[Any, ...]] = []
    api_rows: list[dict[str, Any]] = []
    for idx, entity in enumerate(_fruit_entities()):
        base = float(entity["base_price"])
        if idx != 0 and idx % 20 == 0:
            csv_factor = 0.91 + (idx % 5) * 0.006
            db_factor = 1.00 + (idx % 3) * 0.004
            api_factor = 1.08 + (idx % 6) * 0.009
        else:
            csv_factor = 0.965 + (idx % 9) * 0.004
            db_factor = 0.992 + (idx % 7) * 0.004
            api_factor = 1.004 + (idx % 11) * 0.004
        csv_price = round(base * csv_factor, 2)
        db_price = round(base * db_factor, 2)
        api_price = round(base * api_factor, 2)
        csv_rows.append({
            "fruit": entity["name"],
            "price": f"{csv_price:.2f}",
            "grade": entity["grade"],
            "supplier": entity["supplier_id"],
            "updated": "2026-04-24",
        })
        db_rows.append((entity["name"], db_price, entity["grade"], entity["supplier_id"], "2026-05-07"))
        api_rows.append({
            "product": entity["name"],
            "market_price": api_price,
            "verified_grade": entity["grade"],
            "provider_ref": entity["supplier_id"],
            "timestamp": "2026-05-10T08:30:00Z",
        })
    return csv_rows, db_rows, api_rows


def get_order_rows() -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    db_rows: list[tuple[Any, ...]] = []
    api_rows: list[dict[str, Any]] = []
    domains = ["example.com", "mail.test", "demo.local", "studentmail.test"]
    for i in range(1, ORDER_ROW_COUNT + 1):
        region = _REGIONS[(i * 5) % len(_REGIONS)]
        base_total = 18 + ((i * 37) % 520) + ((i % 9) * 0.75)
        total = round(base_total, 2)
        score = round(0.35 + ((i * 29) % 63) / 100, 2)
        order_id = f"O-{100000 + i}"
        email = f"customer{i:05d}@{domains[i % len(domains)]}"
        db_rows.append((order_id, region, email, total, score))
        api_amount = round(total * (0.985 + (i % 11) * 0.0035), 2)
        api_score = round(min(0.99, max(0.05, score + ((i % 7) - 3) * 0.01)), 2)
        api_rows.append({"id": order_id, "area": region, "contact": email, "amount": api_amount, "demand": api_score})
    return db_rows, api_rows


FRUIT_CSV_ROWS, FRUIT_DB_ROWS, FRUIT_API_ROWS = get_fruit_rows()
ORDER_DB_ROWS, ORDER_API_ROWS = get_order_rows()
SUPPLIER_DB_ROWS = _supplier_rows()

FX_STANDARD_API_ROWS: List[Dict[str, Any]] = [
    {"symbol": "GBP_INR", "spot_rate": 129.62, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "USD_INR", "spot_rate": 83.51, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "EUR_INR", "spot_rate": 111.22, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "GBP_USD", "spot_rate": 1.55, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "EUR_GBP", "spot_rate": 0.858, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "EUR_USD", "spot_rate": 1.33, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "USD_GBP", "spot_rate": 0.645, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "GBP_EUR", "spot_rate": 1.166, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "AUD_INR", "spot_rate": 55.1, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "CAD_INR", "spot_rate": 61.25, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "SGD_INR", "spot_rate": 64.7, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
    {"symbol": "AED_INR", "spot_rate": 22.74, "precision": 4, "as_of": "2026-05-10T09:00:00Z"},
]

FX_PREMIUM_API_ROWS: List[Dict[str, Any]] = [
    {"symbol": row["symbol"], "spot_rate": round(float(row["spot_rate"]) * (1.00004 + (idx % 3) * 0.00001), 5), "precision": 5, "as_of": "2026-05-10T09:00:08Z"}
    for idx, row in enumerate(FX_STANDARD_API_ROWS)
]

SHARED_API_DATA: Dict[str, List[Dict[str, Any]]] = {
    "fruits": FRUIT_API_ROWS,
    "fx_rates": FX_STANDARD_API_ROWS,
    "fx_rates_premium": FX_PREMIUM_API_ROWS,
    "orders": ORDER_API_ROWS,
}

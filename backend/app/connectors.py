from __future__ import annotations

import csv
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

from .catalogue import CATALOGUE
from .models import ParsedPredicate, ParsedQuery
from .seed import DB_PATH

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MOCK_API_BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://localhost:8001")

FALLBACK_API_DATA: Dict[str, List[Dict[str, Any]]] = {
    "/fruits": [
        {"product": "apple", "market_price": 11.00, "verified_grade": "A", "provider_ref": "S1", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "banana", "market_price": 4.45, "verified_grade": "A", "provider_ref": "S2", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "orange", "market_price": 6.05, "verified_grade": "A", "provider_ref": "S3", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "mango", "market_price": 10.50, "verified_grade": "B", "provider_ref": "S4", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "grapes", "market_price": 5.45, "verified_grade": "B", "provider_ref": "S2", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "pear", "market_price": 3.35, "verified_grade": "B", "provider_ref": "S5", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "kiwi", "market_price": 7.25, "verified_grade": "A", "provider_ref": "S4", "timestamp": "2026-05-07T08:30:00Z"},
    ],
    "/fx_rates": [
        {"symbol": "GBP_INR", "spot_rate": 108.43, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "USD_INR", "spot_rate": 83.49, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "EUR_INR", "spot_rate": 91.79, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "GBP_USD", "spot_rate": 1.30, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "EUR_GBP", "spot_rate": 0.84, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
    ],
    "/orders": [
        {"id": "O-1001", "area": "South East", "contact": "asha@example.com", "amount": 148.20, "demand": 0.82},
        {"id": "O-1002", "area": "London", "contact": "ben@example.com", "amount": 249.99, "demand": 0.92},
        {"id": "O-1003", "area": "Midlands", "contact": "chitra@example.com", "amount": 72.40, "demand": 0.61},
        {"id": "O-1004", "area": "Scotland", "contact": "david@example.com", "amount": 310.00, "demand": 0.87},
        {"id": "O-1005", "area": "Wales", "contact": "ella@example.com", "amount": 42.50, "demand": 0.50},
        {"id": "O-1006", "area": "South West", "contact": "faisal@example.com", "amount": 133.10, "demand": 0.75},
        {"id": "O-1007", "area": "North West", "contact": "gina@example.com", "amount": 91.80, "demand": 0.67},
        {"id": "O-1008", "area": "London", "contact": "hari@example.com", "amount": 420.00, "demand": 0.96},
    ],
}


def _coerce(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return value
    text = str(value)
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _compare(left: Any, op: str, right: Any) -> bool:
    left_c = _coerce(left)
    right_c = _coerce(right)
    if op == "=":
        return str(left_c).lower() == str(right_c).lower()
    if op == "!=":
        return str(left_c).lower() != str(right_c).lower()
    try:
        if op == ">":
            return float(left_c) > float(right_c)
        if op == "<":
            return float(left_c) < float(right_c)
        if op == ">=":
            return float(left_c) >= float(right_c)
        if op == "<=":
            return float(left_c) <= float(right_c)
    except Exception:
        return False
    return False


def _project_and_map(dataset_name: str, source_name: str, physical_rows: List[Dict[str, Any]], query: ParsedQuery, selected_cols: List[str]) -> List[Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    mapping = source["mapping"]
    virtual_rows: List[Dict[str, Any]] = []
    for row in physical_rows:
        vrow: Dict[str, Any] = {}
        for virtual_col, physical_col in mapping.items():
            if physical_col in row:
                vrow[virtual_col] = _coerce(row[physical_col])
        if query.where and query.dataset == dataset_name:
            if query.where.left not in vrow or not _compare(vrow.get(query.where.left), query.where.op, query.where.right):
                continue
        out_cols = list(CATALOGUE[dataset_name]["columns"].keys()) if selected_cols == ["*"] else selected_cols
        projected = {col: vrow.get(col) for col in out_cols if col in vrow}
        # Always keep entity key for conflict resolution and provenance, even if not selected.
        key = CATALOGUE[dataset_name]["entity_key"]
        if key in vrow and key not in projected:
            projected[key] = vrow[key]
        projected["_source"] = source_name
        projected["_provider"] = source["provider"]
        projected["_dataset"] = dataset_name
        virtual_rows.append(projected)
    return virtual_rows


def execute_source(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    start = time.perf_counter()
    if source["type"] == "csv":
        rows = _exec_csv(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "sqlite":
        rows = _exec_sqlite(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "api":
        rows = _exec_api(dataset_name, source_name, query, selected_cols)
        api_calls = 1
    else:
        raise ValueError(f"Unsupported source type: {source['type']}")
    elapsed_ms = (time.perf_counter() - start) * 1000
    metrics = {
        "source": source_name,
        "dataset": dataset_name,
        "rows_returned": len(rows),
        "api_calls": api_calls,
        "elapsed_ms": round(elapsed_ms, 3),
        "source_type": source["type"],
    }
    return rows, metrics


def _exec_csv(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> List[Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    with (DATA_DIR / source["file"]).open() as f:
        physical = list(csv.DictReader(f))
    return _project_and_map(dataset_name, source_name, physical, query, selected_cols)


def _exec_sqlite(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> List[Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    mapping = source["mapping"]
    table = source["table"]
    selected = list(CATALOGUE[dataset_name]["columns"].keys()) if selected_cols == ["*"] else selected_cols
    phys_cols = sorted({mapping[c] for c in selected if c in mapping} | {mapping[CATALOGUE[dataset_name]["entity_key"]]})
    sql = f"SELECT {', '.join(phys_cols)} FROM {table}"
    params: list[Any] = []
    if query.where and query.dataset == dataset_name and query.where.left in mapping and query.where.op == "=":
        sql += f" WHERE {mapping[query.where.left]} = ?"
        params.append(query.where.right)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return _project_and_map(dataset_name, source_name, rows, query, selected)


def _exec_api(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> List[Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    endpoint = source["endpoint"]
    params: Dict[str, Any] = {}
    # Our mock API supports generic key/value equality filter.
    if query.where and query.dataset == dataset_name and query.where.op == "=":
        physical_col = source["mapping"].get(query.where.left)
        if physical_col:
            params[physical_col] = query.where.right
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{MOCK_API_BASE_URL}{endpoint}", params=params)
            response.raise_for_status()
            physical = response.json()
    except Exception:
        physical = FALLBACK_API_DATA.get(endpoint, [])
        if params:
            physical = [r for r in physical if all(str(r.get(k)).lower() == str(v).lower() for k, v in params.items())]
    return _project_and_map(dataset_name, source_name, physical, query, selected_cols)

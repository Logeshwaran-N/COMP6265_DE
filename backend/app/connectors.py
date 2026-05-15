from __future__ import annotations

import csv
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

from .catalogue import CATALOGUE
from .config import settings
from .models import ParsedQuery
from .seed import DB_PATH
from .seed_data import SHARED_API_DATA

DATA_DIR = settings.data_dir
MOCK_API_BASE_URL = settings.mock_api_base_url

FALLBACK_API_DATA: Dict[str, List[Dict[str, Any]]] = {
    "/fruits": SHARED_API_DATA["fruits"],
    "/fx_rates": SHARED_API_DATA["fx_rates"],
    "/fx_rates_premium": SHARED_API_DATA["fx_rates_premium"],
    "/orders": SHARED_API_DATA["orders"],
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
        rows, rows_scanned = _exec_csv(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "sqlite":
        rows, rows_scanned = _exec_sqlite(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "api":
        rows, rows_scanned = _exec_api(dataset_name, source_name, query, selected_cols)
        api_calls = 1
    else:
        raise ValueError(f"Unsupported source type: {source['type']}")
    elapsed_ms = (time.perf_counter() - start) * 1000
    metrics = {
        "source": source_name,
        "source_label": source.get("display_name", source_name),
        "source_role": source.get("source_role", source.get("type")),
        "dataset": dataset_name,
        "rows_scanned": rows_scanned,
        "rows_returned": len(rows),
        "api_calls": api_calls,
        "elapsed_ms": round(elapsed_ms, 3),
        "source_type": source["type"],
    }
    return rows, metrics


def _exec_csv(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    with (DATA_DIR / source["file"]).open() as f:
        physical = list(csv.DictReader(f))
    return _project_and_map(dataset_name, source_name, physical, query, selected_cols), len(physical)


def _exec_sqlite(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    mapping = source["mapping"]
    table = source["table"]
    selected = list(CATALOGUE[dataset_name]["columns"].keys()) if selected_cols == ["*"] else selected_cols
    needed_virtual = set(selected) | {CATALOGUE[dataset_name]["entity_key"]}
    if query.where and query.dataset == dataset_name and query.where.left in mapping:
        needed_virtual.add(query.where.left)
    if query.order_by and query.order_by in mapping:
        needed_virtual.add(query.order_by)
    phys_cols = sorted({mapping[c] for c in needed_virtual if c in mapping})
    sql = f"SELECT {', '.join(phys_cols)} FROM {table}"
    params: list[Any] = []
    equality_pushdown = bool(query.where and query.dataset == dataset_name and query.where.left in mapping and query.where.op == "=")
    if equality_pushdown:
        sql += f" WHERE {mapping[query.where.left]} = ?"
        params.append(query.where.right)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    rows_scanned = len(rows) if equality_pushdown else int(source.get("row_count", len(rows)))
    return _project_and_map(dataset_name, source_name, rows, query, selected), rows_scanned


def _exec_api(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    endpoint = source["endpoint"]
    params: Dict[str, Any] = {}
    if query.where and query.dataset == dataset_name and query.where.op == "=":
        physical_col = source["mapping"].get(query.where.left)
        if physical_col:
            params[physical_col] = query.where.right
    base_url = (MOCK_API_BASE_URL or "").strip().lower()
    if base_url in {"", "internal", "disabled", "fallback", "mock"}:
        physical = FALLBACK_API_DATA.get(endpoint, [])
    else:
        try:
            with httpx.Client(timeout=settings.api_timeout_seconds) as client:
                response = client.get(f"{MOCK_API_BASE_URL}{endpoint}", params=params)
                response.raise_for_status()
                physical = response.json()
        except Exception:
            physical = FALLBACK_API_DATA.get(endpoint, [])
    rows_before_filter = len(physical)
    if params:
        physical = [r for r in physical if all(str(r.get(k)).lower() == str(v).lower() for k, v in params.items())]
    rows_scanned = len(physical) if params else rows_before_filter
    return _project_and_map(dataset_name, source_name, physical, query, selected_cols), rows_scanned

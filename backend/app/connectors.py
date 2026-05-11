from __future__ import annotations

import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

from .catalogue import CATALOGUE
from .config import settings
from .models import ParsedQuery
from .seed import DB_PATH, FX_PAIRS
from .seed_data import SHARED_API_DATA

DATA_DIR = settings.data_dir
MOCK_API_BASE_URL = settings.mock_api_base_url

FALLBACK_API_DATA: Dict[str, List[Dict[str, Any]]] = {
    "/fruits": SHARED_API_DATA["fruits"],
    "/fx_rates": SHARED_API_DATA["fx_rates"],
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
        for extra in ("_live_status", "_cache_used", "_api_provider", "_api_date"):
            if extra in row:
                projected[extra] = row[extra]
        virtual_rows.append(projected)
    return virtual_rows


def execute_source(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source = CATALOGUE[dataset_name]["sources"][source_name]
    start = time.perf_counter()
    extra_metrics: Dict[str, Any] = {}
    if source["type"] == "csv":
        rows = _exec_csv(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "sqlite":
        rows = _exec_sqlite(dataset_name, source_name, query, selected_cols)
        api_calls = 0
    elif source["type"] == "api":
        rows = _exec_api(dataset_name, source_name, query, selected_cols)
        api_calls = 1
    elif source["type"] == "live_fx_api":
        rows, extra_metrics = _exec_live_fx_api(dataset_name, source_name, query, selected_cols)
        api_calls = int(extra_metrics.get("api_calls", 0))
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
    metrics.update(extra_metrics)
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
    if params:
        physical = [r for r in physical if all(str(r.get(k)).lower() == str(v).lower() for k, v in params.items())]
    return _project_and_map(dataset_name, source_name, physical, query, selected_cols)


def _cache_path() -> Path:
    path = settings.live_fx_cache_path or (DATA_DIR / "live_fx_cache.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_live_cache() -> Dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_live_cache(cache: Dict[str, Any]) -> None:
    _cache_path().write_text(json.dumps(cache, indent=2, sort_keys=True))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pair_parts(pair: str) -> tuple[str, str]:
    cleaned = pair.strip().upper().replace("/", "_").replace("-", "_")
    if "_" in cleaned:
        base, quote = cleaned.split("_", 1)
    else:
        base, quote = cleaned[:3], cleaned[3:]
    return base, quote


def _default_fx_pairs() -> List[str]:
    return [p[0] for p in FX_PAIRS]


def _fallback_live_row(pair: str, status: str = "fallback_seed") -> Dict[str, Any]:
    fallback = {row["symbol"].upper(): row for row in SHARED_API_DATA["fx_rates"]}
    row = fallback.get(pair.upper())
    if row:
        return {
            "symbol": row["symbol"],
            "spot_rate": row["spot_rate"],
            "precision": row.get("precision", 4),
            "as_of": row.get("as_of"),
            "_live_status": status,
            "_cache_used": False,
            "_api_provider": "internal_fallback",
            "_api_date": row.get("as_of"),
        }
    base, quote = _pair_parts(pair)
    return {
        "symbol": f"{base}_{quote}",
        "spot_rate": None,
        "precision": 4,
        "as_of": _utc_now().isoformat(timespec="seconds"),
        "_live_status": "unavailable",
        "_cache_used": False,
        "_api_provider": "none",
        "_api_date": None,
    }


def _fetch_frankfurter_pair(pair: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    base, quote = _pair_parts(pair)
    pair_key = f"{base}_{quote}"
    now = _utc_now()
    ttl = int(settings.live_fx_cache_ttl_seconds)
    cache = _read_live_cache()
    cached = cache.get(pair_key)
    if cached:
        try:
            fetched_at = datetime.fromisoformat(str(cached.get("fetched_at")).replace("Z", "+00:00"))
            age = (now - fetched_at).total_seconds()
            if age <= ttl:
                return {
                    "symbol": pair_key,
                    "spot_rate": cached["rate"],
                    "precision": 6,
                    "as_of": cached.get("date") or cached.get("fetched_at"),
                    "_live_status": "cache_hit",
                    "_cache_used": True,
                    "_api_provider": cached.get("provider", "frankfurter"),
                    "_api_date": cached.get("date"),
                }, {"api_calls": 0, "cache_used": True, "live_status": "cache_hit", "live_pair": pair_key}
        except Exception:
            pass
    if not bool(settings.live_fx_api_enabled):
        return _fallback_live_row(pair_key, "live_disabled"), {"api_calls": 0, "cache_used": False, "live_status": "live_disabled", "live_pair": pair_key}
    try:
        with httpx.Client(timeout=settings.api_timeout_seconds) as client:
            response = client.get(
                f"{settings.live_fx_api_base_url.rstrip('/')}/rates",
                params={"base": base, "quotes": quote},
            )
            response.raise_for_status()
            payload = response.json()
        rates = payload.get("rates") or {}
        if quote not in rates:
            raise ValueError(f"{quote} missing from Frankfurter response")
        rate = float(rates[quote])
        fetched_at = now.isoformat(timespec="seconds")
        date_value = payload.get("date") or fetched_at
        cache[pair_key] = {
            "rate": rate,
            "provider": "frankfurter",
            "fetched_at": fetched_at,
            "date": date_value,
            "base": base,
            "quote": quote,
        }
        _write_live_cache(cache)
        return {
            "symbol": pair_key,
            "spot_rate": rate,
            "precision": 6,
            "as_of": date_value,
            "_live_status": "live_api",
            "_cache_used": False,
            "_api_provider": "frankfurter",
            "_api_date": date_value,
        }, {"api_calls": 1, "cache_used": False, "live_status": "live_api", "live_pair": pair_key}
    except Exception as exc:
        if cached and cached.get("rate") is not None:
            return {
                "symbol": pair_key,
                "spot_rate": cached["rate"],
                "precision": 6,
                "as_of": cached.get("date") or cached.get("fetched_at"),
                "_live_status": "stale_cache_fallback",
                "_cache_used": True,
                "_api_provider": cached.get("provider", "frankfurter"),
                "_api_date": cached.get("date"),
            }, {"api_calls": 1, "cache_used": True, "live_status": "stale_cache_fallback", "live_error": str(exc), "live_pair": pair_key}
        return _fallback_live_row(pair_key, "fallback_after_api_error"), {"api_calls": 1, "cache_used": False, "live_status": "fallback_after_api_error", "live_error": str(exc), "live_pair": pair_key}


def _exec_live_fx_api(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if dataset_name != "fx_rates":
        return [], {"api_calls": 0, "cache_used": False, "live_status": "unsupported_dataset"}
    if query.where and query.where.left == "pair" and query.where.op == "=":
        pairs = [str(query.where.right).upper()]
    else:
        # Avoid calling the external API many times for broad browse queries; use seed fallback for all pairs.
        physical = [_fallback_live_row(p, "broad_query_seed") for p in _default_fx_pairs()]
        return _project_and_map(dataset_name, source_name, physical, query, selected_cols), {"api_calls": 0, "cache_used": False, "live_status": "broad_query_seed"}
    rows: List[Dict[str, Any]] = []
    calls = 0
    statuses: list[str] = []
    cache_used = False
    errors: list[str] = []
    for pair in pairs:
        row, metrics = _fetch_frankfurter_pair(pair)
        rows.append(row)
        calls += int(metrics.get("api_calls", 0))
        statuses.append(str(metrics.get("live_status", "unknown")))
        cache_used = cache_used or bool(metrics.get("cache_used", False))
        if metrics.get("live_error"):
            errors.append(str(metrics["live_error"]))
    return _project_and_map(dataset_name, source_name, rows, query, selected_cols), {
        "api_calls": calls,
        "cache_used": cache_used,
        "live_status": ",".join(sorted(set(statuses))),
        "live_errors": errors,
        "live_provider": "frankfurter",
    }

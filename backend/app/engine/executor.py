from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from ..catalogue import CATALOGUE
from ..connectors import execute_source
from ..models import CandidatePlan, ParsedQuery
from .conflict import resolve_conflicts
from .pricing import calculate_price


def _selected_columns(dataset_name: str, query: ParsedQuery) -> List[str]:
    if query.select == ["*"]:
        return list(CATALOGUE[dataset_name]["columns"].keys())
    cols = [c for c in query.select if c in CATALOGUE[dataset_name]["columns"]]
    return cols or [CATALOGUE[dataset_name]["entity_key"]]


def _sort_value(value: Any) -> Any:
    if value is None:
        return ""
    try:
        return float(value)
    except Exception:
        return str(value)


def _apply_order_and_limit(rows: List[Dict[str, Any]], query: ParsedQuery) -> List[Dict[str, Any]]:
    out = list(rows)
    if query.order_by:
        reverse = query.order_dir.lower() == "desc"
        out.sort(key=lambda row: _sort_value(row.get(query.order_by)), reverse=reverse)
    if query.limit:
        out = out[: query.limit]
    return out


def execute_plan(query: ParsedQuery, plan: CandidatePlan, role: str, purpose: str, show_all_conflicts: bool) -> Dict[str, Any]:
    if plan.mode.startswith("join"):
        return _execute_join(query, plan, role, purpose, show_all_conflicts)
    return _execute_single(query, plan, role, purpose, show_all_conflicts)


def _execute_single(query: ParsedQuery, plan: CandidatePlan, role: str, purpose: str, show_all_conflicts: bool) -> Dict[str, Any]:
    dataset = query.dataset
    selected = _selected_columns(dataset, query)
    all_rows: List[Dict[str, Any]] = []
    metrics: List[Dict[str, Any]] = []
    for src in plan.sources:
        rows, metric = execute_source(dataset, src, query, selected)
        all_rows.extend(rows)
        metrics.append(metric)
    result_rows, conflicts = resolve_conflicts(dataset, all_rows, selected, show_all_conflicts)
    result_rows = _apply_order_and_limit(result_rows, query)
    pricing = calculate_price(query, plan, conflicts, role, purpose, actual_returned_rows=len(result_rows), actual_metrics=metrics)
    return {"result_rows": result_rows, "conflicts": conflicts, "metrics": metrics, "pricing": pricing}


def _execute_join(query: ParsedQuery, plan: CandidatePlan, role: str, purpose: str, show_all_conflicts: bool) -> Dict[str, Any]:
    left_ds = query.dataset
    right_ds = query.join_dataset or ""
    left_cols = list(set(_selected_columns(left_ds, query) + ([query.join_left] if query.join_left else [])))
    right_cols = list(set(_selected_columns(right_ds, query) + ([query.join_right] if query.join_right else [])))
    metrics: List[Dict[str, Any]] = []
    left_rows_all: List[Dict[str, Any]] = []
    right_rows_all: List[Dict[str, Any]] = []
    for src in plan.sources:
        if src in CATALOGUE[left_ds]["sources"]:
            rows, metric = execute_source(left_ds, src, query, left_cols)
            left_rows_all.extend(rows)
            metrics.append(metric)
        elif src in CATALOGUE[right_ds]["sources"]:
            rows, metric = execute_source(right_ds, src, query, right_cols)
            right_rows_all.extend(rows)
            metrics.append(metric)
    left_rows, left_conflicts = resolve_conflicts(left_ds, left_rows_all, left_cols, show_all_conflicts)
    right_rows, right_conflicts = resolve_conflicts(right_ds, right_rows_all, right_cols, show_all_conflicts)
    joined: List[Dict[str, Any]] = []
    right_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    join_left = query.join_left or CATALOGUE[left_ds]["entity_key"]
    join_right = query.join_right or CATALOGUE[right_ds]["entity_key"]
    for rrow in right_rows:
        key = str(rrow.get(join_right, "")).lower()
        right_index[key].append(rrow)
    for lrow in left_rows:
        key = str(lrow.get(join_left, "")).lower()
        for rrow in right_index.get(key, []):
            merged = {
                **{f"{left_ds}.{k}": v for k, v in lrow.items() if not k.startswith("_")},
                **{f"{right_ds}.{k}": v for k, v in rrow.items() if not k.startswith("_")},
            }
            merged["_chosen_sources"] = [lrow.get("_chosen_source"), rrow.get("_chosen_source")]
            joined.append(merged)
    joined = _apply_order_and_limit(joined, query)
    conflicts = left_conflicts + right_conflicts
    pricing = calculate_price(query, plan, conflicts, role, purpose, actual_returned_rows=len(joined), actual_metrics=metrics)
    return {"result_rows": joined, "conflicts": conflicts, "metrics": metrics, "pricing": pricing}

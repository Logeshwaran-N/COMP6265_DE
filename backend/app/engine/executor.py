from __future__ import annotations

from typing import Any, Dict, List, Tuple

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
        rows, m = execute_source(dataset, src, query, selected)
        all_rows.extend(rows)
        metrics.append(m)
    if plan.mode == "verified":
        result_rows, conflicts = resolve_conflicts(dataset, all_rows, selected, show_all_conflicts)
    else:
        # Single-source still goes through the resolver to attach confidence/provenance consistently.
        result_rows, conflicts = resolve_conflicts(dataset, all_rows, selected, show_all_conflicts)
    if query.limit:
        result_rows = result_rows[: query.limit]
    pricing = calculate_price(query, plan, conflicts, role, purpose)
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
            rows, m = execute_source(left_ds, src, query, left_cols)
            left_rows_all.extend(rows)
            metrics.append(m)
        elif src in CATALOGUE[right_ds]["sources"]:
            rows, m = execute_source(right_ds, src, query, right_cols)
            right_rows_all.extend(rows)
            metrics.append(m)
    left_rows, left_conflicts = resolve_conflicts(left_ds, left_rows_all, left_cols, show_all_conflicts)
    right_rows, right_conflicts = resolve_conflicts(right_ds, right_rows_all, right_cols, show_all_conflicts)
    joined: List[Dict[str, Any]] = []
    for lrow in left_rows:
        for rrow in right_rows:
            if str(lrow.get(query.join_left)).lower() == str(rrow.get(query.join_right)).lower():
                merged = {**{f"{left_ds}.{k}": v for k, v in lrow.items() if not k.startswith("_")}, **{f"{right_ds}.{k}": v for k, v in rrow.items() if not k.startswith("_")}}
                merged["_chosen_sources"] = [lrow.get("_chosen_source"), rrow.get("_chosen_source")]
                joined.append(merged)
    if query.limit:
        joined = joined[: query.limit]
    conflicts = left_conflicts + right_conflicts
    pricing = calculate_price(query, plan, conflicts, role, purpose)
    return {"result_rows": joined, "conflicts": conflicts, "metrics": metrics, "pricing": pricing}

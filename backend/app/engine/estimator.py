from __future__ import annotations

from typing import Any, Dict, List
from ..catalogue import CATALOGUE
from typing import Optional

from ..models import ParsedPredicate, ParsedQuery, SourcePlanEstimate
from .trust import freshness_score, trust_cache


def _selectivity(dataset_name: str, predicate: Optional[ParsedPredicate]) -> float:
    if predicate is None:
        return 1.0
    dataset = CATALOGUE[dataset_name]
    col_meta = dataset["columns"].get(predicate.left)
    if not col_meta:
        return 0.5
    distinct = max(int(col_meta.get("distinct", 10)), 1)
    col_type = col_meta.get("type", "string")
    if predicate.op == "=":
        sel = 1.0 / distinct
        if distinct < 5:
            sel = min(sel * 1.5, 1.0)
        return sel
    if predicate.op in (">", "<", ">=", "<="):
        return 0.25 if col_type == "number" else 0.33
    if predicate.op == "!=":
        return (distinct - 1) / distinct if distinct > 1 else 1.0
    return 1.0


def estimate_source(dataset_name: str, source_name: str, query: ParsedQuery, selected_cols: List[str]) -> SourcePlanEstimate:
    dataset = CATALOGUE[dataset_name]
    source = dataset["sources"][source_name]
    row_count = int(source["row_count"])
    selectivity = _selectivity(dataset_name, query.where if query.dataset == dataset_name else None)
    rows_returned = max(1, int(row_count * selectivity)) if row_count else 0
    # CSV is modelled as scan-all; DB/API can push predicates to reduce scanned rows.
    if source["type"] == "csv":
        rows_scanned = row_count
        pushdown = "CSV connector scans the file then filters in Python."
    else:
        rows_scanned = max(rows_returned, 1)
        pushdown = "Predicate is pushed to SQLite/API endpoint when possible."

    api_calls = 1 if source["type"] == "api" else 0
    latency = float(source["latency_ms"]) + (rows_scanned * 0.35) + (api_calls * 15)
    access_cost = float(source["access_cost"])
    row_cost = rows_scanned * float(source["row_scan_cost"])
    api_cost = api_calls * float(source["api_call_cost"])
    projection_penalty = max(0, len(selected_cols) - 1) * 0.03
    exec_cost = access_cost + row_cost + api_cost + projection_penalty
    trust = trust_cache.get().get(source_name, {}).get("computed_trust", source.get("base_trust", 0.5))
    fresh = freshness_score(source.get("freshness_days", 30))
    return SourcePlanEstimate(
        source_name=source_name,
        dataset=dataset_name,
        estimated_rows_scanned=rows_scanned,
        estimated_rows_returned=rows_returned,
        estimated_latency_ms=latency,
        estimated_execution_cost=exec_cost,
        api_calls=api_calls,
        trust_score=trust,
        freshness_score=fresh,
        conflict_risk=float(source.get("conflict_risk", 0.5)),
        supported_columns=[c for c in selected_cols if c in source["mapping"]],
        explanation=f"rows={row_count}, selectivity={selectivity:.3f}. {pushdown}",
    )


def estimate_join_rows(left_rows: int, right_rows: int, left_distinct: int, right_distinct: int) -> int:
    # Same formula as classical join estimation: |R|*|S| / max(V(R,a), V(S,b))
    denom = max(left_distinct, right_distinct, 1)
    return max(1, int((left_rows * right_rows) / denom))

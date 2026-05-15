from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..catalogue import CATALOGUE
from ..models import CandidatePlan, ParsedQuery


def _columns_for_dataset(dataset_name: str, query: ParsedQuery) -> List[str]:
    dataset = CATALOGUE[dataset_name]
    if query.select == ["*"]:
        return list(dataset["columns"].keys())
    cols = [c for c in query.select if c in dataset["columns"]]
    return cols or [dataset["entity_key"]]


def _arbitrage_guarded_column_price(dataset_name: str, cols: List[str]) -> Dict[str, Any]:
    dataset = CATALOGUE[dataset_name]
    column_sum = sum(float(dataset["columns"][c].get("price", 1.0)) for c in cols if c in dataset["columns"])
    covering_views = []
    col_set = set(cols)
    for view in dataset.get("price_points", []):
        if col_set.issubset(set(view["columns"])):
            covering_views.append(view)
    if covering_views:
        cheapest_cover = min(covering_views, key=lambda v: float(v["price"]))
        guarded = min(column_sum, float(cheapest_cover["price"]))
        method = f"min(column_sum={column_sum:.2f}, covering_view={cheapest_cover['name']}:{cheapest_cover['price']:.2f})"
    else:
        guarded = column_sum
        method = f"column_sum={column_sum:.2f}; no single published view covers requested columns"
    return {"dataset": dataset_name, "columns": cols, "column_sum": round(column_sum, 2), "guarded_price": round(guarded, 2), "method": method}


def _source_multiplier(source: Dict[str, Any]) -> float:
    role = str(source.get("source_role") or "")
    return {
        "archive_bulk": 0.75,
        "daily_reference": 1.0,
        "controlled_warehouse": 1.05,
        "reference_master": 1.0,
        "analytics_api": 1.25,
        "current_market": 1.35,
        "standard_live": 1.35,
        "premium_live": 2.2,
    }.get(role, 1.0)


def _row_tier(returned: int) -> float:
    if returned > 5000:
        return 4.0
    if returned > 1000:
        return 2.0
    if returned > 100:
        return 0.75
    if returned > 10:
        return 0.25
    return 0.0


def calculate_price(query: ParsedQuery, selected_plan: CandidatePlan, conflicts: List[Dict[str, Any]], role: str, purpose: str, actual_returned_rows: Optional[int] = None, actual_metrics: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    datasets = selected_plan.datasets
    column_components = [_arbitrage_guarded_column_price(ds, _columns_for_dataset(ds, query)) for ds in datasets]
    column_price = sum(c["guarded_price"] for c in column_components)
    source_premium = 0.0
    source_breakdown = []
    for ds in datasets:
        for src_name in selected_plan.sources:
            source = CATALOGUE[ds]["sources"].get(src_name)
            if not source:
                continue
            multiplier = _source_multiplier(source)
            premium = round(float(source["access_cost"]) * multiplier * (1.0 + float(source["authority_level"]) * 0.25), 2)
            source_premium += premium
            source_breakdown.append({
                "source": src_name,
                "source_label": source.get("display_name", src_name),
                "dataset": ds,
                "tier": source.get("source_role", source.get("type")),
                "premium": premium,
                "authority_level": source["authority_level"],
            })
    verification_fee = 2.0 if selected_plan.mode in ("verified", "join_verified") else 0.0
    conflict_fee = min(3.0, 0.75 * len(conflicts))
    sensitive_fee = 0.0
    for ds in datasets:
        for col in _columns_for_dataset(ds, query):
            if CATALOGUE[ds]["columns"].get(col, {}).get("pii"):
                sensitive_fee += 2.0
    returned = max(int(actual_returned_rows if actual_returned_rows is not None else selected_plan.estimated_rows_returned or 0), 0)
    row_tier_fee = _row_tier(returned)
    actual_scan = sum(int(m.get("rows_scanned", 0) or 0) for m in actual_metrics or [])
    actual_api_calls = sum(int(m.get("api_calls", 0) or 0) for m in actual_metrics or [])
    base_fee = 1.0
    total = base_fee + column_price + source_premium + verification_fee + conflict_fee + sensitive_fee + row_tier_fee
    return {
        "currency": "credits",
        "total_user_price": round(total, 2),
        "base_fee": base_fee,
        "column_price_arbitrage_guarded": round(column_price, 2),
        "source_premium": round(source_premium, 2),
        "verification_fee": verification_fee,
        "conflict_resolution_fee": round(conflict_fee, 2),
        "sensitive_column_fee": round(sensitive_fee, 2),
        "row_tier_fee": row_tier_fee,
        "charged_output_rows": returned,
        "actual_rows_scanned": actual_scan,
        "actual_api_calls": actual_api_calls,
        "row_tier_note": f"Charged on returned output rows={returned}. Internal scan work is shown separately for optimisation evidence.",
        "column_components": column_components,
        "source_breakdown": source_breakdown,
        "internal_execution_cost_estimate": round(selected_plan.estimated_execution_cost, 4),
        "pricing_note": "User price is data-value pricing. Internal execution cost is separate and used for optimiser decisions.",
        "arbitrage_note": "Column price is capped by published view price when a view determines the requested query output.",
    }

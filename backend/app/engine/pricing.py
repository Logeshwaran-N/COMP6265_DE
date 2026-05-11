from __future__ import annotations

from typing import Any, Dict, List
from ..catalogue import CATALOGUE
from ..models import CandidatePlan, ParsedQuery


def _columns_for_dataset(dataset_name: str, query: ParsedQuery) -> List[str]:
    dataset = CATALOGUE[dataset_name]
    if query.select == ["*"]:
        return list(dataset["columns"].keys())
    cols = [c for c in query.select if c in dataset["columns"]]
    if not cols:
        cols = [dataset["entity_key"]]
    return cols


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


def calculate_price(query: ParsedQuery, selected_plan: CandidatePlan, conflicts: List[Dict[str, Any]], role: str, purpose: str) -> Dict[str, Any]:
    datasets = selected_plan.datasets
    column_components = [_arbitrage_guarded_column_price(ds, _columns_for_dataset(ds, query)) for ds in datasets]
    column_price = sum(c["guarded_price"] for c in column_components)

    # User-facing source premium is not raw system cost. It reflects access to premium/trusted data products.
    source_premium = 0.0
    source_breakdown = []
    for ds in datasets:
        for src_name in selected_plan.sources:
            source = CATALOGUE[ds]["sources"].get(src_name)
            if not source:
                continue
            premium = round(float(source["access_cost"]) * (1.0 + float(source["authority_level"]) * 0.4), 2)
            source_premium += premium
            source_breakdown.append({"source": src_name, "dataset": ds, "premium": premium, "authority_level": source["authority_level"]})

    verification_fee = 2.0 if selected_plan.mode in ("verified", "join_verified") else 0.0
    conflict_fee = min(3.0, 0.75 * len(conflicts))
    sensitive_fee = 0.0
    for ds in datasets:
        for col in _columns_for_dataset(ds, query):
            if CATALOGUE[ds]["columns"].get(col, {}).get("pii"):
                sensitive_fee += 2.0
    row_tier_fee = 0.25 if selected_plan.estimated_rows_returned > 10 else 0.0
    bulk_history_fee = 0.0
    if "fx_history" in datasets:
        # Historical/bulk data is priced by estimated returned rows, separate from live single-point lookup pricing.
        bulk_history_fee = round(min(12.0, max(0.0, selected_plan.estimated_rows_returned * 0.003)), 2)
    live_api_fee = 0.0
    if any(src == "fx_live_api" for src in selected_plan.sources):
        live_api_fee = 1.25 if selected_plan.api_calls else 0.50
    base_fee = 1.0
    total = base_fee + column_price + source_premium + verification_fee + conflict_fee + sensitive_fee + row_tier_fee + bulk_history_fee + live_api_fee
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
        "bulk_history_fee": bulk_history_fee,
        "live_api_or_cache_fee": live_api_fee,
        "column_components": column_components,
        "source_breakdown": source_breakdown,
        "internal_execution_cost_estimate": round(selected_plan.estimated_execution_cost, 4),
        "pricing_note": "User price is query/data-value pricing; internal execution cost is kept separately for optimisation and reporting. Live FX lookups and bulk FX history are priced differently.",
        "arbitrage_note": "Column price is capped by published view price when a view determines the requested query output.",
    }

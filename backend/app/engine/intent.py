from __future__ import annotations

from typing import Any, Dict, List

from ..catalogue import CATALOGUE
from ..models import CandidatePlan, ParsedQuery

INTENT_LABELS = {
    "verified": "Verified multi-source answer",
    "live_point": "Current single-value lookup",
    "daily_point": "Daily reference lookup",
    "historical_bulk": "Historical or bulk data request",
    "analytical_slice": "Filtered analytical query",
    "record_lookup": "Controlled record lookup",
    "exploratory": "General catalogue query",
}

STRATEGY_LABELS = {
    "cheapest": "Cost-effective",
    "balanced": "Balanced",
    "trust_first": "High-trust / premium",
    "privacy_first": "Privacy-first",
}

ROLE_LABELS = {
    "archive_bulk": "CSV archive / data lake",
    "daily_reference": "Daily reference database",
    "current_market": "Current market API",
    "standard_live": "Standard live API",
    "premium_live": "Premium trading feed",
    "controlled_warehouse": "Controlled warehouse database",
    "analytics_api": "Analytics API",
    "reference_master": "Reference master database",
}


def selected_columns(dataset_name: str, query: ParsedQuery) -> List[str]:
    dataset = CATALOGUE[dataset_name]
    if query.select == ["*"]:
        return list(dataset["columns"].keys())
    cols = [c for c in query.select if c in dataset["columns"]]
    return cols or [dataset["entity_key"]]


def classify_query(query: ParsedQuery, verification: bool = False) -> str:
    if verification or query.verification_hint:
        return "verified"
    dataset = CATALOGUE.get(query.dataset)
    if not dataset:
        return "exploratory"
    cols = selected_columns(query.dataset, query)
    entity_key = dataset["entity_key"]
    has_date_signal = query.order_by in {"date", "last_updated", "freshness_days"} or any(c in {"date", "last_updated", "freshness_days"} for c in cols)
    is_history_dataset = "history" in query.dataset or dataset.get("source_category") == "history"
    is_large = bool(query.limit and query.limit >= 100)
    if is_history_dataset or (has_date_signal and is_large) or (query.limit and query.limit >= 500):
        return "historical_bulk"
    if query.where and query.where.op == "=" and query.where.left == entity_key:
        if query.dataset == "fx_rates":
            return "live_point"
        if query.dataset == "fruits":
            return "live_point"
        return "record_lookup"
    if query.where or (query.limit and query.limit > 1):
        return "analytical_slice"
    return "exploratory"


def _source_role(source: Dict[str, Any]) -> str:
    return str(source.get("source_role") or "")


def _role_score(intent: str, role: str, strategy: str) -> float:
    matrix = {
        "live_point": {
            "archive_bulk": 18,
            "daily_reference": 72,
            "current_market": 88,
            "standard_live": 92,
            "premium_live": 98,
            "controlled_warehouse": 70,
            "analytics_api": 72,
            "reference_master": 68,
        },
        "historical_bulk": {
            "archive_bulk": 98,
            "daily_reference": 82,
            "current_market": 30,
            "standard_live": 26,
            "premium_live": 24,
            "controlled_warehouse": 84,
            "analytics_api": 55,
            "reference_master": 80,
        },
        "analytical_slice": {
            "archive_bulk": 74,
            "daily_reference": 86,
            "current_market": 78,
            "standard_live": 72,
            "premium_live": 76,
            "controlled_warehouse": 90,
            "analytics_api": 78,
            "reference_master": 84,
        },
        "record_lookup": {
            "archive_bulk": 40,
            "daily_reference": 76,
            "current_market": 66,
            "standard_live": 62,
            "premium_live": 70,
            "controlled_warehouse": 96,
            "analytics_api": 74,
            "reference_master": 95,
        },
        "exploratory": {
            "archive_bulk": 78,
            "daily_reference": 82,
            "current_market": 72,
            "standard_live": 70,
            "premium_live": 68,
            "controlled_warehouse": 86,
            "analytics_api": 72,
            "reference_master": 84,
        },
    }
    score = matrix.get(intent, matrix["exploratory"]).get(role, 50)
    if intent == "historical_bulk" and strategy in {"cheapest", "balanced"}:
        if role == "archive_bulk":
            score += 34
        if role in {"standard_live", "premium_live", "current_market", "analytics_api"}:
            score -= 18
    if strategy == "cheapest" and role in {"archive_bulk", "daily_reference", "standard_live"}:
        score += 8
    if strategy == "cheapest" and role in {"premium_live", "current_market"}:
        score -= 12
    if strategy == "balanced" and role in {"standard_live", "daily_reference", "controlled_warehouse", "archive_bulk"}:
        score += 4
    if strategy == "trust_first" and role in {"premium_live", "current_market", "daily_reference", "controlled_warehouse", "reference_master"}:
        score += 14
    if strategy == "privacy_first" and role in {"controlled_warehouse", "daily_reference", "reference_master", "archive_bulk"}:
        score += 14
    if strategy == "privacy_first" and role in {"standard_live", "premium_live", "current_market", "analytics_api"}:
        score -= 12
    return score


def source_score(query: ParsedQuery, source_name: str, estimate: Any, strategy: str, verification: bool = False) -> float:
    intent = classify_query(query, verification)
    source = CATALOGUE[estimate.dataset]["sources"][source_name]
    role = _source_role(source)
    access_cost = float(source.get("access_cost", 1.0))
    latency = float(estimate.estimated_latency_ms or source.get("latency_ms", 0))
    trust = float(getattr(estimate, "trust_score", source.get("base_trust", 0.5)))
    freshness = float(getattr(estimate, "freshness_score", 0.5))
    conflict_risk = float(source.get("conflict_risk", getattr(estimate, "conflict_risk", 0.5)))
    base = _role_score(intent, role, strategy)
    if intent == "historical_bulk" and role == "archive_bulk" and strategy in {"cheapest", "balanced"}:
        return base + 60 + trust * 10 + freshness * 3 - access_cost * 10 - latency * 0.002 - conflict_risk * 5
    if strategy == "cheapest":
        return base + trust * 10 + freshness * 3 - access_cost * 14 - latency * 0.025 - conflict_risk * 7
    if strategy == "trust_first":
        return base + trust * 28 + freshness * 8 - access_cost * 3 - latency * 0.006 - conflict_risk * 6
    if strategy == "privacy_first":
        external_penalty = 14 if source.get("type") == "api" else 0
        return base + trust * 16 + freshness * 4 - access_cost * 6 - latency * 0.012 - conflict_risk * 12 - external_penalty
    return base + trust * 18 + freshness * 8 - access_cost * 7 - latency * 0.012 - conflict_risk * 8


def intent_text(intent: str) -> str:
    return INTENT_LABELS.get(intent, "General query")


def strategy_text(strategy: str) -> str:
    return STRATEGY_LABELS.get(strategy, strategy.replace("_", " ").title())


def source_display_name(dataset_name: str, source_name: str) -> str:
    source = CATALOGUE[dataset_name]["sources"].get(source_name, {})
    return str(source.get("display_name") or source_name.replace("_", " ").title())


def source_role_text(dataset_name: str, source_name: str) -> str:
    source = CATALOGUE[dataset_name]["sources"].get(source_name, {})
    return ROLE_LABELS.get(str(source.get("source_role") or ""), str(source.get("type") or "Source"))


def source_selection_reason(query: ParsedQuery, source_name: str, strategy: str, verification: bool = False) -> str:
    intent = classify_query(query, verification)
    source = CATALOGUE[query.dataset]["sources"].get(source_name, {})
    role = str(source.get("source_role") or "")
    label = source_display_name(query.dataset, source_name)
    preference = strategy_text(strategy)
    if verification:
        return "Verified mode checks every compatible provider, compares values and resolves the final answer using trust, authority and freshness."
    if intent == "live_point" and role == "premium_live":
        return f"{label} is selected because this is a current single-value lookup and the user preference is {preference}. The premium feed has the strongest freshness and trust tier."
    if intent == "live_point" and role in {"standard_live", "current_market"}:
        return f"{label} is selected because this is a current single-value lookup. It gives a fresher answer than archive data without using the most expensive premium tier."
    if intent == "live_point" and role == "daily_reference":
        return f"{label} is selected because this is a current point lookup but the user preference is cost-effective or controlled access. It is slightly older than live API data but cheaper and governed."
    if intent == "historical_bulk" and role == "archive_bulk":
        return f"{label} is selected because this is a historical or bulk request. The CSV/data-lake archive is cheaper for many rows than repeatedly asking live APIs."
    if intent == "historical_bulk" and role in {"daily_reference", "controlled_warehouse", "reference_master"}:
        return f"{label} is selected because this is historical data with a higher-trust requirement. It costs more than archive access but gives cleaner reference data."
    if role == "controlled_warehouse":
        return f"{label} is selected because this dataset is controlled business data and the warehouse is the strongest governed source."
    if role == "analytics_api":
        return f"{label} is selected because the query benefits from an analytics provider and the selected strategy accepts external API access."
    if role == "archive_bulk":
        return f"{label} is selected because the query is suitable for low-cost archive access."
    return f"{label} is selected as the best match for the query intent and the {preference} preference."


def build_recommendation(query: ParsedQuery, selected_plan: CandidatePlan, rows: List[Dict[str, Any]], pricing: Dict[str, Any], metrics: List[Dict[str, Any]], conflicts: List[Dict[str, Any]], policy: Dict[str, Any], strategy: str, verification: bool) -> Dict[str, Any]:
    intent = classify_query(query, verification)
    visible_cols = [c for c in selected_columns(query.dataset, query) if not c.startswith("_")]
    first = rows[0] if rows else {}
    answer = "No rows matched this query."
    if rows:
        if len(rows) == 1 and visible_cols:
            key = CATALOGUE[query.dataset]["entity_key"]
            key_value = first.get(key)
            value_cols = [c for c in visible_cols if c != key]
            if value_cols:
                pairs = ", ".join(f"{c}: {first.get(c)}" for c in value_cols)
                answer = f"{key_value}: {pairs}" if key_value is not None else pairs
            else:
                answer = f"{key}: {key_value}"
        else:
            answer = f"Showing {len(rows)} rows for this {intent_text(intent).lower()}."
    selected_sources = selected_plan.sources or []
    primary_source = selected_sources[0] if selected_sources else ""
    source_labels = [source_display_name(ds, s) for ds in selected_plan.datasets for s in selected_sources if s in CATALOGUE[ds]["sources"]]
    source_roles = [source_role_text(ds, s) for ds in selected_plan.datasets for s in selected_sources if s in CATALOGUE[ds]["sources"]]
    actual_rows_scanned = sum(int(m.get("rows_scanned", 0) or 0) for m in metrics)
    api_calls = sum(int(m.get("api_calls", 0) or 0) for m in metrics)
    alternatives = []
    if not verification and query.dataset in CATALOGUE:
        for source_name, source in CATALOGUE[query.dataset]["sources"].items():
            if source_name == primary_source:
                continue
            alternatives.append({
                "source": source_display_name(query.dataset, source_name),
                "role": source_role_text(query.dataset, source_name),
                "trade_off": str(source.get("trade_off") or source.get("description") or "Available alternative source"),
            })
    return {
        "headline": "Answer ready" if rows else "No matching data",
        "answer": answer,
        "query_intent": intent,
        "query_intent_label": intent_text(intent),
        "user_preference": strategy_text(strategy),
        "recommended_source": ", ".join(dict.fromkeys(source_labels)) if source_labels else "None",
        "recommended_source_role": ", ".join(dict.fromkeys(source_roles)) if source_roles else "None",
        "why_this_source": selected_plan.selection_reason or (source_selection_reason(query, primary_source, strategy, verification) if primary_source else "No source selected."),
        "sources_checked": len(dict.fromkeys(selected_sources)),
        "actual_rows_scanned": actual_rows_scanned,
        "api_calls": api_calls,
        "user_price": pricing.get("total_user_price"),
        "currency": pricing.get("currency", "credits"),
        "policy_summary": policy.get("reason", ""),
        "conflict_summary": f"{len(conflicts)} source variation(s) found." if conflicts else "No visible source conflict details.",
        "alternatives": alternatives[:4],
    }

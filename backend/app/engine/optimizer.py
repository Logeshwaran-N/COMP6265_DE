from __future__ import annotations

import itertools
from typing import Dict, List, Optional
from ..catalogue import CATALOGUE
from ..models import CandidatePlan, ParsedQuery, SourcePlanEstimate
from .estimator import estimate_join_rows, estimate_source


def _selected_columns(dataset_name: str, query: ParsedQuery) -> List[str]:
    dataset = CATALOGUE[dataset_name]
    if query.select == ["*"]:
        return list(dataset["columns"].keys())
    return [c for c in query.select if c in dataset["columns"]]


def _can_source_answer(dataset_name: str, source_name: str, columns: List[str]) -> bool:
    mapping = CATALOGUE[dataset_name]["sources"][source_name]["mapping"]
    return all(col in mapping for col in columns)


def _source_type_rank(source_type: str) -> int:
    return {"csv": 1, "sqlite": 2, "api": 3}.get(source_type, 9)


def _preferred_single_source_sort_key(strategy: str, plan: CandidatePlan) -> tuple:
    if not plan.source_estimates:
        return (99, plan.optimiser_score)
    estimate = plan.source_estimates[0]
    source = CATALOGUE[estimate.dataset]["sources"][estimate.source_name]
    source_type = source.get("type", "")
    access_cost = float(source.get("access_cost", 1.0))
    risk = float(source.get("conflict_risk", estimate.conflict_risk))

    if strategy == "cheapest":
        return (access_cost, _source_type_rank(source_type), estimate.estimated_execution_cost)
    if strategy == "trust_first":
        trust_rank = {"api": 1, "sqlite": 2, "csv": 3}.get(source_type, 9)
        return (trust_rank, -estimate.trust_score, -estimate.freshness_score, risk, estimate.estimated_execution_cost)
    if strategy == "privacy_first":
        privacy_rank = {"sqlite": 1, "csv": 2, "api": 3}.get(source_type, 9)
        return (privacy_rank, risk, -estimate.trust_score, estimate.estimated_execution_cost)
    # Balanced: prefer structured reference data where available, then use the general optimiser score.
    balanced_rank = {"sqlite": 1, "api": 2, "csv": 3}.get(source_type, 9)
    return (balanced_rank, plan.optimiser_score, estimate.estimated_execution_cost)


def _source_label(source_type: str) -> str:
    return {"csv": "CSV/file", "sqlite": "SQLite DB", "api": "mock API"}.get(source_type, "source")


def _single_source_explanation(strategy: str, source_name: str) -> str:
    source_type = next((src.get("type", "source") for ds in CATALOGUE.values() for name, src in ds["sources"].items() if name == source_name), "source")
    label = _source_label(source_type)
    if strategy == "cheapest":
        if source_type == "csv":
            return f"Use only {source_name}. Cheapest strategy chooses the low access-price {label} source. It may scan more rows, but its data-access tier is cheapest."
        return f"Use only {source_name}. Cheapest strategy selected the lowest available access-price source for this query."
    if strategy == "trust_first":
        return f"Use only {source_name}. Trust-first strategy prioritises source trust and freshness over price or latency."
    if strategy == "privacy_first":
        return f"Use only {source_name}. Privacy-first strategy favours controlled sources and avoids unnecessary external API exposure."
    return f"Use only {source_name}. Balanced strategy chooses the best trade-off between execution cost, trust, freshness and risk."


def _score(strategy: str, estimates: List[SourcePlanEstimate], verified: bool, join: bool = False) -> float:
    cost = sum(e.estimated_execution_cost for e in estimates)
    latency = max((e.estimated_latency_ms for e in estimates), default=0.0) if verified else sum(e.estimated_latency_ms for e in estimates)
    trust = sum(e.trust_score for e in estimates) / max(len(estimates), 1)
    fresh = sum(e.freshness_score for e in estimates) / max(len(estimates), 1)
    risk = sum(e.conflict_risk for e in estimates) / max(len(estimates), 1)
    api_calls = sum(e.api_calls for e in estimates)
    verification_penalty = 0.65 if verified else 0.0
    join_penalty = 0.45 if join else 0.0
    if strategy == "cheapest":
        return (cost * 1.6) + (latency * 0.005) + (api_calls * 0.2) + (risk * 0.4) - (trust * 0.35)
    if strategy == "trust_first":
        return (cost * 0.65) + (latency * 0.003) + (risk * 1.15) - (trust * 3.0) - (fresh * 0.8) + verification_penalty + join_penalty
    if strategy == "privacy_first":
        # Avoid high conflict and high source count unless asked; useful for minimisation.
        return (cost * 1.0) + (latency * 0.004) + (risk * 2.0) + (len(estimates) * 0.30) - (trust * 1.2) + join_penalty
    # balanced
    return (cost * 1.0) + (latency * 0.004) + (api_calls * 0.25) + (risk * 0.9) - (trust * 1.5) - (fresh * 0.4) + verification_penalty + join_penalty


def _make_plan(
    plan_id: str,
    mode: str,
    strategy: str,
    datasets: List[str],
    estimates: List[SourcePlanEstimate],
    explanation: str,
    complexity: str,
    warnings: Optional[List[str]] = None,
) -> CandidatePlan:
    scanned = sum(e.estimated_rows_scanned for e in estimates)
    returned = max((e.estimated_rows_returned for e in estimates), default=0)
    if mode in ("verified", "join_verified"):
        latency = max((e.estimated_latency_ms for e in estimates), default=0.0)
    else:
        latency = sum(e.estimated_latency_ms for e in estimates)
    cost = sum(e.estimated_execution_cost for e in estimates)
    api_calls = sum(e.api_calls for e in estimates)
    trust = sum(e.trust_score for e in estimates) / max(len(estimates), 1)
    fresh = sum(e.freshness_score for e in estimates) / max(len(estimates), 1)
    risk = sum(e.conflict_risk for e in estimates) / max(len(estimates), 1)
    score = _score(strategy, estimates, mode in ("verified", "join_verified"), "join" in mode)
    return CandidatePlan(
        plan_id=plan_id,
        mode=mode,
        strategy=strategy,
        datasets=datasets,
        sources=[e.source_name for e in estimates],
        source_estimates=estimates,
        estimated_rows_scanned=scanned,
        estimated_rows_returned=returned,
        estimated_latency_ms=latency,
        estimated_execution_cost=cost,
        api_calls=api_calls,
        mean_trust=trust,
        mean_freshness=fresh,
        conflict_risk=risk,
        optimiser_score=score,
        complexity_class=complexity,
        explanation=explanation,
        warnings=warnings or [],
    )


def build_candidate_plans(query: ParsedQuery, strategy: str, verification: bool) -> List[CandidatePlan]:
    if query.dataset not in CATALOGUE:
        raise ValueError(f"Unknown dataset: {query.dataset}")
    verification = verification or query.verification_hint
    if query.join_dataset:
        return _build_join_plans(query, strategy, verification)
    return _build_single_dataset_plans(query, strategy, verification)


def _build_single_dataset_plans(query: ParsedQuery, strategy: str, verification: bool) -> List[CandidatePlan]:
    dataset_name = query.dataset
    selected = _selected_columns(dataset_name, query)
    if not selected:
        selected = [CATALOGUE[dataset_name]["entity_key"]]
    sources = [name for name in CATALOGUE[dataset_name]["sources"] if _can_source_answer(dataset_name, name, selected)]
    candidates: List[CandidatePlan] = []
    for source_name in sources:
        estimate = estimate_source(dataset_name, source_name, query, selected)
        candidates.append(_make_plan(
            plan_id=f"single::{source_name}",
            mode="single_source",
            strategy=strategy,
            datasets=[dataset_name],
            estimates=[estimate],
            explanation=_single_source_explanation(strategy, source_name),
            complexity="Candidate enumeration O(S); execution O(rows_scanned) for selected source.",
        ))
    if verification and len(sources) > 1:
        estimates = [estimate_source(dataset_name, src, query, selected) for src in sources]
        candidates.append(_make_plan(
            plan_id="verified::" + "+".join(sources),
            mode="verified",
            strategy=strategy,
            datasets=[dataset_name],
            estimates=estimates,
            explanation=(
                "Verified mode queries all compatible sources, compares returned values and resolves conflicts by source trust."
            ),
            complexity="Verification O(S*rows + K*V), where S=sources, K=entity keys, V=values per key.",
        ))
    if verification:
        return sorted(candidates, key=lambda p: (p.mode != "verified", p.optimiser_score))
    return sorted(candidates, key=lambda p: _preferred_single_source_sort_key(strategy, p))


def _build_join_plans(query: ParsedQuery, strategy: str, verification: bool) -> List[CandidatePlan]:
    left_ds = query.dataset
    right_ds = query.join_dataset
    if right_ds not in CATALOGUE:
        raise ValueError(f"Unknown joined dataset: {right_ds}")
    left_cols = _selected_columns(left_ds, query) or [query.join_left or CATALOGUE[left_ds]["entity_key"]]
    right_cols = _selected_columns(right_ds, query) or [query.join_right or CATALOGUE[right_ds]["entity_key"]]
    if query.join_left and query.join_left not in left_cols:
        left_cols.append(query.join_left)
    if query.join_right and query.join_right not in right_cols:
        right_cols.append(query.join_right)
    left_sources = [s for s in CATALOGUE[left_ds]["sources"] if _can_source_answer(left_ds, s, left_cols)]
    right_sources = [s for s in CATALOGUE[right_ds]["sources"] if _can_source_answer(right_ds, s, right_cols)]
    plans: List[CandidatePlan] = []
    for left_src, right_src in itertools.product(left_sources, right_sources):
        le = estimate_source(left_ds, left_src, query, left_cols)
        re = estimate_source(right_ds, right_src, query, right_cols)
        left_distinct = CATALOGUE[left_ds]["columns"].get(query.join_left or "", {}).get("distinct", 10)
        right_distinct = CATALOGUE[right_ds]["columns"].get(query.join_right or "", {}).get("distinct", 10)
        joined_rows = estimate_join_rows(le.estimated_rows_returned, re.estimated_rows_returned, int(left_distinct), int(right_distinct))
        # Adjust returned rows for the combined plan.
        le2 = le
        re2 = re
        plan = _make_plan(
            plan_id=f"join::{left_src}+{right_src}",
            mode="join_left_deep",
            strategy=strategy,
            datasets=[left_ds, right_ds],
            estimates=[le2, re2],
            explanation=(
                f"Left-deep join plan. Estimated joined rows={joined_rows}. "
                "The optimiser compares source pairs using cardinality, source cost, and trust."
            ),
            complexity="Join candidate enumeration O(S1*S2); execution O(R+S+J) after predicate pushdown.",
        )
        plan.estimated_rows_returned = joined_rows
        plans.append(plan)
    if verification:
        estimates = [estimate_source(left_ds, s, query, left_cols) for s in left_sources] + [estimate_source(right_ds, s, query, right_cols) for s in right_sources]
        plans.append(_make_plan(
            plan_id="join_verified::" + "+".join(left_sources + right_sources),
            mode="join_verified",
            strategy=strategy,
            datasets=[left_ds, right_ds],
            estimates=estimates,
            explanation="Verify all compatible sources on both sides before joining. Highest confidence, highest cost.",
            complexity="O((S1+S2)*rows + join), with conflict resolution before join.",
        ))
    return sorted(plans, key=lambda p: (p.mode != "join_verified" if verification else False, p.optimiser_score))


def choose_plan(query: ParsedQuery, strategy: str, verification: bool) -> tuple[CandidatePlan, List[CandidatePlan]]:
    plans = build_candidate_plans(query, strategy, verification)
    if not plans:
        raise ValueError("No source can answer the requested columns.")
    if verification or query.verification_hint:
        verified = [p for p in plans if p.mode in ("verified", "join_verified")]
        if verified:
            return verified[0], plans
    return plans[0], plans

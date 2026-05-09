from __future__ import annotations

import time
from math import exp
from typing import Any, Dict, List, Optional

from ..config import settings
from ..catalogue import PROVIDER_ENDORSEMENTS, list_sources


def pagerank(
    graph: Dict[str, List[str]],
    damping: float = settings.pagerank_damping,
    iterations: int = settings.pagerank_iterations,
    tolerance: float = settings.pagerank_tolerance,
) -> Dict[str, float]:
    nodes = sorted(set(graph.keys()) | {dst for out in graph.values() for dst in out})
    n = len(nodes)
    if n == 0:
        return {}
    rank = {node: 1.0 / n for node in nodes}
    for _ in range(iterations):
        new_rank = {node: (1 - damping) / n for node in nodes}
        dangling_sum = sum(rank[node] for node in nodes if not graph.get(node))
        for node in nodes:
            new_rank[node] += damping * dangling_sum / n
        for src, outs in graph.items():
            if outs:
                share = damping * rank[src] / len(outs)
                for dst in outs:
                    new_rank[dst] += share
        delta = sum(abs(new_rank[node] - rank[node]) for node in nodes)
        rank = new_rank
        if delta < tolerance:
            break
    max_rank = max(rank.values()) if rank else 1.0
    return {node: (val / max_rank if max_rank else 0.0) for node, val in rank.items()}


def freshness_score(days: float) -> float:
    # Smooth decay: same-day ~= 1, 7 days ~= .5, stale weeks ~= low.
    return round(exp(-max(days, 0) / 10.0), 4)


def compute_source_trust() -> Dict[str, Dict[str, Any]]:
    pr = pagerank(PROVIDER_ENDORSEMENTS)
    out: Dict[str, Dict[str, Any]] = {}
    for src in list_sources():
        provider = src["provider"]
        pr_score = pr.get(provider, 0.0)
        fresh = freshness_score(src.get("freshness_days", 30))
        base = float(src.get("base_trust", 0.5))
        authority = float(src.get("authority_level", 0.5))
        # Base trust is largest because it is source-specific. PageRank adds ecosystem reputation.
        computed = (0.42 * base) + (0.28 * authority) + (0.18 * pr_score) + (0.12 * fresh)
        out[src["source_name"]] = {
            "source_name": src["source_name"],
            "dataset": src["dataset"],
            "provider": provider,
            "source_type": src["type"],
            "base_trust": round(base, 4),
            "authority_level": round(authority, 4),
            "pagerank_reputation": round(pr_score, 4),
            "freshness_score": round(fresh, 4),
            "computed_trust": round(min(1.0, max(0.0, computed)), 4),
            "freshness_days": src.get("freshness_days", 0),
            "conflict_risk": src.get("conflict_risk", 0.5),
            "explanation": "computed_trust = 0.42*base + 0.28*authority + 0.18*provider_PageRank + 0.12*freshness",
        }
    return out


class TrustCache:
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._value: Optional[Dict[str, Dict[str, Any]]] = None
        self._computed_at: Optional[float] = None  # monotonic seconds

    def get(self) -> Dict[str, Dict[str, Any]]:
        now = time.monotonic()
        if self._value is None or self._computed_at is None or (now - self._computed_at) > self.ttl_seconds:
            self._value = compute_source_trust()
            self._computed_at = now
        return self._value

    def invalidate(self) -> None:
        self._value = None
        self._computed_at = None

    def age_seconds(self) -> Optional[float]:
        if self._computed_at is None:
            return None
        return max(0.0, time.monotonic() - self._computed_at)


trust_cache = TrustCache(ttl_seconds=settings.trust_cache_ttl_seconds)


def trust_for_source(source_name: str) -> float:
    return trust_cache.get().get(source_name, {}).get("computed_trust", 0.0)

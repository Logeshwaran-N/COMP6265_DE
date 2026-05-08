from __future__ import annotations

from collections import defaultdict
from statistics import pstdev
from typing import Any, Dict, List, Tuple
from ..catalogue import CATALOGUE
from .trust import compute_source_trust


def _normalise_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value).strip().lower()


def _source_score(source_name: str) -> float:
    t = compute_source_trust().get(source_name, {})
    return (0.75 * t.get("computed_trust", 0)) + (0.25 * t.get("authority_level", 0))


def resolve_conflicts(dataset_name: str, rows: List[Dict[str, Any]], selected_cols: List[str], show_all: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not rows:
        return [], []
    entity_key = CATALOGUE[dataset_name]["entity_key"]
    groups: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row.get(entity_key)].append(row)

    resolved_rows: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    output_cols = [c for c in selected_cols if c != "*"] or [c for c in CATALOGUE[dataset_name]["columns"]]
    if entity_key not in output_cols:
        output_cols = [entity_key] + output_cols

    for key, candidates in groups.items():
        best = max(candidates, key=lambda r: _source_score(r.get("_source", "")))
        out = {col: best.get(col) for col in output_cols if col in best}
        out["_chosen_source"] = best.get("_source")
        out["_chosen_provider"] = best.get("_provider")
        out["_confidence"] = round(_source_score(best.get("_source", "")), 4)
        out["_source_count_checked"] = len(candidates)
        resolved_rows.append(out)

        for col in output_cols:
            if col == entity_key:
                continue
            values = defaultdict(list)
            for c in candidates:
                if col in c:
                    values[_normalise_value(c.get(col))].append(c)
            if len(values) > 1:
                numeric_vals = []
                for c in candidates:
                    try:
                        numeric_vals.append(float(c.get(col)))
                    except Exception:
                        pass
                conflicts.append({
                    "entity_key": entity_key,
                    "entity_value": key,
                    "column": col,
                    "chosen_value": best.get(col),
                    "chosen_source": best.get("_source"),
                    "reason": "highest combined trust and authority score",
                    "numeric_stddev": round(pstdev(numeric_vals), 4) if len(numeric_vals) > 1 else None,
                    "alternatives": [
                        {
                            "source": c.get("_source"),
                            "provider": c.get("_provider"),
                            "value": c.get(col),
                            "source_score": round(_source_score(c.get("_source", "")), 4),
                        }
                        for c in candidates
                    ] if show_all else [],
                })
    return resolved_rows, conflicts

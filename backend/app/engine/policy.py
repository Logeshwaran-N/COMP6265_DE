from __future__ import annotations

from typing import Any, Dict, List
from ..catalogue import CATALOGUE
from ..models import ParsedQuery


def _requested_columns(dataset_name: str, select: List[str]) -> List[str]:
    dataset = CATALOGUE[dataset_name]
    if select == ["*"]:
        return list(dataset["columns"].keys())
    return select


def evaluate_policy(query: ParsedQuery, role: str, purpose: str, verification: bool) -> Dict[str, Any]:
    if query.dataset not in CATALOGUE:
        return {"allowed": False, "reason": f"Unknown dataset '{query.dataset}'.", "duties": [], "blocked_columns": []}
    datasets = [query.dataset] + ([query.join_dataset] if query.join_dataset else [])
    all_requested: Dict[str, List[str]] = {}
    blocked: List[str] = []
    duties: List[str] = []
    reasons: List[str] = []

    for dataset_name in datasets:
        if not dataset_name:
            continue
        if dataset_name not in CATALOGUE:
            return {"allowed": False, "reason": f"Unknown joined dataset '{dataset_name}'.", "duties": [], "blocked_columns": []}
        dataset = CATALOGUE[dataset_name]
        requested = _requested_columns(dataset_name, query.select)
        # In a join, selected cols can belong to either side. Ignore columns not in this dataset for that dataset check.
        requested = [c for c in requested if c in dataset["columns"]]
        if not requested and query.select != ["*"]:
            requested = []
        all_requested[dataset_name] = requested
        policy = dataset["policy"]
        duties.extend(policy.get("duties", []))

        permission_ok = False
        action = "verify" if verification else "read"
        for permission in policy.get("permissions", []):
            if role in permission.get("roles", []) and purpose in permission.get("purposes", []) and action in permission.get("actions", ["read"]):
                permission_ok = True
            if action == "verify" and role in permission.get("roles", []) and purpose in permission.get("purposes", []) and "read" in permission.get("actions", []):
                # read permission can still run verified mode unless specifically prohibited.
                permission_ok = True
        if not permission_ok:
            reasons.append(f"No permission for role={role}, purpose={purpose}, action={action} on {dataset_name}.")

        for prohibition in policy.get("prohibitions", []):
            if role in prohibition.get("roles", []):
                if "purposes" in prohibition and purpose not in prohibition["purposes"]:
                    continue
                prohibited_cols = prohibition.get("columns", [])
                if not prohibited_cols or any(c in requested for c in prohibited_cols):
                    blocked.extend([f"{dataset_name}.{c}" for c in prohibited_cols if not requested or c in requested])
                    reasons.append(prohibition.get("reason", f"Policy prohibition matched for {dataset_name}."))

        for col in requested:
            meta = dataset["columns"].get(col)
            if meta and meta.get("pii") and not (role == "admin" and purpose == "internal_audit"):
                blocked.append(f"{dataset_name}.{col}")
                reasons.append(f"Column {dataset_name}.{col} is marked as PII and requires admin/internal_audit.")

        max_rows = policy.get("max_rows_by_role", {}).get(role, 0)
        if max_rows <= 0:
            reasons.append(f"Role {role} has max_rows=0 for {dataset_name}.")

    allowed = not reasons and not blocked
    return {
        "allowed": allowed,
        "reason": "Allowed by machine-readable policy constraints." if allowed else " ".join(dict.fromkeys(reasons)),
        "blocked_columns": sorted(set(blocked)),
        "duties": sorted(set(duties)),
        "requested_columns_by_dataset": all_requested,
        "role": role,
        "purpose": purpose,
        "verification": verification,
    }

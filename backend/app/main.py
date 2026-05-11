from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .audit import read_audit, write_audit
from .auth import auth_required, get_current_user, login as auth_login, complete_new_password, change_local_password, forgot_password, confirm_forgot_password, list_users, create_user, delete_user, reset_user_password, require_admin_user, auth_provider
from .catalogue import get_catalogue, list_sources
from .errors import InvalidQueryError, QueryError
from .engine.executor import execute_plan
from .engine.optimizer import choose_plan
from .engine.policy import evaluate_policy
from .logging_config import configure_logging
from .models import QueryRequest, QueryResponse, LoginRequest, NewPasswordRequest, PasswordChangeRequest, ForgotPasswordRequest, ConfirmForgotPasswordRequest, AdminCreateUserRequest
from .parser import parse_query
from .seed import ensure_seed_data

configure_logging()
ensure_seed_data()

app = FastAPI(title="Trust-Aware Federated Data Economy Platform", version="2.2.0")

_frontend_origins_raw = os.getenv("FRONTEND_ORIGINS") or os.getenv("DATA_ECONOMY_FRONTEND_ORIGINS") or "*"
_frontend_origins = [o.strip().rstrip("/") for o in _frontend_origins_raw.split(",") if o.strip()]
_allow_all_origins = _frontend_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all_origins else _frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "data-economy-backend", "version": "2.2.0", "auth_provider": auth_provider()}


@app.get("/api/auth/me")
def auth_me(user=Depends(get_current_user)):
    return {"ok": True, "auth_required": auth_required(), "user": user}


@app.post("/api/auth/login")
def auth_login_endpoint(req: LoginRequest):
    return auth_login(req.email, req.password)


@app.post("/api/auth/new-password")
def auth_new_password_endpoint(req: NewPasswordRequest):
    return complete_new_password(req.email, req.session, req.new_password)




@app.post("/api/auth/forgot-password")
def auth_forgot_password_endpoint(req: ForgotPasswordRequest):
    return forgot_password(req.email)


@app.post("/api/auth/confirm-forgot-password")
def auth_confirm_forgot_password_endpoint(req: ConfirmForgotPasswordRequest):
    return confirm_forgot_password(req.email, req.confirmation_code, req.new_password)

@app.post("/api/auth/change-password")
def auth_change_password_endpoint(req: PasswordChangeRequest, user=Depends(get_current_user)):
    if auth_provider() != "local":
        return {"ok": False, "message": "Use Cognito hosted password reset/change flow for Cognito accounts."}
    return change_local_password(user, req.current_password, req.new_password)


@app.get("/api/admin/users")
def admin_users(search: str = Query(default=""), user=Depends(get_current_user)):
    require_admin_user(user)
    return {"users": list_users(search)}


@app.post("/api/admin/users")
def admin_create_user(req: AdminCreateUserRequest, user=Depends(get_current_user)):
    require_admin_user(user)
    created = create_user(req.email, req.temp_password, req.role.value if hasattr(req.role, "value") else str(req.role), req.name)
    return {"ok": True, "user": created}




@app.post("/api/admin/users/{email}/reset-password")
def admin_reset_password(email: str, user=Depends(get_current_user)):
    require_admin_user(user)
    if email.strip().lower() == str(user.get("email", "")).strip().lower():
        return reset_user_password(email)
    return reset_user_password(email)

@app.delete("/api/admin/users/{email}")
def admin_delete_user(email: str, user=Depends(get_current_user)):
    require_admin_user(user)
    return delete_user(email, user.get("email"))


@app.get("/api/catalogue")
def catalogue(user=Depends(get_current_user)):
    data = get_catalogue()
    from .engine.trust import trust_cache

    trust = trust_cache.get()
    for dataset in data.values():
        for source_name, src in dataset["sources"].items():
            src["trust"] = trust.get(source_name, {})
    return data


@app.get("/api/sources")
def sources(user=Depends(get_current_user)):
    from .engine.trust import trust_cache

    trust = trust_cache.get()
    out = []
    for s in list_sources():
        out.append({**s, **trust.get(s["source_name"], {})})
    return out


@app.get("/api/trust")
def trust(user=Depends(get_current_user)):
    from .engine.trust import trust_cache

    return {
        "sources": trust_cache.get(),
        "provider_pagerank_note": "Provider endorsement graph is scored with PageRank. Source trust then combines base trust, authority, PageRank reputation and freshness.",
        "complexity": "PageRank iteration is O(I*(V+E)), where I is iterations, V providers and E endorsements.",
        "cache_age_seconds": trust_cache.age_seconds(),
    }


@app.get("/api/audit")
def audit(limit: int = 50, user=Depends(get_current_user)):
    require_admin_user(user)
    return read_audit(limit)


@app.get("/api/algorithm")
def algorithm(user=Depends(get_current_user)):
    return {
        "name": "Policy-aware, trust-aware, cost-aware federated optimiser",
        "pipeline": [
            "Parse SQL-like query over virtual catalogue",
            "Map virtual columns to physical source schemas",
            "Evaluate ODRL-inspired role/purpose/column constraints",
            "Enumerate source plans and estimate cardinality/cost/latency/trust",
            "Choose one source by strategy, or all sources when verification is requested",
            "Execute with selection pushdown where source supports it",
            "Detect duplicated/conflicting entity values in verified mode",
            "Resolve conflicts using computed trust + authority and return provenance",
            "Calculate user-facing query price with an arbitrage guard",
            "Write audit event as a duty of policy enforcement",
        ],
        "cost_model": {
            "estimated_execution_cost": "access_cost + rows_scanned*row_scan_cost + api_calls*api_call_cost + projection_penalty",
            "strategy_cheapest": "select the lowest access-price source tier, often CSV/file",
            "strategy_balanced": "select the best trade-off source, usually the structured reference DB",
            "strategy_trust_first": "select the highest trust/freshness source, often API",
            "strategy_privacy_first": "select a controlled source and avoid unnecessary external API calls",
        },
        "pricing_model": {
            "separation": "Internal execution cost is for optimiser decisions; user-facing query price is data-value/access pricing.",
            "arbitrage_guard": "If a published view determines the selected columns, the column price is capped by that view price.",
        },
        "complexities": {
            "single_dataset_plans": "O(S), S = compatible sources",
            "verified_execution": "O(S*R + K*V), sources*rows plus conflict groups",
            "join_plan_enumeration": "O(S1*S2) for two-way source-pair enumeration",
            "pagerank": "O(I*(V+E))",
        },
    }


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest, user=Depends(get_current_user)):
    requested_role = req.role.value if hasattr(req.role, "value") else str(req.role)
    effective_role = requested_role if user.get("role") == "admin" else str(user.get("role") or requested_role)
    audit_base = {
        "actor_email": user.get("email"),
        "actor_username": user.get("username"),
        "actor_sub": user.get("sub"),
        "actor_role": user.get("role"),
        "requested_role": requested_role,
        "effective_role": effective_role,
        "raw_query": req.query,
        "purpose": req.purpose,
        "strategy": req.strategy,
        "verification": req.verification,
    }
    try:
        parsed = parse_query(req.query)
        verification = req.verification or parsed.verification_hint
        policy = evaluate_policy(parsed, effective_role, req.purpose, verification)
        if not policy["allowed"]:
            audit_id = write_audit({**audit_base, "allowed": False, "reason": policy["reason"]})
            return QueryResponse(ok=False, message="Policy denied the query.", parsed_query=parsed.to_dict(), policy_decision=policy, audit_id=audit_id)
        selected_plan, candidates = choose_plan(parsed, req.strategy, verification)
        show_provenance = bool(req.show_all_conflicts and verification)
        exec_result = execute_plan(parsed, selected_plan, effective_role, req.purpose, show_provenance)
        visible_conflicts = exec_result["conflicts"] if show_provenance else []
        actual_sources = [m.get("source") for m in exec_result["metrics"] if m.get("source")]
        if verification:
            message = (
                "Query executed in verified mode with source comparison details."
                if show_provenance
                else "Query executed in verified mode. Sources were compared internally; source comparison details are hidden."
            )
        else:
            message = "Query executed in single-source mode. Enable verification to compare available sources."
        audit_id = write_audit({
            **audit_base,
            "allowed": True,
            "selected_plan": selected_plan.to_dict(),
            "price": exec_result["pricing"].get("total_user_price"),
            "conflict_count": len(exec_result["conflicts"]),
            "row_count": len(exec_result["result_rows"]),
            "actual_sources": actual_sources,
            "show_provenance": show_provenance,
        })
        return QueryResponse(
            ok=True,
            message=message,
            parsed_query=parsed.to_dict(),
            policy_decision=policy,
            selected_plan=selected_plan.to_dict(),
            candidate_plans=[p.to_dict() for p in candidates],
            result_rows=exec_result["result_rows"],
            conflicts=visible_conflicts,
            pricing=exec_result["pricing"],
            execution_metrics={
                "actual_source_metrics": exec_result["metrics"],
                "actual_sources": actual_sources,
                "actual_source_count": len(actual_sources),
                "visible_provenance": show_provenance,
                "internal_conflict_count": len(exec_result["conflicts"]),
            },
            audit_id=audit_id,
        )
    except (InvalidQueryError, QueryError, ValueError) as exc:
        audit_id = write_audit({**audit_base, "allowed": False, "error": str(exc)})
        return QueryResponse(ok=False, message=str(exc), audit_id=audit_id)
    except Exception as exc:
        audit_id = write_audit({**audit_base, "allowed": False, "error": str(exc)})
        return QueryResponse(ok=False, message="Internal error while executing query.", audit_id=audit_id)

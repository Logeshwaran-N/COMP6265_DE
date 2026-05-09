from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .audit import read_audit, write_audit
from .auth import auth_required, get_current_user
from .catalogue import get_catalogue, list_sources
from .errors import InvalidQueryError, QueryError
from .engine.executor import execute_plan
from .engine.optimizer import choose_plan
from .engine.policy import evaluate_policy
from .logging_config import configure_logging
from .models import QueryRequest, QueryResponse
from .parser import parse_query
from .seed import ensure_seed_data

configure_logging()
ensure_seed_data()

app = FastAPI(title="Trust-Aware Federated Data Economy Platform", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "data-economy-backend", "version": "2.0.0"}


@app.get("/api/auth/me")
def auth_me(user=Depends(get_current_user)):
    return {"ok": True, "auth_required": auth_required(), "user": user}


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
            "Choose plan by strategy: balanced, cheapest, trust_first, or privacy_first",
            "Execute with selection pushdown where source supports it",
            "Detect duplicated/conflicting entity values in verified mode",
            "Resolve conflicts using computed trust + authority and return provenance",
            "Calculate user-facing query price with an arbitrage guard",
            "Write audit event as a duty of policy enforcement",
        ],
        "cost_model": {
            "estimated_execution_cost": "access_cost + rows_scanned*row_scan_cost + api_calls*api_call_cost + projection_penalty",
            "score_balanced": "cost + 0.004*latency + 0.25*api_calls + 0.9*conflict_risk - 1.5*trust - 0.4*freshness",
            "score_trust_first": "0.65*cost + 0.003*latency + 1.15*risk - 3*trust - 0.8*freshness",
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
    audit_base = {"raw_query": req.query, "role": req.role, "purpose": req.purpose, "strategy": req.strategy, "verification": req.verification}
    try:
        parsed = parse_query(req.query)
        verification = req.verification or parsed.verification_hint
        policy = evaluate_policy(parsed, req.role, req.purpose, verification)
        if not policy["allowed"]:
            audit_id = write_audit({**audit_base, "allowed": False, "reason": policy["reason"]})
            return QueryResponse(ok=False, message="Policy denied the query.", parsed_query=parsed.to_dict(), policy_decision=policy, audit_id=audit_id)
        selected_plan, candidates = choose_plan(parsed, req.strategy, verification)
        exec_result = execute_plan(parsed, selected_plan, req.role, req.purpose, req.show_all_conflicts)
        audit_id = write_audit({
            **audit_base,
            "allowed": True,
            "selected_plan": selected_plan.to_dict(),
            "price": exec_result["pricing"].get("total_user_price"),
            "conflict_count": len(exec_result["conflicts"]),
            "row_count": len(exec_result["result_rows"]),
        })
        return QueryResponse(
            ok=True,
            message="Query executed with governance, optimisation, pricing and provenance.",
            parsed_query=parsed.to_dict(),
            policy_decision=policy,
            selected_plan=selected_plan.to_dict(),
            candidate_plans=[p.to_dict() for p in candidates],
            result_rows=exec_result["result_rows"],
            conflicts=exec_result["conflicts"],
            pricing=exec_result["pricing"],
            execution_metrics={"actual_source_metrics": exec_result["metrics"]},
            audit_id=audit_id,
        )
    except (InvalidQueryError, QueryError, ValueError) as exc:
        audit_id = write_audit({**audit_base, "allowed": False, "error": str(exc)})
        return QueryResponse(ok=False, message=str(exc), audit_id=audit_id)
    except Exception as exc:
        audit_id = write_audit({**audit_base, "allowed": False, "error": str(exc)})
        return QueryResponse(ok=False, message="Internal error while executing query.", audit_id=audit_id)

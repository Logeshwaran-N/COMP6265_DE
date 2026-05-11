from fastapi.testclient import TestClient
from app.main import app
from app.parser import parse_query
from app.engine.trust import compute_source_trust

client = TestClient(app)


def test_parser_verification():
    q = parse_query("SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION")
    assert q.dataset == "fx_rates"
    assert q.verification_hint is True
    assert q.where.left == "pair"


def test_policy_denies_pii_for_researcher():
    res = client.post("/api/query", json={
        "query": "SELECT customer_email FROM orders WHERE order_id = 'O-1002'",
        "role": "researcher",
        "purpose": "research"
    }).json()
    assert res["ok"] is False
    assert "PII" in res["policy_decision"]["reason"] or "restricted" in res["policy_decision"]["reason"]


def test_verified_fx_conflict():
    res = client.post("/api/query", json={
        "query": "SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION",
        "role": "researcher",
        "purpose": "research",
        "strategy": "trust_first"
    }).json()
    assert res["ok"] is True
    assert res["selected_plan"]["mode"] == "verified"
    assert len(res["conflicts"]) >= 1
    assert res["result_rows"][0]["_chosen_source"] in {"fx_db", "fx_api"}


def test_trust_scores_exist():
    trust = compute_source_trust()
    assert "fx_db" in trust
    assert trust["fx_db"]["computed_trust"] > trust["fx_csv"]["computed_trust"]


def test_fx_history_large_query_ordered():
    res = client.post('/api/query', json={
        'query': "SELECT date, pair, rate FROM fx_history WHERE pair = 'GBP_INR' ORDER BY date DESC LIMIT 100",
        'role': 'researcher',
        'purpose': 'research',
        'strategy': 'balanced'
    }).json()
    assert res['ok'] is True
    assert len(res['result_rows']) == 100
    assert res['result_rows'][0]['date'] >= res['result_rows'][-1]['date']
    assert res['pricing']['row_tier_fee'] >= 0.75

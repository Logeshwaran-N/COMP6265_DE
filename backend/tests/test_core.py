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
        "strategy": "trust_first",
        "show_all_conflicts": True
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


def _selected_source_for_strategy(strategy: str) -> str:
    res = client.post('/api/query', json={
        'query': "SELECT name, price_gbp FROM fruits WHERE name = 'apple'",
        'role': 'researcher',
        'purpose': 'research',
        'strategy': strategy,
        'verification': False,
        'show_all_conflicts': False,
    }).json()
    assert res['ok'] is True
    assert res['selected_plan']['mode'] == 'single_source'
    assert res['execution_metrics']['actual_source_count'] == 1
    assert res['conflicts'] == []
    return res['selected_plan']['sources'][0]


def test_fruit_strategy_source_selection():
    assert _selected_source_for_strategy('cheapest') == 'fruit_csv'
    assert _selected_source_for_strategy('balanced') == 'fruit_db'
    assert _selected_source_for_strategy('trust_first') == 'fruit_api'
    assert _selected_source_for_strategy('privacy_first') == 'fruit_db'


def test_verified_without_provenance_hides_conflict_details():
    res = client.post('/api/query', json={
        'query': "SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION",
        'role': 'researcher',
        'purpose': 'research',
        'strategy': 'balanced',
        'verification': True,
        'show_all_conflicts': False,
    }).json()
    assert res['ok'] is True
    assert res['selected_plan']['mode'] == 'verified'
    assert res['conflicts'] == []
    assert res['execution_metrics']['actual_source_count'] == 3
    assert res['execution_metrics']['internal_conflict_count'] >= 1


def _fx_selected_source_for_strategy(strategy: str) -> str:
    res = client.post('/api/query', json={
        'query': "SELECT rate FROM fx_rates WHERE pair = 'GBP_INR'",
        'role': 'researcher',
        'purpose': 'research',
        'strategy': strategy,
        'verification': False,
        'show_all_conflicts': False,
    }).json()
    assert res['ok'] is True
    assert res['execution_metrics']['actual_source_count'] == 1
    return res['selected_plan']['sources'][0]


def test_fx_strategy_source_selection():
    assert _fx_selected_source_for_strategy('cheapest') == 'fx_csv'
    assert _fx_selected_source_for_strategy('balanced') == 'fx_db'
    assert _fx_selected_source_for_strategy('trust_first') == 'fx_api'

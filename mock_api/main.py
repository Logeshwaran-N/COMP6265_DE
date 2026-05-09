from fastapi import FastAPI, Request

app = FastAPI(title="Mock external data provider API")

try:
    # Keep a single source of truth for mock payloads.
    # When running `uvicorn mock_api.main:app`, project root is typically on sys.path.
    from backend.app.seed_data import SHARED_API_DATA  # type: ignore
except Exception:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from backend.app.seed_data import SHARED_API_DATA  # type: ignore

FRUITS = SHARED_API_DATA["fruits"]
FX = SHARED_API_DATA["fx_rates"]
ORDERS = SHARED_API_DATA["orders"]


def filter_rows(rows, query):
    if not query:
        return rows
    out = []
    for row in rows:
        ok = True
        for k, v in query.items():
            if str(row.get(k, "")).lower() != str(v).lower():
                ok = False
                break
        if ok:
            out.append(row)
    return out


@app.get("/health")
def health():
    return {"ok": True, "provider": "mock-api"}


@app.get("/fruits")
def fruits(request: Request):
    return filter_rows(FRUITS, dict(request.query_params))


@app.get("/fx_rates")
def fx_rates(request: Request):
    return filter_rows(FX, dict(request.query_params))


@app.get("/orders")
def orders(request: Request):
    return filter_rows(ORDERS, dict(request.query_params))

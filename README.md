# Trust-Aware Federated Data Economy Platform

COMP6265 prototype for querying distributed data products with governance, trust, pricing and audit evidence.

## What the system demonstrates

- Federated querying over CSV, SQLite and mock API sources
- Current FX rate verification across multiple providers
- Large FX history access for analytics / bot-training style queries
- Trust-aware conflict resolution and source provenance
- Query pricing and execution-cost estimation
- ODRL-inspired role, purpose and column policy checks
- Audit logging
- Admin-managed users with local auth or Cognito auth

## Current AWS target

```text
Frontend: AWS Amplify
Auth: Amazon Cognito
Backend: EC2 Docker service
HTTPS API: API Gateway proxy to EC2 backend
Data: packaged CSV + SQLite + mock API service
```

The project avoids live third-party APIs in this version so the demonstration is stable and repeatable.

## Local login

There is no public signup page. Users are created by the administrator.

```text
admin@test.com / Admin@12345
```

Admin users can query data, add members, search users, reset passwords and remove members. The current admin account cannot remove itself.

## Run locally with Docker

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:5173
```

Backend health:

```text
http://localhost:8000/api/health
```

## Cognito mode

Backend environment variables:

```text
REQUIRE_AUTH=true
AUTH_PROVIDER=cognito
COGNITO_REGION=eu-west-2
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_APP_CLIENT_ID=YOUR_APP_CLIENT_ID
COGNITO_ADMIN_GROUP=admin
COGNITO_SUPPRESS_INVITE=true
MOCK_API_BASE_URL=http://mock-api:8001
FRONTEND_ORIGINS=https://YOUR-AMPLIFY-URL
```

Frontend environment variable in Amplify:

```text
VITE_API_BASE_URL=https://YOUR-API-GATEWAY-URL
```

## Data sources

```text
CSV current FX source       backend/data/fx_rates.csv
CSV historical FX source    backend/data/fx_history.csv
SQLite reference source     backend/data/warehouse.db
Mock API source             mock_api service / in-process fallback data
```

Seed data size in this version:

```text
fruits:      1,000 records in CSV, SQLite and mock API
orders:      5,000 records in SQLite and mock API
suppliers:   120 reference records
fx_rates:    12 current currency pairs
fx_history:  21,912 historical observations
```


## Query modes and strategies

Standard mode executes one selected source only. Verification mode executes all compatible sources and can show provenance/conflict details.

```text
cheapest      -> lowest access-price source tier, usually CSV/file
balanced      -> best trade-off source, usually SQLite reference data
trust_first   -> highest trust/freshness tier, usually mock API
privacy_first -> controlled source with minimal external exposure, usually SQLite
```

The UI keeps `WITH VERIFICATION` and the verification checkbox in sync. Provenance details are shown only when the provenance checkbox is selected.

## Important queries

Current GBP/INR verification:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

Historical FX query:

```sql
SELECT date, pair, rate FROM fx_history WHERE pair = 'GBP_INR' ORDER BY date DESC LIMIT 100
```

Fruit conflict resolution with controlled source variance:

```sql
SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION
```

Large retail-order query:

```sql
SELECT order_id, customer_region, total_gbp FROM orders WHERE customer_region = 'London' LIMIT 50
```

PII policy denial:

```sql
SELECT customer_email FROM orders WHERE order_id = 'O-100002'
```

## Tests

```bash
PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest backend/tests -q
```

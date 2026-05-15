# Intent-Aware Federated Data Economy Platform

COMP6265 prototype for querying distributed data products through one platform. The system recommends the best source tier based on query intent, user preference, trust, freshness, cost, policy and pricing.

## What the system demonstrates

- Federated querying over CSV, SQLite and API-style sources
- Intent-aware source selection for current point values, historical bulk data, analytics slices and record lookups
- Trust-tiered FX provider choice: daily DB, standard live API and premium trading feed
- Fruit source choice between low-cost daily DB, trusted current market API and CSV data lake
- CSV/data-lake preference for large historical queries
- Verified mode that checks multiple sources, detects conflicts and resolves by trust, authority and freshness
- Query pricing separated from internal execution cost
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

The project avoids live third-party APIs so the coursework demo is stable and repeatable.

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

## Data source tiers

```text
Fruit CSV Data Lake        low-cost archive / bulk scan
Fruit Daily Warehouse DB   daily cleaned fruit price reference
Trusted Fruit Market API   fresher current fruit market price
Manual FX CSV Archive      low-trust/stale current FX file
Official Daily FX DB       governed daily FX reference
Standard FX Live API       normal live-ish FX provider
Premium FX Trading Feed    high-trust premium FX provider
FX History CSV Data Lake   low-cost historical FX bulk access
Official FX History DB     cleaner high-trust historical reference
Enterprise Orders DB       governed internal order analytics
Retail Analytics API       external analytics enrichment
Supplier Master DB         controlled supplier reference data
```

Seed data size in this version:

```text
fruits:      1,000 records in CSV, SQLite and mock API
orders:      5,000 records in SQLite and mock API
suppliers:   120 reference records
fx_rates:    12 current currency pairs
fx_history:  21,912 historical observations
```

## Query modes and preferences

Standard mode executes one recommended source. Verification mode executes all compatible sources and can show source comparison details.

```text
balanced      -> normal choice for the query intent
cheapest      -> cost-effective source that still fits the intent
trust_first   -> premium or highest-authority provider
privacy_first -> controlled DB/warehouse source where possible
```

The UI keeps `WITH VERIFICATION` and the verification checkbox in sync. Source comparison details are shown only when selected.

## Important queries

Normal live FX rate:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR'
```

Premium live FX rate:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR'
```

Run the premium example with the `High trust / premium` preference.

Verified GBP/INR comparison:

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

Low-cost historical FX query:

```sql
SELECT date, pair, rate FROM fx_history WHERE pair = 'GBP_INR' ORDER BY date DESC LIMIT 100
```

Current fruit price:

```sql
SELECT name, price_gbp FROM fruits WHERE name = 'apple'
```

Fruit verified conflict resolution:

```sql
SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION
```

Retail-order analytics:

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

Open http://localhost:5173 in Windows and check http://localhost:8000/api/health.


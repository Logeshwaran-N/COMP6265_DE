# Trust-Aware Federated Data Economy Platform

COMP6265 Data Economy prototype with:

- federated querying over CSV, SQLite and API-style sources
- trust-aware conflict resolution and source provenance
- query pricing and execution-cost estimation
- ODRL-inspired governance checks
- audit logging
- admin-managed email/password users
- local auth for development and Cognito auth for AWS deployment

## Current branch target

This version is prepared for the `logesh-amplify` branch:

```text
Frontend: AWS Amplify
Auth: Amazon Cognito
Backend: AWS App Runner
```

The EC2/Docker setup still works as a fallback.

## Local login

There is no public signup page. Users are created by the admin.

Local test admin:

```text
admin@test.com / Admin@12345
```

Admin abilities:

- run queries like a normal user
- add a member with email + temporary password
- list/search users
- remove users

When a member signs in with a temporary password, the app asks them to set a new password before entering the platform.

## Run locally with Docker

```bash
docker compose up --build -d
```

For older Docker Compose:

```bash
docker-compose up --build -d
```

Open:

```text
http://localhost:5173
```

Backend:

```text
http://localhost:8000/api/health
```

If using a VM from Windows, tunnel both ports:

```powershell
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 logesh@YOUR_VM_IP
```

## Local auth storage

Local users are stored in:

```text
backend/data/users.json
```

Docker Compose mounts `backend/data` into the backend container, so users created in local testing survive container restarts.

To reset local users:

```bash
docker compose down
rm -f backend/data/users.json backend/data/audit_log.jsonl
docker compose up --build -d
```

The default admin will be recreated on next backend start.

## AWS deployment

Read:

```text
docs/AWS_DEPLOYMENT.md
docs/COGNITO_SETUP_NOTES.md
```

Quick AWS target:

```text
Amplify branch: logesh-amplify
Amplify env: VITE_API_BASE_URL=https://YOUR-APP-RUNNER-URL
App Runner source directory: backend
App Runner env: AUTH_PROVIDER=cognito, Cognito IDs, FRONTEND_ORIGINS
```

## Cognito mode

Set backend environment variables:

```text
REQUIRE_AUTH=true
AUTH_PROVIDER=cognito
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_APP_CLIENT_ID=YOUR_APP_CLIENT_ID
COGNITO_ADMIN_GROUP=admin
COGNITO_SUPPRESS_INVITE=true
MOCK_API_BASE_URL=internal
FRONTEND_ORIGINS=https://YOUR-AMPLIFY-URL
```

The backend verifies Cognito JWT tokens and performs admin user operations through Cognito admin APIs.

## Data sources

Current prototype sources:

```text
CSV files      backend/data/fruits.csv, backend/data/fx_rates.csv
SQLite DB      backend/data/warehouse.db
API source     mock_api service locally; in-process fallback in App Runner
```

For this coursework dataset size, packaged CSV/SQLite is enough for the first cloud model. S3 can be added later if you want a proper cloud data-lake source.

## Frontend build

Docker serves the already-built `frontend/dist` folder. If you change `frontend/index.html`, rebuild:

```bash
cd frontend
npm install
npm run build
cd ..
docker compose up --build -d
```

Amplify builds automatically using `amplify.yml`.

## Tests

```bash
PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest backend/tests -q
```

Expected currently:

```text
6 passed
```

## Important demo queries

```sql
SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION
```

```sql
SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION
```

```sql
SELECT customer_email FROM orders WHERE order_id = 'O-1002'
```

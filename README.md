# Trust-Aware Federated Data Economy Platform

A COMP6265 Data Economy prototype with:

- federated querying over CSV, SQLite and API sources
- source trust and conflict resolution
- query pricing and execution-cost estimation
- policy/governance checks
- audit logging
- admin-managed email/password accounts

## Login and users

There is no public signup page. Users must be created by an admin.

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

Then open:

```text
http://localhost:5173
```

## Local auth storage

Local users are stored in:

```text
backend/data/users.json
```

Docker Compose mounts `backend/data` into the backend container, so users created in local testing survive container restarts.

To reset all local users, stop Docker and delete:

```bash
rm backend/data/users.json
```

The default admin will be recreated on next backend start.

## AWS-compatible auth mode

The app has two backend auth modes:

```text
AUTH_PROVIDER=local
AUTH_PROVIDER=cognito
```

For local/EC2 testing, use `AUTH_PROVIDER=local`.

For AWS Cognito, set:

```text
REQUIRE_AUTH=true
AUTH_PROVIDER=cognito
COGNITO_REGION=YOUR_REGION
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_APP_CLIENT_ID=YOUR_APP_CLIENT_ID
COGNITO_ADMIN_GROUP=admin
```

The Cognito app client must support email/password sign-in from the backend. For this implementation, use an app client without a client secret and enable the password auth flow used by the backend.

For admin-created users in Cognito:

- backend admin action maps to `AdminCreateUser`
- the user receives/uses a temporary password
- first login returns `NEW_PASSWORD_REQUIRED`
- the app submits the new password and continues

For admin list/delete users, the backend needs IAM permission for Cognito user-pool admin APIs.

## Data sources

Current prototype sources:

```text
CSV files      backend/data/fruits.csv, backend/data/fx_rates.csv
SQLite DB      backend/data/warehouse.db
Mock API       mock_api service on port 8001
```

For the final AWS demo, the simplest stable route is EC2 + Docker Compose. CSV files can stay on EC2 storage because the coursework dataset is small. S3 can be described as a production extension if we later move CSV/data-lake files out of EC2.

## Frontend build note

Docker serves the already-built `frontend/dist` folder. If you change `frontend/index.html`, rebuild the frontend before Docker build:

```bash
cd frontend
npm install
npm run build
cd ..
docker compose up --build -d
```

## Tests

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
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

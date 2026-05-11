# AWS deployment notes

Current deployment target:

```text
React frontend  -> AWS Amplify
Public API      -> API Gateway HTTP API
Backend         -> EC2 Docker Compose
Auth            -> Cognito User Pool
Data            -> packaged CSV, SQLite and mock API sources
```

## Backend on EC2

Run the backend stack on the EC2 instance:

```bash
git checkout logesh-amplify
git pull
docker compose down
docker compose up --build -d
```

Backend environment for Cognito mode:

```text
REQUIRE_AUTH=true
AUTH_PROVIDER=cognito
COGNITO_REGION=eu-west-2
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_APP_CLIENT_ID=YOUR_CLIENT_ID
COGNITO_ADMIN_GROUP=admin
COGNITO_SUPPRESS_INVITE=true
MOCK_API_BASE_URL=http://mock-api:8001
FRONTEND_ORIGINS=https://YOUR-AMPLIFY-DOMAIN
```

Check:

```bash
curl http://localhost:8000/api/health
```

## API Gateway

Create an HTTP API proxy that forwards to:

```text
http://EC2_PUBLIC_IP:8000
```

The generated endpoint should look like:

```text
https://xxxx.execute-api.eu-west-2.amazonaws.com
```

Use that endpoint in Amplify.

## Amplify frontend

Amplify settings:

```text
Branch: logesh-amplify
Monorepo app root: frontend
Build command: npm run build
Output directory: dist
```

Environment variable:

```text
VITE_API_BASE_URL=https://YOUR-API-GATEWAY-URL
```

## Runtime data

Do not commit runtime files:

```text
backend/data/users.json
backend/data/audit_log.jsonl
```

The committed CSV and SQLite files are seed/demo data for the coursework prototype.

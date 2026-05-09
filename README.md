# Trust-Aware Federated Data Economy Platform

This version contains the new dark UI, an email/password login page, Google/Cognito sign-in options, the FastAPI backend, and the mock external API.

## What is inside

- `frontend/` - Vite static frontend with the new UI, local email/password login, and Cognito/Google buttons
- `backend/` - FastAPI backend for catalogue, policy, optimiser, trust, pricing and audit
- `mock_api/` - Mock external provider used by the backend
- `aws/lambda/pre_signup_google_link_provider/` - optional Cognito Pre sign-up Lambda for linking Google users by email
- `docker-compose.yml` - local full-stack run for testing

## Local run with Docker Compose

From the project root:

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:5173
```

If running inside a VM and opening from Windows, use the VM IP:

```text
http://YOUR_VM_IP:5173
```

Backend health check:

```text
http://YOUR_VM_IP:8000/api/health
```

For local testing, use the hardcoded email/password form. Demo credentials are:

```text
demo@comp6265.local / demo123
admin@comp6265.local / admin123
```

There is also **Continue without password** for quick UI testing. In AWS production, set `VITE_AUTH_REQUIRED=true` so local login and demo mode are hidden.

## Email/password and Google login/signup with AWS Cognito

Use Cognito Hosted UI for production. The **Sign in / sign up with Cognito email** button opens the normal Cognito Hosted UI page, where existing Cognito users can log in by email/password and new users can sign up if self-registration is enabled. The **Continue with Google** button sends users directly to Google through the same Cognito User Pool.

### Cognito setup summary

1. Create a Cognito User Pool.
2. In sign-in options, allow email/username sign-in. Enable self sign-up if you want new users to create accounts from the Hosted UI.
3. Add **Google** as an identity provider if you want Google login too.
4. Create an app client for a browser/static app.
5. Do **not** use a client secret for the frontend.
6. Enable OAuth flow for the Hosted UI. This frontend uses the simple browser flow `response_type=token`, so enable the **Implicit grant** flow for the app client.
7. Add callback and logout URLs:

```text
http://localhost:5173/
https://YOUR-AMPLIFY-DOMAIN/
```

8. Enable scopes:

```text
openid
email
profile
```

9. In Amplify frontend environment variables, set:

```text
VITE_AUTH_ENABLED=true
VITE_AUTH_REQUIRED=true
VITE_COGNITO_DOMAIN=https://YOUR_COGNITO_DOMAIN.auth.YOUR_REGION.amazoncognito.com
VITE_COGNITO_CLIENT_ID=YOUR_COGNITO_APP_CLIENT_ID
VITE_COGNITO_REDIRECT_URI=https://YOUR-AMPLIFY-DOMAIN/
VITE_COGNITO_LOGOUT_URI=https://YOUR-AMPLIFY-DOMAIN/
VITE_COGNITO_PROVIDER=Google
VITE_API_BASE_URL=https://YOUR-BACKEND-URL
```


### Local hardcoded login vs Cognito users

The local form is only for VM/coursework testing. The hardcoded users are inside `frontend/index.html` under `LOCAL_USERS`. Do not put real passwords there.

For AWS, create users in the Cognito User Pool or enable Cognito self sign-up. Cognito will authenticate real users through Hosted UI. The frontend does not store real Cognito passwords.

### Backend JWT protection

Local Docker keeps backend auth off:

```text
REQUIRE_AUTH=false
```

When deploying the backend, enable Python-side Cognito JWT validation:

```text
REQUIRE_AUTH=true
COGNITO_REGION=YOUR_REGION
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_APP_CLIENT_ID=YOUR_COGNITO_APP_CLIENT_ID
```

The frontend sends the Cognito token in the `Authorization: Bearer ...` header. The backend validates it in Python using Cognito JWKS.

## Optional Cognito Pre sign-up Lambda

If you later allow both local Cognito users and Google users, use:

```text
aws/lambda/pre_signup_google_link_provider/lambda_function.py
```

Attach it to the Cognito **Pre sign-up** trigger. It links a new Google external provider user to an existing Cognito user with the same email. If you only use Google sign-in, this Lambda is optional.

## Why frontend Docker is prebuilt

The Docker frontend intentionally does **not** run `npm install` during Docker build. It serves the already-built `frontend/dist` folder, so Docker startup is fast and avoids npm install hangs.

If you change frontend HTML/JS:

```bash
cd frontend
npm install
npm run build
cd ..
docker compose up --build -d
```

## Frontend-only development

```bash
cd frontend
npm install
npm run dev
```

## Backend tests

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

## AWS Amplify note

Amplify should deploy the **frontend** only. Use the `frontend` folder as the app root. The FastAPI backend must be deployed separately, for example on a server/container service. For coursework testing, Docker Compose runs frontend + backend + mock API together.

# AWS deployment plan for `logesh-amplify`

This branch is intended for the real AWS deployment path:

```text
Frontend  -> AWS Amplify Hosting
Auth      -> Amazon Cognito User Pool
Backend   -> AWS App Runner
Data      -> packaged CSV/SQLite seed data inside backend service for now
API source-> in-process fallback API data in App Runner; Docker mock-api stays for local testing
```

The existing EC2 deployment can remain as the stable fallback.

## 1. Push this branch

```bash
git checkout -b logesh-amplify
git add .
git commit -m "Prepare Amplify Cognito App Runner deployment"
git push -u origin logesh-amplify
```

## 2. Create Cognito User Pool

Recommended Cognito settings:

```text
Sign-in identifier: email
Self sign-up: disabled
App client: public client, no client secret
Auth flow: ALLOW_USER_PASSWORD_AUTH / USER_PASSWORD_AUTH enabled
Groups: admin, researcher, analyst, data_steward, guest
```

Create the admin user:

```text
admin@test.com
```

Add the admin user to the `admin` group. First login can use temporary-password flow.

## 3. Backend on App Runner

Use source directory:

```text
backend
```

The `backend/apprunner.yaml` file is included. App Runner builds from `backend/requirements.txt` and starts:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set these App Runner environment variables:

```text
REQUIRE_AUTH=true
AUTH_PROVIDER=cognito
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=<your-pool-id>
COGNITO_APP_CLIENT_ID=<your-app-client-id>
COGNITO_ADMIN_GROUP=admin
COGNITO_SUPPRESS_INVITE=true
MOCK_API_BASE_URL=internal
DATA_ECONOMY_MOCK_API_BASE_URL=internal
FRONTEND_ORIGINS=https://<your-amplify-domain>
```

For the first backend test, before Amplify exists, you can temporarily use:

```text
FRONTEND_ORIGINS=*
```

## 4. Backend IAM role

The running backend must be allowed to call Cognito login, password-reset and admin-user APIs.
For the current EC2 deployment, attach these permissions to the EC2 instance role. If you later use another compute service, attach the equivalent runtime role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminDeleteUser",
        "cognito-idp:AdminAddUserToGroup",
        "cognito-idp:AdminListGroupsForUser",
        "cognito-idp:AdminResetUserPassword",
        "cognito-idp:ListUsers",
        "cognito-idp:InitiateAuth",
        "cognito-idp:RespondToAuthChallenge",
        "cognito-idp:ForgotPassword",
        "cognito-idp:ConfirmForgotPassword"
      ],
      "Resource": "arn:aws:cognito-idp:<region>:<account-id>:userpool/<user-pool-id>"
    }
  ]
}
```

## 5. Frontend on Amplify

Connect the same GitHub repo and select branch:

```text
logesh-amplify
```

Use the included `amplify.yml`.

Set Amplify environment variable:

```text
VITE_API_BASE_URL=https://<your-app-runner-service-url>
```

No Cognito secret is stored in the frontend. The frontend sends email/password to the backend, and the backend performs Cognito login/challenge handling.

## 6. Test order

1. Open backend health URL:

```text
https://<app-runner-url>/api/health
```

2. Open Amplify URL.
3. Login with `admin@test.com`.
4. If Cognito asks for a new password, set it.
5. Run a query.
6. Open Admin and add one member.
7. Logout and login as that member with temporary password.
8. Set new password and run a query.

## 7. Local testing still works

```bash
docker compose up --build -d
```

Local admin:

```text
admin@test.com / Admin@12345
```

## Live FX API environment

The live FX connector uses Frankfurter by default and does not require an API key.

Optional backend environment variables:

```env
DATA_ECONOMY_LIVE_FX_API_ENABLED=true
DATA_ECONOMY_LIVE_FX_API_BASE_URL=https://api.frankfurter.dev/v2
DATA_ECONOMY_LIVE_FX_CACHE_TTL_SECONDS=3600
```

The backend can still run if the external API fails because it falls back to cached or internal seed data.

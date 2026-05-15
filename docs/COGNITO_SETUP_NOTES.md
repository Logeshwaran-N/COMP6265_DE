# Cognito setup notes

## Groups used by the application

The backend maps Cognito groups to project roles:

```text
admin        -> admin
researcher   -> researcher
analyst      -> analyst
data_steward -> data_steward
guest        -> guest
member       -> researcher fallback, optional
```

If a user belongs to multiple groups, the backend applies this priority:

```text
admin > data_steward > analyst > researcher > guest > member
```

## User creation flow

Admin creates a user inside the web app with:

```text
email + temporary password + role
```

The backend calls Cognito `AdminCreateUser` and assigns the selected group. On first login, Cognito returns `NEW_PASSWORD_REQUIRED`; the app then asks the user to set a new password.

## Useful local script

You can run this after creating the user pool and app client:

```bash
python scripts/setup_cognito_groups_admin.py \
  --region us-east-1 \
  --user-pool-id YOUR_POOL_ID \
  --admin-email admin@test.com \
  --temp-password Admin@12345
```

This creates the expected groups and the initial admin user if missing.

## Password reset flow

The app supports two reset paths:

```text
User forgot password -> /api/auth/forgot-password -> Cognito ForgotPassword
User enters code      -> /api/auth/confirm-forgot-password -> Cognito ConfirmForgotPassword
Admin reset user      -> /api/admin/users/{email}/reset-password -> Cognito AdminResetUserPassword
```

For Cognito mode, the user must have a verified email address and Cognito email delivery must be configured or available. For local development mode, the backend returns a temporary reset code in the API response because there is no email service.

The EC2/backend IAM role needs these additional actions:

```text
cognito-idp:ForgotPassword
cognito-idp:ConfirmForgotPassword
cognito-idp:AdminResetUserPassword
```

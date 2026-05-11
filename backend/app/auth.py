from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Header, HTTPException, status

from .config import settings

_USERS_LOCK = Lock()
_USERS_FILE = settings.data_dir / "users.json"
_DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@test.com").strip().lower()
_DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@12345")
_DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Platform Admin")


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def auth_required() -> bool:
    return _truthy(os.getenv("REQUIRE_AUTH"), default=False)


def auth_provider() -> str:
    return os.getenv("AUTH_PROVIDER", "local").strip().lower() or "local"


def _token_secret() -> str:
    return os.getenv("LOCAL_AUTH_SECRET", "dev-only-change-this-secret")


def _now() -> int:
    return int(time.time())


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64e(raw)
    sig = hmac.new(_token_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def _verify_signed_payload(token: str, expected_type: str) -> dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(_token_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64d(sig), expected):
            raise ValueError("bad signature")
        payload = json.loads(_b64d(body).decode("utf-8"))
        if payload.get("type") != expected_type:
            raise ValueError("wrong token type")
        if int(payload.get("exp", 0)) < _now():
            raise ValueError("expired token")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def _hash_password(password: str, salt: str | None = None) -> str:
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 210_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        candidate = _hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def _ensure_user_store() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with _USERS_LOCK:
        if _USERS_FILE.exists():
            users = _read_users_unlocked()
        else:
            users = []
        if not any(u.get("email", "").lower() == _DEFAULT_ADMIN_EMAIL for u in users):
            users.append({
                "email": _DEFAULT_ADMIN_EMAIL,
                "name": _DEFAULT_ADMIN_NAME,
                "role": "admin",
                "status": "CONFIRMED",
                "enabled": True,
                "created_at": _now(),
                "updated_at": _now(),
                "password_hash": _hash_password(_DEFAULT_ADMIN_PASSWORD),
            })
            _write_users_unlocked(users)


def _read_users_unlocked() -> list[dict[str, Any]]:
    if not _USERS_FILE.exists():
        return []
    try:
        return json.loads(_USERS_FILE.read_text())
    except Exception:
        return []


def _write_users_unlocked(users: list[dict[str, Any]]) -> None:
    _USERS_FILE.write_text(json.dumps(users, indent=2, sort_keys=True))


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": user.get("email"),
        "name": user.get("name") or user.get("email"),
        "role": user.get("role", "researcher"),
        "status": user.get("status", "UNKNOWN"),
        "enabled": bool(user.get("enabled", True)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "provider": "local",
    }


def _find_local_user(email: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int]:
    email = email.strip().lower()
    users = _read_users_unlocked()
    for i, user in enumerate(users):
        if user.get("email", "").lower() == email:
            return users, user, i
    return users, None, -1


def local_login(email: str, password: str) -> dict[str, Any]:
    _ensure_user_store()
    with _USERS_LOCK:
        users, user, _ = _find_local_user(email)
        if not user or not bool(user.get("enabled", True)) or not _check_password(password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if user.get("status") == "FORCE_CHANGE_PASSWORD":
            challenge = _sign_payload({
                "type": "new_password",
                "email": user["email"],
                "iat": _now(),
                "exp": _now() + 15 * 60,
            })
            return {"ok": True, "challenge": "NEW_PASSWORD_REQUIRED", "session": challenge, "user": _public_user(user)}
        token = _issue_local_access_token(user)
        return {"ok": True, "access_token": token, "token_type": "Bearer", "user": _public_user(user)}


def _issue_local_access_token(user: dict[str, Any]) -> str:
    return _sign_payload({
        "type": "access",
        "sub": user.get("email"),
        "email": user.get("email"),
        "name": user.get("name") or user.get("email"),
        "role": user.get("role", "researcher"),
        "iat": _now(),
        "exp": _now() + 8 * 60 * 60,
    })


def complete_local_new_password(session: str, new_password: str) -> dict[str, Any]:
    payload = _verify_signed_payload(session, "new_password")
    email = payload["email"].strip().lower()
    with _USERS_LOCK:
        users, user, idx = _find_local_user(email)
        if not user or idx < 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user["password_hash"] = _hash_password(new_password)
        user["status"] = "CONFIRMED"
        user["updated_at"] = _now()
        users[idx] = user
        _write_users_unlocked(users)
        return {"ok": True, "access_token": _issue_local_access_token(user), "token_type": "Bearer", "user": _public_user(user)}


def change_local_password(current_user: dict[str, Any], current_password: str, new_password: str) -> dict[str, Any]:
    email = str(current_user.get("email", "")).strip().lower()
    with _USERS_LOCK:
        users, user, idx = _find_local_user(email)
        if not user or idx < 0 or not _check_password(current_password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
        user["password_hash"] = _hash_password(new_password)
        user["status"] = "CONFIRMED"
        user["updated_at"] = _now()
        users[idx] = user
        _write_users_unlocked(users)
        return {"ok": True, "user": _public_user(user)}


def list_local_users(query: str | None = None) -> list[dict[str, Any]]:
    _ensure_user_store()
    q = (query or "").strip().lower()
    with _USERS_LOCK:
        users = [_public_user(u) for u in _read_users_unlocked()]
    if q:
        users = [u for u in users if q in (u.get("email") or "").lower() or q in (u.get("name") or "").lower() or q in (u.get("role") or "").lower()]
    return sorted(users, key=lambda u: (u.get("role") != "admin", u.get("email") or ""))


def create_local_user(email: str, temp_password: str, role: str = "researcher", name: str | None = None) -> dict[str, Any]:
    _ensure_user_store()
    email = email.strip().lower()
    role = role.strip().lower()
    if role not in {"guest", "analyst", "researcher", "data_steward", "admin"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    with _USERS_LOCK:
        users, existing, _ = _find_local_user(email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user = {
            "email": email,
            "name": name.strip() if name else email.split("@")[0],
            "role": role,
            "status": "FORCE_CHANGE_PASSWORD",
            "enabled": True,
            "created_at": _now(),
            "updated_at": _now(),
            "password_hash": _hash_password(temp_password),
        }
        users.append(user)
        _write_users_unlocked(users)
        return _public_user(user)


def delete_local_user(email: str, actor_email: str | None = None) -> dict[str, Any]:
    _ensure_user_store()
    email = email.strip().lower()
    if actor_email and email == actor_email.strip().lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot remove their own account")
    with _USERS_LOCK:
        users = _read_users_unlocked()
        kept = [u for u in users if u.get("email", "").lower() != email]
        if len(kept) == len(users):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        _write_users_unlocked(kept)
    return {"ok": True, "deleted": email}


# Cognito helpers. These are only used when AUTH_PROVIDER=cognito.
def _cognito_client():
    try:
        import boto3
    except Exception as exc:  # pragma: no cover - AWS deployment path
        raise HTTPException(status_code=500, detail="boto3 is required for AUTH_PROVIDER=cognito") from exc
    region = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    return boto3.client("cognito-idp", region_name=region)


@lru_cache(maxsize=1)
def _cognito_settings() -> dict[str, str]:
    region = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}" if region and user_pool_id else ""
    return {"region": region, "user_pool_id": user_pool_id, "app_client_id": app_client_id, "issuer": issuer, "jwks_url": f"{issuer}/.well-known/jwks.json" if issuer else ""}


@lru_cache(maxsize=1)
def _jwks_client():
    settings_c = _cognito_settings()
    if not settings_c["jwks_url"]:
        raise RuntimeError("Cognito JWKS URL is not configured")
    from jwt import PyJWKClient
    return PyJWKClient(settings_c["jwks_url"])


def cognito_login(email: str, password: str) -> dict[str, Any]:
    cfg = _cognito_settings()
    if not cfg["app_client_id"]:
        raise HTTPException(status_code=500, detail="COGNITO_APP_CLIENT_ID is missing")
    try:
        resp = _cognito_client().initiate_auth(
            ClientId=cfg["app_client_id"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
            return {"ok": True, "challenge": "NEW_PASSWORD_REQUIRED", "session": resp["Session"], "user": {"email": email, "role": "researcher", "status": "FORCE_CHANGE_PASSWORD", "provider": "cognito"}}
        auth = resp.get("AuthenticationResult", {})
        claims = _verify_cognito_token(auth.get("IdToken") or auth.get("AccessToken"))
        return {"ok": True, "access_token": auth.get("AccessToken"), "id_token": auth.get("IdToken"), "token_type": "Bearer", "user": _cognito_user_from_claims(claims)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Cognito login failed: {exc}") from exc


def complete_cognito_new_password(email: str, session: str, new_password: str) -> dict[str, Any]:
    cfg = _cognito_settings()
    try:
        resp = _cognito_client().respond_to_auth_challenge(
            ClientId=cfg["app_client_id"],
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=session,
            ChallengeResponses={"USERNAME": email, "NEW_PASSWORD": new_password},
        )
        auth = resp.get("AuthenticationResult", {})
        claims = _verify_cognito_token(auth.get("IdToken") or auth.get("AccessToken"))
        return {"ok": True, "access_token": auth.get("AccessToken"), "id_token": auth.get("IdToken"), "token_type": "Bearer", "user": _cognito_user_from_claims(claims)}
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Could not set new password: {exc}") from exc


def _role_from_groups(groups: Any) -> str:
    """Map Cognito groups to the role names used by the policy engine.

    Precedence matters. A user can accidentally be in multiple groups, so the
    highest-privilege role wins deterministically. Group names intentionally
    match the project roles to keep the AWS setup simple.
    """
    if isinstance(groups, str):
        groups = [groups]
    groups = set(groups or [])
    priority = [
        os.getenv("COGNITO_ADMIN_GROUP", "admin"),
        "data_steward",
        "analyst",
        "researcher",
        "guest",
        "member",
    ]
    for group in priority:
        if group in groups:
            return "researcher" if group == "member" else group
    return "researcher"


def _cognito_user_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    groups = claims.get("cognito:groups") or []
    role = _role_from_groups(groups)
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email") or claims.get("username") or claims.get("cognito:username"),
        "name": claims.get("name") or claims.get("given_name") or claims.get("email"),
        "username": claims.get("cognito:username") or claims.get("username"),
        "role": role,
        "status": "CONFIRMED",
        "provider": "cognito",
        "groups": list(groups) if not isinstance(groups, str) else [groups],
    }


def _verify_cognito_token(token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    settings_c = _cognito_settings()
    if not settings_c["issuer"] or not settings_c["app_client_id"]:
        raise HTTPException(status_code=500, detail="Cognito auth is not fully configured")

    try:
        import jwt
        from jwt import InvalidTokenError

        signing_key = _jwks_client().get_signing_key_from_jwt(token).key

        # Cognito ID token has an audience claim named "aud".
        # Cognito access token does not have "aud"; it has "client_id".
        # The frontend sends the access token in Authorization headers, so both
        # token types must be verified correctly.
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        token_use = unverified_claims.get("token_use")

        if token_use == "id":
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=settings_c["app_client_id"],
                issuer=settings_c["issuer"],
            )
        elif token_use == "access":
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=settings_c["issuer"],
                options={"verify_aud": False},
            )
            if claims.get("client_id") != settings_c["app_client_id"]:
                raise HTTPException(status_code=401, detail="Token client_id does not match this app client")
        else:
            raise HTTPException(status_code=401, detail="Unsupported Cognito token type")

        return claims

    except HTTPException:
        raise
    except InvalidTokenError as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=401, detail=f"Invalid Cognito token: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Could not validate Cognito token: {exc}") from exc


def list_cognito_users(query: str | None = None) -> list[dict[str, Any]]:
    cfg = _cognito_settings()
    kwargs: dict[str, Any] = {"UserPoolId": cfg["user_pool_id"], "Limit": 60}
    if query:
        kwargs["Filter"] = f'email ^= "{query}"'
    resp = _cognito_client().list_users(**kwargs)
    rows = []
    admin_group = os.getenv("COGNITO_ADMIN_GROUP", "admin")
    client = _cognito_client()
    for u in resp.get("Users", []):
        attrs = {a["Name"]: a.get("Value") for a in u.get("Attributes", [])}
        username = u.get("Username")
        try:
            group_resp = client.admin_list_groups_for_user(UserPoolId=cfg["user_pool_id"], Username=username)
            group_names = [g.get("GroupName") for g in group_resp.get("Groups", [])]
            role = _role_from_groups(group_names)
        except Exception:
            group_names = []
            role = "researcher"
        rows.append({"email": attrs.get("email") or username, "name": attrs.get("name") or attrs.get("email") or username, "role": role, "groups": group_names, "status": u.get("UserStatus"), "enabled": u.get("Enabled", True), "provider": "cognito"})
    return rows


def create_cognito_user(email: str, temp_password: str, role: str = "researcher", name: str | None = None) -> dict[str, Any]:
    cfg = _cognito_settings()
    client = _cognito_client()
    role = role.strip().lower()
    if role not in {"guest", "analyst", "researcher", "data_steward", "admin"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    attrs = [{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}]
    if name:
        attrs.append({"Name": "name", "Value": name})
    create_kwargs: dict[str, Any] = {
        "UserPoolId": cfg["user_pool_id"],
        "Username": email,
        "TemporaryPassword": temp_password,
        "UserAttributes": attrs,
    }
    if _truthy(os.getenv("COGNITO_SUPPRESS_INVITE"), default=True):
        create_kwargs["MessageAction"] = "SUPPRESS"
    else:
        create_kwargs["DesiredDeliveryMediums"] = ["EMAIL"]
    client.admin_create_user(**create_kwargs)
    group_name = os.getenv("COGNITO_ADMIN_GROUP", "admin") if role == "admin" else role
    try:
        client.admin_add_user_to_group(UserPoolId=cfg["user_pool_id"], Username=email, GroupName=group_name)
    except Exception as exc:
        # The user was created, but role assignment failed. This usually means the Cognito
        # group has not been created yet. Make the problem clear in the API response.
        raise HTTPException(status_code=500, detail=f"Cognito user created but group '{group_name}' could not be assigned: {exc}") from exc
    return {"email": email, "name": name or email, "role": role, "groups": [group_name], "status": "FORCE_CHANGE_PASSWORD", "enabled": True, "provider": "cognito"}


def delete_cognito_user(email: str) -> dict[str, Any]:
    cfg = _cognito_settings()
    _cognito_client().admin_delete_user(UserPoolId=cfg["user_pool_id"], Username=email)
    return {"ok": True, "deleted": email}


def login(email: str, password: str) -> dict[str, Any]:
    return cognito_login(email, password) if auth_provider() == "cognito" else local_login(email, password)


def complete_new_password(email: str | None, session: str, new_password: str) -> dict[str, Any]:
    if auth_provider() == "cognito":
        if not email:
            raise HTTPException(status_code=400, detail="Email is required for Cognito password challenge")
        return complete_cognito_new_password(email, session, new_password)
    return complete_local_new_password(session, new_password)


def list_users(query: str | None = None) -> list[dict[str, Any]]:
    return list_cognito_users(query) if auth_provider() == "cognito" else list_local_users(query)


def create_user(email: str, temp_password: str, role: str = "researcher", name: str | None = None) -> dict[str, Any]:
    return create_cognito_user(email, temp_password, role, name) if auth_provider() == "cognito" else create_local_user(email, temp_password, role, name)


def delete_user(email: str, actor_email: str | None = None) -> dict[str, Any]:
    if actor_email and email.strip().lower() == actor_email.strip().lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot remove their own account")
    return delete_cognito_user(email) if auth_provider() == "cognito" else delete_local_user(email, actor_email)


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if auth_provider() == "cognito":
            return _cognito_user_from_claims(_verify_cognito_token(token))
        payload = _verify_signed_payload(token, "access")
        return {"sub": payload.get("sub"), "email": payload.get("email"), "name": payload.get("name"), "role": payload.get("role", "researcher"), "auth_mode": "local"}

    if not auth_required():
        return {"sub": "local-demo-user", "email": "local-demo@comp6265.local", "name": "Local demo user", "role": "researcher", "auth_mode": "local-demo"}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")


def require_admin_user(user: dict[str, Any]) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

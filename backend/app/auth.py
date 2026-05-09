from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import Header, HTTPException, status


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def auth_required() -> bool:
    return _truthy(os.getenv("REQUIRE_AUTH"), default=False)


@lru_cache(maxsize=1)
def _cognito_settings() -> dict[str, str]:
    region = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or ""
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}" if region and user_pool_id else ""
    return {
        "region": region,
        "user_pool_id": user_pool_id,
        "app_client_id": app_client_id,
        "issuer": issuer,
        "jwks_url": f"{issuer}/.well-known/jwks.json" if issuer else "",
    }


@lru_cache(maxsize=1)
def _jwks_client():
    settings = _cognito_settings()
    if not settings["jwks_url"]:
        raise RuntimeError("Cognito JWKS URL is not configured")
    try:
        from jwt import PyJWKClient
    except Exception as exc:  # pragma: no cover - only hit when auth is enabled without dependency
        raise RuntimeError("PyJWT is required when REQUIRE_AUTH=true") from exc
    return PyJWKClient(settings["jwks_url"])


def _verify_cognito_token(token: str) -> dict[str, Any]:
    settings = _cognito_settings()
    if not settings["issuer"] or not settings["app_client_id"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cognito auth is required but COGNITO_REGION/AWS_REGION, COGNITO_USER_POOL_ID, or COGNITO_APP_CLIENT_ID is missing.",
        )

    try:
        import jwt
        from jwt import InvalidAudienceError, InvalidTokenError

        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=settings["app_client_id"],
                issuer=settings["issuer"],
            )
        except InvalidAudienceError:
            # Cognito access tokens use client_id instead of aud. ID tokens use aud.
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=settings["issuer"],
                options={"verify_aud": False},
            )
            if claims.get("client_id") != settings["app_client_id"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token client_id does not match this app client")

        token_use = claims.get("token_use")
        if token_use not in {"access", "id"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported Cognito token type")
        return claims
    except HTTPException:
        raise
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Cognito token: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Could not validate Cognito token: {exc}") from exc


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Return the authenticated user.

    Local/docker development keeps REQUIRE_AUTH=false, so the project remains easy to test.
    In AWS, set REQUIRE_AUTH=true and provide Cognito env vars to enforce JWT checks.
    """
    if not auth_required():
        return {
            "sub": "local-demo-user",
            "email": "local-demo@comp6265.local",
            "name": "Local demo user",
            "auth_mode": "local-demo",
        }

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    claims = _verify_cognito_token(token)
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email") or claims.get("username") or claims.get("cognito:username"),
        "name": claims.get("name") or claims.get("given_name") or claims.get("email"),
        "username": claims.get("cognito:username") or claims.get("username"),
        "token_use": claims.get("token_use"),
        "auth_mode": "cognito-google",
    }

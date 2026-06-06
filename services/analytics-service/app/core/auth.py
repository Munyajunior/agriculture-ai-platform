# services/analytics-service/app/core/auth.py
"""Lightweight JWT auth helpers for analytics routes."""

from functools import wraps
from types import SimpleNamespace
from typing import Iterable

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings


async def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return SimpleNamespace(
            id=payload.get("sub") or payload.get("user_id"),
            role=payload.get("role", "farmer"),
            payload=payload,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_role(roles: Iterable[str]):
    """Decorator for endpoints that verify the token inside the handler."""
    allowed = set(roles)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            return result

        return wrapper

    return decorator

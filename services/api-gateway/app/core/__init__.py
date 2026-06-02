# services/api-gateway/app/core/__init__.py
"""Core modules for API Gateway"""

from .redis_client import redis_client
from .rate_limiter import limiter
from .dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
    get_current_agronomist_user,
)

__all__ = [
    "redis_client",
    "limiter",
    "get_current_user",
    "get_current_active_user",
    "get_current_admin_user",
    "get_current_agronomist_user",
]
# services/auth-service/app/api/v1/__init__.py
"""API v1 router for authentication service"""

from fastapi import APIRouter
from . import auth, users, oauth, api_keys, sessions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
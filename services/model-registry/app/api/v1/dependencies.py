# services/model-registry/app/api/v1/dependencies.py
"""API dependencies for Model Registry"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ...config import settings

security = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Verify API key for model registry access"""
    
    api_key = credentials.credentials
    
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return api_key
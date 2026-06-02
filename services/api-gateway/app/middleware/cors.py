# services/api-gateway/app/middleware/cors.py
"""CORS configuration for API Gateway"""

from fastapi.middleware.cors import CORSMiddleware
from ..config import settings


class CORSMiddlewareConfig:
    """Configure CORS for the application"""
    
    @staticmethod
    def get_cors_config() -> dict:
        """Get CORS configuration dictionary"""
        return {
            "allow_origins": settings.CORS_ORIGINS,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "Accept",
                "Origin",
                "X-Requested-With",
                "X-Request-ID",
            ],
            "expose_headers": [
                "X-Request-ID",
                "X-Process-Time-MS",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
            ],
            "max_age": 86400,  # 24 hours
        }
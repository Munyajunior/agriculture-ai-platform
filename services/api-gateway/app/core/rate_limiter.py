# services/api-gateway/app/core/rate_limiter.py
"""Rate limiting implementation"""

from typing import Dict, Tuple, Optional
import time
from fastapi import Request, HTTPException, status
from .redis_client import redis_client


class RateLimiter:
    """Token bucket rate limiter with Redis backend"""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_multiplier: float = 1.5
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = int(requests_per_minute * burst_multiplier)
    
    async def check_rate_limit(
        self,
        key: str,
        requests_per_minute: Optional[int] = None
    ) -> Tuple[bool, Dict]:
        """
        Check if request is within rate limit
        
        Returns:
            (is_allowed, headers_info)
        """
        limit = requests_per_minute or self.requests_per_minute
        window_size = 60  # 1 minute in seconds
        
        current_time = time.time()
        window_key = f"rate_limit:{key}:{int(current_time / window_size)}"
        
        # Get current count
        current_count = await redis_client.get(window_key)
        if current_count is None:
            current_count = 0
        
        # Check if limit exceeded
        if int(current_count) >= limit:
            return False, {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int((int(current_time / window_size) + 1) * window_size))
            }
        
        # Increment counter
        new_count = await redis_client.increment(window_key, 1, window_size)
        
        return True, {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(limit - new_count),
            "X-RateLimit-Reset": str(int((int(current_time / window_size) + 1) * window_size))
        }


class IPRateLimiter(RateLimiter):
    """Rate limiter based on IP address"""
    
    async def check(self, request: Request) -> Tuple[bool, Dict]:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ip:{client_ip}"
        return await self.check_rate_limit(key)


class UserRateLimiter(RateLimiter):
    """Rate limiter based on user ID"""
    
    async def check(self, user_id: str) -> Tuple[bool, Dict]:
        key = f"user:{user_id}"
        return await self.check_rate_limit(key)


class EndpointRateLimiter(RateLimiter):
    """Rate limiter based on endpoint"""
    
    async def check(self, endpoint: str) -> Tuple[bool, Dict]:
        key = f"endpoint:{endpoint}"
        return await self.check_rate_limit(key)


# Create rate limiter instances
limiter = IPRateLimiter(requests_per_minute=100)
user_limiter = UserRateLimiter(requests_per_minute=300)
auth_limiter = IPRateLimiter(requests_per_minute=10)  # Stricter for auth
admin_limiter = UserRateLimiter(requests_per_minute=500)  # Higher for admins


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI middleware for rate limiting"""
    # Determine which rate limiter to use
    path = request.url.path
    
    if path.startswith("/api/v1/auth"):
        is_allowed, headers = await auth_limiter.check(request)
    elif path.startswith("/api/v1/admin"):
        # For admin, we need user ID, but we don't have it yet
        is_allowed, headers = await limiter.check(request)
    else:
        is_allowed, headers = await limiter.check(request)
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers=headers
        )
    
    response = await call_next(request)
    
    # Add rate limit headers to response
    for key, value in headers.items():
        response.headers[key] = value
    
    return response
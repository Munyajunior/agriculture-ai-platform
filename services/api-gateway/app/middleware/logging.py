# services/api-gateway/app/middleware/logging.py
"""Request logging middleware"""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = f"{int(time.time())}-{id(request)}"
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        
        # Log request details
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = (time.time() - start_time) * 1000
            
            # Log response
            await self._log_response(request, response, process_time, request_id)
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-MS"] = str(int(process_time))
            
            return response
            
        except Exception as e:
            logger.error(
                f"Request failed: {request.method} {request.url.path} | "
                f"Request ID: {request_id} | Error: {str(e)}"
            )
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details"""
        headers = dict(request.headers)
        # Remove sensitive headers
        headers.pop("authorization", None)
        headers.pop("cookie", None)
        
        logger.info(
            f"Request | ID: {request_id} | "
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Client: {request.client.host if request.client else 'unknown'} | "
            f"User-Agent: {headers.get('user-agent', 'unknown')}"
        )
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        process_time: float,
        request_id: str
    ):
        """Log response details"""
        logger.info(
            f"Response | ID: {request_id} | "
            f"Status: {response.status_code} | "
            f"Time: {process_time:.2f}ms | "
            f"Path: {request.method} {request.url.path}"
        )
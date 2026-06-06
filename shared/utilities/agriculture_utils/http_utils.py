# shared/utilities/agriculture_utils/http_utils.py
"""Standardised HTTP error helpers for FastAPI services."""

from fastapi import HTTPException, status


def service_error(detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> HTTPException:
    """Return a 500 (or custom) HTTPException with a consistent structure."""
    return HTTPException(status_code=status_code, detail=detail)


def not_found(detail: str = "Resource not found") -> HTTPException:
    """Return a 404 HTTPException."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def unauthorized(detail: str = "Not authenticated") -> HTTPException:
    """Return a 401 HTTPException."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(detail: str = "Permission denied") -> HTTPException:
    """Return a 403 HTTPException."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def bad_request(detail: str) -> HTTPException:
    """Return a 400 HTTPException."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

# services/api-gateway/app/clients/base.py
"""Shared async HTTP client utilities for downstream services."""

import logging
from typing import Any

import httpx


class BaseServiceClient:
    """Small wrapper around httpx for gateway service-to-service calls."""

    service_name = "service"

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        data: dict[str, Any] | None = None,
        token: str | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request and return the JSON response body."""
        headers = {"Authorization": f"Bearer {token}"} if token else None
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=data if method.upper() == "GET" else None,
                    json=data if method.upper() not in {"GET", "DELETE"} and files is None else None,
                    data=data if files is not None else None,
                    files=files,
                )
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
            except httpx.HTTPStatusError as exc:
                self.logger.error("%s error: %s", self.service_name, exc.response.text)
                raise
            except httpx.HTTPError as exc:
                self.logger.error("%s request failed: %s", self.service_name, exc)
                raise

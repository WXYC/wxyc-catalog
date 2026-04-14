"""Async HTTP client with rate limiting and exponential backoff retry.

Provides:
- Shared httpx.AsyncClient session (reused across requests)
- Configurable rate limiter (token-bucket via asyncio primitives)
- Exponential backoff retry on 429 (Too Many Requests) and 403 (Forbidden)
- Request/response logging
- Configurable timeout
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 403}


class HttpSource:
    """Async HTTP client with rate limiting and exponential backoff retry.

    Args:
        base_url: Base URL for all requests. If ``None``, full URLs must be provided.
        rate_limit: Maximum number of requests per ``rate_window``.
        rate_window: Time window in seconds for the rate limit.
        max_retries: Maximum number of retries on retryable status codes.
        timeout: Request timeout in seconds.
        headers: Extra headers to include with every request.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        rate_limit: float = 60.0,
        rate_window: float = 60.0,
        max_retries: int = 3,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._rate_limit = rate_limit
        self._rate_window = rate_window
        self._max_retries = max_retries
        self._timeout = timeout
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None

        # Token-bucket rate limiter state
        self._interval = rate_window / rate_limit if rate_limit > 0 else 0.0
        self._last_request_time: float | None = None
        self._rate_lock = asyncio.Lock()

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared client, creating it lazily."""
        if self._client is None or self._client.is_closed:
            kwargs: dict[str, Any] = {
                "timeout": self._timeout,
                "headers": self._headers,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def _wait_for_rate_limit(self) -> None:
        """Wait until the rate limiter allows the next request."""
        if self._interval <= 0:
            return

        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            if self._last_request_time is not None:
                elapsed = now - self._last_request_time
                wait = self._interval - elapsed
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        """Execute an HTTP request with rate limiting and retry.

        Returns the response on success, or ``None`` if all retries are exhausted.
        """
        client = self._get_client()

        for attempt in range(1 + self._max_retries):
            await self._wait_for_rate_limit()
            try:
                response = await getattr(client, method)(path, **kwargs)
            except httpx.HTTPError:
                logger.warning("HTTP %s %s failed", method.upper(), path, exc_info=True)
                return None

            if response.status_code not in RETRYABLE_STATUS_CODES:
                return response

            if attempt < self._max_retries:
                delay = 2**attempt * 0.1  # 0.1s, 0.2s, 0.4s, ...
                logger.info(
                    "Retryable %d from %s %s, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    method.upper(),
                    path,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)

        logger.warning(
            "Exhausted %d retries for %s %s", self._max_retries, method.upper(), path
        )
        return None

    async def get(self, path: str, **kwargs: Any) -> httpx.Response | None:
        """Send a GET request.

        Args:
            path: URL path (appended to ``base_url``) or full URL.
            **kwargs: Extra arguments passed to ``httpx.AsyncClient.get()``.

        Returns:
            The response, or ``None`` if the request failed or retries were exhausted.
        """
        return await self._request("get", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response | None:
        """Send a POST request.

        Args:
            path: URL path (appended to ``base_url``) or full URL.
            **kwargs: Extra arguments passed to ``httpx.AsyncClient.post()``.

        Returns:
            The response, or ``None`` if the request failed or retries were exhausted.
        """
        return await self._request("post", path, **kwargs)

    async def close(self) -> None:
        """Close the underlying HTTP client, if one was created."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

import time

from wxyc_catalog.sources.http import HttpSource


class TestHttpSourceRateLimiting:
    """HttpSource should respect configured rate limits."""

    async def test_rate_limit_delays_requests(self, httpx_mock):
        """Consecutive requests should be delayed to respect rate limit."""
        httpx_mock.add_response(status_code=200)
        httpx_mock.add_response(status_code=200)

        # 1 request per second rate limit
        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1.0,
            rate_window=1.0,
        )
        start = time.monotonic()
        await source.get("/a")
        await source.get("/b")
        elapsed = time.monotonic() - start
        # Second request should be delayed by ~1 second
        assert elapsed >= 0.9
        await source.close()


class TestHttpSourceRetry:
    """HttpSource should retry on 429 and 403 with exponential backoff."""

    async def test_retry_on_429(self, httpx_mock):
        """Should retry on 429 Too Many Requests."""
        httpx_mock.add_response(status_code=429)
        httpx_mock.add_response(status_code=200, json={"ok": True})

        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1000,
            max_retries=3,
        )
        response = await source.get("/test")
        assert response is not None
        assert response.status_code == 200
        await source.close()

    async def test_retry_on_403(self, httpx_mock):
        """Should retry on 403 Forbidden (Wikidata rate limit)."""
        httpx_mock.add_response(status_code=403)
        httpx_mock.add_response(status_code=200, json={"ok": True})

        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1000,
            max_retries=3,
        )
        response = await source.get("/test")
        assert response is not None
        assert response.status_code == 200
        await source.close()

    async def test_returns_none_after_max_retries(self, httpx_mock):
        """Should return None after exhausting all retries."""
        for _ in range(4):
            httpx_mock.add_response(status_code=429)

        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1000,
            max_retries=3,
        )
        response = await source.get("/test")
        assert response is None
        await source.close()

    async def test_no_retry_on_non_retryable_status(self, httpx_mock):
        """Should not retry on 404, 500, or other non-retryable codes."""
        httpx_mock.add_response(status_code=404)

        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1000,
            max_retries=3,
        )
        response = await source.get("/test")
        assert response is not None
        assert response.status_code == 404
        await source.close()


class TestHttpSourcePost:
    """HttpSource should support POST requests."""

    async def test_post_request(self, httpx_mock):
        """post() should send a POST request."""
        httpx_mock.add_response(status_code=200, json={"created": True})

        source = HttpSource(
            base_url="https://example.com",
            rate_limit=1000,
        )
        response = await source.post("/items", json={"name": "test"})
        assert response is not None
        assert response.status_code == 200
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        await source.close()


class TestHttpSourceClose:
    """HttpSource close() should clean up the client."""

    async def test_close_is_safe_without_requests(self):
        """close() should be safe to call even if no requests were made."""
        source = HttpSource(base_url="https://example.com", rate_limit=1000)
        await source.close()  # should not raise

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from wxyc_catalog.sources.pg import PgSource


class TestPgSourceLazyConnect:
    """PgSource should create the pool on first query, not at init time."""

    async def test_no_pool_at_init(self):
        """Pool should not be created during __init__."""
        source = PgSource("postgresql://localhost/test")
        assert source._pool is None

    async def test_pool_created_on_first_query(self):
        """Pool should be created when first query is executed."""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_pool.fetch = AsyncMock(return_value=[])
            mock_create.return_value = mock_pool
            source = PgSource("postgresql://localhost/test")
            await source.fetchall("SELECT 1")
            mock_create.assert_awaited_once()


class TestPgSourceGracefulNone:
    """PgSource should return None on connection failure, not raise."""

    async def test_none_dsn_returns_none(self):
        """When dsn is None, all queries should return None."""
        source = PgSource(None)
        result = await source.fetchall("SELECT 1")
        assert result is None

    async def test_connection_failure_returns_none(self):
        """When connection fails, queries should return None."""
        with patch("asyncpg.create_pool", new_callable=AsyncMock, side_effect=Exception("refused")):
            source = PgSource("postgresql://bad-host/db")
            result = await source.fetchall("SELECT 1")
            assert result is None

    async def test_fetchone_none_dsn_returns_none(self):
        """fetchone() should also return None when dsn is None."""
        source = PgSource(None)
        result = await source.fetchone("SELECT 1")
        assert result is None

    async def test_execute_none_dsn_returns_none(self):
        """execute() should also return None when dsn is None."""
        source = PgSource(None)
        result = await source.execute("SELECT 1")
        assert result is None

    async def test_query_after_pool_close_reconnects_or_returns_none(self):
        """After pool is closed, queries should attempt reconnect or return None."""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_pool.fetch = AsyncMock(side_effect=Exception("pool closed"))
            mock_pool.is_closing = MagicMock(return_value=True)
            mock_create.return_value = mock_pool
            source = PgSource("postgresql://localhost/test")
            result = await source.fetchall("SELECT 1")
            assert result is None


class TestPgSourceReconnect:
    """PgSource should reconnect when the pool is closed or broken."""

    async def test_reconnects_after_closed_pool(self):
        """A new pool should be created after the old one is closed."""
        call_count = 0

        async def create_pool_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_pool = AsyncMock()
            if call_count == 1:
                mock_pool.fetch = AsyncMock(side_effect=Exception("closed"))
                mock_pool.is_closing = MagicMock(return_value=True)
            else:
                mock_pool.fetch = AsyncMock(return_value=[{"id": 1}])
                mock_pool.is_closing = MagicMock(return_value=False)
            return mock_pool

        with patch(
            "asyncpg.create_pool",
            new_callable=AsyncMock,
            side_effect=create_pool_side_effect,
        ):
            source = PgSource("postgresql://localhost/test")
            # First call triggers pool creation, pool is "closed"
            await source.fetchall("SELECT 1")
            # Force reconnect by resetting internal pool
            source._pool = None
            result = await source.fetchall("SELECT 1")
            assert result is not None


class TestPgSourceBatchHelpers:
    """PgSource batch query helpers."""

    async def test_fetch_with_unnest(self):
        """fetch_with_unnest should pass values as unnest parameter."""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_pool.fetch = AsyncMock(return_value=[])
            mock_create.return_value = mock_pool
            source = PgSource("postgresql://localhost/test")
            await source.fetch_with_unnest(
                "SELECT * FROM t WHERE name = ANY($1)",
                ["alice", "bob"],
            )
            mock_pool.fetch.assert_awaited_once()

    async def test_fetch_with_unnest_none_dsn(self):
        """fetch_with_unnest should return None when dsn is None."""
        source = PgSource(None)
        result = await source.fetch_with_unnest(
            "SELECT * FROM t WHERE name = ANY($1)",
            ["alice", "bob"],
        )
        assert result is None


class TestPgSourceClose:
    """PgSource close() should clean up resources."""

    async def test_close_pool(self):
        """close() should close the underlying pool."""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_pool.fetch = AsyncMock(return_value=[])
            mock_pool.close = AsyncMock()
            mock_create.return_value = mock_pool
            source = PgSource("postgresql://localhost/test")
            await source.fetchall("SELECT 1")
            await source.close()
            mock_pool.close.assert_awaited_once()

    async def test_close_no_pool(self):
        """close() should be safe to call when no pool was created."""
        source = PgSource("postgresql://localhost/test")
        await source.close()  # should not raise

"""Async PostgreSQL connection pool with lazy connect and graceful degradation.

Provides:
- Lazy connection: pool created on first query, not at init time
- Graceful None: returns None instead of raising on connection failure
- Reconnect: automatically reconnects if pool is closed
- Batch helpers: fetch_with_unnest()
- Configurable pool size via min_size/max_size
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class PgSource:
    """Async PostgreSQL connection pool with lazy connect and graceful degradation.

    All query methods return ``None`` on connection failure instead of raising,
    letting callers implement fallback logic (e.g., falling back to an HTTP API
    when a PostgreSQL cache is unavailable).

    Args:
        dsn: PostgreSQL connection string, or ``None`` to disable all queries.
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.
    """

    def __init__(self, dsn: str | None, *, min_size: int = 1, max_size: int = 5) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def get_pool(self) -> asyncpg.Pool | None:
        """Return the connection pool, creating it lazily on first call.

        Returns ``None`` if ``dsn`` was not provided or if connecting fails.
        """
        if self._dsn is None:
            return None

        if self._pool is not None and not self._pool.is_closing():
            return self._pool

        try:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            return self._pool
        except Exception:
            logger.warning("Failed to connect to PostgreSQL at %s", self._dsn, exc_info=True)
            self._pool = None
            return None

    async def fetchall(self, query: str, *args: Any) -> list[asyncpg.Record] | None:
        """Execute a query and return all rows, or ``None`` on failure.

        Args:
            query: SQL query string with ``$1``, ``$2``, ... placeholders.
            *args: Positional parameters for the query.
        """
        pool = await self.get_pool()
        if pool is None:
            return None
        try:
            return await pool.fetch(query, *args)
        except Exception:
            logger.warning("Query failed: %s", query, exc_info=True)
            return None

    async def fetchone(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and return the first row, or ``None`` on failure.

        Args:
            query: SQL query string with ``$1``, ``$2``, ... placeholders.
            *args: Positional parameters for the query.
        """
        pool = await self.get_pool()
        if pool is None:
            return None
        try:
            return await pool.fetchrow(query, *args)
        except Exception:
            logger.warning("Query failed: %s", query, exc_info=True)
            return None

    async def execute(self, query: str, *args: Any) -> str | None:
        """Execute a query and return the status string, or ``None`` on failure.

        Args:
            query: SQL query string with ``$1``, ``$2``, ... placeholders.
            *args: Positional parameters for the query.
        """
        pool = await self.get_pool()
        if pool is None:
            return None
        try:
            return await pool.execute(query, *args)
        except Exception:
            logger.warning("Query failed: %s", query, exc_info=True)
            return None

    async def fetch_with_unnest(
        self, query: str, values: list, type_: str = "text"
    ) -> list[asyncpg.Record] | None:
        """Execute a query passing *values* as an unnested array parameter.

        Useful for ``WHERE col = ANY($1)`` patterns where ``$1`` is a list.

        Args:
            query: SQL query with a ``$1`` placeholder for the array.
            values: List of values to pass as the array parameter.
            type_: PostgreSQL type name for the array elements (default ``"text"``).
        """
        pool = await self.get_pool()
        if pool is None:
            return None
        try:
            return await pool.fetch(query, values)
        except Exception:
            logger.warning("Query failed: %s", query, exc_info=True)
            return None

    async def close(self) -> None:
        """Close the connection pool, if one was created."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

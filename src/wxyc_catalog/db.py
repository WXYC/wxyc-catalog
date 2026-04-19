"""MySQL connection utilities for WXYC catalog databases.

Supports MySQL 4.1+ (Kattare runs MySQL 4.1.22) via mysql-connector-python,
with pymysql as a fallback for newer servers.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


def connect_mysql(db_url: str):
    """Connect to MySQL using a URL string.

    Uses mysql-connector-python when available (supports MySQL 4.1's old password
    auth), falling back to pymysql for newer servers.

    Args:
        db_url: MySQL connection URL (mysql://user:pass@host:port/dbname).

    Returns:
        A DB-API 2.0 connection object.
    """
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    user = unquote(parsed.username or "root")
    password = unquote(parsed.password or "")
    database = parsed.path.lstrip("/")

    try:
        import mysql.connector

        logger.info("Connecting to MySQL via mysql-connector-python (%s:%d)", host, port)
        return mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8",
            use_pure=True,
        )
    except ImportError:
        pass

    import pymysql

    logger.info("Connecting to MySQL via pymysql (%s:%d)", host, port)
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8",
    )

"""MySQL connection utilities for WXYC catalog databases.

Supports MySQL 4.1+ (Kattare runs MySQL 4.1.22 with old-format password hashes)
via mysqlclient (C-based libmysqlclient), with pymysql as a fallback for newer servers.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


def connect_mysql(db_url: str):
    """Connect to MySQL using a URL string.

    Tries mysqlclient (C-based) first — its libmysqlclient handles MySQL 4.1's
    old password auth natively. Falls back to pymysql for newer servers where
    old password auth isn't needed.

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
        import MySQLdb

        logger.info("Connecting to MySQL via mysqlclient (%s:%d)", host, port)
        return MySQLdb.connect(
            host=host,
            port=port,
            user=user,
            passwd=password,
            db=database,
            charset="utf8",
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

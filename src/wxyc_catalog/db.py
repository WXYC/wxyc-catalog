"""MySQL connection utilities for WXYC catalog databases.

Supports MySQL 4.1+ (Kattare runs MySQL 4.1.22 with old-format password hashes)
via MariaDB Connector/Python, which maintains backward compatibility with old
MySQL auth protocols. Falls back to mysqlclient, then pymysql.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def connect_mysql(db_url: str):
    """Connect to MySQL using a URL string.

    Tries drivers in order: mariadb (best old-password support), mysqlclient,
    pymysql. Kattare runs MySQL 4.1.22 with old-format password hashes; the
    MariaDB connector handles this natively.

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
        import mariadb

        logger.info("Connecting to MySQL via mariadb connector (%s:%d)", host, port)
        return mariadb.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except ImportError:
        pass

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

    if pymysql is None:
        raise ImportError("No MySQL driver available (tried mariadb, mysqlclient, pymysql)")

    logger.info("Connecting to MySQL via pymysql (%s:%d)", host, port)
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8",
    )

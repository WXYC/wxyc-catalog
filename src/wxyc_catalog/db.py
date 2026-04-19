"""MySQL connection utilities for WXYC catalog databases.

Note: Python MySQL drivers (pymysql, mysqlclient, mysql-connector-python) do not
support MySQL 4.1's old-format password hashes. The daily library sync workflow
uses the MariaDB ``mysql`` CLI client instead (see discogs-etl/scripts/sync-library.sh).
This module works with MySQL 5.x+ servers.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

import pymysql

logger = logging.getLogger(__name__)


def connect_mysql(db_url: str):
    """Connect to MySQL using a URL string.

    Args:
        db_url: MySQL connection URL (mysql://user:pass@host:port/dbname).

    Returns:
        A pymysql connection object.
    """
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    user = unquote(parsed.username or "root")
    password = unquote(parsed.password or "")
    database = parsed.path.lstrip("/")

    logger.info("Connecting to MySQL via pymysql (%s:%d)", host, port)
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8",
    )

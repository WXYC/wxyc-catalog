"""MySQL connection utilities for WXYC catalog databases.

Note: Python MySQL drivers (pymysql, mysqlclient, mysql-connector-python) do not
support MySQL 4.1's old-format password hashes. The daily library sync workflow
uses the MariaDB ``mysql`` CLI client instead (see discogs-etl/scripts/sync-library.sh).
This module works with MySQL 5.x+ servers.

``pymysql`` is imported lazily inside ``connect_mysql()`` so consumers that
only use the SQLite export or the PG ``BackendServiceSource`` don't have to
install it. The package's ``[mysql]`` extra still pulls it for users that
do call this function.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


def connect_mysql(db_url: str):
    """Connect to MySQL using a URL string.

    Args:
        db_url: MySQL connection URL (mysql://user:pass@host:port/dbname).

    Returns:
        A pymysql connection object.

    Raises:
        ImportError: ``pymysql`` is not installed. Install ``wxyc-catalog[mysql]``
            to pull it in, or fall back to the MariaDB CLI path used by
            ``scripts/sync-library.sh`` for MySQL 4.1 servers.
    """
    try:
        import pymysql
    except ImportError as exc:
        raise ImportError(
            "pymysql is required for connect_mysql(). Install it via "
            "`pip install wxyc-catalog[mysql]` (or directly: `pip install pymysql`)."
        ) from exc

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

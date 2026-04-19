"""Unit tests for wxyc_catalog.db."""

from __future__ import annotations

import builtins
from unittest.mock import patch

from wxyc_catalog.db import connect_mysql

# Force connect_mysql to fall through to pymysql by blocking mariadb and MySQLdb imports.
_real_import = builtins.__import__


def _import_no_mysql(name, *args, **kwargs):
    if name in ("mariadb", "MySQLdb"):
        raise ImportError(f"mocked: {name} not available")
    return _real_import(name, *args, **kwargs)


class TestConnectMysql:
    """connect_mysql() parses a URL and returns a pymysql connection."""

    @patch("wxyc_catalog.db.pymysql")
    @patch("builtins.__import__", side_effect=_import_no_mysql)
    def test_parses_full_url(self, _mock_import, mock_pymysql) -> None:
        connect_mysql("mysql://wxyc:secret@db.example.com:3307/wxycmusic")
        mock_pymysql.connect.assert_called_once_with(
            host="db.example.com",
            port=3307,
            user="wxyc",
            password="secret",
            database="wxycmusic",
            charset="utf8",
        )

    @patch("wxyc_catalog.db.pymysql")
    @patch("builtins.__import__", side_effect=_import_no_mysql)
    def test_defaults_for_minimal_url(self, _mock_import, mock_pymysql) -> None:
        connect_mysql("mysql:///mydb")
        mock_pymysql.connect.assert_called_once_with(
            host="localhost",
            port=3306,
            user="root",
            password="",
            database="mydb",
            charset="utf8",
        )

    @patch("wxyc_catalog.db.pymysql")
    @patch("builtins.__import__", side_effect=_import_no_mysql)
    def test_returns_connection(self, _mock_import, mock_pymysql) -> None:
        result = connect_mysql("mysql://u:p@h/db")
        assert result == mock_pymysql.connect.return_value

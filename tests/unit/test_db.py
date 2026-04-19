"""Unit tests for wxyc_catalog.db."""

from __future__ import annotations

import logging
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

DB_URL = "mysql://wxyc:secret@db.example.com:3307/wxycmusic"


def _make_mock_module(name: str) -> ModuleType:
    """Create a mock module with a connect() method."""
    mod = MagicMock(spec=ModuleType)
    mod.__name__ = name
    mod.connect = MagicMock()
    return mod


class TestConnectMysql:
    """connect_mysql() parses a URL and connects via the first available driver."""

    def test_parses_full_url(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql("mysql://wxyc:secret@db.example.com:3307/wxycmusic")
            mock_pymysql.connect.assert_called_once_with(
                host="db.example.com",
                port=3307,
                user="wxyc",
                password="secret",
                database="wxycmusic",
                charset="utf8",
            )

    def test_defaults_for_minimal_url(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql("mysql:///mydb")
            mock_pymysql.connect.assert_called_once_with(
                host="localhost",
                port=3306,
                user="root",
                password="",
                database="mydb",
                charset="utf8",
            )

    def test_returns_connection(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            result = db_mod.connect_mysql("mysql://u:p@h/db")
            assert result == mock_pymysql.connect.return_value


# ---------------------------------------------------------------------------
# Driver fallback chain
# ---------------------------------------------------------------------------


class TestDriverFallbackChain:
    """connect_mysql() tries mariadb, then mysqlclient, then pymysql."""

    def test_uses_mariadb_when_available(self) -> None:
        mock_mariadb = _make_mock_module("mariadb")
        with patch.dict(sys.modules, {"mariadb": mock_mariadb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            mock_mariadb.connect.assert_called_once()

    def test_falls_back_to_mysqlclient_when_mariadb_unavailable(self) -> None:
        mock_mysqldb = _make_mock_module("MySQLdb")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": mock_mysqldb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            mock_mysqldb.connect.assert_called_once()
            # mysqlclient uses passwd= and db= instead of password= and database=
            call_kwargs = mock_mysqldb.connect.call_args.kwargs
            assert "passwd" in call_kwargs
            assert "db" in call_kwargs

    def test_falls_back_to_pymysql_when_both_unavailable(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            mock_pymysql.connect.assert_called_once()

    def test_mariadb_connect_returns_connection(self) -> None:
        mock_mariadb = _make_mock_module("mariadb")
        sentinel = object()
        mock_mariadb.connect.return_value = sentinel
        with patch.dict(sys.modules, {"mariadb": mock_mariadb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            result = db_mod.connect_mysql(DB_URL)
            assert result is sentinel

    def test_mysqlclient_connect_returns_connection(self) -> None:
        mock_mysqldb = _make_mock_module("MySQLdb")
        sentinel = object()
        mock_mysqldb.connect.return_value = sentinel
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": mock_mysqldb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            result = db_mod.connect_mysql(DB_URL)
            assert result is sentinel


# ---------------------------------------------------------------------------
# URL decoding
# ---------------------------------------------------------------------------


class TestUrlDecoding:
    """connect_mysql() URL-decodes username and password."""

    def test_url_decodes_username(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql("mysql://wxyc%40host:secret@db.example.com:3306/wxycmusic")
            call_kwargs = mock_pymysql.connect.call_args.kwargs
            assert call_kwargs["user"] == "wxyc@host"

    def test_url_decodes_password_with_special_chars(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql("mysql://wxyc:p%40ss%23w0rd@db.example.com:3306/wxycmusic")
            call_kwargs = mock_pymysql.connect.call_args.kwargs
            assert call_kwargs["password"] == "p@ss#w0rd"


# ---------------------------------------------------------------------------
# Charset parameter
# ---------------------------------------------------------------------------


class TestCharsetParameter:
    """mysqlclient and pymysql get charset='utf8'; mariadb does not."""

    def test_mysqlclient_passes_charset_utf8(self) -> None:
        mock_mysqldb = _make_mock_module("MySQLdb")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": mock_mysqldb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            call_kwargs = mock_mysqldb.connect.call_args.kwargs
            assert call_kwargs["charset"] == "utf8"

    def test_pymysql_passes_charset_utf8(self) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            call_kwargs = mock_pymysql.connect.call_args.kwargs
            assert call_kwargs["charset"] == "utf8"

    def test_mariadb_does_not_pass_charset(self) -> None:
        mock_mariadb = _make_mock_module("mariadb")
        with patch.dict(sys.modules, {"mariadb": mock_mariadb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            db_mod.connect_mysql(DB_URL)
            call_kwargs = mock_mariadb.connect.call_args.kwargs
            assert "charset" not in call_kwargs


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestDriverLogging:
    """connect_mysql() logs which driver is being used."""

    def test_logs_mariadb_driver_info(self, caplog) -> None:
        mock_mariadb = _make_mock_module("mariadb")
        with patch.dict(sys.modules, {"mariadb": mock_mariadb}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            with caplog.at_level(logging.INFO, logger="wxyc_catalog.db"):
                db_mod.connect_mysql(DB_URL)
            assert "mariadb connector" in caplog.text.lower()

    def test_logs_pymysql_driver_info(self, caplog) -> None:
        mock_pymysql = _make_mock_module("pymysql")
        with patch.dict(sys.modules, {"mariadb": None, "MySQLdb": None, "pymysql": mock_pymysql}):
            from importlib import reload

            import wxyc_catalog.db as db_mod

            reload(db_mod)
            with caplog.at_level(logging.INFO, logger="wxyc_catalog.db"):
                db_mod.connect_mysql(DB_URL)
            assert "pymysql" in caplog.text.lower()

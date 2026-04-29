"""Unit tests for wxyc_catalog.db."""

from __future__ import annotations

import importlib
import logging
import sys
from unittest.mock import patch

import pytest

from wxyc_catalog.db import connect_mysql


class TestConnectMysql:
    """connect_mysql() parses a URL and connects via pymysql."""

    @patch("pymysql.connect")
    def test_parses_full_url(self, mock_connect) -> None:
        connect_mysql("mysql://wxyc:secret@db.example.com:3307/wxycmusic")
        mock_connect.assert_called_once_with(
            host="db.example.com",
            port=3307,
            user="wxyc",
            password="secret",
            database="wxycmusic",
            charset="utf8",
        )

    @patch("pymysql.connect")
    def test_defaults_for_minimal_url(self, mock_connect) -> None:
        connect_mysql("mysql:///mydb")
        mock_connect.assert_called_once_with(
            host="localhost",
            port=3306,
            user="root",
            password="",
            database="mydb",
            charset="utf8",
        )

    @patch("pymysql.connect")
    def test_returns_connection(self, mock_connect) -> None:
        result = connect_mysql("mysql://u:p@h/db")
        assert result == mock_connect.return_value


class TestUrlDecoding:
    """connect_mysql() URL-decodes username and password."""

    @patch("pymysql.connect")
    def test_url_decodes_username(self, mock_connect) -> None:
        connect_mysql("mysql://wxyc%40host:secret@db.example.com:3306/wxycmusic")
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs["user"] == "wxyc@host"

    @patch("pymysql.connect")
    def test_url_decodes_password_with_special_chars(self, mock_connect) -> None:
        connect_mysql("mysql://wxyc:p%40ss%23w0rd@db.example.com:3306/wxycmusic")
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs["password"] == "p@ss#w0rd"


class TestDriverLogging:
    """connect_mysql() logs connection info."""

    @patch("pymysql.connect")
    def test_logs_pymysql_driver_info(self, mock_connect, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="wxyc_catalog.db"):
            connect_mysql("mysql://u:p@db.example.com:3306/mydb")
        assert "pymysql" in caplog.text.lower()


class TestPymysqlImportIsLazy:
    """Module-load doesn't require pymysql to be installed.

    Regression: ``wxyc_catalog`` is consumed by services that don't use the
    MySQL TubafrenzySource at all (just the SQLite export path or the PG
    BackendServiceSource). Forcing them to install pymysql to even
    ``import wxyc_catalog`` is a wart we want to keep out — particularly
    after the publish-to-PyPI cleanup, where discogs-etl had to declare
    ``wxyc-catalog[mysql]`` to keep the import chain resolving.
    """

    def test_db_module_imports_without_pymysql(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Setting sys.modules['pymysql'] = None makes subsequent `import pymysql`
        # raise ImportError — the standard trick for masking optional deps.
        monkeypatch.setitem(sys.modules, "pymysql", None)
        # Force a fresh import of db so the masked pymysql is what it sees.
        monkeypatch.delitem(sys.modules, "wxyc_catalog.db", raising=False)
        importlib.import_module("wxyc_catalog.db")  # must not raise

    def test_connect_mysql_raises_clear_error_when_pymysql_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "pymysql", None)
        monkeypatch.delitem(sys.modules, "wxyc_catalog.db", raising=False)
        db = importlib.import_module("wxyc_catalog.db")
        with pytest.raises(ImportError, match=r"pymysql"):
            db.connect_mysql("mysql://u:p@h/d")

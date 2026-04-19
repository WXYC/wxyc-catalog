"""Unit tests for wxyc_catalog.db."""

from __future__ import annotations

import logging
from unittest.mock import patch

from wxyc_catalog.db import connect_mysql


class TestConnectMysql:
    """connect_mysql() parses a URL and connects via pymysql."""

    @patch("wxyc_catalog.db.pymysql")
    def test_parses_full_url(self, mock_pymysql) -> None:
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
    def test_defaults_for_minimal_url(self, mock_pymysql) -> None:
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
    def test_returns_connection(self, mock_pymysql) -> None:
        result = connect_mysql("mysql://u:p@h/db")
        assert result == mock_pymysql.connect.return_value


class TestUrlDecoding:
    """connect_mysql() URL-decodes username and password."""

    @patch("wxyc_catalog.db.pymysql")
    def test_url_decodes_username(self, mock_pymysql) -> None:
        connect_mysql("mysql://wxyc%40host:secret@db.example.com:3306/wxycmusic")
        call_kwargs = mock_pymysql.connect.call_args.kwargs
        assert call_kwargs["user"] == "wxyc@host"

    @patch("wxyc_catalog.db.pymysql")
    def test_url_decodes_password_with_special_chars(self, mock_pymysql) -> None:
        connect_mysql("mysql://wxyc:p%40ss%23w0rd@db.example.com:3306/wxycmusic")
        call_kwargs = mock_pymysql.connect.call_args.kwargs
        assert call_kwargs["password"] == "p@ss#w0rd"


class TestDriverLogging:
    """connect_mysql() logs connection info."""

    @patch("wxyc_catalog.db.pymysql")
    def test_logs_pymysql_driver_info(self, mock_pymysql, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="wxyc_catalog.db"):
            connect_mysql("mysql://u:p@db.example.com:3306/mydb")
        assert "pymysql" in caplog.text.lower()

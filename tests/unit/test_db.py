"""Unit tests for wxyc_catalog.db."""

from __future__ import annotations

from unittest.mock import patch

from wxyc_catalog.db import connect_mysql


class TestConnectMysql:
    """connect_mysql() parses a URL and returns a pymysql connection."""

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

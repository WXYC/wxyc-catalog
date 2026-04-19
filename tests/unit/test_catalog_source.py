"""Unit tests for wxyc_catalog.catalog_source."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wxyc_catalog.catalog_source import (
    BackendServiceSource,
    CatalogSource,
    TubafrenzySource,
    _strip_label_rows,
    _strip_name_rows,
    create_catalog_source,
)

# ---------------------------------------------------------------------------
# CatalogSource Protocol
# ---------------------------------------------------------------------------


class TestCatalogSourceProtocol:
    """CatalogSource is a runtime-checkable Protocol."""

    def test_tubafrenzy_source_is_catalog_source(self) -> None:
        assert issubclass(TubafrenzySource, CatalogSource)

    def test_backend_service_source_is_catalog_source(self) -> None:
        assert issubclass(BackendServiceSource, CatalogSource)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestStripNameRows:
    """_strip_name_rows extracts stripped non-empty names."""

    def test_filters_empty_none_whitespace(self) -> None:
        rows = [("Alice",), ("",), (None,), ("  ",), ("Bob",), (" Carol ",)]
        result = _strip_name_rows(rows)
        assert result == {"Alice", "Bob", "Carol"}

    def test_empty_input(self) -> None:
        assert _strip_name_rows([]) == set()


class TestStripLabelRows:
    """_strip_label_rows extracts stripped non-empty triples."""

    def test_filters_incomplete_rows(self) -> None:
        rows = [
            ("Stereolab", "Aluminum Tunes", "Duophonic"),
            ("Cat Power", "", "Matador"),
            (None, "Moon Pix", "Matador"),
            ("Juana Molina", "DOGA", "Sonamos"),
        ]
        result = _strip_label_rows(rows)
        assert result == {
            ("Stereolab", "Aluminum Tunes", "Duophonic"),
            ("Juana Molina", "DOGA", "Sonamos"),
        }

    def test_strips_whitespace(self) -> None:
        rows = [(" Sessa ", " Pequena Vertigem ", " Mexican Summer ")]
        result = _strip_label_rows(rows)
        assert result == {("Sessa", "Pequena Vertigem", "Mexican Summer")}

    def test_empty_input(self) -> None:
        assert _strip_label_rows([]) == set()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestCreateCatalogSource:
    """create_catalog_source returns the right implementation."""

    @patch("wxyc_catalog.catalog_source.TubafrenzySource")
    def test_creates_tubafrenzy_source(self, mock_cls) -> None:
        result = create_catalog_source("tubafrenzy", "mysql://user:pass@host/db")
        mock_cls.assert_called_once_with("mysql://user:pass@host/db")
        assert result == mock_cls.return_value

    @patch("wxyc_catalog.catalog_source.BackendServiceSource")
    def test_creates_backend_service_source(self, mock_cls) -> None:
        result = create_catalog_source("backend-service", "postgresql://user:pass@host/db")
        mock_cls.assert_called_once_with("postgresql://user:pass@host/db")
        assert result == mock_cls.return_value

    def test_raises_for_unknown_source(self) -> None:
        with pytest.raises(ValueError, match="Unknown catalog source"):
            create_catalog_source("unknown", "url")


# ---------------------------------------------------------------------------
# TubafrenzySource
# ---------------------------------------------------------------------------


def _make_mock_cursor(rows: list):
    """Create a mock pymysql cursor that supports context manager and iteration."""
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = rows
    cursor.__iter__ = MagicMock(return_value=iter(rows))
    return cursor


class TestTubafrenzySourceFetchLibraryRows:
    """TubafrenzySource.fetch_library_rows queries LIBRARY_RELEASE and returns dicts."""

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_list_of_dicts(self, mock_connect) -> None:
        cursor = _make_mock_cursor(
            [(1, "DOGA", "Juana Molina", "JM", 42, 1, "Rock", "LP", None, "Sonamos")]
        )
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        rows = source.fetch_library_rows()

        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["title"] == "DOGA"
        assert rows[0]["artist"] == "Juana Molina"
        assert rows[0]["call_letters"] == "JM"
        assert rows[0]["artist_call_number"] == 42
        assert rows[0]["release_call_number"] == 1
        assert rows[0]["genre"] == "Rock"
        assert rows[0]["format"] == "LP"
        assert rows[0]["alternate_artist_name"] is None
        assert rows[0]["label"] == "Sonamos"

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_null_label(self, mock_connect) -> None:
        """Rows without a matching rotation release should have label=None."""
        cursor = _make_mock_cursor(
            [(1, "DOGA", "Juana Molina", "JM", 42, 1, "Rock", "LP", None, None)]
        )
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        rows = source.fetch_library_rows()

        assert len(rows) == 1
        assert rows[0]["label"] is None


class TestTubafrenzySourceFetchAlternateNames:
    """TubafrenzySource.fetch_alternate_names returns set of name strings."""

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_set_of_strings(self, mock_connect) -> None:
        cursor = _make_mock_cursor([("Body Count",), ("Ice Cube",)])
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        names = source.fetch_alternate_names()
        assert names == {"Body Count", "Ice Cube"}

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_strips_whitespace(self, mock_connect) -> None:
        cursor = _make_mock_cursor([("  Body Count  ",)])
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        names = source.fetch_alternate_names()
        assert names == {"Body Count"}

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_excludes_empty_and_none(self, mock_connect) -> None:
        cursor = _make_mock_cursor([("Body Count",), ("",), (None,)])
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        names = source.fetch_alternate_names()
        assert names == {"Body Count"}


class TestTubafrenzySourceFetchCrossReferencedArtists:
    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_set_of_strings(self, mock_connect) -> None:
        cursor = _make_mock_cursor([("Ice-T",), ("Body Count",)])
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        names = source.fetch_cross_referenced_artists()
        assert names == {"Ice-T", "Body Count"}


class TestTubafrenzySourceFetchReleaseCrossRefArtists:
    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_set_of_strings(self, mock_connect) -> None:
        cursor = _make_mock_cursor([("John Coltrane",)])
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        names = source.fetch_release_cross_ref_artists()
        assert names == {"John Coltrane"}


class TestTubafrenzySourceFetchLibraryLabels:
    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_returns_set_of_tuples(self, mock_connect) -> None:
        cursor = _make_mock_cursor(
            [("Juana Molina", "DOGA", "Sonamos"), ("Stereolab", "Aluminum Tunes", "Duophonic")]
        )
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        labels = source.fetch_library_labels()
        assert labels == {
            ("Juana Molina", "DOGA", "Sonamos"),
            ("Stereolab", "Aluminum Tunes", "Duophonic"),
        }

    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_strips_and_excludes_empty(self, mock_connect) -> None:
        cursor = _make_mock_cursor(
            [
                (" Juana Molina ", " DOGA ", " Sonamos "),
                ("", "title", "label"),
                (None, None, None),
            ]
        )
        mock_connect.return_value.cursor.return_value = cursor

        source = TubafrenzySource("mysql://user:pass@host/db")
        labels = source.fetch_library_labels()
        assert labels == {("Juana Molina", "DOGA", "Sonamos")}


class TestTubafrenzySourceClose:
    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_close(self, mock_connect) -> None:
        source = TubafrenzySource("mysql://user:pass@host/db")
        source.close()
        mock_connect.return_value.close.assert_called_once()


class TestTubafrenzySourceContextManager:
    @patch("wxyc_catalog.catalog_source.connect_mysql")
    def test_context_manager(self, mock_connect) -> None:
        with TubafrenzySource("mysql://user:pass@host/db") as source:
            assert source is not None
        mock_connect.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# BackendServiceSource
# ---------------------------------------------------------------------------


def _make_pg_mock():
    """Create a mock psycopg module where conn.cursor() returns a context-managed cursor."""
    mock_psycopg = MagicMock()
    cursor = MagicMock()
    mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_psycopg, cursor


class TestBackendServiceSourceFetchLibraryRows:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_returns_list_of_dicts(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.description = [
            ("id",),
            ("title",),
            ("artist",),
            ("call_letters",),
            ("artist_call_number",),
            ("release_call_number",),
            ("genre",),
            ("format",),
            ("alternate_artist_name",),
            ("label",),
        ]
        cursor.fetchall.return_value = [
            (1, "DOGA", "Juana Molina", "JM", 42, 1, "Rock", "LP", None, None)
        ]

        source = BackendServiceSource("postgresql://user:pass@host/db")
        rows = source.fetch_library_rows()

        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["title"] == "DOGA"
        assert rows[0]["artist"] == "Juana Molina"
        assert rows[0]["label"] is None

    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_sql_references_wxyc_schema(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.description = []
        cursor.fetchall.return_value = []

        source = BackendServiceSource("postgresql://user:pass@host/db")
        source.fetch_library_rows()

        sql = cursor.execute.call_args[0][0]
        assert "wxyc_schema" in sql


class TestBackendServiceSourceFetchAlternateNames:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_returns_set_of_strings(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = [("Body Count",), ("Ice Cube",)]

        source = BackendServiceSource("postgresql://user:pass@host/db")
        names = source.fetch_alternate_names()
        assert names == {"Body Count", "Ice Cube"}


class TestBackendServiceSourceFetchCrossReferencedArtists:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_returns_set_of_strings(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = [("Ice-T",), ("Body Count",)]

        source = BackendServiceSource("postgresql://user:pass@host/db")
        names = source.fetch_cross_referenced_artists()
        assert names == {"Ice-T", "Body Count"}

    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_sql_references_artist_crossreference(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = []

        source = BackendServiceSource("postgresql://user:pass@host/db")
        source.fetch_cross_referenced_artists()

        sql = cursor.execute.call_args[0][0]
        assert "artist_crossreference" in sql


class TestBackendServiceSourceFetchReleaseCrossRefArtists:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_returns_set_of_strings(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = [("John Coltrane",)]

        source = BackendServiceSource("postgresql://user:pass@host/db")
        names = source.fetch_release_cross_ref_artists()
        assert names == {"John Coltrane"}

    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_sql_references_artist_library_crossreference(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = []

        source = BackendServiceSource("postgresql://user:pass@host/db")
        source.fetch_release_cross_ref_artists()

        sql = cursor.execute.call_args[0][0]
        assert "artist_library_crossreference" in sql


class TestBackendServiceSourceFetchLibraryLabels:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_returns_set_of_tuples(self, mock_psycopg) -> None:
        _, cursor = _make_pg_mock()
        mock_psycopg.connect.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=cursor
        )
        mock_psycopg.connect.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        cursor.fetchall.return_value = [
            ("Juana Molina", "DOGA", "Sonamos"),
            ("Stereolab", "Aluminum Tunes", "Duophonic"),
        ]

        source = BackendServiceSource("postgresql://user:pass@host/db")
        labels = source.fetch_library_labels()
        assert labels == {
            ("Juana Molina", "DOGA", "Sonamos"),
            ("Stereolab", "Aluminum Tunes", "Duophonic"),
        }


class TestBackendServiceSourceClose:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_close(self, mock_psycopg) -> None:
        source = BackendServiceSource("postgresql://user:pass@host/db")
        source.close()
        mock_psycopg.connect.return_value.close.assert_called_once()


class TestBackendServiceSourceContextManager:
    @patch("wxyc_catalog.catalog_source.psycopg")
    def test_context_manager(self, mock_psycopg) -> None:
        with BackendServiceSource("postgresql://user:pass@host/db") as source:
            assert source is not None
        mock_psycopg.connect.return_value.close.assert_called_once()

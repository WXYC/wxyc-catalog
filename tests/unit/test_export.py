"""Unit tests for wxyc_catalog.export_to_sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.factories import make_library_row
from wxyc_catalog.export_to_sqlite import export, export_rows_to_sqlite, format_size, parse_args


class TestExportRowsToSqlite:
    """Tests for the export_rows_to_sqlite() public function."""

    def test_creates_library_table(self, tmp_path: Path) -> None:
        """Exported database should have a 'library' table with correct schema."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite([make_library_row()], db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT * FROM library WHERE id = 9001")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "DOGA"  # title

    def test_creates_fts5_index(self, tmp_path: Path) -> None:
        """Exported database should have a working FTS5 index."""
        rows = [
            make_library_row(id=1, title="DOGA", artist="Juana Molina"),
            make_library_row(
                id=2,
                title="Moon Pix",
                artist="Cat Power",
                call_letters="C",
                artist_call_number="456",
                release_call_number="2",
            ),
        ]
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite(rows, db_path)

        conn = sqlite3.connect(db_path)
        cur = conn.execute("""
            SELECT l.artist FROM library l
            JOIN library_fts fts ON l.id = fts.rowid
            WHERE library_fts MATCH 'juana'
        """)
        results = cur.fetchall()
        conn.close()

        assert len(results) == 1
        assert results[0][0] == "Juana Molina"

    def test_row_count_matches_input(self, tmp_path: Path) -> None:
        """Exported database row count should match input."""
        rows = [make_library_row(id=i) for i in range(1, 51)]
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite(rows, db_path)

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM library").fetchone()[0]
        conn.close()
        assert count == 50

    def test_exports_alternate_artist_name(self, tmp_path: Path) -> None:
        """Rows with alternate_artist_name should store it in SQLite."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite(
            [
                make_library_row(
                    id=1,
                    title="Drum n Bass for Papa",
                    artist="Luke Vibert",
                    alternate_artist_name="Plug",
                )
            ],
            db_path,
        )

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT alternate_artist_name FROM library WHERE id = 1").fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Plug"

    def test_exports_null_alternate_artist_name(self, tmp_path: Path) -> None:
        """Rows with None alternate_artist_name should store NULL in SQLite."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite([make_library_row(id=1, alternate_artist_name=None)], db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT alternate_artist_name FROM library WHERE id = 1").fetchone()
        conn.close()

        assert row is not None
        assert row[0] is None

    def test_fts_indexes_alternate_artist_name(self, tmp_path: Path) -> None:
        """The FTS5 index should include alternate_artist_name for full-text search."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite(
            [make_library_row(id=1, artist="Luke Vibert", alternate_artist_name="Plug")],
            db_path,
        )

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT l.id, l.alternate_artist_name
            FROM library l
            JOIN library_fts fts ON l.id = fts.rowid
            WHERE library_fts MATCH 'Plug'
        """)
        results = cursor.fetchall()
        conn.close()

        assert len(results) == 1
        assert results[0][1] == "Plug"

    def test_creates_indexes(self, tmp_path: Path) -> None:
        """Indexes on artist, title, alternate_artist_name should exist."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite([make_library_row()], db_path)

        conn = sqlite3.connect(db_path)
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()

        assert "idx_artist" in indexes
        assert "idx_title" in indexes
        assert "idx_alternate_artist" in indexes

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """If the output file already exists, it should be replaced."""
        db_path = tmp_path / "library.db"
        db_path.write_text("garbage")

        export_rows_to_sqlite([make_library_row()], db_path)

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM library").fetchone()[0]
        conn.close()
        assert count == 1

    def test_exports_label(self, tmp_path: Path) -> None:
        """Rows with label should store it in SQLite."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite(
            [make_library_row(id=1, artist="Juana Molina", title="DOGA", label="Sonamos")],
            db_path,
        )

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT label FROM library WHERE id = 1").fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Sonamos"

    def test_exports_null_label(self, tmp_path: Path) -> None:
        """Rows with None label should store NULL in SQLite."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite([make_library_row(id=1, label=None)], db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT label FROM library WHERE id = 1").fetchone()
        conn.close()

        assert row is not None
        assert row[0] is None

    def test_mixed_rows_with_and_without_alternate(self, tmp_path: Path) -> None:
        """Mix of rows with and without alternate_artist_name should export correctly."""
        db_path = tmp_path / "library.db"
        rows = [
            make_library_row(id=1, artist="Luke Vibert", alternate_artist_name="Plug"),
            make_library_row(id=2, artist="Stereolab", alternate_artist_name=None),
        ]
        export_rows_to_sqlite(rows, db_path)

        conn = sqlite3.connect(db_path)
        results = conn.execute(
            "SELECT id, alternate_artist_name FROM library ORDER BY id"
        ).fetchall()
        conn.close()

        assert results == [(1, "Plug"), (2, None)]

    def test_empty_rows_creates_schema_only(self, tmp_path: Path) -> None:
        """Zero rows should create table, FTS, and indexes but no data."""
        db_path = tmp_path / "library.db"
        export_rows_to_sqlite([], db_path)

        conn = sqlite3.connect(db_path)
        # Table exists
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "library" in tables
        # FTS exists
        assert "library_fts" in tables
        # Indexes exist
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        assert "idx_artist" in indexes
        assert "idx_title" in indexes
        assert "idx_alternate_artist" in indexes
        # No data
        count = conn.execute("SELECT COUNT(*) FROM library").fetchone()[0]
        conn.close()
        assert count == 0

    def test_row_with_all_none_values(self, tmp_path: Path) -> None:
        """A row with id=1 and all other fields None should insert without error."""
        db_path = tmp_path / "library.db"
        row = make_library_row(
            id=1,
            title=None,
            artist=None,
            call_letters=None,
            artist_call_number=None,
            release_call_number=None,
            genre=None,
            format=None,
            alternate_artist_name=None,
        )
        export_rows_to_sqlite([row], db_path)

        conn = sqlite3.connect(db_path)
        result = conn.execute("SELECT * FROM library WHERE id = 1").fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 1
        # All other columns are None
        assert all(v is None for v in result[1:])

    def test_unicode_characters_round_trip(self, tmp_path: Path) -> None:
        """Unicode characters (accented, non-Latin) should survive the round trip."""
        db_path = tmp_path / "library.db"
        row = make_library_row(
            id=1,
            title="\u00c1g\u00e6tis byrjun",
            artist="Sigur R\u00f3s",
        )
        export_rows_to_sqlite([row], db_path)

        conn = sqlite3.connect(db_path)
        result = conn.execute("SELECT artist, title FROM library WHERE id = 1").fetchone()
        conn.close()

        assert result[0] == "Sigur R\u00f3s"
        assert result[1] == "\u00c1g\u00e6tis byrjun"

    def test_special_characters_in_artist(self, tmp_path: Path) -> None:
        """Ampersands and other special characters should be stored correctly."""
        db_path = tmp_path / "library.db"
        row = make_library_row(
            id=1,
            title="Duke Ellington & John Coltrane",
            artist="Duke Ellington & John Coltrane",
        )
        export_rows_to_sqlite([row], db_path)

        conn = sqlite3.connect(db_path)
        result = conn.execute("SELECT artist FROM library WHERE id = 1").fetchone()
        conn.close()

        assert result[0] == "Duke Ellington & John Coltrane"


class TestParseArgs:
    """Tests for parse_args() CLI argument parsing."""

    def test_required_args_missing(self) -> None:
        """Missing required args should cause SystemExit."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_default_output(self) -> None:
        """Default --output should be Path('library.db')."""
        args = parse_args(
            [
                "--catalog-source",
                "tubafrenzy",
                "--catalog-db-url",
                "mysql://u:p@h/db",
            ]
        )
        assert args.output == Path("library.db")

    def test_invalid_source_rejected(self) -> None:
        """An invalid --catalog-source value should cause SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(
                [
                    "--catalog-source",
                    "invalid-source",
                    "--catalog-db-url",
                    "mysql://u:p@h/db",
                ]
            )

    def test_custom_output(self) -> None:
        """--output should accept a custom path."""
        args = parse_args(
            [
                "--catalog-source",
                "tubafrenzy",
                "--catalog-db-url",
                "mysql://u:p@h/db",
                "--output",
                "/tmp/custom.db",
            ]
        )
        assert args.output == Path("/tmp/custom.db")


class TestExportCli:
    """Tests for the export() CLI entry point."""

    @patch("wxyc_catalog.export_to_sqlite.create_catalog_source")
    def test_calls_source_and_writes_db(self, mock_create, tmp_path: Path) -> None:
        """export() should call create_catalog_source, fetch rows, and write a database."""
        mock_source = MagicMock()
        mock_source.fetch_library_rows.return_value = [
            make_library_row(id=1, artist="Autechre", title="Confield"),
            make_library_row(id=2, artist="Stereolab", title="Aluminum Tunes"),
        ]
        mock_create.return_value = mock_source

        db_path = tmp_path / "output.db"
        export(
            [
                "--catalog-source",
                "tubafrenzy",
                "--catalog-db-url",
                "mysql://u:p@h/db",
                "--output",
                str(db_path),
            ]
        )

        mock_create.assert_called_once_with("tubafrenzy", "mysql://u:p@h/db")
        mock_source.fetch_library_rows.assert_called_once()

        # Verify the database was actually written
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM library").fetchone()[0]
        conn.close()
        assert count == 2

    @patch("wxyc_catalog.export_to_sqlite.create_catalog_source")
    def test_closes_source(self, mock_create, tmp_path: Path) -> None:
        """source.close() should always be called, even on success."""
        mock_source = MagicMock()
        mock_source.fetch_library_rows.return_value = [make_library_row(id=1)]
        mock_create.return_value = mock_source

        db_path = tmp_path / "output.db"
        export(
            [
                "--catalog-source",
                "tubafrenzy",
                "--catalog-db-url",
                "mysql://u:p@h/db",
                "--output",
                str(db_path),
            ]
        )

        mock_source.close.assert_called_once()

    @patch("wxyc_catalog.export_to_sqlite.create_catalog_source")
    def test_closes_source_on_error(self, mock_create) -> None:
        """source.close() should be called even if fetch_library_rows raises."""
        mock_source = MagicMock()
        mock_source.fetch_library_rows.side_effect = RuntimeError("connection lost")
        mock_create.return_value = mock_source

        with pytest.raises(RuntimeError, match="connection lost"):
            export(
                [
                    "--catalog-source",
                    "tubafrenzy",
                    "--catalog-db-url",
                    "mysql://u:p@h/db",
                ]
            )

        mock_source.close.assert_called_once()


class TestFormatSize:
    """Test human-readable size formatting."""

    @pytest.mark.parametrize(
        "size_bytes, expected",
        [
            (0, "0.0 B"),
            (1023, "1023.0 B"),
            (1024, "1.0 KB"),
            (1048576, "1.0 MB"),
            (1073741824, "1.0 GB"),
            (1099511627776, "1.0 TB"),
        ],
        ids=["zero", "bytes", "kilobytes", "megabytes", "gigabytes", "terabytes"],
    )
    def test_format_size(self, size_bytes: int, expected: str) -> None:
        assert format_size(size_bytes) == expected

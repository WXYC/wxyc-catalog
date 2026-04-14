"""Unit tests for wxyc_catalog.export_to_sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.factories import make_library_row
from wxyc_catalog.export_to_sqlite import export_rows_to_sqlite, format_size


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

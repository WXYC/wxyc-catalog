"""Integration test for the full export-to-sqlite pipeline.

Exercises the complete flow: CatalogSource mock -> export_rows_to_sqlite ->
verify the output library.db has the correct schema, row counts, FTS5 index,
and indexes. Uses an in-memory SQLite source database as the mock catalog
and writes the output to a real file via tmp_path.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from tests.factories import EXAMPLE_LABEL_TRIPLES, EXAMPLE_LIBRARY_ROWS
from wxyc_catalog.enrich_library_artists import extract_base_artists, merge_and_write
from wxyc_catalog.export_to_sqlite import export_rows_to_sqlite
from wxyc_catalog.extract_library_labels import write_library_labels_csv

pytestmark = pytest.mark.integration


class TestExportPipeline:
    """Full export flow: rows -> SQLite library.db with FTS5."""

    @pytest.fixture(autouse=True)
    def _export_db(self, tmp_path: Path) -> None:
        """Export the canonical example rows to a library.db and store the path."""
        self.db_path = tmp_path / "library.db"
        export_rows_to_sqlite(list(EXAMPLE_LIBRARY_ROWS), self.db_path)
        self.conn = sqlite3.connect(self.db_path)

    def teardown_method(self) -> None:
        if hasattr(self, "conn"):
            self.conn.close()

    def test_library_table_exists(self) -> None:
        """The library table should exist."""
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "library" in tables

    def test_row_count(self) -> None:
        """Row count should match the number of example rows."""
        count = self.conn.execute("SELECT COUNT(*) FROM library").fetchone()[0]
        assert count == len(EXAMPLE_LIBRARY_ROWS)

    def test_schema_columns(self) -> None:
        """The library table should have all expected columns."""
        cursor = self.conn.execute("PRAGMA table_info(library)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id",
            "title",
            "artist",
            "call_letters",
            "artist_call_number",
            "release_call_number",
            "genre",
            "format",
            "alternate_artist_name",
        }
        assert columns == expected

    def test_fts5_table_exists(self) -> None:
        """The FTS5 virtual table should exist."""
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "library_fts" in tables

    def test_fts5_search_by_artist(self) -> None:
        """FTS5 search by artist name should return matching rows."""
        cursor = self.conn.execute("""
            SELECT l.artist, l.title FROM library l
            JOIN library_fts fts ON l.id = fts.rowid
            WHERE library_fts MATCH 'stereolab'
        """)
        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == "Stereolab"
        assert results[0][1] == "Aluminum Tunes"

    def test_fts5_search_by_title(self) -> None:
        """FTS5 search by title should return matching rows."""
        cursor = self.conn.execute("""
            SELECT l.artist FROM library l
            JOIN library_fts fts ON l.id = fts.rowid
            WHERE library_fts MATCH 'moon'
        """)
        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == "Cat Power"

    def test_indexes_exist(self) -> None:
        """Standard indexes on artist, title, alternate_artist_name should exist."""
        indexes = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_artist" in indexes
        assert "idx_title" in indexes
        assert "idx_alternate_artist" in indexes

    def test_all_canonical_artists_present(self) -> None:
        """All canonical example artists should be present."""
        cursor = self.conn.execute("SELECT DISTINCT artist FROM library")
        artists = {row[0] for row in cursor.fetchall()}
        expected_artists = {row["artist"] for row in EXAMPLE_LIBRARY_ROWS}
        assert artists == expected_artists

    def test_data_integrity(self) -> None:
        """Individual row data should match the factory input."""
        cursor = self.conn.execute("SELECT id, title, artist, genre FROM library ORDER BY id")
        rows = cursor.fetchall()
        for db_row, expected in zip(rows, sorted(EXAMPLE_LIBRARY_ROWS, key=lambda r: r["id"])):
            assert db_row[0] == expected["id"]
            assert db_row[1] == expected["title"]
            assert db_row[2] == expected["artist"]
            assert db_row[3] == expected["genre"]


class TestEnrichmentPipeline:
    """Full enrichment flow: library.db -> extract artists -> enrich -> write output."""

    @pytest.fixture(autouse=True)
    def _set_up_library(self, tmp_path: Path) -> None:
        """Create a library.db from canonical data and set up paths."""
        self.tmp_path = tmp_path
        self.db_path = tmp_path / "library.db"
        export_rows_to_sqlite(list(EXAMPLE_LIBRARY_ROWS), self.db_path)
        self.output_path = tmp_path / "library_artists.txt"

    def test_extract_base_artists_from_exported_db(self) -> None:
        """extract_base_artists should find all canonical artists in the exported db."""
        artists = extract_base_artists(self.db_path)
        expected = {row["artist"] for row in EXAMPLE_LIBRARY_ROWS}
        assert artists == expected

    def test_full_enrichment_with_mock_catalog(self) -> None:
        """Merge base artists with mock catalog sources and verify output."""
        base = extract_base_artists(self.db_path)
        alternates = {"Rafael Toral", "Buck Meek"}
        cross_refs = {"Anne Gillis"}
        release_cross_refs = {"Sessa"}

        merge_and_write(base, alternates, cross_refs, release_cross_refs, self.output_path)

        lines = set(self.output_path.read_text().splitlines())
        # All base artists should be present
        for row in EXAMPLE_LIBRARY_ROWS:
            assert row["artist"] in lines
        # All enrichment artists should be present
        assert "Rafael Toral" in lines
        assert "Buck Meek" in lines
        assert "Anne Gillis" in lines
        assert "Sessa" in lines

    def test_output_is_sorted(self) -> None:
        """The output file should be alphabetically sorted."""
        base = extract_base_artists(self.db_path)
        merge_and_write(base, set(), set(), set(), self.output_path)
        lines = self.output_path.read_text().splitlines()
        assert lines == sorted(lines)

    def test_output_has_no_duplicates(self) -> None:
        """No duplicate lines in output when sources overlap."""
        base = extract_base_artists(self.db_path)
        # Overlap: "Cat Power" is already in base
        alternates = {"Cat Power", "Nourished by Time"}
        merge_and_write(base, alternates, set(), set(), self.output_path)
        lines = self.output_path.read_text().splitlines()
        assert len(lines) == len(set(lines))


class TestLabelExtractionPipeline:
    """Full label extraction flow: triples -> CSV with sorted output."""

    def test_write_and_read_back(self, tmp_path: Path) -> None:
        """Write canonical label triples to CSV, then read back and verify."""
        output = tmp_path / "library_labels.csv"
        write_library_labels_csv(EXAMPLE_LABEL_TRIPLES, output)

        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == len(EXAMPLE_LABEL_TRIPLES)

        # Verify all canonical triples are present
        read_back = {
            (r["artist_name"], r["release_title"], r["label_name"]) for r in rows
        }
        assert read_back == EXAMPLE_LABEL_TRIPLES

    def test_csv_is_sorted(self, tmp_path: Path) -> None:
        """Rows in the CSV should be sorted by (artist, title, label)."""
        output = tmp_path / "library_labels.csv"
        write_library_labels_csv(EXAMPLE_LABEL_TRIPLES, output)

        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            artists = [r["artist_name"] for r in reader]

        assert artists == sorted(artists)

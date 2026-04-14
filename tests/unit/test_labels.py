"""Unit tests for wxyc_catalog.extract_library_labels."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from wxyc_catalog.extract_library_labels import (
    parse_args,
    write_library_labels_csv,
)

# ---------------------------------------------------------------------------
# write_library_labels_csv
# ---------------------------------------------------------------------------


class TestWriteLibraryLabelsCsv:
    """Writing label triples to CSV."""

    def test_writes_correct_headers(self, tmp_path: Path) -> None:
        output = tmp_path / "labels.csv"
        write_library_labels_csv(
            {("Stereolab", "Aluminum Tunes", "Duophonic")},
            output,
        )
        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert headers == ["artist_name", "release_title", "label_name"]

    def test_writes_sorted_rows(self, tmp_path: Path) -> None:
        output = tmp_path / "labels.csv"
        write_library_labels_csv(
            {
                ("Stereolab", "Aluminum Tunes", "Duophonic"),
                ("Cat Power", "Moon Pix", "Matador Records"),
                ("Juana Molina", "DOGA", "Sonamos"),
            },
            output,
        )
        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)
        artists = [row[0] for row in rows]
        assert artists == sorted(artists)

    def test_empty_set_writes_header_only(self, tmp_path: Path) -> None:
        output = tmp_path / "labels.csv"
        write_library_labels_csv(set(), output)
        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
        assert headers == ["artist_name", "release_title", "label_name"]
        assert rows == []

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "sub" / "dir" / "labels.csv"
        write_library_labels_csv(
            {("Sessa", "Pequena Vertigem", "Mexican Summer")},
            output,
        )
        assert output.exists()


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """CLI argument parsing."""

    def test_required_args(self) -> None:
        args = parse_args(["--wxyc-db-url", "mysql://u:p@h/db", "--output", "out.csv"])
        assert args.wxyc_db_url == "mysql://u:p@h/db"
        assert args.output == Path("out.csv")

    def test_catalog_source_args(self) -> None:
        args = parse_args(
            [
                "--catalog-source",
                "backend-service",
                "--catalog-db-url",
                "postgresql://u:p@h/db",
                "--output",
                "out.csv",
            ]
        )
        assert args.catalog_source == "backend-service"
        assert args.catalog_db_url == "postgresql://u:p@h/db"
        assert args.wxyc_db_url is None

    def test_missing_output_exits(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--wxyc-db-url", "mysql://u:p@h/db"])

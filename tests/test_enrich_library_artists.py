"""Unit tests for wxyc_catalog.enrich_library_artists."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wxyc_catalog.enrich_library_artists import (
    extract_base_artists,
    merge_and_write,
    parse_args,
)


# ---------------------------------------------------------------------------
# extract_base_artists
# ---------------------------------------------------------------------------


class TestExtractBaseArtists:
    """Extracting unique artist names from library.db."""

    def test_returns_nonempty_set(self, sample_library_db: Path) -> None:
        artists = extract_base_artists(sample_library_db)
        assert isinstance(artists, set)
        assert len(artists) > 0

    def test_excludes_compilation_artists(self, sample_library_db: Path) -> None:
        artists = extract_base_artists(sample_library_db)
        assert "Various Artists" not in artists
        assert "Soundtrack" not in artists
        assert "Juana Molina" in artists

    def test_strips_whitespace(self, sample_library_db: Path) -> None:
        artists = extract_base_artists(sample_library_db)
        for name in artists:
            assert name == name.strip()
        assert "Sessa" in artists

    def test_no_empty_strings(self, sample_library_db: Path) -> None:
        artists = extract_base_artists(sample_library_db)
        assert "" not in artists
        assert all(name.strip() for name in artists)

    def test_preserves_original_case(self, sample_library_db: Path) -> None:
        artists = extract_base_artists(sample_library_db)
        assert "Cat Power" in artists


# ---------------------------------------------------------------------------
# merge_and_write
# ---------------------------------------------------------------------------


class TestMergeAndWrite:
    """Merging artist sets and writing output file."""

    def test_merges_all_sources(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Alpha", "Beta"},
            alternates={"Gamma"},
            cross_refs={"Delta"},
            release_cross_refs={"Epsilon"},
            output=output,
        )
        lines = output.read_text().splitlines()
        assert set(lines) == {"Alpha", "Beta", "Gamma", "Delta", "Epsilon"}

    def test_no_duplicates(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Alpha", "Beta"},
            alternates={"Beta", "Gamma"},
            cross_refs={"Gamma", "Delta"},
            release_cross_refs={"Alpha"},
            output=output,
        )
        lines = output.read_text().splitlines()
        assert len(lines) == len(set(lines))
        assert set(lines) == {"Alpha", "Beta", "Gamma", "Delta"}

    def test_sorted_output(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Zebra", "Apple", "Mango"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = output.read_text().splitlines()
        assert lines == sorted(lines)

    def test_excludes_empty_strings(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Alpha", ""},
            alternates={"  ", "Beta"},
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = output.read_text().splitlines()
        assert "" not in lines
        assert "  " not in lines
        assert set(lines) == {"Alpha", "Beta"}

    def test_excludes_compilation_artists(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Alpha"},
            alternates={"Various Artists", "Soundtrack Orchestra"},
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = output.read_text().splitlines()
        assert "Various Artists" not in lines
        assert "Soundtrack Orchestra" not in lines
        assert "Alpha" in lines

    def test_preserves_original_case(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"RZA", "dj shadow"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = output.read_text().splitlines()
        assert "RZA" in lines
        assert "dj shadow" in lines

    def test_trailing_newline(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Alpha"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        content = output.read_text()
        assert content.endswith("\n")

    def test_empty_sets_produce_empty_file(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base=set(),
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        content = output.read_text()
        assert content == ""


# ---------------------------------------------------------------------------
# Multi-artist splitting in merge_and_write
# ---------------------------------------------------------------------------


class TestMultiArtistSplitting:
    """merge_and_write should expand multi-artist entries into components."""

    def test_comma_split_adds_components(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Mike Vainio, Ryoji, Alva Noto"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = set(output.read_text().splitlines())
        assert "Mike Vainio, Ryoji, Alva Noto" in lines
        assert "Mike Vainio" in lines
        assert "Ryoji" in lines
        assert "Alva Noto" in lines

    def test_slash_split_adds_components(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"J Dilla / Jay Dee"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = set(output.read_text().splitlines())
        assert "J Dilla / Jay Dee" in lines
        assert "J Dilla" in lines
        assert "Jay Dee" in lines

    def test_ampersand_split_with_known_standalone(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Duke Ellington & John Coltrane", "Duke Ellington"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = set(output.read_text().splitlines())
        assert "Duke Ellington & John Coltrane" in lines
        assert "Duke Ellington" in lines
        assert "John Coltrane" in lines

    def test_ampersand_no_split_without_standalone(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Simon & Garfunkel"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = set(output.read_text().splitlines())
        assert "Simon & Garfunkel" in lines
        assert "Simon" not in lines
        assert "Garfunkel" not in lines

    def test_no_duplicate_lines(self, tmp_path: Path) -> None:
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Duke Ellington & John Coltrane", "Duke Ellington", "John Coltrane"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = output.read_text().splitlines()
        assert len(lines) == len(set(lines))

    def test_compilation_components_excluded(self, tmp_path: Path) -> None:
        """If a split component is a compilation artist, it should be excluded."""
        output = tmp_path / "artists.txt"
        merge_and_write(
            base={"Juana Molina / Various Artists"},
            alternates=set(),
            cross_refs=set(),
            release_cross_refs=set(),
            output=output,
        )
        lines = set(output.read_text().splitlines())
        assert "Juana Molina" in lines
        assert "Various Artists" not in lines


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """CLI argument parsing."""

    def test_required_args(self) -> None:
        args = parse_args(["--library-db", "library.db", "--output", "artists.txt"])
        assert args.library_db == Path("library.db")
        assert args.output == Path("artists.txt")
        assert args.wxyc_db_url is None

    def test_with_wxyc_db_url(self) -> None:
        args = parse_args([
            "--library-db", "library.db",
            "--output", "artists.txt",
            "--wxyc-db-url", "mysql://wxyc:wxyc@localhost:3307/wxycmusic",
        ])
        assert args.wxyc_db_url == "mysql://wxyc:wxyc@localhost:3307/wxycmusic"

    def test_missing_required_args_exits(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--library-db", "library.db"])  # missing --output

    def test_with_catalog_source_and_db_url(self) -> None:
        args = parse_args([
            "--library-db", "library.db",
            "--output", "artists.txt",
            "--catalog-source", "backend-service",
            "--catalog-db-url", "postgresql://user:pass@host/db",
        ])
        assert args.catalog_source == "backend-service"
        assert args.catalog_db_url == "postgresql://user:pass@host/db"
        assert args.wxyc_db_url is None

    def test_catalog_source_defaults_to_none(self) -> None:
        args = parse_args(["--library-db", "library.db", "--output", "artists.txt"])
        assert args.catalog_source is None
        assert args.catalog_db_url is None


# ---------------------------------------------------------------------------
# main (mocked)
# ---------------------------------------------------------------------------


class TestMain:
    """main() orchestrates extraction and merge."""

    def test_with_library_db_only(self, tmp_path: Path) -> None:
        """With --library-db only, base artists are extracted and written."""
        library_db = tmp_path / "library.db"
        conn = sqlite3.connect(library_db)
        conn.execute("CREATE TABLE library (artist TEXT, title TEXT)")
        conn.execute("INSERT INTO library VALUES ('Stereolab', 'Aluminum Tunes')")
        conn.execute("INSERT INTO library VALUES ('Cat Power', 'Moon Pix')")
        conn.commit()
        conn.close()

        output = tmp_path / "artists.txt"

        from wxyc_catalog import enrich_library_artists as mod

        with patch.object(
            mod,
            "parse_args",
            return_value=parse_args(["--library-db", str(library_db), "--output", str(output)]),
        ):
            mod.main()

        lines = set(output.read_text().splitlines())
        assert "Stereolab" in lines
        assert "Cat Power" in lines

    def test_with_catalog_source(self, tmp_path: Path) -> None:
        """With --catalog-source, enrichment sources are fetched."""
        library_db = tmp_path / "library.db"
        conn = sqlite3.connect(library_db)
        conn.execute("CREATE TABLE library (artist TEXT, title TEXT)")
        conn.execute("INSERT INTO library VALUES ('Cat Power', 'Moon Pix')")
        conn.commit()
        conn.close()

        output = tmp_path / "artists.txt"
        mock_source = MagicMock()
        mock_source.fetch_alternate_names.return_value = {"Rafael Toral"}
        mock_source.fetch_cross_referenced_artists.return_value = set()
        mock_source.fetch_release_cross_ref_artists.return_value = set()

        from wxyc_catalog import enrich_library_artists as mod

        with (
            patch.object(
                mod,
                "parse_args",
                return_value=parse_args([
                    "--library-db", str(library_db),
                    "--output", str(output),
                    "--catalog-source", "backend-service",
                    "--catalog-db-url", "postgresql://user:pass@host/db",
                ]),
            ),
            patch.object(mod, "create_catalog_source", return_value=mock_source) as mock_factory,
        ):
            mod.main()

        mock_factory.assert_called_once_with("backend-service", "postgresql://user:pass@host/db")
        lines = set(output.read_text().splitlines())
        assert "Cat Power" in lines
        assert "Rafael Toral" in lines
        mock_source.close.assert_called_once()

    def test_missing_library_db_exits(self, tmp_path: Path) -> None:
        """Non-existent library.db triggers sys.exit(1)."""
        output = tmp_path / "artists.txt"

        from wxyc_catalog import enrich_library_artists as mod

        with (
            patch.object(
                mod,
                "parse_args",
                return_value=parse_args([
                    "--library-db", str(tmp_path / "missing.db"),
                    "--output", str(output),
                ]),
            ),
            pytest.raises(SystemExit, match="1"),
        ):
            mod.main()

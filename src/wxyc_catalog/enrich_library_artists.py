"""Generate an enriched library_artists.txt from library.db and catalog sources.

Extracts base artist names from a SQLite library database, optionally enriches
with alternate names, cross-references, and release cross-references from a
CatalogSource, expands multi-artist entries, and writes sorted output.

The text normalization functions (``split_artist_name_contextual``,
``is_compilation_artist``) are imported from ``wxyc_etl`` — there are no
local copies.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import unicodedata
from pathlib import Path

from wxyc_etl.text import is_compilation_artist, split_artist_name_contextual

from wxyc_catalog.catalog_source import create_catalog_source

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--library-db",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to library.db (SQLite database with artist/title pairs).",
    )
    parser.add_argument(
        "--wxyc-db-url",
        type=str,
        default=None,
        metavar="URL",
        help="MySQL connection URL for WXYC catalog database "
        "(e.g. mysql://user:pass@host:port/dbname). "
        "Alias for --catalog-source tubafrenzy --catalog-db-url <url>. "
        "If omitted, only base artists from library.db are extracted.",
    )
    parser.add_argument(
        "--catalog-source",
        type=str,
        choices=["tubafrenzy", "backend-service"],
        default=None,
        metavar="SOURCE",
        help="Catalog source type: 'tubafrenzy' (MySQL) or 'backend-service' (PostgreSQL).",
    )
    parser.add_argument(
        "--catalog-db-url",
        type=str,
        default=None,
        metavar="URL",
        help="Database connection URL for the catalog source.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="FILE",
        help="Output path for library_artists.txt.",
    )
    return parser.parse_args(argv)


def extract_base_artists(library_db_path: Path) -> set[str]:
    """Extract unique artist names from library.db, excluding compilations.

    Args:
        library_db_path: Path to the SQLite library database.

    Returns:
        Set of distinct artist names (original case, no compilations).
    """
    logger.info("Extracting base artists from %s", library_db_path)
    conn = sqlite3.connect(library_db_path)
    try:
        cur = conn.execute("SELECT DISTINCT artist FROM library")
        artists = set()
        for (name,) in cur:
            if name and name.strip() and not is_compilation_artist(name):
                artists.add(name.strip())
    finally:
        conn.close()
    logger.info("Extracted %d base artists", len(artists))
    return artists


def _expand_multi_artist_names(all_names: set[str]) -> set[str]:
    """Expand multi-artist entries into individual components.

    Uses context-free splitting for unambiguous delimiters (comma, slash, plus)
    and contextual splitting for ampersand (only when a component is already
    a known standalone artist).

    Returns the expanded set (original names + new components).
    """

    def _normalize(name: str) -> str:
        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    known_artists = {_normalize(n) for n in all_names}

    expanded: set[str] = set()
    split_count = 0

    for name in all_names:
        components = split_artist_name_contextual(name, known_artists)
        if components:
            split_count += 1
            for c in components:
                expanded.add(c)
                known_artists.add(_normalize(c))

    if split_count:
        logger.info(
            "Split %d multi-artist entries into %d new components",
            split_count,
            len(expanded - all_names),
        )

    return expanded


def merge_and_write(
    base: set[str],
    alternates: set[str],
    cross_refs: set[str],
    release_cross_refs: set[str],
    output: Path,
) -> None:
    """Merge all artist name sources and write to output file.

    Names are sorted alphabetically for stable diffs. Empty strings and
    compilation artist names are filtered out. Original case is preserved.
    Multi-artist entries are expanded into individual components.

    Args:
        base: Artist names from library.db.
        alternates: Alternate artist names from LIBRARY_RELEASE.
        cross_refs: Artist names from LIBRARY_CODE_CROSS_REFERENCE.
        release_cross_refs: Artist names from RELEASE_CROSS_REFERENCE.
        output: Path to write the output file.
    """
    all_names = base | alternates | cross_refs | release_cross_refs

    split_components = _expand_multi_artist_names(all_names)
    all_names = all_names | split_components

    filtered = sorted(
        name for name in all_names if name and name.strip() and not is_compilation_artist(name)
    )

    new_from_alternates = len(alternates - base)
    new_from_cross_refs = len(cross_refs - base - alternates)
    new_from_release_xrefs = len(release_cross_refs - base - alternates - cross_refs)

    logger.info(
        "Merged: %d base + %d new from alternates + %d new from cross-refs "
        "+ %d new from release cross-refs = %d total",
        len(base),
        new_from_alternates,
        new_from_cross_refs,
        new_from_release_xrefs,
        len(filtered),
    )

    with open(output, "w", encoding="utf-8") as f:
        for name in filtered:
            f.write(name + "\n")

    logger.info("Wrote %d artist names to %s", len(filtered), output)


def _resolve_catalog_args(args: argparse.Namespace) -> tuple[str, str] | None:
    """Resolve --catalog-source/--catalog-db-url or --wxyc-db-url into (source_type, db_url).

    Returns None if no catalog source is configured (library.db-only mode).
    """
    if args.catalog_source and args.catalog_db_url:
        return (args.catalog_source, args.catalog_db_url)
    if args.wxyc_db_url:
        return ("tubafrenzy", args.wxyc_db_url)
    if args.catalog_source and not args.catalog_db_url:
        logger.error("--catalog-source requires --catalog-db-url")
        sys.exit(1)
    if args.catalog_db_url and not args.catalog_source:
        logger.error("--catalog-db-url requires --catalog-source")
        sys.exit(1)
    return None


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: extract, enrich, and write library artist names."""
    args = parse_args(argv)

    if not args.library_db.exists():
        logger.error("library.db not found: %s", args.library_db)
        sys.exit(1)

    base = extract_base_artists(args.library_db)

    alternates: set[str] = set()
    cross_refs: set[str] = set()
    release_cross_refs: set[str] = set()

    catalog_args = _resolve_catalog_args(args)
    if catalog_args:
        source = create_catalog_source(*catalog_args)
        try:
            alternates = source.fetch_alternate_names()
            cross_refs = source.fetch_cross_referenced_artists()
            release_cross_refs = source.fetch_release_cross_ref_artists()
        finally:
            source.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    merge_and_write(base, alternates, cross_refs, release_cross_refs, args.output)

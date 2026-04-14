"""Export library catalog to SQLite with FTS5 full-text search.

Provides ``export_rows_to_sqlite()`` for programmatic use and an ``export()``
CLI entry point that fetches rows via a CatalogSource and writes them to a
SQLite database.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

from wxyc_catalog.catalog_source import create_catalog_source

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string."""
    size_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024
    return f"{size_float:.1f} TB"


def export_rows_to_sqlite(rows: list[dict], output_path: Path) -> None:
    """Export library rows to a SQLite database with FTS5 index.

    Creates the ``library`` table, a ``library_fts`` FTS5 virtual table
    (indexing title, artist, and alternate_artist_name), and indexes on
    artist, title, and alternate_artist_name columns.

    Args:
        rows: List of dicts with keys: id, title, artist, call_letters,
              artist_call_number, release_call_number, genre, format,
              alternate_artist_name.
        output_path: Path where the SQLite database will be written.
                     An existing file at this path will be removed first.
    """
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(output_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE library (
            id INTEGER PRIMARY KEY,
            title TEXT,
            artist TEXT,
            call_letters TEXT,
            artist_call_number INTEGER,
            release_call_number INTEGER,
            genre TEXT,
            format TEXT,
            alternate_artist_name TEXT
        )
    """)

    cur.execute("""
        CREATE VIRTUAL TABLE library_fts USING fts5(
            title,
            artist,
            alternate_artist_name,
            content='library',
            content_rowid='id'
        )
    """)

    for row in rows:
        cur.execute(
            """
            INSERT INTO library (id, title, artist, call_letters, artist_call_number,
                                 release_call_number, genre, format, alternate_artist_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["title"],
                row["artist"],
                row["call_letters"],
                row["artist_call_number"],
                row["release_call_number"],
                row["genre"],
                row["format"],
                row.get("alternate_artist_name"),
            ),
        )

    cur.execute("""
        INSERT INTO library_fts(rowid, title, artist, alternate_artist_name)
        SELECT id, title, artist, alternate_artist_name FROM library
    """)

    cur.execute("CREATE INDEX idx_artist ON library(artist)")
    cur.execute("CREATE INDEX idx_title ON library(title)")
    cur.execute("CREATE INDEX idx_alternate_artist ON library(alternate_artist_name)")

    conn.commit()
    conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the export CLI."""
    parser = argparse.ArgumentParser(
        description="Export WXYC library catalog to SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--catalog-source",
        type=str,
        choices=["tubafrenzy", "backend-service"],
        required=True,
        metavar="SOURCE",
        help="Catalog source type: 'tubafrenzy' (MySQL) or 'backend-service' (PostgreSQL).",
    )
    parser.add_argument(
        "--catalog-db-url",
        type=str,
        required=True,
        metavar="URL",
        help="Database connection URL for the catalog source.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("library.db"),
        metavar="FILE",
        help="Output path for the SQLite database (default: library.db).",
    )
    return parser.parse_args(argv)


def export(argv: list[str] | None = None) -> None:
    """CLI entry point: fetch rows from a CatalogSource and export to SQLite."""
    args = parse_args(argv)

    logger.info("Fetching library from %s...", args.catalog_source)
    source = create_catalog_source(args.catalog_source, args.catalog_db_url)
    try:
        rows = source.fetch_library_rows()
    finally:
        source.close()
    logger.info("Fetched %d rows", len(rows))

    export_rows_to_sqlite(rows, args.output)
    logger.info("Exported %d rows to %s", len(rows), args.output)

    size_mb = args.output.stat().st_size / (1024 * 1024)
    logger.info("Database size: %.2f MB", size_mb)

"""Extract WXYC label preferences from a CatalogSource.

Queries for (artist_name, release_title, label_name) triples from flowsheet
plays linked to library releases, then writes them as a CSV for use by
downstream pipeline steps (e.g. dedup_releases.py --library-labels).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

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
        "--wxyc-db-url",
        type=str,
        default=None,
        metavar="URL",
        help="MySQL connection URL for WXYC catalog database "
        "(e.g. mysql://user:pass@host:port/dbname). "
        "Alias for --catalog-source tubafrenzy --catalog-db-url <url>.",
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
        help="Output path for library_labels.csv.",
    )
    return parser.parse_args(argv)


def write_library_labels_csv(triples: set[tuple[str, str, str]], output: Path) -> None:
    """Write label triples to a CSV file.

    Args:
        triples: Set of (artist_name, release_title, label_name) tuples.
        output: Path to the output CSV file.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(triples)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["artist_name", "release_title", "label_name"])
        writer.writerows(sorted_rows)
    logger.info("Wrote %d label preferences to %s", len(sorted_rows), output)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: extract library labels and write to CSV."""
    args = parse_args(argv)

    if args.catalog_source and args.catalog_db_url:
        source_type, db_url = args.catalog_source, args.catalog_db_url
    elif args.wxyc_db_url:
        source_type, db_url = "tubafrenzy", args.wxyc_db_url
    elif args.catalog_source and not args.catalog_db_url:
        logger.error("--catalog-source requires --catalog-db-url")
        sys.exit(1)
    elif args.catalog_db_url and not args.catalog_source:
        logger.error("--catalog-db-url requires --catalog-source")
        sys.exit(1)
    else:
        logger.error("One of --wxyc-db-url or --catalog-source/--catalog-db-url is required")
        sys.exit(1)

    source = create_catalog_source(source_type, db_url)
    try:
        triples = source.fetch_library_labels()
    finally:
        source.close()
    write_library_labels_csv(triples, args.output)

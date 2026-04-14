"""WXYC library catalog access and operations.

Provides the ``CatalogSource`` protocol and implementations for querying the
WXYC library catalog, plus scripts for producing pipeline inputs (library.db,
library_artists.txt, library_labels.csv).
"""

from wxyc_catalog.catalog_source import (
    BackendServiceSource,
    CatalogSource,
    TubafrenzySource,
    create_catalog_source,
)
from wxyc_catalog.export_to_sqlite import export_rows_to_sqlite
from wxyc_catalog.sources.archive import ArchiveSource
from wxyc_catalog.sources.http import HttpSource
from wxyc_catalog.sources.pg import PgSource
from wxyc_catalog.sources.sparql import SparqlSource

__all__ = [
    "ArchiveSource",
    "BackendServiceSource",
    "CatalogSource",
    "HttpSource",
    "PgSource",
    "SparqlSource",
    "TubafrenzySource",
    "create_catalog_source",
    "export_rows_to_sqlite",
]

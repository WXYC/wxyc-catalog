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

__all__ = [
    "BackendServiceSource",
    "CatalogSource",
    "TubafrenzySource",
    "create_catalog_source",
    "export_rows_to_sqlite",
]

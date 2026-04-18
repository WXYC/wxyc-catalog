# wxyc-catalog

WXYC library catalog access and operations. This package defines the `CatalogSource` protocol — a read-only interface to the WXYC library catalog — with implementations for tubafrenzy (MySQL) and Backend-Service (PostgreSQL). It also provides CLI tools that produce pipeline inputs for downstream services: `library.db` (SQLite with FTS5), `library_artists.txt`, and `library_labels.csv`.

## CatalogSource Protocol

`CatalogSource` is a `@runtime_checkable` Protocol that abstracts over the two catalog databases. Both implementations return identical data structures despite different underlying schemas.

```python
class CatalogSource(Protocol):
    def fetch_library_rows(self) -> list[dict[str, Any]]:
        """Library releases. Keys: id, title, artist, call_letters,
        artist_call_number, release_call_number, genre, format,
        alternate_artist_name."""

    def fetch_alternate_names(self) -> set[str]:
        """Alternate artist names (e.g. 'Body Count' filed under Ice-T)."""

    def fetch_cross_referenced_artists(self) -> set[str]:
        """Artist names from both sides of the artist cross-reference table."""

    def fetch_release_cross_ref_artists(self) -> set[str]:
        """Artist names from library-level cross-references."""

    def fetch_library_labels(self) -> set[tuple[str, str, str]]:
        """(artist, title, label) triples from flowsheet plays."""

    def close(self) -> None:
        """Release the database connection."""
```

### Implementations

| Source | Database | Connection |
|--------|----------|------------|
| `TubafrenzySource` | MySQL 4.1+ (Kattare) | `mysql-connector-python` with `allow_old_password=True`, pymysql fallback |
| `BackendServiceSource` | PostgreSQL (Backend-Service) | `psycopg` |

Use the factory function to create a source by name:

```python
from wxyc_catalog import create_catalog_source

source = create_catalog_source("tubafrenzy", "mysql://user:pass@host/db")
# or
source = create_catalog_source("backend-service", "postgresql://user:pass@host/db")
```

### MySQL 4.1 Compatibility

Kattare runs MySQL 4.1.22, which predates plugin-based authentication. The `connect_mysql()` helper uses `mysql-connector-python` with `allow_old_password=True` as the primary driver, falling back to `pymysql` when it's not installed. Credentials in the connection URL are URL-decoded to handle special characters.

## Installation

```bash
pip install wxyc-catalog
```

For MySQL support (tubafrenzy):

```bash
pip install "wxyc-catalog[mysql]"
```

## CLI Tools

### `wxyc-export-to-sqlite`

Exports the library catalog to a SQLite database with an FTS5 full-text search index on title, artist, and alternate_artist_name.

```bash
wxyc-export-to-sqlite \
    --catalog-source tubafrenzy \
    --catalog-db-url mysql://user:pass@host/db \
    --output library.db
```

### `wxyc-enrich-library-artists`

Generates `library_artists.txt` containing all unique artist names, enriched with alternate names, cross-references, and contextual splitting of multi-artist entries (names with commas, slashes, ampersands) via `wxyc_etl`.

```bash
wxyc-enrich-library-artists \
    --library-db library.db \
    --catalog-source backend-service \
    --catalog-db-url postgresql://user:pass@host/db \
    --output library_artists.txt
```

### `wxyc-extract-library-labels`

Extracts (artist, title, label) triples from flowsheet plays to CSV.

```bash
wxyc-extract-library-labels \
    --catalog-source tubafrenzy \
    --catalog-db-url mysql://user:pass@host/db \
    --output library_labels.csv
```

## Programmatic Usage

```python
from wxyc_catalog import create_catalog_source, export_rows_to_sqlite
from pathlib import Path

source = create_catalog_source("backend-service", "postgresql://user:pass@host/db")
rows = source.fetch_library_rows()
source.close()

export_rows_to_sqlite(rows, Path("library.db"))
```

## Dependencies

- `psycopg[binary]>=3.1` — PostgreSQL driver
- `wxyc-etl>=0.1.0` — text normalization (`split_artist_name_contextual`, `is_compilation_artist`)
- `mysql-connector-python>=8.0` — MySQL driver with old password auth support (optional, `[mysql]` extra)

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check
ruff format --check
```

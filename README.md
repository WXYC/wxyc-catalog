# wxyc-catalog

WXYC library catalog access and operations. Extracted from discogs-cache, this package owns the `CatalogSource` protocol and its implementations for querying the WXYC library catalog from tubafrenzy (MySQL) or Backend-Service (PostgreSQL), plus the scripts that produce pipeline inputs (`library.db`, `library_artists.txt`, `library_labels.csv`).

## Installation

```bash
pip install wxyc-catalog
```

For MySQL support (tubafrenzy):

```bash
pip install "wxyc-catalog[mysql]"
```

## Usage

### Programmatic

```python
from wxyc_catalog import create_catalog_source, export_rows_to_sqlite
from pathlib import Path

# Fetch library rows from a catalog source
source = create_catalog_source("backend-service", "postgresql://user:pass@host/db")
rows = source.fetch_library_rows()
source.close()

# Export to SQLite with FTS5 search index
export_rows_to_sqlite(rows, Path("library.db"))
```

### CLI

Export library to SQLite:

```bash
wxyc-export-to-sqlite \
    --catalog-source backend-service \
    --catalog-db-url postgresql://user:pass@host/db \
    --output library.db
```

Enrich library artists:

```bash
wxyc-enrich-library-artists \
    --library-db library.db \
    --catalog-source backend-service \
    --catalog-db-url postgresql://user:pass@host/db \
    --output library_artists.txt
```

Extract library labels:

```bash
wxyc-extract-library-labels \
    --catalog-source tubafrenzy \
    --catalog-db-url mysql://user:pass@host/db \
    --output library_labels.csv
```

## Dependencies

- `psycopg[binary]>=3.1` (PostgreSQL)
- `wxyc-etl>=0.1.0` (text normalization: `split_artist_name_contextual`, `is_compilation_artist`)
- `pymysql>=1.0` (optional, for MySQL/tubafrenzy support)

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check
ruff format --check
```

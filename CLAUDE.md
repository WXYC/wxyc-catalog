# wxyc-catalog

WXYC library catalog access and operations package, extracted from discogs-cache.

## Package Structure

```
src/wxyc_catalog/
  __init__.py              # Re-exports: CatalogSource, TubafrenzySource, BackendServiceSource, create_catalog_source, export_rows_to_sqlite
  catalog_source.py        # CatalogSource protocol + TubafrenzySource/BackendServiceSource implementations + factory
  db.py                    # MySQL connection helper (connect_mysql)
  export_to_sqlite.py      # SQLite export with FTS5 index (export_rows_to_sqlite + export CLI)
  enrich_library_artists.py # Artist enrichment pipeline (extract_base_artists, merge_and_write + main CLI)
  extract_library_labels.py # Label extraction (write_library_labels_csv + main CLI)
```

## Development

- **TDD**: Write failing test first, then implement.
- **Code style**: ruff for linting and formatting, 100 char line length.
- **Testing**: `pytest` runs all tests. No external database required; tests use mocks and tmp_path fixtures.
- **Text normalization**: Always import from `wxyc_etl.text` (`split_artist_name_contextual`, `is_compilation_artist`). Never create local copies.

## Dependencies

- `wxyc-etl` provides text normalization via PyO3 bindings (Rust).
- `psycopg` for PostgreSQL (BackendServiceSource).
- `pymysql` for MySQL (TubafrenzySource, optional extra).

## Test Fixtures

Use WXYC-representative artist data (not mainstream): Juana Molina, Stereolab, Cat Power, Autechre, Prince Jammy, Sessa, Duke Ellington & John Coltrane, etc.

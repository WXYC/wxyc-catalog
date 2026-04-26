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
- **Text normalization**: Always import from `wxyc_etl.text` (`split_artist_name_contextual`, `is_compilation_artist`). Never create local copies.

## Dependencies

- `wxyc-etl` provides text normalization via PyO3 bindings (Rust).
- `psycopg` for PostgreSQL (BackendServiceSource).
- `pymysql` for MySQL (TubafrenzySource, optional extra).

## Testing

```bash
pytest                    # unit tests only (default, no external deps)
pytest -m integration     # integration tests (SQLite-based, no external DB)
pytest -m '' -v           # all tests
```

Markers follow the canonical WXYC 6-marker convention (`unit`, `postgres`, `integration`, `e2e`, `parity`, `slow`) declared in every Python repo for org-wide consistency (see `plans/test-patterns.md`). The `addopts` in `pyproject.toml` deselects everything except `unit` so `pytest` with no arguments runs only unit tests. CI runs `integration` in a dedicated job; the marker-sync workflow guards against silent-deselection regressions for any marker actually used by a test in this repo.

### Test Layout

```
tests/
  conftest.py                          # Shared fixtures (sample_library_db, sample_library_rows)
  factories.py                         # Factory functions (make_library_row, EXAMPLE_LIBRARY_ROWS, EXAMPLE_LABEL_TRIPLES)
  unit/
    test_catalog_source.py             # Protocol compliance, helpers, factory, TubafrenzySource, BackendServiceSource
    test_db.py                         # MySQL connection URL parsing
    test_enrich.py                     # Artist enrichment (extract, merge, multi-artist splitting, CLI args)
    test_export.py                     # SQLite export (schema, FTS5, indexes, overwrite), format_size
    test_labels.py                     # Label extraction (CSV output, CLI args)
  integration/
    test_export_pipeline.py            # Full export/enrichment/label-extraction pipelines end-to-end
```

### Test Fixtures

Use WXYC-representative artist data (not mainstream): Juana Molina, Stereolab, Cat Power, Jessica Pratt, Chuquimamani-Condori, Sessa, Duke Ellington & John Coltrane, etc. Factory functions in `tests/factories.py` provide canonical defaults aligned with `wxyc-shared/src/test-utils/wxyc-example-data.json`.

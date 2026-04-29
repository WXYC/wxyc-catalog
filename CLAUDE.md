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
pytest                    # all tests (no markers needed — this repo has no infra deps)
pytest tests/unit/ -v     # unit tests only
pytest tests/integration/ # integration tests only (SQLite-based)
```

Markers follow architecture A (see [the wiki test-patterns doc](https://github.com/WXYC/wiki/blob/main/plans/test-patterns.md), Section 3): markers exist to route CI by infrastructure, and wxyc-catalog has no infrastructure dependencies — it is SQLite-only with no PostgreSQL, no external APIs, and no docker stack. The repo therefore declares zero markers in `pyproject.toml`. The tests in `tests/integration/` are unmarked and run alongside `tests/unit/` in the default `test` CI job. The `marker-sync` CI job (reusable workflow from wxyc-etl) guards against silent-deselection regressions if markers are ever introduced.

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

## Releases

`wxyc-catalog` is published to PyPI as the `wxyc-catalog` distribution. Releases are tag-driven via `.github/workflows/release.yml`:

```bash
# Bump pyproject.toml version, commit, then:
git tag v0.1.0
git push origin v0.1.0
```

The workflow verifies the tag matches `pyproject.toml`, builds an sdist + wheel with `python -m build`, and uploads via `pypa/gh-action-pypi-publish`. The workflow's `workflow_dispatch` trigger with `dry_run: true` (default) is a rehearsal that runs everything except the upload — useful for shaking out build issues without burning a version number.

**One-time operator setup**: a `PYPI_API_TOKEN` repo secret is required. Generate at https://pypi.org/manage/account/token/; on first publish use an account-scoped token, then narrow it to the `wxyc-catalog` project once the project exists on PyPI. Trusted Publishing (OIDC) is a future migration; the current workflow uses token auth to match the wxyc-etl precedent.

External consumers depend on the published version:

```toml
# discogs-etl pyproject.toml, etc.
dependencies = [
    "wxyc-catalog>=0.1.0",
    ...
]
```

Once the package is on PyPI, the `git clone https://github.com/WXYC/wxyc-catalog` step in `discogs-etl/.github/workflows/rebuild-cache.yml` (and any sibling workflow) can be dropped — `pip install -e ".[dev]"` resolves wxyc-catalog from PyPI directly.

"""Shared fixtures for wxyc-catalog tests.

Provides SQLite library.db fixtures populated with canonical WXYC example data
from tests/factories.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.factories import EXAMPLE_LIBRARY_ROWS


@pytest.fixture
def sample_library_db(tmp_path: Path) -> Path:
    """Create a minimal library.db fixture with representative WXYC data.

    Includes canonical artists plus edge cases (compilation artists, whitespace).
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE library (artist TEXT, title TEXT)")
    conn.executemany(
        "INSERT INTO library VALUES (?, ?)",
        [
            ("Juana Molina", "DOGA"),
            ("Stereolab", "Aluminum Tunes"),
            ("Cat Power", "Moon Pix"),
            ("Various Artists", "CMJ New Music"),
            ("Soundtrack", "Lost Highway"),
            ("Duke Ellington & John Coltrane", "Duke Ellington & John Coltrane"),
            ("  Sessa  ", "Pequena Vertigem"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def sample_library_rows() -> list[dict]:
    """Return the canonical WXYC example library rows."""
    return list(EXAMPLE_LIBRARY_ROWS)

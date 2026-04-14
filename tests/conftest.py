"""Shared fixtures for wxyc-catalog tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def sample_library_db(tmp_path: Path) -> Path:
    """Create a minimal library.db fixture with representative WXYC data."""
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

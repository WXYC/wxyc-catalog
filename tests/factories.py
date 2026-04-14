"""Factory functions for wxyc-catalog test data.

All defaults use WXYC-representative artists from the canonical data source
(wxyc-shared/src/test-utils/wxyc-example-data.json).
"""

from __future__ import annotations

from typing import Any


def make_library_row(**overrides: Any) -> dict[str, Any]:
    """Create a library row dict with sensible WXYC defaults.

    Returns a dict matching the column contract of CatalogSource.fetch_library_rows().
    Override any key via keyword arguments.
    """
    defaults: dict[str, Any] = {
        "id": 9001,
        "title": "DOGA",
        "artist": "Juana Molina",
        "call_letters": "RO",
        "artist_call_number": 42,
        "release_call_number": 1,
        "genre": "Rock",
        "format": "CD",
        "alternate_artist_name": None,
    }
    defaults.update(overrides)
    return defaults


# Pre-built rows matching the canonical example data.
EXAMPLE_LIBRARY_ROWS: list[dict[str, Any]] = [
    make_library_row(
        id=9001,
        title="DOGA",
        artist="Juana Molina",
        call_letters="RO",
        artist_call_number=42,
        release_call_number=1,
        genre="Rock",
        format="CD",
    ),
    make_library_row(
        id=9002,
        title="Aluminum Tunes",
        artist="Stereolab",
        call_letters="RO",
        artist_call_number=87,
        release_call_number=5,
        genre="Rock",
        format="CD",
    ),
    make_library_row(
        id=9003,
        title="Moon Pix",
        artist="Cat Power",
        call_letters="RO",
        artist_call_number=23,
        release_call_number=2,
        genre="Rock",
        format="CD",
    ),
    make_library_row(
        id=9004,
        title="On Your Own Love Again",
        artist="Jessica Pratt",
        call_letters="RO",
        artist_call_number=112,
        release_call_number=1,
        genre="Rock",
        format="Vinyl LP",
    ),
    make_library_row(
        id=9005,
        title="Edits",
        artist="Chuquimamani-Condori",
        call_letters="EL",
        artist_call_number=15,
        release_call_number=1,
        genre="Electronic",
        format="Vinyl LP",
    ),
]


# Label triples matching canonical data.
EXAMPLE_LABEL_TRIPLES: set[tuple[str, str, str]] = {
    ("Juana Molina", "DOGA", "Sonamos"),
    ("Stereolab", "Aluminum Tunes", "Duophonic"),
    ("Cat Power", "Moon Pix", "Matador Records"),
    ("Jessica Pratt", "On Your Own Love Again", "Drag City"),
    ("Chuquimamani-Condori", "Edits", "self-released"),
}

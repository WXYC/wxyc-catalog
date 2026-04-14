"""File loading from directories and tar archives with SQLite index caching.

Provides:
- Load files from a directory by relative path
- Load files from tar archives with an on-disk SQLite index for fast member lookup
- Batch reads grouped by storage unit (directory or tar file)
- List files matching a glob pattern
- Async via ``asyncio.to_thread()`` for blocking filesystem I/O
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import tarfile
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


class ArchiveSource:
    """File loading from directories and tar archives with SQLite index caching.

    Paths are relative to ``base_path``. For tar archives, use the format
    ``"archive.tar/member_name.json"`` where the first component is the tar
    filename and the remainder is the member path within the archive.

    Args:
        base_path: Root directory for all file lookups.
        index_path: Path for the SQLite index file used to cache tar member
            offsets. If ``None``, a default ``index.db`` file is created in
            ``base_path``.
    """

    def __init__(
        self, base_path: str | Path, *, index_path: str | Path | None = None
    ) -> None:
        self._base_path = Path(base_path)
        self._index_path = (
            Path(index_path) if index_path else self._base_path / "index.db"
        )
        self._db: sqlite3.Connection | None = None

    def _get_db(self) -> sqlite3.Connection:
        """Return the SQLite connection, creating it and the schema lazily."""
        if self._db is None:
            self._db = sqlite3.connect(str(self._index_path), check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS tar_index ("
                "  tar_name TEXT NOT NULL,"
                "  member_name TEXT NOT NULL,"
                "  offset INTEGER NOT NULL,"
                "  size INTEGER NOT NULL,"
                "  PRIMARY KEY (tar_name, member_name)"
                ")"
            )
            self._db.commit()
        return self._db

    def _is_indexed(self, tar_name: str) -> bool:
        """Check whether a tar archive has already been indexed."""
        db = self._get_db()
        row = db.execute(
            "SELECT 1 FROM tar_index WHERE tar_name = ? LIMIT 1", (tar_name,)
        ).fetchone()
        return row is not None

    def _index_tar(self, tar_path: Path, tar_name: str) -> None:
        """Build the SQLite index for a tar archive's members."""
        db = self._get_db()
        with tarfile.open(tar_path, "r") as tf:
            for member in tf.getmembers():
                if member.isfile():
                    db.execute(
                        "INSERT OR REPLACE INTO tar_index (tar_name, member_name, offset, size) "
                        "VALUES (?, ?, ?, ?)",
                        (tar_name, member.name, member.offset_data, member.size),
                    )
        db.commit()

    def _load_from_tar(self, tar_path: Path, member_name: str) -> bytes | None:
        """Load a single member from a tar archive using the index if available."""
        tar_name = tar_path.name

        if not self._is_indexed(tar_name):
            self._index_tar(tar_path, tar_name)

        db = self._get_db()
        row = db.execute(
            "SELECT offset, size FROM tar_index WHERE tar_name = ? AND member_name = ?",
            (tar_name, member_name),
        ).fetchone()

        if row is None:
            return None

        offset, size = row
        with open(tar_path, "rb") as f:
            f.seek(offset)
            return f.read(size)

    def _load_from_directory(self, rel_path: str) -> bytes | None:
        """Load a file from the base directory by relative path."""
        full_path = self._base_path / rel_path
        if not full_path.is_file():
            return None
        return full_path.read_bytes()

    def _parse_path(self, path: str) -> tuple[Path | None, str | None, str]:
        """Parse a path into (tar_path, member_name, raw_path).

        Returns (tar_path, member_name, raw_path) where tar_path is set if the
        path refers to a tar member, otherwise both tar_path and member_name are
        None and raw_path is used for directory loading.
        """
        parts = path.split("/", 1)
        if len(parts) == 2 and parts[0].endswith(".tar"):
            tar_path = self._base_path / parts[0]
            if tar_path.is_file():
                return tar_path, parts[1], path
        return None, None, path

    def _sync_load_file(self, path: str) -> bytes | None:
        """Synchronous file loading (called from asyncio.to_thread)."""
        tar_path, member_name, raw_path = self._parse_path(path)
        if tar_path is not None and member_name is not None:
            return self._load_from_tar(tar_path, member_name)
        return self._load_from_directory(raw_path)

    def _sync_load_files(self, paths: list[str]) -> dict[str, bytes]:
        """Synchronous batch file loading, grouping tar reads by archive."""
        results: dict[str, bytes] = {}

        # Group paths by storage unit
        tar_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
        dir_paths: list[str] = []

        for path in paths:
            tar_path, member_name, raw_path = self._parse_path(path)
            if tar_path is not None and member_name is not None:
                tar_groups[str(tar_path)].append((path, member_name))
            else:
                dir_paths.append(raw_path)

        # Load from tar archives (grouped by archive for efficiency)
        for tar_path_str, members in tar_groups.items():
            tar_path_obj = Path(tar_path_str)
            tar_name = tar_path_obj.name

            if not self._is_indexed(tar_name):
                self._index_tar(tar_path_obj, tar_name)

            for orig_path, member_name in members:
                data = self._load_from_tar(tar_path_obj, member_name)
                if data is not None:
                    results[orig_path] = data

        # Load from directories
        for path in dir_paths:
            data = self._load_from_directory(path)
            if data is not None:
                results[path] = data

        return results

    def _sync_list_files(self, pattern: str) -> list[str]:
        """Synchronous file listing by glob pattern."""
        return [
            str(p.relative_to(self._base_path))
            for p in self._base_path.glob(pattern)
            if p.is_file()
        ]

    async def load_file(self, path: str) -> bytes | None:
        """Load a single file by relative path.

        For tar members, use ``"archive.tar/member_name.json"`` format.

        Args:
            path: Relative path from the base directory.

        Returns:
            File contents as bytes, or ``None`` if the file does not exist.
        """
        return await asyncio.to_thread(self._sync_load_file, path)

    async def load_files(self, paths: list[str]) -> dict[str, bytes]:
        """Batch-load multiple files, grouping tar reads by archive.

        Args:
            paths: List of relative paths.

        Returns:
            Dict mapping each successfully loaded path to its bytes content.
        """
        return await asyncio.to_thread(self._sync_load_files, paths)

    async def list_files(self, pattern: str = "*") -> list[str]:
        """List files matching a glob pattern relative to the base directory.

        Args:
            pattern: Glob pattern (default ``"*"``).

        Returns:
            List of relative file paths matching the pattern.
        """
        return await asyncio.to_thread(self._sync_list_files, pattern)

    async def close(self) -> None:
        """Close the SQLite index connection, if one was opened."""
        if self._db is not None:
            self._db.close()
            self._db = None

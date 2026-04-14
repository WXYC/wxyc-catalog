import asyncio
import io
import tarfile

from wxyc_catalog.sources.archive import ArchiveSource


class TestArchiveSourceDirectory:
    """ArchiveSource should load files from a directory."""

    async def test_load_file_from_directory(self, tmp_path):
        """Should load a file by relative path from the base directory."""
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "file.json").write_text('{"key": "value"}')

        source = ArchiveSource(tmp_path)
        content = await source.load_file("data/file.json")
        assert content is not None
        assert b'"key"' in content
        await source.close()

    async def test_load_missing_file_returns_none(self, tmp_path):
        """Should return None for non-existent files."""
        source = ArchiveSource(tmp_path)
        content = await source.load_file("nonexistent.json")
        assert content is None
        await source.close()

    async def test_list_files(self, tmp_path):
        """Should list files matching a glob pattern."""
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("")

        source = ArchiveSource(tmp_path)
        json_files = await source.list_files("*.json")
        assert len(json_files) == 2
        assert all(f.endswith(".json") for f in json_files)
        await source.close()

    async def test_load_files_batch(self, tmp_path):
        """Should batch-load multiple files from a directory."""
        for i in range(3):
            (tmp_path / f"file_{i}.json").write_text(f'{{"id": {i}}}')

        source = ArchiveSource(tmp_path)
        results = await source.load_files([f"file_{i}.json" for i in range(3)])
        assert len(results) == 3
        await source.close()


class TestArchiveSourceTar:
    """ArchiveSource should load files from tar archives."""

    async def test_load_file_from_tar(self, tmp_path):
        """Should load a file from a tar archive."""
        tar_path = tmp_path / "archive.tar"
        content = b'{"feature": [1.0, 2.0, 3.0]}'
        with tarfile.open(tar_path, "w") as tf:
            info = tarfile.TarInfo(name="Q12345.json")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        source = ArchiveSource(tmp_path)
        loaded = await source.load_file("archive.tar/Q12345.json")
        assert loaded is not None
        assert b'"feature"' in loaded
        await source.close()

    async def test_load_missing_member_returns_none(self, tmp_path):
        """Should return None for non-existent tar members."""
        tar_path = tmp_path / "archive.tar"
        with tarfile.open(tar_path, "w") as tf:
            data = b"{}"
            info = tarfile.TarInfo(name="exists.json")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        source = ArchiveSource(tmp_path)
        loaded = await source.load_file("archive.tar/missing.json")
        assert loaded is None
        await source.close()

    async def test_batch_load_from_tar(self, tmp_path):
        """Should batch-load multiple files from the same tar efficiently."""
        tar_path = tmp_path / "archive.tar"
        with tarfile.open(tar_path, "w") as tf:
            for i in range(5):
                data = f'{{"id": {i}}}'.encode()
                info = tarfile.TarInfo(name=f"file_{i}.json")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

        source = ArchiveSource(tmp_path)
        paths = [f"archive.tar/file_{i}.json" for i in range(5)]
        results = await source.load_files(paths)
        assert len(results) == 5
        await source.close()


class TestArchiveSourceSqliteIndex:
    """ArchiveSource should persist a SQLite index for tar member lookup."""

    async def test_creates_index_on_first_access(self, tmp_path):
        """SQLite index should be created on first tar access."""
        tar_path = tmp_path / "archive.tar"
        with tarfile.open(tar_path, "w") as tf:
            data = b"{}"
            info = tarfile.TarInfo(name="test.json")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        index_path = tmp_path / "index.db"
        source = ArchiveSource(tmp_path, index_path=index_path)
        await source.load_file("archive.tar/test.json")
        assert index_path.exists()
        await source.close()

    async def test_reuses_existing_index(self, tmp_path):
        """Second access should use the existing SQLite index, not re-scan."""
        tar_path = tmp_path / "archive.tar"
        with tarfile.open(tar_path, "w") as tf:
            data = b"{}"
            info = tarfile.TarInfo(name="test.json")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        index_path = tmp_path / "index.db"
        # First access: build index
        source1 = ArchiveSource(tmp_path, index_path=index_path)
        await source1.load_file("archive.tar/test.json")
        mtime1 = index_path.stat().st_mtime
        await source1.close()

        await asyncio.sleep(0.1)

        # Second access: reuse index (mtime should not change)
        source2 = ArchiveSource(tmp_path, index_path=index_path)
        await source2.load_file("archive.tar/test.json")
        mtime2 = index_path.stat().st_mtime
        assert mtime1 == mtime2
        await source2.close()


class TestArchiveSourceClose:
    """ArchiveSource close() should clean up resources."""

    async def test_close_is_safe(self, tmp_path):
        """close() should be safe to call even without any file access."""
        source = ArchiveSource(tmp_path)
        await source.close()  # should not raise

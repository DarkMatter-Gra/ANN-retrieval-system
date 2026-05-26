"""
FAISS/hnswlib file I/O helpers for Windows paths with non-ASCII characters.

FAISS's C runtime uses the ANSI fopen, which cannot open paths containing
characters outside the system code-page (e.g. CJK). Work around this by
routing I/O through a temp file in %TEMP% (always ASCII) and moving/copying
as needed.
"""

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import faiss
import hnswlib


@contextlib.contextmanager
def _ascii_write(target: Path) -> Generator[str, None, None]:
    fd, tmp = tempfile.mkstemp(suffix=target.suffix)
    os.close(fd)
    try:
        yield tmp
        shutil.move(tmp, str(target))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def _ascii_read(source: str) -> Generator[str, None, None]:
    if source.isascii():
        yield source
        return
    fd, tmp = tempfile.mkstemp(suffix=Path(source).suffix)
    os.close(fd)
    shutil.copy2(source, tmp)
    try:
        yield tmp
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def write_faiss(index: faiss.Index, path: str) -> None:
    if path.isascii():
        faiss.write_index(index, path)
        return
    with _ascii_write(Path(path)) as tmp:
        faiss.write_index(index, tmp)


def read_faiss(path: str) -> faiss.Index:
    with _ascii_read(path) as tmp:
        return faiss.read_index(tmp)


def write_hnsw(hnsw: hnswlib.Index, path: str) -> None:
    if path.isascii():
        hnsw.save_index(path)
        return
    with _ascii_write(Path(path)) as tmp:
        hnsw.save_index(tmp)


def load_hnsw(path: str, space: str, dim: int) -> hnswlib.Index:
    obj = hnswlib.Index(space=space, dim=dim)
    with _ascii_read(path) as tmp:
        obj.load_index(tmp)
    return obj

import shutil
from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def remove_dir(path: Path | str) -> None:
    p = Path(path)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def merge_chunks(chunk_paths: list[Path], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        for chunk in sorted(chunk_paths):
            f.write(chunk.read_bytes())
    return target

import numpy as np


def encode_vector(vector: np.ndarray) -> bytes:
    """统一 float32 + 行向量字节流，便于跨语言/版本兼容。"""
    return np.asarray(vector, dtype=np.float32).tobytes()


def decode_vector(blob: bytes, dim: int | None = None) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float32)
    if dim is not None:
        arr = arr.reshape(-1, dim)
    return arr


def stack_vectors(blobs: list[bytes]) -> np.ndarray:
    return np.vstack([np.frombuffer(b, dtype=np.float32) for b in blobs]).astype(np.float32)

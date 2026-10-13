"""Deterministic hashed bag-of-words embedding. A stand-in, not a semantic model: it only
needs to put summaries that share words near each other for memory.similar."""
import hashlib
import math
import re

DIM = 64


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        h = int.from_bytes(hashlib.md5(token.encode()).digest()[:4], "big")
        vec[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

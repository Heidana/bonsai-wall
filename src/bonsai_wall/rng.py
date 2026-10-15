"""Seed streams and hashed per-entity draws for V2.

Only this module creates randomness in V2 code (V1 keeps its own `random.Random`
derivation untouched, see docs/v1_inventory.md section 9). Per-entity draws are
hashed from (seed, stream, keys...) so a local change stays local.
"""
from __future__ import annotations

import numpy as np

STREAMS = ("look", "layout", "origin", "biology", "maintainer", "render", "anim")
STREAM_IDS = {name: i + 1 for i, name in enumerate(STREAMS)}
_M = (1 << 64) - 1


def stream(seed: int, name: str) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, STREAM_IDS[name]])))


def _mix(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & _M
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _M
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _M
    return x ^ (x >> 31)


def hash_u01(seed: int, stream_id: int, *keys: int) -> float:
    """splitmix64 over (seed, stream, keys...) -> [0, 1)."""
    h = _mix(seed & _M)
    h = _mix(h ^ (stream_id & _M))
    for k in keys:
        h = _mix(h ^ (int(k) & _M))
    return (h >> 11) * (1.0 / (1 << 53))


def _mix_np(x):
    u = np.uint64
    x = x + u(0x9E3779B97F4A7C15)
    x = (x ^ (x >> u(30))) * u(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> u(27))) * u(0x94D049BB133111EB)
    return x ^ (x >> u(31))


def hash_u01_np(seed: int, stream_id: int, *keys) -> np.ndarray:
    """Vectorised hash_u01; `keys` are integer arrays (or scalars) that broadcast."""
    u = np.uint64
    with np.errstate(over="ignore"):
        h = _mix_np(u(seed & _M))
        h = _mix_np(h ^ u(stream_id & _M))
        for k in keys:
            h = _mix_np(h ^ np.asarray(k).astype(np.int64).astype(np.uint64))
        return (h >> u(11)).astype(np.float64) * (1.0 / (1 << 53))

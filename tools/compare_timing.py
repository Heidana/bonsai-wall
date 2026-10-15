#!/usr/bin/env python3
"""Phase 1 exit check: end-to-end time of the zipapp vs the untouched root script.

Jobs run in A B B A order on one core (taskset -c 0), 4K, --preview only, so drift cancels.
Usage (fish):
  python build.py
  python tools/compare_timing.py
"""
from __future__ import annotations

import csv
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import baseline_v1 as b  # noqa: E402

OUT = ROOT / "docs" / "baseline" / "p1_timing.csv"
SIZE = b.SIZE_4K
A = [sys.executable, str(ROOT / "bonsai-wall.py")]
B = [str(ROOT / "dist" / "bonsai-wall")]


def timed(cmd, sp, st, seed):
    with tempfile.TemporaryDirectory() as td:
        full = ["taskset", "-c", "0"] + cmd + ["--seed", str(seed), "--species", sp, "--style", st,
                                               "--size", SIZE, "--preview", td]
        t0 = time.perf_counter()
        r = subprocess.run(full, capture_output=True, text=True)
        dt = time.perf_counter() - t0
        assert r.returncode == 0, r.stderr
        return dt


def main():
    rows = []
    for sp, st in b.combos():
        for seed in (1, 2):
            for tag, cmd in (("ref", A), ("pkg", B), ("pkg", B), ("ref", A)):
                rows.append(dict(species=sp, style=st, seed=seed, target=tag,
                                 wall_s=timed(cmd, sp, st, seed)))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for tag in ("ref", "pkg"):
        v = [r["wall_s"] for r in rows if r["target"] == tag]
        print(f"{tag}: n={len(v)} mean {statistics.mean(v):.3f} p50 {np.percentile(v, 50):.3f} "
              f"p95 {np.percentile(v, 95):.3f}")
    ref = [r["wall_s"] for r in rows if r["target"] == "ref"]
    pkg = [r["wall_s"] for r in rows if r["target"] == "pkg"]
    for name, f in (("mean", statistics.mean), ("p50", lambda x: np.percentile(x, 50)),
                    ("p95", lambda x: np.percentile(x, 95))):
        print(f"pkg/ref {name}: {f(pkg) / f(ref):.3f}")


if __name__ == "__main__":
    main()

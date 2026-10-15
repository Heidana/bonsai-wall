#!/usr/bin/env python3
"""Generate tests/golden/v1_goldens.json from the untouched root script bonsai-wall.py.

Run once at the start of Phase 1; the file is committed. Usage (fish):
  python tools/make_goldens.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import golden_cases as gc  # noqa: E402

_API = None


def api():
    global _API
    if _API is None:
        spec = importlib.util.spec_from_file_location("bw_ref", ROOT / "bonsai-wall.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _API = m
    return _API


def work(case):
    S, frames = gc.run_case(api(), case)
    return dict(case, **gc.digest(S, frames))


def pick_cases():
    m = api()
    per, seeds = {}, []
    for seed in range(1, 200):
        sp = m.choose_look(seed)["species"]
        if per.get(sp, 0) < 3 or (len(seeds) < 20 and per.get(sp, 0) < 4):
            per[sp] = per.get(sp, 0) + 1
            seeds.append(seed)
        if len(seeds) == 20:
            break
    cases = []
    for i, seed in enumerate(seeds):
        bg = "scene" if i % 5 == 4 else "studio"
        look = m.choose_look(seed, "random", "auto", bg, "auto")
        for size in gc.SIZES:
            cases.append(dict(seed=seed, size=size, species=look["species"], style=None, bg=bg))
    for sp in sorted(m.SPECIES):
        for st in sorted(m.SPECIES[sp]["styles"]):
            cases.append(dict(seed=7, size=gc.SIZES[0], species=sp, style=st, bg="studio"))
    return cases


if __name__ == "__main__":
    cases = pick_cases()
    with Pool(12) as pool:
        out = pool.map(work, cases, chunksize=2)
    path = ROOT / "tests" / "golden" / "v1_goldens.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {len(out)} goldens to {path}")

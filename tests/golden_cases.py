"""Golden cases shared by tools/make_goldens.py and tests/test_goldens.py.

A case is rendered through an `api` object exposing choose_look, grow_scene and
render_frames with V1's signatures (the untouched script or the package).
"""
from __future__ import annotations

import hashlib

SIZES = ("2560x1440", "3440x1440", "1440x2560")      # 16:9, 21:9, portrait
SCALE_TARGET = 360


def art_size(api, size):
    w, h = (int(v) for v in size.split("x"))
    s = api.pick_scale(w, h)
    return -(-w // s), -(-h // s)


def run_case(api, case):
    """case = dict(seed, size, species, style, bg). Returns (S, frames)."""
    cw, ch = art_size(api, case["size"])
    look = api.choose_look(case["seed"], "random", "auto", case["bg"], "auto", None, None,
                           case["species"])
    look["style"] = case["style"]
    S = api.grow_scene(case["seed"], cw, ch, look, 0.5)
    frames = api.render_frames(S, 10.0, 12.0)
    return S, frames


def digest(S, frames):
    h = hashlib.sha256()
    h.update(bytes(S.bg.getpalette() or b""))
    for f in frames:
        h.update(f.tobytes())
    return dict(sha=h.hexdigest(), frames=len(frames), palette=len(S.pal),
                xmin=S.xmin, xmax=S.xmax, crown_top=S.crown_top)

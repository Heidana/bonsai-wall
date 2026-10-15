"""D5/D6: the front-limb layer and the shari band must not touch the V1 path."""
from __future__ import annotations

import dataclasses

from bonsai_wall import animate
from bonsai_wall.ir import Stroke
from bonsai_wall.look import choose_look
from bonsai_wall.render.limbs import draw_limb
from bonsai_wall.render.static import finish, prepare
from bonsai_wall.v1.builder import build_tree

PTS = tuple((20.0 + i * 0.5, 10.0 + i * 0.1) for i in range(60))
RAD = tuple(6.0 - i * 0.05 for i in range(60))


def test_draw_limb_default_equals_explicit_none():
    a, b = {}, {}
    draw_limb(a, PTS, RAD, 3, rough=0.3, shari_frac=0.4)
    draw_limb(b, PTS, RAD, 3, rough=0.3, shari_frac=0.4, shari_band=None)
    assert a == b


def test_shari_band_marks_deadwood():
    plain, banded = {}, {}
    draw_limb(plain, PTS, RAD, 3)
    band = tuple((-0.2, 0.3) for _ in PTS)
    draw_limb(banded, PTS, RAD, 3, shari_band=band)
    assert all(v[1] >= 0 for v in plain.values())
    dead = [p for p, v in banded.items() if v[1] < 0]
    assert len(dead) > 50
    assert set(banded) == set(plain)                    # same footprint, only the shading differs
    none_band = tuple(None for _ in PTS)
    clean = {}
    draw_limb(clean, PTS, RAD, 3, shari_band=none_band)
    assert all(v[1] >= 0 for v in clean.values())


def scene_for(extra=()):
    look = choose_look(8, "random", "auto", "studio", "auto", None, None, "acer")
    look["style"] = "moyogi"
    t = build_tree(8, 640, 360, look)
    if extra:
        t = dataclasses.replace(t, strokes=t.strokes + tuple(extra))
    S = prepare(t, look)
    return finish(S)


def test_v1_has_no_front_limb_layer():
    S = scene_for()
    assert S.over is None


def test_front_limb_layer_composites_after_pads():
    xs = [(p.cx, p.cy) for p in build_tree(8, 640, 360, choose_look(8, "random", "auto", "studio", "auto", None, None, "acer")).pads]
    cx, cy = xs[0]
    limb = Stroke(pts=tuple((cx - 20 + i, cy) for i in range(41)), radius=tuple([2.5] * 41), seed=1,
                  order=2, layer="over", bark="acer")
    S0, S1 = scene_for(), scene_for((limb,))
    assert S1.over is not None
    f0, f1 = animate.render_frames(S0, 10.0, 1.0)[0], animate.render_frames(S1, 10.0, 1.0)[0]
    assert f0.tobytes() != f1.tobytes()
    ys = [i for i in range(int(cy) - 4, int(cy) + 5)]
    p = f1.load()
    assert any(p[int(cx) + dx, y] != f0.load()[int(cx) + dx, y] for dx in range(-15, 15, 3) for y in ys)

from __future__ import annotations

import dataclasses

import pytest

from bonsai_wall.ir import Stroke, validate
from bonsai_wall.look import SPECIES, choose_look
from bonsai_wall.v1.builder import build_tree

COMBOS = [(sp, st) for sp in sorted(SPECIES) for st in sorted(SPECIES[sp]["styles"])]


def tree(sp, st, seed=3, W=640, H=360):
    look = choose_look(seed, "random", "auto", "studio", "auto", None, None, sp)
    look["style"] = st
    return build_tree(seed, W, H, look), look


@pytest.mark.parametrize("sp,st", COMBOS)
def test_v1_scene_is_valid(sp, st):
    t, _ = tree(sp, st)
    assert validate(t) == []
    assert t.strokes[0].order == 0 and t.strokes[0].layer in ("back", "front")
    assert t.meta["engine"] == "v1" and t.meta["species"] == sp and t.meta["style"] == st
    assert all(s.layer != "over" for s in t.strokes)        # V1 never uses the front-limb layer
    assert all(s.shari is None for s in t.strokes)          # V1 uses shari_frac only
    assert {s.order for s in t.strokes} <= {0, 1, 2, 3}
    assert t.pads and t.layout.Ht > 0


def test_builder_is_deterministic():
    a, _ = tree("pinus", "moyogi", seed=11)
    b, _ = tree("pinus", "moyogi", seed=11)
    assert a == b                                           # v1_rng is excluded from equality
    c, _ = tree("pinus", "moyogi", seed=12)
    assert a != c


def test_validate_catches_problems():
    t, _ = tree("acer", "moyogi")
    s0 = t.strokes[0]
    bad = dataclasses.replace(t, strokes=(dataclasses.replace(s0, radius=s0.radius[:-1]),) + t.strokes[1:])
    assert any("radii" in p for p in validate(bad))
    bad = dataclasses.replace(t, strokes=(dataclasses.replace(s0, layer="sideways"),) + t.strokes[1:])
    assert any("layer" in p for p in validate(bad))
    p0 = t.pads[0]
    bad = dataclasses.replace(t, pads=(dataclasses.replace(p0, ramp=99),) + t.pads[1:])
    assert any("ramp index" in p for p in validate(bad))
    bad = dataclasses.replace(t, pads=())
    assert "no pads" in validate(bad)
    assert Stroke(pts=((0, 0), (1, 1)), radius=(1, 1), seed=1, order=0)   # defaults are valid

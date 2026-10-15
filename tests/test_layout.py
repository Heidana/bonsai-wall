from __future__ import annotations

import pytest

from bonsai_wall.layout import DesignSpace
from bonsai_wall.look import SPECIES, choose_look
from bonsai_wall.v1.builder import build_tree

COMBOS = [(sp, st) for sp in sorted(SPECIES) for st in sorted(SPECIES[sp]["styles"])]


@pytest.mark.parametrize("sp,st", COMBOS)
@pytest.mark.parametrize("size", [(640, 360), (860, 360), (180, 320)])
def test_design_space_from_v1_layout(sp, st, size):
    W, H = size
    look = choose_look(5, "random", "auto", "studio", "auto", None, None, sp)
    look["style"] = st
    lay = build_tree(5, W, H, look).layout
    ds = DesignSpace.from_layout(lay)
    assert ds.free_height == lay.yb - 0.07 * H
    assert lay.Ht <= ds.free_height + 1e-9               # V1: Ht = min(hfrac * H, free height)
    assert ds.height_lo <= ds.height_hi <= ds.free_height + 1e-9
    assert lay.rim_top < lay.pot_bot <= lay.stand_top + 1 < lay.stand_bot <= H
    assert ds.left < ds.right and 0 < ds.top_y < ds.base_y
    assert lay.soil_top(lay.xc) == lay.rim_top - lay.mound
    assert lay.soil_top(lay.xc + lay.soil_half + 1) == lay.rim_top


def test_design_space_depends_only_on_layout_rows():
    look = choose_look(5, "random", "auto", "studio", "auto", None, None, "acer")
    look["style"] = "moyogi"
    lay = build_tree(5, 640, 360, look).layout
    a = DesignSpace.from_layout(lay, (0.40, 0.50))
    b = DesignSpace.from_layout(lay, (0.40, 0.50))
    assert a == b
    assert a.height_lo == 0.40 * 360 and a.height_hi == 0.50 * 360

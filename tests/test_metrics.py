from __future__ import annotations

import numpy as np
import pytest

from bonsai_wall import metrics
from bonsai_wall.look import SPECIES, choose_look
from bonsai_wall.v1.builder import build_tree


def tree(sp, st, seed=3):
    look = choose_look(seed, "random", "auto", "studio", "auto", None, None, sp)
    look["style"] = st
    return build_tree(seed, 640, 360, look)


def test_metrics_are_sane_for_every_combo():
    for sp in sorted(SPECIES):
        for st in sorted(SPECIES[sp]["styles"]):
            m, g, h = metrics.scene_metrics(tree(sp, st))
            assert 40 < m["tree_h"] < 330 and m["width_over_h"] > 0.2, (sp, st)
            assert g.shape == (metrics.GRID_H, metrics.GRID_W) and g.any()
            assert abs(h.sum() - 1) < 1e-9 and m["n_primary"] > 0
            assert 0 <= m["inner_open"] <= 1 and m["taper"] > 0 and m["bends"] >= 0


def test_structure_distance_properties():
    a = metrics.scene_metrics(tree("pinus", "moyogi", 1))
    b = metrics.scene_metrics(tree("pinus", "moyogi", 2))
    d_same = metrics.structure_distance(a[1], a[2], a[1], a[2])
    d_ab = metrics.structure_distance(a[1], a[2], b[1], b[2])
    assert d_same == 0 and 0 < d_ab <= 1
    assert d_ab == metrics.structure_distance(b[1], b[2], a[1], a[2])


def test_canonical_makes_mirror_images_identical():
    g, h = metrics.scene_metrics(tree("pinus", "fukinagashi", 4))[1:]
    gm, hm = g[:, ::-1], h[::-1]
    c1, c2 = metrics.canonical(g, h), metrics.canonical(gm, hm)
    assert np.array_equal(c1[0], c2[0]) and np.allclose(c1[1], c2[1])
    assert metrics.structure_distance(g, h, gm, hm) > 0.3       # raw metric calls them different
    assert metrics.structure_distance(*c1, *c2) < 1e-9


def test_bends_counts_s_curve():
    t = np.linspace(0, 1, 60)
    xs, ys = 10 * np.sin(2 * np.pi * t), 100 - 100 * t
    lobes, amp, max_turn, total = metrics.bends_and_turns(xs, ys)
    assert lobes == 2 and total > max_turn > 0 and 8 < amp < 11
    lobes, amp, _, _ = metrics.bends_and_turns(np.zeros(30), np.linspace(100, 0, 30))
    assert amp == 0
    assert lobes == 0


def _frame0(t, look):
    from bonsai_wall import animate
    from bonsai_wall.render.static import finish, prepare
    S = finish(prepare(t, look))
    return S, animate.render_frames(S, 10.0, 1.0)[0]


def test_stand_overlap_excludes_only_pixels_the_pot_hides():
    """acer broom, seed 22: the trunk base flare disc reaches below the pot into the stand rows.

    The naive count sees it; `stand_overlap_px` does not, because the final frame shows no trace of
    it there. Proof: replace the main trunk by a hairline copy (no flare) and the frame is
    pixel-identical at every pixel the flare covered inside the stand rows.
    """
    import dataclasses

    seed = 22
    look = choose_look(seed, "random", "auto", "studio", "auto", None, None, "acer")
    look["style"] = "broom"
    t = build_tree(seed, 640, 360, look)
    lay = t.layout
    limb, fol = metrics.masks(t)
    sx0, sx1 = int(lay.xc - lay.stand_w / 2), int(lay.xc + lay.stand_w / 2)
    flare = limb[lay.stand_top:, sx0:sx1 + 1] & ~fol[lay.stand_top:, sx0:sx1 + 1]
    ys, xs = np.nonzero(flare)
    assert len(ys) >= 5, "this seed must have flare in the stand rows"      # the naive overlap
    m, _, _ = metrics.scene_metrics(t)
    assert m["stand_overlap_px"] == 0                                        # the metric ignores it

    s0 = t.strokes[0]
    hair = dataclasses.replace(s0, radius=tuple(0.5 for _ in s0.radius))
    t2 = build_tree(seed, 640, 360, look)       # fresh builder state: prepare() consumes v1_rng
    t2 = dataclasses.replace(t2, strokes=(hair,) + t2.strokes[1:])
    t = build_tree(seed, 640, 360, look)
    _, a = _frame0(t, look)
    _, b = _frame0(t2, look)
    pa, pb = a.load(), b.load()
    for x, y in zip(xs + sx0, ys + lay.stand_top):
        assert pa[int(x), int(y)] == pb[int(x), int(y)], (x, y)             # flare left no trace
    # and the flare really is drawn above the pot rim, so the exclusion is not hiding visible limb
    above = limb[:lay.rim_top + 1].sum()
    assert above > 0 and not np.array_equal(np.asarray(a), np.asarray(b))

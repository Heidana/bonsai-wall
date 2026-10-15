"""Realism and style metrics over a projected TreeScene (2D front view).

Both engines are measured from the same IR: strokes (limbs) and pads (foliage extents), so
V1 and V2 numbers are comparable. Used by the harness and tests now, and by the maintainer's
perception later. Conventions: art px, y down, strokes[0] is the main trunk.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

GRID_W, GRID_H = 192, 144       # height-normalised silhouette: x in [xb-H, xb+H], y in [yb-H, yb+H/2]
ANG_BINS = 24


# ---------------------------------------------------------------- rasterisation
def _pad_polygon(p, n=40):
    pts = []
    for i in range(n):
        a = math.tau * i / n
        s = math.sin(a)
        pts.append((p.cx + p.rx * math.cos(a), p.cy + (p.ryt if s < 0 else p.ryb) * s))
    return pts


def masks(scene):
    """(limb mask, foliage mask) as bool arrays of the canvas size."""
    lay = scene.layout
    W, H = lay.W, lay.H
    limbs = Image.new("L", (W, H), 0)
    fol = Image.new("L", (W, H), 0)
    dl, df = ImageDraw.Draw(limbs), ImageDraw.Draw(fol)
    for s in scene.strokes:
        pts, rad = s.pts, s.radius
        step = 2 if len(pts) > 2 and math.dist(pts[0], pts[1]) < 0.9 else 1
        idx = list(range(0, len(pts), step))
        if idx[-1] != len(pts) - 1:
            idx.append(len(pts) - 1)
        for i in idx:
            r = max(0.5, rad[i])
            x, y = pts[i]
            dl.ellipse((x - r, y - r, x + r, y + r), fill=255)
    for p in scene.pads:
        df.polygon(_pad_polygon(p), fill=255)
    return np.asarray(limbs) > 0, np.asarray(fol) > 0


def hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h

    lo, up = half(pts), half(reversed(pts))
    return lo[:-1] + up[:-1]


def row_extremes(mask):
    ys = np.nonzero(mask.any(axis=1))[0]
    pts = []
    for y in ys:
        xs = np.nonzero(mask[y])[0]
        pts += [(int(xs[0]), int(y)), (int(xs[-1]), int(y))]
    return pts


def hull_mask(mask):
    poly = hull(row_extremes(mask))
    im = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
    if len(poly) >= 3:
        ImageDraw.Draw(im).polygon(poly, fill=255)
    return np.asarray(im) > 0


# ---------------------------------------------------------------- trunk
def trunk_profile(scene, step=4.0):
    """Trunk polyline resampled every `step` px of arc length: (xs, ys, radii)."""
    s = scene.strokes[0]
    pts = np.array(s.pts, float)
    d = np.r_[0.0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    n = max(2, int(d[-1] / step) + 1)
    t = np.linspace(0, d[-1], n)
    return (np.interp(t, d, pts[:, 0]), np.interp(t, d, pts[:, 1]),
            np.interp(t, d, np.array(s.radius, float)), float(d[-1]))


def radius_at_height(scene, f, tree_h, yb):
    s = scene.strokes[0]
    ys = np.array([p[1] for p in s.pts])
    i = int(np.argmin(np.abs(ys - (yb - f * tree_h))))
    return float(s.radius[i])


def bends_and_turns(xs, ys):
    """(lobes, mean lobe amplitude px, sharpest heading change deg, total turning deg).

    Lobes are runs on one side of the base-apex chord that reach more than 2 px off it."""
    p0, p1 = np.array([xs[0], ys[0]]), np.array([xs[-1], ys[-1]])
    chord = p1 - p0
    L = float(np.hypot(*chord)) or 1.0
    nx, ny = -chord[1] / L, chord[0] / L
    d = (xs - p0[0]) * nx + (ys - p0[1]) * ny
    lobes, cur, peak, amps = 0, 0, 0.0, []
    for v in d:
        sgn = 1 if v > 0 else -1
        if sgn != cur:
            if cur and peak > 2.0:
                lobes += 1
                amps.append(peak)
            cur, peak = sgn, 0.0
        peak = max(peak, abs(v))
    if cur and peak > 2.0:
        lobes += 1
        amps.append(peak)
    seg = np.diff(np.c_[xs, ys], axis=0)
    head = np.degrees(np.arctan2(seg[:, 0], -seg[:, 1]))
    dh = np.abs((np.diff(head) + 180) % 360 - 180)
    return lobes, (float(np.mean(amps)) if amps else 0.0), float(dh.max()) if len(dh) else 0.0, float(dh.sum())


# ---------------------------------------------------------------- per-scene metrics
def scene_metrics(scene):
    """Return (metrics dict, silhouette grid bool[GRID_H, GRID_W], primary-angle histogram)."""
    lay = scene.layout
    W, H = lay.W, lay.H
    limb, fol = masks(scene)
    tree = limb | fol
    ys, xs = np.nonzero(tree)
    top = int(ys.min())
    xb, yb = lay.xb, lay.yb
    tree_h = max(1.0, yb - top)
    apex_x = float(xs[ys <= top + 2].mean())
    fy = np.nonzero(fol)[0]
    hm = hull_mask(tree)
    neg = float((hm & ~tree).sum()) / max(1, int(hm.sum()))

    # trunk: taper, apex, bends
    tx, ty, tr, tlen = trunk_profile(scene)
    lobes, bend_amp, max_turn, total_turn = bends_and_turns(tx, ty)
    r_base = radius_at_height(scene, 0.05, tree_h, yb)
    r_70 = radius_at_height(scene, 0.70, tree_h, yb)
    r_tip = float(scene.strokes[0].radius[-1])

    top_pad = min(scene.pads, key=lambda p: p.cy)
    apex_w = 2 * top_pad.rx

    # inner thinning on the foliage hull: eroded core vs shell, at quarter resolution
    fh = hull_mask(fol)
    q = 4
    small = Image.fromarray((fh * 255).astype(np.uint8)).resize((W // q, H // q), Image.BOX)
    sm = np.asarray(small) > 127
    hw = (np.nonzero(sm.any(axis=0))[0][[0, -1]] if sm.any() else [0, 1])
    hh = (np.nonzero(sm.any(axis=1))[0][[0, -1]] if sm.any() else [0, 1])
    R = max(1, int(0.18 * min(hw[1] - hw[0], hh[1] - hh[0])))
    core = _erode(sm, R)
    core_full = np.asarray(Image.fromarray((core * 255).astype(np.uint8)).resize(
        (W // q * q, H // q * q), Image.NEAREST)) > 0
    core_full = np.pad(core_full, ((0, H - core_full.shape[0]), (0, W - core_full.shape[1])))
    shell = fh & ~core_full
    core_cov = float(fol[core_full & fh].mean()) if (core_full & fh).any() else float("nan")
    shell_cov = float(fol[shell].mean()) if shell.any() else float("nan")

    # lowest extent, stand and pot overlaps
    # the main trunk's base flare sits inside the pot by design: measure everything else
    low_stroke = max((max(p[1] + r for p, r in zip(s.pts, s.radius)) for s in scene.strokes[1:]),
                     default=0.0)
    low_pad = max((p.cy + p.ryb for p in scene.pads))
    lowest = max(low_stroke, low_pad)
    sx0 = int(lay.xc - lay.stand_w / 2)
    sx1 = int(lay.xc + lay.stand_w / 2)
    px0, px1 = int(lay.xc - lay.pot_w / 2), int(lay.xc + lay.pot_w / 2)
    # V1's renderer drops limb pixels below the rim inside the pot's width (the pot hides them;
    # trunk base flare reaches past the pot in shallow pots). Semi-cascades are re-stamped over the pot.
    visible = limb.copy()
    if scene.meta.get("style") != "hankengai":
        visible[lay.rim_top + 1:, max(0, px0):px1 + 1] = False
    stand_ov = int((visible | fol)[lay.stand_top:, max(0, sx0):sx1 + 1].sum())
    pot_rows = slice(lay.rim_top, lay.pot_bot - lay.feet)
    pad_in_pot = int(fol[pot_rows, max(0, px0):px1 + 1].sum())

    prim = [s for s in scene.strokes if s.order == 1 and s.wood == "live"]
    hist = np.zeros(ANG_BINS)
    for s in prim:
        dx, dy = s.pts[-1][0] - s.pts[0][0], s.pts[-1][1] - s.pts[0][1]
        ang = math.atan2(dx, -dy)
        b = min(ANG_BINS - 1, int((ang + math.pi) / math.tau * ANG_BINS))
        hist[b] += math.hypot(dx, dy)
    hist = hist / hist.sum() if hist.sum() else hist
    window60 = max(float(sum(hist[(i + j) % ANG_BINS] for j in range(4))) for i in range(ANG_BINS))
    # leeward = the side the crown leans to; share of foliage area on that side of the trunk base
    cols = np.arange(W)
    side_mask = (cols > xb) if apex_x >= xb else (cols < xb)
    leeward = float(fol[:, side_mask].sum()) / max(1, int(fol.sum()))

    box = (round(xb - tree_h), round(yb - tree_h), round(xb + tree_h), round(yb + 0.5 * tree_h))
    grid = np.asarray(Image.fromarray((tree * 255).astype(np.uint8)).crop(box).resize(
        (GRID_W, GRID_H), Image.BOX)) > 127

    met = dict(
        tree_h=tree_h, width_over_h=float(xs.max() - xs.min() + 1) / tree_h,
        crown_w=float(xs.max() - xs.min() + 1),
        lean_deg=abs(math.degrees(math.atan2(apex_x - xb, yb - top))),
        apex_offset=(apex_x - xb) / tree_h,
        foliage_centroid_h=(yb - float(fy.mean())) / tree_h if len(fy) else float("nan"),
        negative_space=neg, n_pads=len(scene.pads), n_strokes=len(scene.strokes),
        n_primary=len(prim),
        taper=r_base / max(0.1, r_70), trunk_len=tlen, trunk_h_frac=(yb - float(ty.min())) / tree_h,
        trunk_r_base=r_base, trunk_r_tip=r_tip, apex_ratio=r_tip / max(0.1, r_base),
        bends=lobes, bends_per_100px=lobes / max(1.0, tlen) * 100, bend_amp_px=bend_amp,
        bend_amp_over_r=bend_amp / max(0.1, r_base), height_over_base_d=tree_h / max(0.2, 2 * r_base),
        apex_pad_w_over_crown=apex_w / max(1.0, float(xs.max() - xs.min() + 1)),
        apex_pad_w_over_median=apex_w / max(1.0, float(np.median([2 * p.rx for p in scene.pads]))),
        leeward=leeward, primary_window_60=window60, max_turn_deg=max_turn, twist_deg_per_100px=total_turn / max(1.0, tlen) * 100,
        inner_cover=core_cov, shell_cover=shell_cov,
        inner_open=1 - core_cov if core_cov == core_cov else float("nan"),
        lowest_y=lowest, canvas_clear=(H - 1) - lowest, stand_clear=lay.stand_top - lowest,
        stand_overlap_px=stand_ov, pad_in_pot_px=pad_in_pot)
    return met, grid, hist


def _erode(mask, r):
    """Binary erosion by a (2r+1) square, numpy only."""
    out = mask.copy()
    for ax in (0, 1):
        acc = out.copy()
        for s in range(1, r + 1):
            acc &= np.roll(out, s, axis=ax) & np.roll(out, -s, axis=ax)
        out = acc
    return out


# ---------------------------------------------------------------- structure distance
def canonical(grid, hist):
    """Flip so the silhouette mass lies on +x (the engines mirror trees at random)."""
    cols = np.nonzero(grid)[1]
    if len(cols) and cols.mean() < (GRID_W - 1) / 2 - 0.5:
        return grid[:, ::-1], hist[::-1]
    return grid, hist


def structure_distance(g1, h1, g2, h2):
    """Mean of (1 - IoU of height-normalised silhouettes) and total variation of the
    primary-angle histograms. 0 = identical structure, 1 = nothing in common."""
    union = np.logical_or(g1, g2).sum()
    iou = np.logical_and(g1, g2).sum() / union if union else 1.0
    tv = 0.5 * float(np.abs(h1 - h2).sum())
    return 0.5 * ((1 - iou) + tv)

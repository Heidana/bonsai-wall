"""Limb rasteriser, moved from V1."""
from __future__ import annotations

import math

from ..util import LIGHT, h2


def draw_limb(buf, pts, radii, seed, streaks=True, rough=0.0, shari_frac=0.0, shari_band=None):
    """Stamp a tapered, cylinder-shaded limb into buf {(x,y): (depth, level)}.
    Negative levels (-1..-3) encode bleached deadwood (shari/jin).
    shari_band (V2): optional per-point (lo, hi) offsets in [-1, 1] across the limb that are dead
    wood; None keeps V1's single-fraction behaviour exactly.
    """
    lx, ly = LIGHT
    u = 0.0
    n = len(pts)
    for i in range(n):
        x, y = pts[i]
        r = radii[i]
        j0, j1 = max(0, i - 1), min(n - 1, i + 1)
        tx, ty = pts[j1][0] - pts[j0][0], pts[j1][1] - pts[j0][1]
        tl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / tl, tx / tl
        if nx * lx + ny * ly < 0:
            nx, ny = -nx, -ny
        if i:
            u += math.hypot(x - pts[i - 1][0], y - pts[i - 1][1])
        R = int(r) + 2
        ix, iy = int(x), int(y)
        shari_center = 0.22 * math.sin(u * 0.08 + seed * 0.13)
        for yy in range(iy - R, iy + R + 1):
            for xx in range(ix - R, ix + R + 1):
                dx, dy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(dx, dy)
                if d > r:
                    continue
                dn = d / r
                old = buf.get((xx, yy))
                if old is not None and old[0] <= dn:
                    continue
                s = (dx * nx + dy * ny) / r
                # Shari is strictly interior (dn < 0.58) so living bark always frames it
                shari_w = abs(s - shari_center)
                is_jin = shari_frac > 0.99
                is_shari = (not is_jin) and (
                    0.05 < shari_frac < 0.95 and r >= 2.8
                    and shari_w < shari_frac * 0.36
                    and dn < 0.58
                )
                if shari_band is not None and not is_jin:
                    band = shari_band[i]
                    is_shari = band is not None and band[0] <= s <= band[1] and dn < 0.9
                if is_jin or is_shari:
                    slev = -3 if s > 0.25 else -2 if s > -0.35 else -1
                    if h2(xx, int(u * 0.8), seed + 77) < 0.18:
                        slev = min(-1, slev + 1)
                    buf[(xx, yy)] = (dn, slev)
                    continue
                if r >= 2.5:
                    lev = 3 if s > 0.38 else 2 if s > -0.2 else 1 if s > -0.72 else 0
                    if dn > 0.84 and s < 0.25:
                        lev = max(0, lev - 1)
                    # Darken the living cambium roll right next to a shari vein
                    if 0.05 < shari_frac < 0.95 and r >= 2.8 and dn < 0.68 \
                            and shari_w < shari_frac * 0.36 + 0.16:
                        lev = 0
                    elif streaks:
                        hv = h2(round(s * r * 1.2) + 50, int(u / 2.6), seed)
                        if hv < 0.10 + 0.16 * rough:
                            lev = max(0, lev - 1)
                        elif hv > 0.94 - 0.05 * rough and lev == 2:
                            lev = 3
                elif r >= 1.4:
                    lev = 2 if s > 0.2 else 1
                else:
                    lev = 1
                buf[(xx, yy)] = (dn, lev)

"""Small helpers moved verbatim from V1."""
from __future__ import annotations

import math

TAU = math.tau
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
LIGHT = (-0.8, -0.6)  # unit vector pointing *towards* the light (upper left)


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def tint(c, f):
    return tuple(max(0, min(255, round(c[i] * f[i]))) for i in range(3))


def smooth(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def pixels(img):
    f = getattr(img, "get_flattened_data", None)
    return f() if f else img.getdata()


def luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def dith(x, y, frac):
    """Ordered (Bayer 4x4) dither decision, True with probability ~frac."""
    return frac * 16.0 > BAYER[y & 3][x & 3] + 0.5


def h2(x, y, s=0):
    """Cheap deterministic 2D hash -> [0, 1)."""
    n = (int(x) * 374761393 + int(y) * 668265263 + int(s) * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65536.0


def spline(ctrl, step=0.5):
    """Catmull-Rom through control points, sampled every ~step px."""
    if len(ctrl) < 2:
        return list(ctrl)
    p = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        segs = max(2, int(math.dist(p1, p2) / step))
        for j in range(segs):
            t = j / segs
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[a] + (-p0[a] + p2[a]) * t
                       + (2 * p0[a] - 5 * p1[a] + 4 * p2[a] - p3[a]) * t2
                       + (-p0[a] + 3 * p1[a] - 3 * p2[a] + p3[a]) * t3)
                for a in (0, 1)))
    out.append(tuple(ctrl[-1]))
    return out


def arcfrac(pts):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + math.dist(pts[i - 1], pts[i]))
    tot = d[-1] or 1.0
    return [v / tot for v in d], tot

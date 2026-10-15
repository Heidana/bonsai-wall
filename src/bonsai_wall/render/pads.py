"""Foliage pad sprite renderers, moved verbatim from V1."""
from __future__ import annotations

import math

from PIL import Image

from ..util import TAU, dith, h2


class RenderPad:
    """One foliage pad - rendered once, swayed per frame."""

    def __init__(self, cx, cy, rx, ryt, ryb, bias, back=False):
        self.cx, self.cy, self.rx, self.ryt, self.ryb = cx, cy, rx, ryt, ryb
        self.bias, self.back = bias, back
        self.kind = "cloud"
        self.droop = 0.0
        self.shear = 0.0
        self.ramp = self.ramp2 = self.tip_ramp = None
        self.tip_start = 1.0
        self.mix = 0.0
        self.grad = 0.95
        self.amp = 1.0
        self.lag = 0.0
        self.sprites = None
        self.ox = self.oy = 0
        self.bottom = {}


def _bake_pad_sprites(pad, grid, seed):
    if not grid:
        grid[(int(pad.cx), int(pad.cy))] = (2, False)
    xs = [p[0] for p in grid]
    ys = [p[1] for p in grid]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    im_a = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im_b = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pa, pb = im_a.load(), im_b.load()
    shimmer_p = 0.22 if pad.kind in ("needle", "scale", "larch") else 0.13
    for (x, y), (lev, alt) in grid.items():
        if alt == "tip" and pad.tip_ramp:
            leaf = pad.tip_ramp
        else:
            leaf = pad.ramp2 if (alt is True and pad.ramp2) else pad.ramp
        pa[x - x0, y - y0] = leaf[lev] + (255,)
        lb = lev + 1 if (1 <= lev <= 3 and h2(x, y, seed + 17) < shimmer_p) else lev
        pb[x - x0, y - y0] = leaf[lb] + (255,)
        if y > pad.bottom.get(x, -1):
            pad.bottom[x] = y
    pad.sprites = (im_a, im_b)
    pad.ox, pad.oy = x0, y0


def render_pad(pad, seed, rng):
    """Broadleaf cloud pad (Acer / Zelkova)."""
    rx, ryt, ryb = pad.rx, pad.ryt, pad.ryb
    fine = pad.kind == "fine"
    ph = [rng.uniform(0, TAU) for _ in range(3)]

    def inside(u, v):
        u_sh = u - pad.shear * v
        ry = ryt if v < 0 else ryb
        a = math.atan2(v / ry, u_sh / rx)
        m = 1 + 0.12 * math.sin(3 * a + ph[0]) + 0.08 * math.sin(5 * a + ph[1]) \
            + 0.05 * math.sin(8 * a + ph[2])
        return (u_sh / rx) ** 2 + (v / ry) ** 2 <= m * m

    bs = max(0.62 if fine else 0.72, min(1.15, rx / 22))
    if fine:
        bs *= 0.84
    n = int(math.pi * rx * (ryt + ryb) / 2 / (6.2 * bs * bs)) + 6
    blobs, tries = [], 0
    while len(blobs) < n and tries < n * 30:
        tries += 1
        u, v = rng.uniform(-rx * 1.1, rx * 1.1), rng.uniform(-ryt, ryb * 0.92)
        if inside(u * 1.06, v * 1.06):
            blobs.append((u, v, rng.uniform(1.6, 2.9) * bs))
    m = int(rx * 0.4) + 3
    for i in range(m):
        a = math.pi + math.pi * (i + rng.uniform(0.15, 0.85)) / m
        blobs.append((math.cos(a) * rx * 0.86, math.sin(a) * ryt * 0.86,
                      rng.uniform(1.8, 2.8) * bs))
    blobs.sort(key=lambda b: -(b[1] + rng.uniform(-1.0, 1.0)))

    grid = {}
    for u, v, rb in blobs:
        alt = rng.random() < pad.mix
        g = -(0.45 * u / rx + 0.95 * v / (ryt if v < 0 else ryb))
        base = 1.85 + pad.grad * g + pad.bias
        bx, by = pad.cx + u, pad.cy + v
        R = int(rb) + 1
        for yy in range(int(by) - R, int(by) + R + 1):
            for xx in range(int(bx) - R, int(bx) + R + 1):
                if fine and h2(xx, yy, seed + 41) < 0.09:
                    continue
                dx, dy = xx + 0.5 - bx, yy + 0.5 - by
                d2 = dx * dx + dy * dy
                if d2 > rb * rb:
                    continue
                l = -(0.55 * dx + 0.85 * dy) / rb
                val = base + 0.85 * l + (h2(xx, yy, seed) - 0.5) * 0.55
                if math.sqrt(d2) > rb - 0.9 and l < -0.1:
                    val -= 0.75 if pad.grad > 0.6 else 0.45
                grid[(xx, yy)] = (max(0, min(4, int(round(val)))), alt)

    for (x, y), (lev, alt) in list(grid.items()):
        if (x, y - 1) not in grid and lev >= 2 and h2(x, y, seed + 5) < 0.26:
            grid[(x, y - 1)] = (lev, alt)
        if (x, y + 1) not in grid and h2(x, y, seed + 6) < 0.14:
            grid[(x, y + 1)] = (0, alt)

    _bake_pad_sprites(pad, grid, seed)


def render_scale_pad(pad, seed, rng):
    """Shimpaku Juniper scale foliage: tight, crisp horizontal sub-clouds
    with bright sunlit upper ridges and dark recessed undersides."""
    rx, ryt, ryb = pad.rx, pad.ryt, pad.ryb
    n_sub = max(5, int(rx * 0.75))
    subclouds = []
    for i in range(n_sub):
        fx = (i + rng.uniform(0.1, 0.9)) / n_sub * 2 - 1
        u = fx * rx * 0.84
        v = rng.uniform(-ryt * 0.55, ryb * 0.35) + abs(fx) * ryb * 0.25
        srx = rng.uniform(2.8, 4.8) * max(0.75, min(1.2, rx / 16))
        sry = srx * rng.uniform(0.52, 0.68)
        subclouds.append((u, v, srx, sry))
    subclouds.sort(key=lambda c: -c[1])

    grid = {}
    for u, v, srx, sry in subclouds:
        bx, by = pad.cx + u, pad.cy + v
        g_pad = -(0.35 * u / rx + 0.85 * v / max(1.0, ryt + ryb))
        for yy in range(int(by - sry) - 1, int(by + sry * 0.85) + 2):
            for xx in range(int(bx - srx) - 1, int(bx + srx) + 2):
                dx = (xx + 0.5 - bx) / srx
                dy = (yy + 0.5 - by) / sry
                scallop = 0.14 * math.sin(dx * 4.5 + u)
                if dy > 0.62 + scallop or dx * dx + (dy - scallop) ** 2 > 1.0:
                    continue
                l = -(0.45 * dx + 0.92 * dy)
                val = 1.90 + pad.bias + 0.65 * g_pad + 1.15 * l + (h2(xx, yy, seed) - 0.5) * 0.65
                if dy > 0.32:
                    val -= 0.95
                grid[(xx, yy)] = (max(0, min(4, int(round(val)))), False)

    for (x, y), (lev, alt) in list(grid.items()):
        if (x, y - 1) not in grid and lev >= 2 and h2(x, y, seed + 19) < 0.35:
            grid[(x, y - 1)] = (min(4, lev + 1), alt)

    _bake_pad_sprites(pad, grid, seed)


def render_needles(pad, seed, rng):
    """Pine pad: flat-bottomed tier composed of radiating needle clusters/rosettes."""
    rx, ryt, ryb = pad.rx, pad.ryt, pad.ryb
    n_tufts = max(6, int(rx * 1.1))
    tufts = []
    for i in range(n_tufts):
        fx = (i + rng.uniform(0.1, 0.9)) / n_tufts * 2 - 1
        u = fx * rx * 0.88 + rng.uniform(-1.0, 1.0)
        v = rng.uniform(-ryt * 0.45, ryb * 0.35) + (fx * fx) * ryb * 0.25
        tufts.append((u, v))
    tufts.sort(key=lambda t: -t[1])

    grid = {}
    n_len = max(2.6, min(4.6, rx * 0.28))
    for u, v in tufts:
        bx, by = pad.cx + u, pad.cy + v
        g_pad = -(0.35 * u / rx + 0.8 * v / max(1.0, ryt + ryb))
        for dx in (-1, 0, 1):
            grid[(int(bx) + dx, int(by))] = (0 if dx >= 0 else 1, False)
        n_rays = rng.randint(5, 8)
        for r_i in range(n_rays):
            ang = -math.pi * 0.92 + math.pi * 0.84 * (r_i + rng.uniform(0.1, 0.9)) / n_rays
            ang += pad.shear * 0.35
            cs, sn = math.cos(ang), math.sin(ang)
            ln = n_len * rng.uniform(0.75, 1.15)
            steps = max(3, int(ln * 1.8))
            for s_i in range(steps + 1):
                tf = s_i / steps
                px = round(bx + cs * ln * tf)
                py = round(by + sn * ln * tf)
                light_dot = -(0.55 * cs + 0.83 * sn)
                val = 1.55 + pad.bias + 0.55 * g_pad + 0.95 * tf + 0.65 * light_dot \
                    + (h2(px, py, seed + r_i) - 0.5) * 0.45
                lev = max(0, min(4, int(round(val))))
                is_tip = "tip" if (pad.tip_ramp and tf < 0.35 and rng.random() < 0.28) else False
                grid[(px, py)] = (lev, is_tip)

    _bake_pad_sprites(pad, grid, seed)


def render_larch(pad, seed, rng):
    """Japanese Larch (Larix): cohesive, softly arched foliage pad with a shaded
    core and delicate tufted needle rosettes along the outer/lower spurs."""
    rx, ryt, ryb = pad.rx, pad.ryt, pad.ryb
    grid = {}
    n_tufts = max(7, int(rx * 1.05))
    tufts = []
    for i in range(n_tufts):
        fx = (i + rng.uniform(0.1, 0.9)) / n_tufts * 2 - 1
        u = fx * rx * 0.86 + rng.uniform(-0.8, 0.8)
        # Gently arched pad: center is higher, tips droop slightly
        v = rng.uniform(-ryt * 0.55, ryb * 0.30) + (fx * fx) * ryb * 0.42
        tufts.append((u, v, fx))
    tufts.sort(key=lambda t: -t[1])

    for u, v, fx in tufts:
        bx, by = pad.cx + u, pad.cy + v
        g_pad = -(0.35 * u / rx + 0.85 * v / max(1.0, ryt + ryb))
        rel_out = min(1.0, abs(fx) * 0.82 + max(0.0, v / max(1.0, ryb)) * 0.25)
        # Cohesive soft interior cushion (2x2 / 3x2 shaded core)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if abs(dx) + abs(dy) > 1 and rng.random() < 0.4:
                    continue
                px, py = round(bx) + dx, round(by) + dy
                c_val = 1.65 + pad.bias + 0.65 * g_pad - 0.45 * dy - 0.25 * dx
                is_tip = "tip" if (
                    pad.tip_ramp is not None
                    and dith(px, py, max(0.0, (rel_out - pad.tip_start) * 1.8))
                ) else False
                grid[(px, py)] = (max(0, min(4, int(round(c_val)))), is_tip)

        # Short radiating needle fascicles around the tuft
        n_fasc = rng.randint(5, 7)
        for f_i in range(n_fasc):
            ang = rng.uniform(-math.pi * 0.95, math.pi * 0.95)
            cs, sn = math.cos(ang), math.sin(ang)
            flen = rng.uniform(1.6, 2.8)
            for step in (0.55, 1.0):
                px = round(bx + cs * flen * step)
                py = round(by + sn * flen * step)
                ld = -(0.50 * cs + 0.85 * sn)
                val = 1.95 + pad.bias + 0.65 * g_pad + 0.85 * ld \
                    + (h2(px, py, seed + f_i) - 0.5) * 0.45
                is_tip = "tip" if (
                    pad.tip_ramp is not None
                    and dith(px, py, max(0.0, (rel_out + 0.12 * step - pad.tip_start) * 1.9))
                ) else False
                grid[(px, py)] = (max(0, min(4, int(round(val)))), is_tip)

    _bake_pad_sprites(pad, grid, seed)


def render_spray(pad, seed, rng):
    """Flat conifer spray (Metasequoia): feathered horizontal frond."""
    rx, ry, sag = pad.rx, pad.ryb, pad.droop
    ph, ph2 = rng.uniform(0, TAU), rng.uniform(0, TAU)
    lobe = rng.uniform(2.2, 3.2)
    bx, by = pad.cx, pad.cy
    grid = {}
    for xi in range(int(bx - rx) - 1, int(bx + rx) + 2):
        u = xi + 0.5 - bx
        t = abs(u) / rx
        if t > 1.04:
            continue
        env = max(0.0, 1.0 - t * t) ** 0.40
        lob = 0.70 + 0.40 * math.sin(u * (TAU / lobe) + ph)
        th = ry * env * lob
        if th < 0.35:
            continue
        v0 = by + sag * (u / rx) ** 2 + pad.shear * u * 0.25 + 0.2 * ry * math.sin(u * 0.55 + ph2)
        top, bot = v0 - th, v0 + th * 0.92
        for yi in range(int(math.floor(top)), int(math.ceil(bot)) + 1):
            v = yi + 0.5
            if v < top - 0.4 or v > bot + 0.4:
                continue
            f = max(-1.0, min(1.0, (v - v0) / max(0.7, th)))
            val = 2.45 + pad.bias - 1.30 * f - 0.40 * t + (h2(xi, yi, seed) - 0.5) * 0.7
            rel = t * 0.88 + max(0.0, f) * 0.12
            tip = "tip" if (
                pad.tip_ramp is not None
                and rel > pad.tip_start + (h2(xi, yi, seed + 3) - 0.5) * 0.28
            ) else False
            grid[(xi, yi)] = (max(0, min(4, int(round(val)))), tip)

    for (x, y), (lev, tip) in list(grid.items()):
        if (x, y - 1) not in grid and h2(x, y, seed + 7) < 0.3:
            grid[(x, y - 1)] = (min(4, lev + 1), tip)
        if (x, y + 1) not in grid and h2(x, y, seed + 9) < 0.34:
            grid[(x, y + 1)] = (max(0, lev - 1), tip)

    _bake_pad_sprites(pad, grid, seed)

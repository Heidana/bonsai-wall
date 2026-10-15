"""V1 tree builder: design-first (envelope -> clusters -> skeleton), emitting a TreeScene.

Moved from bonsai-wall.py build_scene. Colour, rasterisation and scene dressing live in render/.
"""
from __future__ import annotations

import math
import random

from ..ir import Flute, Stroke, TreeScene
from ..ir import Pad as IRPad
from ..layout import Layout
from ..look import ACER_AUTUMN_MIX, LEAVES, SPECIES, TIPS, wpick
from ..util import TAU, arcfrac, h2, spline


class Pad:
    """Mutable pad under construction (becomes an ir.Pad)."""

    def __init__(self, cx, cy, rx, ryt, ryb, bias, back=False):
        self.cx, self.cy, self.rx, self.ryt, self.ryb = cx, cy, rx, ryt, ryb
        self.bias, self.back = bias, back
        self.kind = "cloud"
        self.droop = 0.0
        self.shear = 0.0
        self.ramp = self.ramp2 = 0
        self.tip_ramp = None
        self.tip_start = 1.0
        self.mix = 0.0
        self.grad = 0.95
        self.amp = 1.0
        self.lag = 0.0


def build_tree(seed, W, H, look, xfrac=0.5, shrink=1.0, shift=0.0):
    """V1's design-first builder, emitting a TreeScene (no rasterisation, no colours)."""
    rng = random.Random(seed)
    k = H / 360.0
    species = look.get("species", "acer")
    sp = SPECIES[species]
    strokes = []
    ramp, fall = LEAVES[look["leaf"]]
    names = sp.get("autumn_mix", ACER_AUTUMN_MIX) if ramp is None else (look["leaf"],)
    n_ramps = len(names)
    tip_ramp = TIPS.get(look["leaf"]) is not None     # only truthiness matters to the builder

    # ---- structural plan ----------------------------------------------------
    u = rng.uniform
    style = look.get("style") or wpick(rng, sp["styles"])
    caliper = rng.choices(("slender", "medium", "stout"), (30, 44, 26))[0]
    if style in ("bunjin", "forest"):
        caliper = "slender"
    elif style == "broom":
        caliper = rng.choices(("slender", "medium"), (45, 55))[0]
    elif style in ("moyogi", "slant", "hankengai") and species in ("pinus", "juniperus"):
        caliper = rng.choices(("medium", "stout"), (48, 52))[0]

    long_side = rng.choice((-1, 1))
    fol_kind = sp["foliage"]

    if style == "chokkan":
        hfrac, wr, cfrac = u(0.48, 0.60), u(0.36, 0.48), u(0.68, 0.80)
        peak, e_top, q_bot = u(0.78, 0.92), u(0.75, 1.05), u(0.10, 0.35)
        asym, skew, tilt = u(0.0, 0.08), u(-0.02, 0.02), u(-0.02, 0.02)
        mode = "tiers" if fol_kind == "spray" else "pads"
        droop = u(0.04, 0.12)
    elif style == "moyogi":
        hfrac, wr, cfrac = u(0.42, 0.50), u(0.54, 0.76), u(0.58, 0.72)
        peak, e_top, q_bot = u(0.72, 0.88), u(0.52, 0.78), u(0.15, 0.40)
        asym, skew, tilt = u(0.06, 0.22), u(-0.04, 0.08), u(-0.03, 0.05)
        mode = "pads" if (fol_kind in ("needle", "scale", "larch") or rng.random() < 0.78) else "dome"
        droop = u(0.04, 0.16)
    elif style == "slant":
        hfrac, wr, cfrac = u(0.38, 0.46), u(0.60, 0.84), u(0.54, 0.68)
        peak, e_top, q_bot = u(0.74, 0.90), u(0.45, 0.65), u(0.15, 0.38)
        asym, skew, tilt = u(0.20, 0.38), u(0.18, 0.32), u(0.10, 0.22)
        mode = "pads" if (fol_kind in ("needle", "scale", "larch") or rng.random() < 0.75) else "dome"
        droop = u(0.08, 0.20)
    elif style == "fukinagashi":
        hfrac, wr, cfrac = u(0.36, 0.45), u(0.68, 0.92), u(0.55, 0.70)
        peak, e_top, q_bot = u(0.72, 0.88), u(0.45, 0.70), u(0.15, 0.35)
        asym, skew, tilt = u(0.38, 0.58), u(0.26, 0.42), u(0.16, 0.28)
        mode = "pads"
        droop = u(0.06, 0.16)
    elif style == "hankengai":
        hfrac, wr, cfrac = u(0.30, 0.38), u(0.62, 0.82), u(0.60, 0.74)
        peak, e_top, q_bot = u(0.75, 0.90), u(0.45, 0.70), u(0.15, 0.35)
        asym, skew, tilt = u(0.30, 0.50), u(0.08, 0.20), u(0.16, 0.30)
        mode = "pads"
        droop = u(0.12, 0.24)
    elif style == "bunjin":
        hfrac, wr, cfrac = u(0.54, 0.64), u(0.32, 0.44), u(0.24, 0.34)
        peak, e_top, q_bot = u(0.65, 0.82), u(0.45, 0.72), u(0.15, 0.42)
        asym, skew, tilt = u(0.12, 0.32), u(-0.08, 0.16), u(-0.05, 0.12)
        mode = "pads"
        droop = u(0.06, 0.16)
    elif style == "broom":
        hfrac, wr, cfrac = u(0.40, 0.48), u(0.74, 0.98), u(0.56, 0.68)
        peak, e_top, q_bot = u(0.62, 0.76), u(0.38, 0.54), u(0.45, 0.72)
        asym, skew, tilt = u(0.0, 0.08), u(-0.02, 0.02), u(-0.02, 0.02)
        mode = "dome"
        droop = u(-0.04, 0.04)
    elif style == "twin":
        hfrac, wr, cfrac = u(0.40, 0.49), u(0.58, 0.82), u(0.58, 0.72)
        peak, e_top, q_bot = u(0.74, 0.90), u(0.45, 0.68), u(0.15, 0.38)
        asym, skew, tilt = u(0.08, 0.22), u(-0.04, 0.08), u(-0.03, 0.06)
        mode = "pads" if (fol_kind in ("needle", "scale", "larch") or rng.random() < 0.70) else "dome"
        droop = u(0.05, 0.16)
    elif style == "clump":
        hfrac, wr, cfrac = u(0.42, 0.50), u(0.55, 0.78), u(0.62, 0.76)
        peak, e_top, q_bot = u(0.62, 0.78), u(0.55, 0.78), u(0.30, 0.60)
        asym, skew, tilt = u(0.0, 0.15), u(-0.04, 0.04), u(-0.03, 0.03)
        mode = "pads" if fol_kind in ("needle", "scale", "larch") else ("dome" if rng.random() < 0.7 else "pads")
        droop = u(0.0, 0.12)
    else:  # forest
        hfrac, wr, cfrac = u(0.42, 0.52), u(0.75, 1.02), u(0.55, 0.70)
        peak, e_top, q_bot = u(0.68, 0.88), u(0.50, 0.75), u(0.25, 0.55)
        asym, skew, tilt = u(0.08, 0.24), u(-0.04, 0.04), 0.0
        mode = "tiers" if fol_kind == "spray" else "dome"
        droop = u(0.0, 0.10)

    if fol_kind == "larch":
        droop = u(0.10, 0.20)
        if style != "forest":
            mode = "pads"

    rough = u(0.55, 1.0) if species in ("pinus", "larix", "metasequoia") else (
        u(0.35, 0.75) if caliper == "stout" else 0.15
    )
    has_shari = (rng.random() < sp["shari_p"]) and style not in ("forest", "broom")
    has_jin = (rng.random() < sp["jin_p"]) and style not in ("forest", "broom")
    shari_frac = u(0.28, 0.48) if has_shari else 0.0

    if fol_kind == "spray" and style in ("chokkan", "moyogi", "twin", "forest"):
        mode = "tiers"
        if style in ("chokkan", "forest"):
            hfrac, wr = u(0.54, 0.66), u(0.30, 0.44)
            cfrac = u(0.70, 0.86)

    prof = "cone" if mode == "tiers" else "blob"
    p_cone = u(0.8, 1.2)
    wind_dir = long_side if style == "fukinagashi" else rng.choice((-1, 1))

    Ht = hfrac * H
    Wh = wr * Ht * shrink
    skew, tilt = skew * shrink, tilt * shrink
    margin = (10 if mode == "dome" else 14 if mode == "tiers" else 24) * k

    def span():
        a_top, a_bot = skew * long_side * Ht, tilt * long_side * Ht
        extra_casc = (0.45 * Ht * shrink * long_side) if style == "hankengai" else 0.0
        return (min(a_top, a_bot, extra_casc) - Wh * (1 - asym * long_side) - margin,
                max(a_top, a_bot, extra_casc) + Wh * (1 + asym * long_side) + margin)

    L_, R_ = span()
    if R_ - L_ > 0.90 * W:
        f_ = 0.90 * W / (R_ - L_)
        Wh, skew, tilt = Wh * f_, skew * f_, tilt * f_
        L_, R_ = span()

    # ---- layout: pot & stand sized to the architecture ----------------------
    cw = 2 * Wh
    if style == "forest":
        pot_w, pot_h = cw * u(0.72, 0.90), u(7, 11) * k
        pot_style = rng.choices(("slab", "oval", "rect"), (45, 35, 20))[0]
    elif style == "hankengai":
        pot_w, pot_h = max(58 * k * shrink, cw * u(0.34, 0.44)), u(26, 36) * k
        pot_style = rng.choices(("flared", "drum", "rect"), (45, 35, 20))[0]
    elif style == "bunjin":
        pot_w, pot_h = max(56 * k * shrink, cw * u(0.42, 0.54)), u(11, 16) * k
        pot_style = rng.choices(("drum", "flared", "slab"), (50, 30, 20))[0]
    elif style in ("broom", "clump"):
        pot_w, pot_h = cw * u(0.48, 0.58), u(11, 16) * k
        pot_style = rng.choices(("oval", "rect", "slab"), (60, 28, 12))[0]
    else:
        pot_w, pot_h = cw * u(0.48, 0.64), u(15, 22) * k
        pot_style = rng.choices(("rect", "oval", "drum", "flared"), (38, 32, 18, 12))[0]

    if mode == "tiers" and style != "forest":
        pot_w *= u(1.10, 1.28)
        pot_h *= u(0.80, 0.95)
    pot_w = round(max(54 * k * shrink, min(pot_w, 240 * k, 0.72 * W)))
    pot_h = round(pot_h)
    stand_style = rng.choices(("table", "scroll", "jiita"),
                              (25, 25, 50) if pot_style == "slab" else (50, 30, 20))[0]
    stand_pad = round(u(10, 18) * k * min(1.0, shrink))
    stand_w = min(W - 12, pot_w + 2 * stand_pad)

    if style in ("slant", "fukinagashi", "hankengai"):
        base_off = -long_side * u(0.08, 0.16) * pot_w
    elif style in ("forest", "broom"):
        base_off = u(-0.04, 0.04) * pot_w if style == "broom" else 0.0
    else:
        base_off = u(-0.09, 0.09) * pot_w

    xc = W * xfrac - 0.6 * (base_off + (L_ + R_) / 2)
    lo, hi = 0.04 * W - (base_off + L_), 0.96 * W - (base_off + R_)
    xc = min(max(xc, lo), hi) if lo <= hi else (lo + hi) / 2
    xc += shift
    lo_st, hi_st = stand_w / 2 + 4, W - stand_w / 2 - 4
    xc = min(max(xc, lo_st), hi_st) if lo_st <= hi_st else W / 2

    deck_y = round(H * 0.80)
    stand_bot = round(H * 0.925)
    if stand_style == "jiita":
        slab, legs = max(3, round(3.5 * k)), 0
    else:
        slab, legs = max(4, round(5.5 * k)), max(3, round(5 * k))
    stand_top = stand_bot - slab - legs
    feet = 0 if pot_style == "slab" else max(2, round(3 * k))
    pot_bot = stand_top + 1
    rim_top = pot_bot - feet - pot_h
    mound = u(4.5, 7.5) * k if pot_style == "slab" else u(3.8, 5.8) * k
    soil_half = max(8.0, pot_w / 2 - (2 * k if pot_style == "slab" else 4 * k))
    xb = xc + base_off

    def soil_top(x):
        q = (x - xc) / soil_half
        if abs(q) >= 1:
            return float(rim_top)
        return rim_top - mound * math.sqrt(1 - q * q)

    yb = soil_top(xb) + 2 * k
    Ht = min(Ht, yb - 0.07 * H)
    lay = Layout(W=W, H=H, k=k, deck_y=deck_y, stand_top=stand_top, stand_bot=stand_bot,
                 rim_top=rim_top, pot_bot=pot_bot, pot_w=pot_w, pot_h=pot_h, pot_style=pot_style,
                 stand_style=stand_style, stand_w=stand_w, slab=slab, legs=legs, feet=feet,
                 mound=mound, soil_half=soil_half, xc=xc, xb=xb, yb=yb, Ht=Ht)

    # ---- canopy envelope -----------------------------------------------------
    y_top = yb - Ht
    ch = cfrac * Ht
    y_bot = y_top + ch
    cx_top = xb + skew * long_side * Ht
    cx_bot = xb + tilt * long_side * Ht
    if style == "forest":
        m_tr = rng.choice((5, 7, 9))
        main = min(m_tr - 1, int(m_tr * u(0.25, 0.42)))
        if rng.random() < 0.5:
            main = m_tr - 1 - main
        span_x = soil_half * 0.86
        fxs = sorted(xc + span_x * (-1 + 2 * (i + u(-0.38, 0.38)) / (m_tr - 1))
                     for i in range(m_tr))
        cx_top = fxs[main]

    def cxat(y):
        t = min(1.0, max(0.0, (y - y_top) / ch))
        return cx_top + (cx_bot - cx_top) * t

    def half(y, s):
        t = (y - y_top) / ch
        if t < 0 or t > 1:
            return -1.0
        if prof == "cone":
            w = (min(t, peak) / peak) ** p_cone
            if t > peak:
                w *= max(0.0, 1 - q_bot * ((t - peak) / (1 - peak + 1e-6)) ** 2)
        elif t <= peak:
            w = (1 - ((peak - t) / peak) ** 2) ** e_top
        else:
            w = max(0.0, 1 - q_bot * ((t - peak) / (1 - peak + 1e-6)) ** 2) ** 0.5
        return Wh * (1 + asym * s * long_side) * w

    # ---- trunk system (leaders) with segment-clamped sweeping bends ----------
    r_base = {"slender": u(0.042, 0.056), "medium": u(0.062, 0.078),
              "stout": u(0.082, 0.098)}[caliper] * Ht
    if style == "bunjin":
        r_base = u(0.032, 0.044) * Ht
    elif style == "broom":
        r_base = u(0.046, 0.062) * Ht
    elif style == "forest":
        r_base = u(0.032, 0.046) * Ht
    if mode == "tiers":
        r_base *= 0.65 if style != "forest" else 0.85
        flare_len, flare0 = u(16, 24), u(0.50, 0.75)
    elif style == "broom":
        flare_len, flare0 = u(12, 18), u(0.45, 0.65)
    else:
        flare_len, flare0 = u(10, 15), u(0.32, 0.52)

    leaders, bases, bend_anchors = [], [], []
    rph = u(0, TAU)

    def path_bonsai(x0, y0, x1, y1, bends, amp, side0=None, power=0.82):
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        s = side0 or rng.choice((-1, 1))
        raws = [0.0] + [((i + 1 + u(-0.10, 0.10)) / (bends + 1)) ** power for i in range(bends)] + [1.0]
        ctrl = [(x0, y0)]
        for i in range(1, bends + 1):
            f = raws[i]
            local_seg = min(raws[i] - raws[i - 1], raws[i + 1] - raws[i]) * L
            decay = 1.0 - 0.45 * (i - 1) / max(1, bends)
            a = min(amp * L * decay * u(0.75, 1.20), 0.32 * local_seg) * s
            bx_i = x0 + ux * L * f - uy * a
            by_i = y0 + uy * L * f + ux * a
            ctrl.append((bx_i, by_i))
            bend_anchors.append((bx_i, by_i, s))
            s = -s
        ctrl.append((x1, y1))
        return spline(ctrl)

    def add_leader(pts, r0, r1, flare=0.0, elig=float("inf"), p=None, back_=False):
        flare = flare0 if (flare and flare0) else flare
        q, tot = arcfrac(pts)
        p = p or u(0.85, 1.05)
        rad = []
        for f in q:
            r = r1 + (r0 - r1) * (1 - f) ** p
            if flare:
                r += r0 * flare * math.exp(-f * tot / (flare_len * k))
            if rough:
                r *= 1 + 0.07 * rough * math.sin(f * tot / (6.5 * k) + rph)
            rad.append(r)
        leaders.append((pts, rad, elig, back_))

    y_apex = y_top + ch * u(0.10, 0.20)
    elig = min(y_bot + u(0.0, 0.04) * Ht, yb - 0.30 * Ht)
    r_tip = max(1.3 * k, 0.14 * r_base)

    if style == "chokkan":
        add_leader(path_bonsai(xb, yb, cx_top, y_top + ch * u(0.02, 0.06), 1, u(0.003, 0.012)),
                   r_base, max(1.1 * k, 0.10 * r_base), 0.35, elig, p=u(1.0, 1.3))
        bases.append((xb, r_base))
    elif style in ("moyogi", "slant", "fukinagashi"):
        bends = rng.randint(2, 3) if style == "moyogi" else 2
        amp = u(0.05, 0.10) if style == "moyogi" else u(0.04, 0.07)
        add_leader(path_bonsai(xb, yb, cx_top, y_apex, bends, amp, -long_side),
                   r_base, r_tip, 0.35, elig)
        bases.append((xb, r_base))
    elif style == "bunjin":
        bends = rng.randint(2, 3)
        elig_b = y_bot + 0.04 * Ht
        add_leader(path_bonsai(xb, yb, cx_top, y_apex, bends, u(0.05, 0.10), -long_side, power=0.88),
                   r_base, max(1.2 * k, 0.22 * r_base), 0.25, elig_b)
        bases.append((xb, r_base))
    elif style == "hankengai":
        apex_x = xb - long_side * u(0.04, 0.10) * Ht * shrink
        apex_y = y_top + ch * u(0.14, 0.24)
        add_leader(path_bonsai(xb, yb, apex_x, apex_y, 2, u(0.05, 0.09), -long_side),
                   r_base, r_tip, 0.35, yb - 0.18 * Ht)
        bases.append((xb, r_base))
        knee_x = xb + long_side * u(0.16, 0.26) * Ht * shrink
        knee_y = yb - u(0.32, 0.45) * Ht
        casc_x = xb + long_side * (pot_w * 0.46 + u(0.22, 0.36) * Ht * shrink)
        casc_y = yb + u(0.04, 0.18) * Ht
        casc_ctrl = [
            (xb + long_side * r_base * 0.3, yb - u(0.20, 0.28) * Ht),
            (knee_x, knee_y),
            ((knee_x + casc_x) * 0.5, (knee_y + casc_y) * 0.5 - u(4, 10) * k),
            (casc_x, casc_y),
        ]
        add_leader(spline(casc_ctrl), r_base * 0.72, 1.3 * k, 0.0, casc_y + 10 * k)
    elif style == "broom":
        # Graceful lower trunk dividing smoothly across the collar into a recursive Y-fan
        hs = u(0.27, 0.34) * Ht
        sx, sy = xb + u(-0.015, 0.015) * Ht, yb - hs
        r_split = r_base * u(0.70, 0.80)
        add_leader(path_bonsai(xb, yb, sx, sy, 1, 0.015), r_base, r_split, 0.45, -1e9)
        bases.append((xb, r_base))
        broom_tips = []
        n1 = rng.choice((3, 4))
        sp1 = math.radians(u(42, 56))
        for i in range(n1):
            t1 = -1.0 + 2.0 * i / (n1 - 1)
            ang1 = t1 * sp1 + math.radians(u(-5, 5))
            # Offset starting points across the trunk top so no flat shelf remains
            x1_0 = sx + t1 * r_split * 0.48
            y1_0 = sy + abs(t1) * r_split * 0.22
            r1_0 = r_split * (0.62 if abs(t1) < 0.5 else 0.56)
            len1 = ch * u(0.36, 0.46)
            x1_1 = x1_0 + math.sin(ang1) * len1
            y1_1 = y1_0 - math.cos(ang1) * len1
            r1_1 = r1_0 * u(0.62, 0.70)
            add_leader(path_bonsai(x1_0, y1_0, x1_1, y1_1, 1, 0.04, 1 if ang1 >= 0 else -1),
                       r1_0, r1_1, 0.0, sy)
            # Secondary V-forks from each primary limb
            n2 = 2 if n1 == 4 else rng.choice((2, 3))
            for j in range(n2):
                t2 = -1.0 + 2.0 * j / max(1, n2 - 1)
                ang2 = ang1 * 0.92 + t2 * math.radians(u(16, 24)) + math.radians(u(-4, 4))
                ang2 = max(-math.radians(74), min(math.radians(74), ang2))
                len2 = ch * u(0.34, 0.46) * (1.0 - 0.14 * abs(ang2))
                x2_1 = x1_1 + math.sin(ang2) * len2
                y2_1 = y1_1 - math.cos(ang2) * len2
                r2_0 = r1_1 * u(0.66, 0.76)
                r2_1 = max(1.0 * k, r2_0 * u(0.45, 0.55))
                bk2 = (i + j) % 3 == 1 and rng.random() < 0.35
                add_leader(path_bonsai(x1_1, y1_1, x2_1, y2_1, 1, 0.04, 1 if ang2 >= 0 else -1),
                           r2_0, r2_1, 0.0, sy, back_=bk2)
                broom_tips.append((x2_1, y2_1, ang2, r2_1, bk2))
                # Tertiary twigs reaching into the upper/outer dome
                for m_i in (-1, 1):
                    ang3 = ang2 + m_i * math.radians(u(10, 18))
                    len3 = ch * u(0.16, 0.25)
                    x3_1 = x2_1 + math.sin(ang3) * len3
                    y3_1 = y2_1 - math.cos(ang3) * len3
                    add_leader(spline([(x2_1, y2_1), (x3_1, y3_1)]),
                               r2_1 * 0.78, 0.85 * k, 0.0, sy, back_=bk2)
                    broom_tips.append((x3_1, y3_1, ang3, 0.85 * k, bk2))
    elif style == "twin":
        s2 = long_side if rng.random() < 0.6 else -long_side
        r2f = u(0.55, 0.72)
        gx = r_base * 0.85
        xm, xo = xb - s2 * gx * 0.4, xb + s2 * gx * 0.5
        m0 = (xm, soil_top(xm) + 2 * k, r_base * 0.88, 0.30)
        o0 = (xo, soil_top(xo) + 2 * k, r_base * 0.88 * r2f, 0.25)
        bases += [(xm, m0[2]), (xo, o0[2])]
        add_leader(path_bonsai(m0[0], m0[1], cx_top - s2 * u(0.02, 0.08) * Ht, y_apex,
                               rng.randint(2, 3), u(0.04, 0.08), -s2), m0[2], r_tip, m0[3], elig)
        y2 = y_top + ch * u(0.32, 0.52)
        x2 = cxat(y2) + s2 * max(0.0, half(y2, s2)) * u(0.35, 0.60)
        add_leader(path_bonsai(o0[0], o0[1], x2, y2, rng.randint(2, 3), u(0.04, 0.07), s2),
                   o0[2], 1.3 * k, o0[3], elig + 0.06 * Ht)
    elif style == "clump":
        n = rng.randint(3, 5)
        main = rng.randrange(n)
        tops = sorted(u(-0.55, 0.55) for _ in range(n))
        for i in range(n):
            bx = xb + (i - (n - 1) / 2) * r_base * 0.52
            ty = y_apex if i == main else y_top + ch * u(0.24, 0.56)
            tx = cxat(ty) + tops[i] * Wh
            rr = r_base * (0.72 if i == main else u(0.38, 0.58))
            add_leader(path_bonsai(bx, soil_top(bx) + 2 * k, tx, ty, rng.randint(1, 2),
                                   u(0.03, 0.06)), rr, 1.3 * k, 0.22, elig)
            bases.append((bx, rr))
    else:  # forest
        h_main = Ht - ch * u(0.25, 0.36)
        for i, bx in enumerate(fxs):
            dd = abs(i - main) / (m_tr - 1)
            h = h_main * (1 - 0.58 * dd) * u(0.84, 1.06)
            rr = r_base * (h / h_main) ** 1.35
            by = soil_top(bx) + 2 * k
            lean = (i - main) / (m_tr - 1) * u(0.05, 0.16) * Ht + u(-0.02, 0.02) * Ht
            bk = i != main and rng.random() < 0.32
            add_leader(path_bonsai(bx, by, bx + lean, by - h, rng.randint(1, 2), u(0.015, 0.035)),
                       rr * (0.8 if bk else 1.0), 1.1 * k, 0.18, by - h * u(0.36, 0.50),
                       back_=bk)
            if not bk:
                bases.append((bx, rr))

    flute = []
    NX, NY, NR, PAR, KIND, SIDE, BK, CH, LID, ARC, CONV, PAD_ID = ([] for _ in range(12))
    cand = []
    for li, (pts, rad, ey, lbk) in enumerate(leaders):
        strokes.append(Stroke(
            pts=tuple(pts), radius=tuple(rad), seed=seed + li * 19, order=0, bark=species,
            layer="back" if lbk else "front", streaks=True, rough=rough,
            shari_frac=shari_frac if li == 0 else shari_frac * 0.5))
        if mode == "tiers":
            flute.append(("back" if lbk else "front", pts[0][0], rad[0], u(0, TAU)))
        q, tot = arcfrac(pts)
        for j in range(0, len(pts), 5):
            px, py = pts[j]
            c_side = 0
            for bx_a, by_a, bs_a in bend_anchors:
                if abs(py - by_a) < 10 * k and abs(px - bx_a) < 10 * k:
                    c_side = bs_a
                    break
            NX.append(px)
            NY.append(py)
            NR.append(rad[j])
            PAR.append(-1)
            KIND.append(0)
            SIDE.append(0)
            BK.append(lbk)
            CH.append(0)
            LID.append(li)
            ARC.append(q[j] * tot)
            CONV.append(c_side)
            PAD_ID.append(-1)
            if py <= ey:
                cand.append(len(NX) - 1)
    trunk_idx = list(range(len(NX)))

    def leader_at_y(li, y_q):
        """Return (x, y, r, node_idx) on leader li closest to height y_q."""
        l_nodes = [i for i in trunk_idx if LID[i] == li] or trunk_idx
        best_i = min(l_nodes, key=lambda i: abs(NY[i] - y_q))
        return NX[best_i], NY[best_i], NR[best_i], best_i

    # Add Jin (deadwood apex/branch stubs) on old conifers
    if has_jin:
        for (pts, rad, ey, lbk) in leaders[:2]:
            if lbk:
                continue
            if rng.random() < 0.55 and style in ("moyogi", "bunjin", "slant", "hankengai"):
                tx, ty = pts[-1]
                jx = tx + u(-5, 5) * k
                jy = ty - u(6, 13) * k
                jpts = spline([(tx, ty + 2 * k), ((tx + jx) * 0.5 + u(-1.5, 1.5) * k, (ty + jy) * 0.5),
                               (jx, jy)])
                jf, _ = arcfrac(jpts)
                strokes.append(Stroke(
                    pts=tuple(jpts), radius=tuple(max(0.7, rad[-1] * 0.85 * (1 - q) ) for q in jf),
                    seed=seed + 91, order=1, wood="jin", bark=species, streaks=False, shari_frac=1.0))
            if rng.random() < 0.65:
                idx_j = rng.randint(int(len(pts) * 0.32), int(len(pts) * 0.68))
                bx_j, by_j = pts[idx_j]
                js = rng.choice((-1, 1))
                jlen = u(5, 10) * k
                jpts = spline([(bx_j, by_j),
                               (bx_j + js * jlen * 0.55, by_j + u(-1.5, 2.0) * k),
                               (bx_j + js * jlen, by_j + u(-3.0, 3.0) * k)])
                jf, _ = arcfrac(jpts)
                r0_j = max(1.3 * k, rad[idx_j] * 0.38)
                strokes.append(Stroke(
                    pts=tuple(jpts), radius=tuple(max(0.6, r0_j * (1 - q) ** 0.8) for q in jf),
                    seed=seed + idx_j, order=1, wood="jin", bark=species, streaks=False,
                    shari_frac=1.0))

    # ---- foliage clusters (attractors) & primary pad scaffolds ---------------
    atts = []
    primary_paths = []
    rx0 = (u(6, 8) if style == "forest" else u(7.5, 10.5)) * k
    shell = rx0 * u(1.6, 2.6)

    def poisson(region, n_max, spacing, tries_max, grid=None, pad_id=-1):
        cell = spacing / 1.4143
        grid = {} if grid is None else grid
        x0_, x1_, y0_, y1_ = region.bbox
        tries = 0
        got = 0
        while tries < tries_max and got < n_max:
            tries += 1
            x, y = u(x0_, x1_), u(y0_, y1_)
            r = region(x, y)
            if r is None:
                continue
            gx, gy = int(x // cell), int(y // cell)
            sp_d = spacing * (1.25 if r[0] else 1.0)
            if any(grid.get((i, j)) and (grid[(i, j)][0] - x) ** 2 + (grid[(i, j)][1] - y) ** 2
                   < sp_d * sp_d for i in range(gx - 2, gx + 3) for j in range(gy - 2, gy + 3)):
                continue
            grid[(gx, gy)] = (x, y)
            got += 1
            atts.append(dict(x=x, y=y, rx=rx0 * u(0.78, 1.25), back=r[0],
                             depth=r[1], tl=r[2], pad_id=pad_id))
        return grid

    if mode == "tiers":
        rx0 = u(7.5, 11.0) * k
        ry0 = rx0 * u(0.26, 0.34)
        step = rx0 * u(1.15, 1.45)
        sy_t = rx0 * u(0.72, 0.96)
        backp = u(0.3, 0.5)
        for (pts, rad, ey, lbk) in leaders:
            tx, ty = pts[-1]
            bx0, by0 = pts[0]
            L = max(2 * rx0, by0 - ty)
            cd = L * cfrac
            hw_max = wr * L * shrink * (1.0 if len(leaders) == 1 else u(0.8, 1.0))
            n_t = max(3, int(cd / sy_t))
            for i in range(n_t):
                if i > 1 and rng.random() < 0.12:
                    continue
                f = (i + u(0.1, 0.9)) / n_t
                y = ty + cd * f
                ax = tx + (bx0 - tx) * min(1.0, (y - ty) / max(1.0, by0 - ty))
                hw = hw_max * f ** p_cone * u(0.74, 1.08)
                if f > peak:
                    hw *= max(0.25, 1 - q_bot * ((f - peak) / (1 - peak + 1e-6)) ** 2)
                if hw < rx0 * 0.62:
                    atts.append(dict(x=ax + u(-0.4, 0.4) * k, y=y,
                                     rx=max(rx0 * 0.34, hw), ry=ry0 * u(0.7, 1.0),
                                     back=lbk or rng.random() < backp * 0.3,
                                     depth=0.0, tl=f, pad_id=-1))
                    continue
                sides = (-1, 1) if rng.random() > 0.15 else (rng.choice((-1, 1)),)
                for sd in sides:
                    x = ax + sd * rx0 * u(0.35, 0.7)
                    lim = hw * u(0.85, 1.0)
                    while abs(x - ax) < lim:
                        if rng.random() > 0.16:
                            taper = 0.62 + 0.38 * (1 - abs(x - ax) / lim)
                            atts.append(dict(x=x, y=y + u(-0.6, 0.6) * k,
                                             rx=rx0 * u(0.85, 1.2) * taper,
                                             ry=ry0 * u(0.85, 1.2) * (0.8 + 0.2 * taper),
                                             back=lbk or rng.random() < backp * 0.4,
                                             depth=0.0, tl=f, pad_id=-1))
                        x += sd * step * u(0.85, 1.2)
            atts.append(dict(x=tx + u(-1, 1) * k, y=ty + ry0 * u(0.6, 1.4),
                             rx=rx0 * u(0.45, 0.7), ry=ry0 * u(0.8, 1.1), back=lbk,
                             depth=0.0, tl=0.02, pad_id=-1))
    elif mode == "pads":
        pr0 = (u(16, 21) if style == "bunjin" else u(19, 27)) * k * min(1.0, shrink ** 0.5)
        n_tiers = rng.randint(3, 4) if style == "bunjin" else rng.randint(4, 6)
        y_low, y_cr = y_bot - pr0 * 0.10, y_top + pr0 * 0.34
        dy_tier = (y_low - y_cr) / max(1, n_tiers)
        regions = []  # (px0, py0, hw, hh, bk, leader_id, is_apex)
        s = long_side
        for i in range(n_tiers):
            tf = i / max(1, n_tiers - 1)  # 0 at bottom (ichi-no-eda), 1 near top
            y_base = y_low - (y_low - y_cr) * (tf ** 0.90)
            # Monotonic taper from bottom primary pad to upper pads
            hw = pr0 * (1.20 - 0.46 * tf) * u(0.90, 1.08)
            hh = hw * (u(0.28, 0.38) if fol_kind in ("needle", "scale", "larch") else u(0.34, 0.44))
            if style == "fukinagashi":
                sd_list = [(long_side, 0.0)]
                hw *= 1.18
            elif style == "bunjin":
                sd_list = [(s, 0.0)]
            else:
                both = (i < n_tiers - 1 and rng.random() < 0.38)
                # Stagger opposite pads vertically by 40% of a tier so no bar-branches form
                sd_list = [(s, 0.0), (-s, -0.42 * dy_tier)] if both else [(s, 0.0)]

            for sd, y_stagger in sd_list:
                py_p = max(y_cr + hh * 0.5, y_base + y_stagger + u(-0.06, 0.06) * dy_tier)
                # Anchor pad horizontally to the ACTUAL trunk coordinate at height py_p
                li_use = 1 if (style == "twin" and sd == s2 and py_p > leaders[1][0][-1][1]) else 0
                tx_y, _, tr_y, _ = leader_at_y(li_use, py_p)
                reach_mult = u(0.85, 1.18) * (1.25 - 0.50 * tf)
                if style == "fukinagashi":
                    reach_mult = u(0.95, 1.35) * (1.20 - 0.35 * tf)
                elif style == "slant" and sd == long_side:
                    reach_mult *= 1.18
                px_p = tx_y + sd * (tr_y + hw * reach_mult)
                regions.append((px_p, py_p, hw, hh, False, li_use, False))

            if rng.random() < 0.48:  # Depth pad behind trunk
                tx_b, _, _, _ = leader_at_y(0, y_base)
                bx_p = tx_b + (long_side * hw * 0.38 if style == "fukinagashi"
                               else -s * hw * u(0.20, 0.55))
                regions.append((bx_p, y_base - hh * 0.30, hw * 0.82, hh * 0.82, True, 0, False))
            s = -s

        # Apex crown pad directly capping each upright leader tip
        for li_a, (pts_a, _, ey_a, lbk_a) in enumerate(leaders):
            if ey_a < -1e8 or (style == "hankengai" and li_a == 1):
                continue
            tx_a, ty_a = pts_a[-1]
            hw_a = pr0 * (u(0.92, 1.12) if li_a == 0 else u(0.72, 0.88))
            hh_a = hw_a * u(0.36, 0.46)
            regions.append((tx_a, ty_a - hh_a * 0.15, hw_a, hh_a, lbk_a, li_a, True))

        # Semi-cascade stepping pads anchored tightly along the cascading leader
        if style == "hankengai" and len(leaders) > 1:
            c_pts = leaders[1][0]
            n_cp = rng.randint(3, 5)
            for ci in range(1, n_cp + 1):
                cf = ci / n_cp
                c_idx = min(len(c_pts) - 1, int(cf * (len(c_pts) - 1)))
                px_c, py_c = c_pts[c_idx]
                chw = pr0 * (0.90 - 0.28 * cf) * u(0.88, 1.06)
                chh = chw * u(0.30, 0.38)
                side_c = 1 if ci % 2 == 0 else -1
                regions.append((px_c + side_c * chw * 0.22, py_c - chh * 0.18,
                                chw, chh, ci % 3 == 0, 1, cf > 0.85))

        # Build an explicit, anatomically sound Primary Branch Spline for every pad region
        sp_mult = u(0.92, 1.08)
        grid = {}
        for reg_id, (px0, py0, hw, hh, bk, li_r, is_apex) in enumerate(regions):
            tx_p, ty_p, tr_p, _ = leader_at_y(li_r, py0)
            sd_p = 1 if px0 >= tx_p else -1
            dx_reach = abs(px0 - tx_p)
            if is_apex or dx_reach < hw * 0.35:
                # Apex or near-trunk pad attaches directly to the leader tip/node
                _, _, _, orig_i = leader_at_y(li_r, min(elig, py0 + hh * 0.4))
                PAD_ID[orig_i] = reg_id
            else:
                # Primary branch origin on the trunk at the proper botanical angle
                if fol_kind in ("cloud", "fine"):
                    y_orig = min(elig, py0 + dx_reach * u(0.16, 0.30))
                elif fol_kind == "larch":
                    y_orig = min(elig, max(leaders[li_r][0][-1][1] + 3 * k,
                                           py0 + dx_reach * u(-0.08, 0.08)))
                else:  # pinus / juniperus
                    y_orig = min(elig, py0 + dx_reach * u(0.02, 0.16))
                tx_o, ty_o, tr_o, orig_i = leader_at_y(li_r, y_orig)
                x0_b = tx_o + sd_p * tr_o * 0.72
                y0_b = ty_o
                x2_b = px0 - sd_p * hw * 0.18
                y2_b = py0 + hh * 0.12
                # Smooth outward arch (never bowing sharply upward and plunging down)
                x1_b = x0_b + (x2_b - x0_b) * u(0.45, 0.58)
                arch_y = u(-2.2, 0.8) * k if fol_kind == "larch" else u(-1.2, 1.8) * k
                y1_b = y0_b + (y2_b - y0_b) * 0.52 + arch_y
                b_pts = spline([(x0_b, y0_b), (x1_b, y1_b), (x2_b, y2_b)], step=1.8)
                prev_b = orig_i
                b_idx = []
                for bp_x, bp_y in b_pts[1:]:
                    NX.append(bp_x)
                    NY.append(bp_y)
                    NR.append(0.0)
                    PAR.append(prev_b)
                    KIND.append(1)
                    SIDE.append(sd_p)
                    BK.append(bk)
                    CH.append(0)
                    LID.append(li_r)
                    ARC.append(0.0)
                    CONV.append(0)
                    PAD_ID.append(reg_id)
                    prev_b = len(NX) - 1
                    b_idx.append(prev_b)
                    cand.append(prev_b)
                if b_idx:
                    primary_paths.append((orig_i, b_idx, dict(rx=hw * 0.52, back=bk), (x0_b, y0_b)))

            def region(x, y, px0=px0, py0=py0, hw=hw, hh=hh, bk=bk):
                dx, dy = (x - px0) / hw, (y - py0) / hh
                if dy > 0.45 or dx * dx + dy * dy > 1:
                    return None
                return (bk, 0.0, (dy + 1) / 1.45)
            region.bbox = (px0 - hw, px0 + hw, py0 - hh, py0 + hh)
            n = int(hw * hh * 2.9 / (rx0 * rx0)) + 3
            grid = poisson(region, n, rx0 * sp_mult, n * 30, grid, pad_id=reg_id)
    elif style == "forest":
        crowns = []
        for (pts, rad, ey, bk) in leaders:
            tx, ty = pts[-1]
            h = yb - ty
            cwd = h * u(0.24, 0.36) * shrink
            crowns.append((tx, ty + cwd * 0.3, cwd, cwd * u(0.75, 1.10), bk))
        grid = {}
        for (qx, qy, cwd, chh, bk) in sorted(crowns, key=lambda c_: c_[4]):
            def region(x, y, qx=qx, qy=qy, cwd=cwd, chh=chh, bk=bk):
                dx, dy = (x - qx) / cwd, (y - qy) / chh
                rho = math.hypot(dx, dy)
                if rho > 1 or dy > 0.82:
                    return None
                dep = (1 - rho) * min(cwd, chh)
                if dep < shell and not bk:
                    return (False, dep, (dy + 1) / 1.7)
                return (True, dep, (dy + 1) / 1.7) if rng.random() < 0.5 else None
            region.bbox = (qx - cwd, qx + cwd, qy - chh, qy + chh)
            n = int(cwd * chh * 3.0 / (rx0 * rx0)) + 2
            grid = poisson(region, n, rx0 * u(0.82, 0.96), n * 30, grid)
    else:  # dome (broom & rounded deciduous crowns)
        grid = {}
        # Anchor clusters directly on broom branch tips first
        if style == "broom":
            for tx_b, ty_b, ang_b, _, bk_b in broom_tips:
                tl_b = max(0.0, min(1.0, (ty_b - y_top) / ch))
                atts.append(dict(x=tx_b, y=ty_b, rx=rx0 * u(0.95, 1.25),
                                 back=bk_b, depth=0.0, tl=tl_b, pad_id=-1))
        # Fill the rounded umbrella dome volume (with arched underside, never a flat skirt)
        cy_dome = y_top + ch * 0.56
        ry_up = ch * 0.56
        ry_dn = ch * 0.42
        backp = u(0.28, 0.45)

        def region(x, y):
            c0 = cxat(y)
            hw_d = Wh * (1 + asym * (1 if x >= c0 else -1) * long_side)
            dx = (x - c0) / max(1.0, hw_d)
            dy = (y - cy_dome) / (ry_up if y <= cy_dome else ry_dn)
            # Umbrella arch at the base of the crown so the bottom curves up toward the fork
            arch_lift = 0.22 * (1.0 - min(1.0, dx * dx * 1.4))
            if dy > 0.78 - arch_lift:
                return None
            rho = math.hypot(dx, dy)
            if rho > 1.0:
                return None
            # Leave small natural air pockets in the lower core to glimpse the Y-forks
            if rho < 0.38 and dy > 0.05 and h2(int(x / 7), int(y / 7), seed + 61) < 0.55:
                return None
            dep = (1.0 - rho) * min(hw_d, ry_up)
            tl = (y - y_top) / ch
            if rho > 0.62:
                return (False, dep, tl)
            return (rng.random() < backp, dep, tl)

        bx_l = min(cx_top, cx_bot) - Wh * (1 + asym) - 2
        bx_r = max(cx_top, cx_bot) + Wh * (1 + asym) + 2
        region.bbox = (bx_l, bx_r, y_top, y_bot)
        poisson(region, 260, rx0 * u(0.84, 0.98), 14000, grid)

    # ---- grow the branch skeleton towards the clusters -------------------------
    trunk_pen = 1.0 if mode in ("pads", "tiers") else u(1.15, 1.45)
    gap = (6.5 if mode == "pads" else 3.0 if mode == "tiers" else 4.5) * k
    r_tw = 0.75 * k
    prim = u(0.36, 0.48) if mode == "pads" else u(0.24, 0.34)

    def near_trunk(a):
        return min(trunk_idx, key=lambda i: (NX[i] - a["x"]) ** 2 + (NY[i] - a["y"]) ** 2)

    for a in atts:
        t = near_trunk(a)
        a["side"] = 1 if a["x"] >= NX[t] else -1
        a["dist"] = math.hypot(NX[t] - a["x"], NY[t] - a["y"])
    atts.sort(key=lambda a: a["dist"])
    used = []
    paths = list(primary_paths)
    for a in atts:
        ax, ay, sa, bk = a["x"], a["y"], a["side"], a["back"]
        pid = a.get("pad_id", -1)
        best, bc = -1, 1e18
        for i in cand:
            # Strict pad ownership: attractors in a pad only connect to that pad's scaffold
            if pid >= 0 and PAD_ID[i] != pid:
                continue
            dx, dy = ax - NX[i], ay - NY[i]
            d = math.hypot(dx, dy)
            if d < 0.5:
                continue
            # Hard geometric guardrails: forbid vertical downward drops or inward backtracking
            if KIND[i] == 1:
                if dy > 2.5 * k and abs(dx) < 0.95 * dy:
                    continue
                if style != "fukinagashi" and dx * SIDE[i] < -2.0 * k:
                    continue
            if mode == "dome" and dy > 3.5 * k:
                continue
            cst = d
            down = dy / d
            if down > 0.25 + droop:
                cst *= 1 + 2.5 * (down - 0.25 - droop)
            if KIND[i] == 0:
                cst *= trunk_pen
                if CONV[i] == sa:
                    cst *= 0.75
                elif CONV[i] == -sa:
                    cst *= 1.30
                if d > 14 * NR[i]:
                    cst *= 1 + 0.5 * (d / (14 * NR[i]) - 1)
                for lid, arc in used:
                    if lid == LID[i] and abs(arc - ARC[i]) < gap:
                        cst *= 2.2
                        break
            else:
                if SIDE[i] != sa and style != "fukinagashi" and pid < 0:
                    cst *= 3.0
                if d > 20 * k:
                    cst *= 1 + 0.7 * (d / (20 * k) - 1)
                if BK[i] != bk:
                    cst *= 1.4
                cst *= 1 + 0.35 * CH[i]
            if cst < bc:
                bc, best = cst, i
        if best < 0:
            continue
        x0, y0 = NX[best], NY[best]
        if KIND[best] == 0:
            d0 = math.hypot(ax - x0, ay - y0) or 1.0
            x0 += (ax - x0) / d0 * NR[best] * 0.75
            y0 += (ay - y0) / d0 * NR[best] * 0.75
        d = max(1.0, math.hypot(ax - x0, ay - y0))
        tt = u(0.40, 0.58)
        # Consistent upward/downward arch regardless of whether branch is on left or right
        mx = x0 + (ax - x0) * tt
        my = y0 + (ay - y0) * tt + u(-0.10, 0.10) * d + droop * d * 0.35
        nseg = max(2, int(d / 2))
        prev, idx = best, []
        for j in range(1, nseg + 1):
            q = j / nseg
            NX.append((1 - q) ** 2 * x0 + 2 * (1 - q) * q * mx + q * q * ax)
            NY.append((1 - q) ** 2 * y0 + 2 * (1 - q) * q * my + q * q * ay)
            NR.append(0.0)
            PAR.append(prev)
            KIND.append(1)
            SIDE.append(sa)
            BK.append(bk)
            CH.append(0)
            LID.append(LID[best])
            ARC.append(0.0)
            CONV.append(0)
            PAD_ID.append(pid)
            prev = len(NX) - 1
            idx.append(prev)
            cand.append(prev)
        CH[best] += 1
        if KIND[best] == 0:
            used.append((LID[best], ARC[best]))
        paths.append((best, idx, a, (x0, y0)))

    # Pipe model: limb thickness proportional to supported foliage, strictly capped
    wgt = [0.0] * len(NX)
    for start, idx, a, _ in paths:
        wv = max(0.8, (a["rx"] / (5.5 * k)) ** 2)
        j = idx[-1]
        while j >= 0 and KIND[j] == 1:
            wgt[j] += wv
            j = PAR[j]
    for j in range(len(NX)):
        if KIND[j] == 1:
            NR[j] = max(0.8, r_tw * (wgt[j] ** 0.42))
    for start, idx, a, p0 in paths:
        cap = NR[start] * (0.52 if KIND[start] == 0 else 0.82)
        ln = math.hypot(NX[idx[-1]] - NX[start], NY[idx[-1]] - NY[start])
        r0 = min(cap, max(NR[idx[0]], NR[start] * (prim if KIND[start] == 0 else 0.5),
                          0.032 * ln if KIND[start] == 0 else 0.0))
        for m_, j in enumerate(idx):
            f_ = m_ / max(1, len(idx) - 1)
            NR[j] = min(cap, max(NR[j], r0 * (1 - f_) + NR[j] * f_))
        pts = [p0] + [(NX[j], NY[j]) for j in idx]
        rad = [NR[idx[0]]] + [NR[j] for j in idx]
        strokes.append(Stroke(
            pts=tuple(pts), radius=tuple(rad), seed=seed, order=1 if KIND[start] == 0 else 2,
            bark=species, layer="back" if a["back"] else "front", streaks=rad[0] >= 2.5,
            rough=rough * 0.5))

    flutes = []
    for layer_, bx0, r0, fph in flute:
        y_fl = yb - u(0.16, 0.26) * Ht
        flutes.append(Flute(layer=layer_, x0=bx0, r0=r0, phase=fph, y_start=y_fl,
                            after=len(strokes)))

    turn = u(0.35, 0.85) if tip_ramp else 0.0

    # ---- foliage pads ------------------------------------------------------------
    pads = []
    wind_shear = (0.45 * long_side) if style == "fukinagashi" else 0.0
    # Only spawn foliage pads on attractor paths (skip bare primary branch scaffolds)
    for start, idx, a, _ in paths[len(primary_paths):]:
        x, y, rx = NX[idx[-1]], NY[idx[-1]], a["rx"]
        if style == "fukinagashi":
            rx *= 1.25
        hf = max(0.0, min(1.0, (yb - y) / Ht))
        if mode == "tiers":
            bias = (-0.75 if a["back"] else 0.45) - 0.75 * a["tl"]
            if fol_kind != "spray":
                p = Pad(x, y, rx, a["ry"] * 1.5, a["ry"] * 1.1, bias, a["back"])
                p.kind = fol_kind
                p.grad = 0.55
                pads.append(p)
                continue
            p = Pad(x, y, rx, a["ry"], a["ry"], bias, a["back"])
            p.kind = "spray"
            p.shear = wind_shear
            p.droop = a["ry"] * u(0.6, 1.5) * (0.7 + 0.6 * rx / rx0)
            p.tip_ramp = tip_ramp
            if tip_ramp:
                adv = turn * (0.45 + 0.55 * (1 - a["tl"])) * u(0.75, 1.25)
                p.tip_start = max(0.12, 1.05 - 1.15 * adv)
            pads.append(p)
            continue

        if a["back"]:
            bias = -0.62 - 0.15 * a["tl"]
        elif mode == "pads":
            bias = 0.55 - 1.05 * a["tl"] + 0.15 * hf
        else:
            outer = 1 - min(1.0, a["depth"] / shell)
            bias = 0.58 - 0.85 * a["tl"] + 0.2 * outer

        if fol_kind in ("needle", "scale"):
            ryt, ryb = rx * u(0.46, 0.60), rx * u(0.24, 0.36)
        elif fol_kind == "larch":
            ryt, ryb = rx * u(0.48, 0.62), rx * u(0.32, 0.45)
        else:
            ryt, ryb = rx * u(0.58, 0.74), rx * u(0.40, 0.54)
        p = Pad(x, y, rx, ryt, ryb, bias, a["back"])
        p.kind = fol_kind
        p.shear = wind_shear
        p.tip_ramp = tip_ramp
        if tip_ramp and fol_kind == "larch":
            adv = turn * (0.45 + 0.55 * (1 - a["tl"])) * u(0.75, 1.25)
            p.tip_start = max(0.22, 1.05 - 1.05 * adv)
        p.grad = 0.55
        pads.append(p)

    # Subtle twig tips peeking out below pads
    if mode == "pads" or fol_kind in ("fine", "larch"):
        twig_prob = 0.30 if fol_kind == "larch" else 0.22 if fol_kind == "fine" else 0.15
        for p in pads:
            if p.back or rng.random() > twig_prob:
                continue
            x0 = p.cx + u(-0.45, 0.45) * p.rx
            y0 = p.cy + p.ryb * 0.25
            dx_tw = rng.choice((-1, 1)) * u(1.5, 4.0) * k
            dy_tw = u(3.5, 6.0) * k if fol_kind == "larch" else u(2.5, 4.5) * k
            tw = spline([(x0, y0), (x0 + dx_tw * 0.55, y0 + dy_tw * 0.55), (x0 + dx_tw, y0 + dy_tw)])
            strokes.append(Stroke(pts=tuple(tw), radius=tuple([0.8] * len(tw)), seed=seed, order=3,
                                  bark=species, streaks=False))

    # Leaf colour per pad (indices into the look's ramp list)
    nph = (u(0, TAU), u(0, TAU))
    for p in pads:
        if n_ramps == 1:
            p.ramp = p.ramp2 = 0
            p.mix = 0.0
            continue
        ty = min(1.0, max(0.0, (p.cy - y_top) / ch))
        c0 = cxat(p.cy)
        hw = max(1.0, half(p.cy, 1 if p.cx >= c0 else -1))
        outer = min(1.0, abs(p.cx - c0) / hw)
        nz = 0.5 + 0.3 * math.sin(p.cx / (31 * k) + nph[0]) * math.cos(p.cy / (23 * k) + nph[1]) \
            + 0.2 * math.sin((p.cx + p.cy) / (13 * k) + nph[1])
        v = 0.25 * (1 - ty) + 0.1 * outer + 0.75 * nz - (0.1 if p.back else 0.0) + u(-0.12, 0.12)
        i = max(0, min(n_ramps - 1, int(v * n_ramps - 0.4)))
        p.ramp = i
        p.ramp2 = max(0, min(n_ramps - 1, i + rng.choice((-1, 1))))
        p.mix = 0.22

    # Sway amplitude and lag (no randomness)
    p_left_est = min(p.cx - p.rx for p in pads)
    p_right_est = max(p.cx + p.rx for p in pads)
    for p in pads:
        hf = max(0.0, min(1.0, (yb - p.cy) / Ht))
        raw_amp = (0.65 + 1.05 * hf + 0.55 * min(1.0, abs(p.cx - xb) / (0.6 * Ht))) \
            * (0.78 if p.back else 1.0)
        if p.kind in ("needle", "scale"):
            raw_amp *= 0.88
        p.amp = max(0.78 if p.back else 0.98, raw_amp)
        p.lag = (p.cx - p_left_est) / max(1.0, p_right_est - p_left_est) * 0.14

    ir_pads = tuple(IRPad(
        kind=p.kind, cx=p.cx, cy=p.cy, rx=p.rx, ryt=p.ryt, ryb=p.ryb, bias=p.bias, grad=p.grad,
        shear=p.shear, droop=p.droop, back=p.back, ramp=p.ramp, ramp2=p.ramp2, mix=p.mix,
        tip_start=p.tip_start, amp=p.amp, lag=p.lag,
        bake_seed=seed + int(p.cx * 7 + p.cy * 13)) for p in pads)
    return TreeScene(
        seed=seed, strokes=tuple(strokes), pads=ir_pads, flutes=tuple(flutes),
        trunk_bases=tuple(bases),
        root_rules=dict(style=style, long_side=long_side, shrink=shrink, rough=rough, seed=seed),
        wind_dir=wind_dir, layout=lay,
        meta=dict(engine="v1", species=species, style=style, caliper=caliper, mode=mode,
                  n_ramps=n_ramps, tip=tip_ramp),
        v1_rng=rng)

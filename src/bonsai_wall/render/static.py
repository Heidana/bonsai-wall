"""Static layer and sprite baking: TreeScene -> pixels. Moved from V1 build_scene.

prepare() rasterises limbs, bakes pad sprites and composes the static layer up to exact bounds
(the retry loop in pipeline.py needs those); finish() paints the backdrop and builds the palette.
"""
from __future__ import annotations

import math

from PIL import Image

from ..look import (ACER_AUTUMN_FALL, ACER_AUTUMN_MIX, AKADAMA, BACKDROPS, DECIDUOUS_TIPS, LEAVES, MOSS,
                    POTS, SHARI, SOIL, SPECIES, STONE, THEMES, TIPS, WOOD)
from ..util import TAU, dith, h2, hx, pixels, spline, arcfrac, tint
from .backdrop import paint_background, paint_studio
from .limbs import draw_limb
from .pads import (RenderPad, render_larch, render_needles, render_pad, render_scale_pad,
                   render_spray)


class Scene:
    pass


def _apply_flute(bufs, fl, seed, yb):
    buf = bufs[fl.layer]
    bx0, r0, fph, y_fl = fl.x0, fl.r0, fl.phase, fl.y_start
    for (x, y), v in buf.items():
        if v[1] < 0 or y < y_fl or abs(x - bx0) > r0 * 2.2:
            continue
        g = math.sin((x - bx0) * 1.9 + fph)
        f = min(1.0, (y - y_fl) / (yb - y_fl))
        if g < -0.35 and h2(x, y, seed + 31) < 0.55 + 0.45 * f:
            buf[(x, y)] = (v[0], max(0, v[1] - 1))
        elif g > 0.75 and f > 0.35 and v[1] < 3:
            buf[(x, y)] = (v[0], v[1] + 1)


def prepare(tree, look):
    """Rasterise a TreeScene up to exact bounds: limbs, pad sprites, static layer.

    Consumes tree.v1_rng (V1) in the same order the original build_scene did.
    """
    lay = tree.layout
    W, H, k, seed = lay.W, lay.H, lay.k, tree.seed
    rng = tree.v1_rng
    style = tree.meta["style"]
    species = tree.meta["species"]
    long_side = tree.root_rules["long_side"]
    shrink = tree.root_rules["shrink"]
    rough = tree.root_rules["rough"]
    bases = tree.trunk_bases
    deck_y, stand_top, stand_bot, rim_top = lay.deck_y, lay.stand_top, lay.stand_bot, lay.rim_top
    xc, stand_w, pot_w, soil_half, soil_top = lay.xc, lay.stand_w, lay.pot_w, lay.soil_half, lay.soil_top
    pot_style, stand_style, slab, legs, feet, pot_bot = (
        lay.pot_style, lay.stand_style, lay.slab, lay.legs, lay.feet, lay.pot_bot)
    xb, yb, Ht = lay.xb, lay.yb, lay.Ht
    if look["bg"] == "scene":
        th = THEMES[look["theme"]]
        T = th["tint"]
    else:
        th = BACKDROPS[look["backdrop"]]
        g = hx(th["ramp"][-1])
        m = sum(g) / 3 or 1.0
        T = tuple(1 + 0.12 * (v / m - 1) for v in g)

    def c(hexstr):
        return tint(hx(hexstr), T)


    S = Scene()
    S.W, S.H, S.seed, S.look = W, H, seed, look
    sp = SPECIES[species]
    ramp, fall = LEAVES[look["leaf"]]
    if ramp is None:
        names = sp.get("autumn_mix", ACER_AUTUMN_MIX)
        fall = sp.get("autumn_fall", ACER_AUTUMN_FALL)
    else:
        names = (look["leaf"],)
    ramps = [[c(v) for v in LEAVES[nm][0]] for nm in names]
    leaf = ramps[0]
    tname = TIPS.get(look["leaf"])
    tip_ramp = [c(v) for v in LEAVES[tname][0]] if tname else None
    if look["leaf"] in DECIDUOUS_TIPS:
        fall = LEAVES[DECIDUOUS_TIPS[look["leaf"]]][1]
    bark = [c(v) for v in sp["bark"]]
    shari_col = [c(v) for v in SHARI]
    soil = [c(v) for v in SOIL]
    akadama = [c(v) for v in AKADAMA]
    moss = [c(v) for v in MOSS]
    wood = [c(v) for v in WOOD]
    stone = [c(v) for v in STONE]
    glaze = [c(v) if v else None for v in POTS[look["pot"]]]
    S.leaf = leaf

    # ---- limbs: replay the strokes in builder order into the layer buffers ------------
    front, back, ontop = {}, {}, {}
    bufs = {"front": front, "back": back, "over": ontop}

    def draw(st):
        draw_limb(bufs[st.layer], st.pts, st.radius, st.seed, streaks=st.streaks,
                  rough=st.rough, shari_frac=st.shari_frac, shari_band=st.shari)

    flutes = sorted(tree.flutes, key=lambda f: f.after)
    fi = 0
    for si, st in enumerate(tree.strokes):
        while fi < len(flutes) and flutes[fi].after == si:
            _apply_flute(bufs, flutes[fi], seed, yb)
            fi += 1
        draw(st)
    while fi < len(flutes):
        _apply_flute(bufs, flutes[fi], seed, yb)
        fi += 1

    # ---- foliage pads ------------------------------------------------------------------
    pads = []
    for ip in tree.pads:
        p = RenderPad(ip.cx, ip.cy, ip.rx, ip.ryt, ip.ryb, ip.bias, ip.back)
        p.kind, p.grad, p.shear, p.droop = ip.kind, ip.grad, ip.shear, ip.droop
        p.ramp, p.ramp2, p.mix = ramps[ip.ramp], ramps[ip.ramp2], ip.mix
        p.tip_ramp, p.tip_start = tip_ramp, ip.tip_start
        p.amp, p.lag = ip.amp, ip.lag
        pads.append(p)

    renderers = {
        "spray": render_spray,
        "needle": render_needles,
        "scale": render_scale_pad,
        "larch": render_larch,
        "cloud": render_pad,
        "fine": render_pad,
    }
    for p, ip in zip(pads, tree.pads):
        renderers.get(p.kind, render_pad)(p, ip.bake_seed, rng)

    S.pads_back = [p for p in pads if p.back]
    S.pads_front = sorted((p for p in pads if not p.back), key=lambda p: -p.cy)

    # Canopy shade on limbs directly below foliage
    for p in pads:
        for x, by in p.bottom.items():
            for dy in (1, 2, 3):
                v = front.get((x, by + dy))
                if v is not None and v[1] >= 0:
                    front[(x, by + dy)] = (v[0], max(0, v[1] - 1))

    # ---- static mid layer (limbs, soil, pot, stand) -----------------------
    def bark_or_shari(lev):
        return shari_col[lev + 3] if lev < 0 else bark[lev]

    mid = {pos: bark_or_shari(lev) for pos, (_, lev) in front.items()
           if pos[1] <= rim_top or pos[0] < xc - pot_w / 2 or pos[0] > xc + pot_w / 2}

    # Soil mound with scattered akadama granules
    for x in range(int(xc - soil_half), int(xc + soil_half) + 1):
        top = round(soil_top(x + 0.5))
        for y in range(top, rim_top + 2):
            hv = h2(x, y, seed + 3)
            if hv > 0.92:
                mid[(x, y)] = akadama[1 if hv > 0.96 else 0]
            else:
                mid[(x, y)] = soil[2] if (y == top or hv > 0.82) else soil[1] if hv > 0.38 else soil[0]

    # Surface roots (nebari)
    roots = {}
    for bx0, br in bases:
        for s in (-1, 1):
            n_rt = rng.randint(1, 3) if style != "forest" else rng.randint(0, 1)
            for _ in range(n_rt):
                x0 = bx0 + s * br * rng.uniform(0.25, 0.75)
                r_span = rng.uniform(9, 22) * k * (0.5 if style == "forest" else 1.0) * min(1.0, shrink)
                if style in ("slant", "fukinagashi", "hankengai") and s == -long_side:
                    r_span *= 1.35
                elif style == "broom":
                    r_span *= 1.25
                x1 = bx0 + s * (br + r_span)
                pts = spline([(x0, soil_top(x0) - 1.6 * k),
                              ((x0 + x1) / 2, soil_top((x0 + x1) / 2) - 1.0 * k),
                              (x1, soil_top(x1) + 0.5)])
                rf, _ = arcfrac(pts)
                rr = br * rng.uniform(0.28, 0.44)
                draw_limb(roots, pts, [0.8 + (rr - 0.8) * (1 - q) for q in rf], seed,
                          rough=rough)
    for pos, (_, lev) in roots.items():
        if pos[1] <= rim_top:
            mid[pos] = bark_or_shari(lev)

    # Moss carpet over the soil
    mph = [rng.uniform(0, TAU) for _ in range(3)]
    for x in range(int(xc - soil_half) + 1, int(xc + soil_half)):
        n = (math.sin(x * 0.21 / k + mph[0]) + 0.6 * math.sin(x * 0.53 / k + mph[1])
             + 0.4 * math.sin(x * 1.3 / k + mph[2])) / 2.0
        if n < -0.25:
            continue
        top = round(soil_top(x + 0.5))
        thick = 1 + (n > 0.15) + (n > 0.55)
        if n > 0.45 and h2(x, 1, seed + 8) < 0.5 and (x, top - 1) not in front:
            top -= 1
            thick += 1
        for j in range(thick):
            y = top + j
            if y > rim_top or (x, y) in roots:
                continue
            lev = 2 if j == 0 else 1 if j == 1 else 0
            if lev == 2 and x > xc + soil_half * 0.3 and h2(x, y, seed + 10) < 0.5:
                lev = 1
            if h2(x, y, seed + 9) < 0.12:
                lev = max(0, lev - 1)
            mid[(x, y)] = moss[lev]

    # Viewing stone (suiseki) or accent rock + optional kusamono grass blades
    if rng.random() < 0.68:
        sxp = xc + rng.choice((-1, 1)) * rng.uniform(0.42, 0.78) * soil_half
        syp = soil_top(sxp) - 0.5
        srx, sry = rng.uniform(3.0, 5.5) * k, rng.uniform(2.0, 3.6) * k
        for y in range(int(syp - sry), int(syp + sry) + 1):
            for x in range(int(sxp - srx), int(sxp + srx) + 1):
                dx, dy = (x + 0.5 - sxp) / srx, (y + 0.5 - syp) / sry
                crag = 0.15 * math.sin(dx * 4.0 + seed)
                if dx * dx + (dy - crag) ** 2 <= 1 and y <= rim_top:
                    lv = -(0.7 * dx + 0.7 * dy)
                    mid[(x, y)] = stone[2 if lv > 0.32 else 1 if lv > -0.38 else 0]
        if rng.random() < 0.55:
            gx0 = int(sxp + rng.choice((-1, 1)) * srx * 0.9)
            gy0 = int(soil_top(gx0))
            for b_i in range(rng.randint(2, 4)):
                g_dx = rng.choice((-1, 0, 1))
                for gh in range(1, round(rng.uniform(2.5, 4.5) * k)):
                    mid[(gx0 + b_i + (gh * g_dx) // 2, gy0 - gh)] = moss[2 if gh > 1 else 1]

    # Stand (table, scroll stand, or flat jiita burl board)
    sx0 = round(xc - stand_w / 2)
    sx1 = sx0 + stand_w - 1
    legw = max(3, round(5 * k))
    pot_r = xc + pot_w / 2
    for y in range(stand_top, stand_bot):
        r = y - stand_top
        for x in range(sx0, sx1 + 1):
            if stand_style == "jiita":
                trim = round(2 * k * math.sin(r * 1.3 + seed))
                if x < sx0 + abs(trim) or x > sx1 - abs(trim):
                    continue
                lev = 3 if r == 0 else 0 if r == slab - 1 else 2
                if r <= 1 and xc - pot_w / 2 + 2 * k < x < pot_r + 8 * k:
                    lev = 1
                mid[(x, y)] = wood[lev]
            elif r < slab:
                if r == 0 and x in (sx0, sx1):
                    continue
                if r <= 1:
                    lev = 3 if r == 0 else 2
                    if xc - pot_w / 2 + 3 * k < x < pot_r + 9 * k:
                        lev = 1
                elif r == slab - 1:
                    lev = 0
                else:
                    lev = 1 if h2(int(x / 6 + r * 2.3), r, seed + 11) < 0.3 else 2
                    if x - sx0 < 2:
                        lev = min(3, lev + 1)
                    elif sx1 - x < 2:
                        lev = max(0, lev - 1)
                mid[(x, y)] = wood[lev]
            else:
                inset = round((6 if stand_style == "scroll" else 3) * k)
                if stand_style == "scroll":
                    inset += round(1.5 * k * math.sin((r - slab) / max(1, legs) * math.pi))
                inl = sx0 + inset <= x < sx0 + inset + legw
                inr = sx1 - inset - legw < x <= sx1 - inset
                if not (inl or inr):
                    continue
                edge = x in (sx0 + inset, sx1 - inset - legw + 1)
                lev = 0 if y == stand_bot - 1 else 2 if edge else 1
                mid[(x, y)] = wood[lev]

    # Pot rendering (rect, oval, drum, flared, or natural rock slab)
    hw0 = pot_w / 2
    if pot_style == "slab":
        for y in range(rim_top, pot_bot):
            q = (y - rim_top) / max(1, pot_bot - rim_top)
            jaggedL = 3 * k * math.sin(y * 0.7 + seed)
            jaggedR = 3 * k * math.cos(y * 0.6 + seed * 2)
            for x in range(int(xc - hw0 + jaggedL), int(xc + hw0 + jaggedR) + 1):
                hp = (x - xc) / hw0
                val = 1.6 - 1.1 * hp - 0.8 * q + (h2(x, y, seed + 29) - 0.5) * 0.6
                lev = max(0, min(2, int(round(val))))
                mid[(x, y)] = stone[lev]
    else:
        lip = max(2, round((2 if pot_style == "drum" else 3) * k))
        over = max(1, round((3.5 if pot_style == "flared" else 1 if pot_style == "drum" else 2) * k))
        body_top = rim_top + lip
        body_bot = pot_bot - feet
        body_h = max(2, body_bot - body_top)
        for y in range(rim_top, rim_top + lip):
            hw = hw0 + over
            for x in range(int(xc - hw), int(xc + hw) + 1):
                q = (x + 0.5 - xc) / hw
                if y == rim_top and abs(q) > 0.985:
                    continue
                if y == rim_top:
                    lev = 3 if q < 0.3 else 2
                elif y == rim_top + lip - 1:
                    lev = 1 if q < 0.4 else 0
                else:
                    lev = 3 if q < -0.55 else 2 if q < 0.45 else 1
                mid[(x, y)] = glaze[lev]
        hw_bot = hw0
        for y in range(body_top, body_bot):
            q = (y - body_top) / max(1, body_h - 1)
            if pot_style == "rect":
                hw = hw0 - 2 * k * q - 0.5
            elif pot_style == "drum":
                hw = hw0 * (1.0 - 0.04 * (q - 0.5) ** 2)
            elif pot_style == "flared":
                hw = hw0 * (0.68 + 0.32 * (1 - q) ** 1.6)
            else:  # oval
                hw = hw0 * math.sqrt(max(0.0, 1 - (q * 0.72) ** 2))
            hw_bot = hw
            is_bead_row = (pot_style == "drum" and y in (body_top + round(2 * k), body_bot - round(2.5 * k)))
            for x in range(int(xc - hw), int(xc + hw) + 1):
                hp = (x + 0.5 - xc) / hw
                val = 1.75 - 1.25 * hp - 0.9 * q
                base = math.floor(val)
                lev = max(0, min(3, base + (1 if dith(x, y, val - base) else 0)))
                if is_bead_row and int(abs(x - xc) / max(1, 3.5 * k)) % 2 == 0 and abs(hp) < 0.88:
                    lev = min(3, lev + 1)
                if y == body_bot - 1 or hp > 0.97:
                    lev = 0
                col = glaze[lev]
                if glaze[4] and 0 <= x - round(xc - hw * 0.62) < max(1, round(1.5 * k)) \
                        and 0.15 < q < 0.7:
                    col = glaze[4]
                mid[(x, y)] = col
        fw = max(4, round(7 * k))
        for fx0 in (round(xc - hw_bot + 3 * k), round(xc + hw_bot - 3 * k - fw)):
            for y in range(body_bot, pot_bot):
                for x in range(fx0, fx0 + fw):
                    mid[(x, y)] = glaze[0] if (y == pot_bot - 1 or x == fx0 + fw - 1) else glaze[1]

    # Re-stamp cascading branches that pass in front of the pot
    if style == "hankengai":
        for (x, y), (_, lev) in front.items():
            if y > rim_top and x > xc + pot_w * 0.25 * long_side:
                mid[(x, y)] = bark_or_shari(lev)

    S.back_limbs = {pos: bark_or_shari(max(0, lev - 1) if lev >= 0 else lev)
                    for pos, (_, lev) in back.items()}

    # Compute exact pixel bounds across all sprites (including max wind sway) and mid/back layers
    pad_xmin = min(p.ox - math.ceil(p.amp) - 1 for p in pads)
    pad_xmax = max(p.ox + p.sprites[0].width + math.ceil(p.amp) + 1 for p in pads)
    layer_xs = [x for (x, _) in mid] + [x for (x, _) in S.back_limbs]
    S.xmin = min([pad_xmin] + layer_xs)
    S.xmax = max([pad_xmax] + layer_xs)
    S.crown_top = min(p.oy for p in pads)

    mim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mp = mim.load()
    for (x, y), col in mid.items():
        if 0 <= x < W and 0 <= y < H:
            mp[x, y] = col + (255,)

    S.k = k
    S.xb, S.yb, S.Ht = xb, yb, Ht
    S.species, S.style, S.caliper, S.mode = species, style, tree.meta["caliper"], tree.meta["mode"]
    S.wind_dir = tree.wind_dir
    S.deck_y, S.stand_top, S.stand_bot, S.rim_top = deck_y, stand_top, stand_bot, rim_top
    S.xc, S.stand_w, S.pot_w, S.soil_top, S.soil_half = xc, stand_w, pot_w, soil_top, soil_half
    S.layout, S.tree = lay, tree
    S._over_img = None
    if ontop:
        oim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        op = oim.load()
        for pos, (_, lev) in ontop.items():
            if 0 <= pos[0] < W and 0 <= pos[1] < H:
                op[pos] = bark_or_shari(lev) + (255,)
        S._over_img = oim
    S._ctx = dict(th=th, c=c, fall=fall, mim=mim, rng=rng, seed=seed, k=k, deck_y=deck_y,
                  stand_bot=stand_bot, look=look)
    return S


def finish(S):
    """Backdrop, exact-index palette and sprite conversion (needs prepare() first)."""
    ctx = S._ctx
    th, c, fall, mim = ctx["th"], ctx["c"], ctx["fall"], ctx["mim"]
    rng, seed, k, look = ctx["rng"], ctx["seed"], ctx["k"], ctx["look"]
    deck_y, stand_bot = ctx["deck_y"], ctx["stand_bot"]
    W, H = S.W, S.H
    pads = S.pads_back + S.pads_front
    if look["bg"] == "scene":
        bg = paint_background(S, th, rng, seed, k)
        S.floor = (deck_y + 3 * k, deck_y + 18 * k)
    else:
        bg = paint_studio(S, th, k)
        S.floor = (stand_bot - 4 * k, stand_bot + 5 * k)
    S.mote = tuple(hx(v) for v in th["mote"])
    S.leaf_fall = [(c(a), c(b)) for a, b in fall]
    S.rng = rng

    # Shared 8-bit palette for GIF encoding (must stay <= 255 colours)
    pal = S.pal = {}

    def ix(col):
        i = pal.get(col)
        if i is None:
            i = pal[col] = len(pal)
        return i

    S.ix = ix
    bgp = Image.new("P", (W, H))
    bgp.putdata([ix(col[:3]) for col in pixels(bg)])
    S.bg = bgp

    def to_p(img):
        data = pixels(img)
        pim = Image.new("P", img.size)
        pim.putdata([ix(v[:3]) if v[3] else 0 for v in data])
        return pim, img.getchannel("A")

    S.mid = to_p(mim)
    S.over = to_p(S._over_img) if S._over_img is not None else None
    for p in S.pads_back + S.pads_front:
        p.psprites = [to_p(sp_) for sp_ in p.sprites]
    for a, b in S.leaf_fall:
        ix(a), ix(b)
    for m in S.mote:
        ix(m)
    if len(pal) > 255:
        raise SystemExit(f"bonsai-wall: palette overflow ({len(pal)} colours)")
    flat = [v for col in sorted(pal, key=pal.get) for v in col]
    S.bg.putpalette(flat)
    return S

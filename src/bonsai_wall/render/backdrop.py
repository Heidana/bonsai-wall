"""Backdrop painters, moved verbatim from V1."""
from __future__ import annotations

import math

from PIL import Image

from ..util import TAU, dith, h2, hx, smooth


def paint_background(S, th, rng, seed, k):
    W, H = S.W, S.H
    sky = [hx(v) for v in th["sky"]]
    pix = [None] * (W * H)
    deck_y = S.deck_y
    n = len(sky) - 1
    for y in range(deck_y):
        t = y / max(1, deck_y - 1) * n
        i = min(int(t), n - 1)
        fr = t - i
        a, b = sky[i], sky[i + 1]
        o = y * W
        for x in range(W):
            pix[o + x] = b if dith(x, y, fr) else a

    if th["stars"]:
        dim, bright = hx("#5d6d88"), hx("#c9d4e8")
        for _ in range(int(W * H * 0.0010)):
            x, y = rng.randrange(W), rng.randrange(int(deck_y * 0.7))
            pix[y * W + x] = bright if rng.random() < 0.25 else dim

    disc, halo = hx(th["disc"]), hx(th["halo"])
    R = rng.uniform(0.15, 0.2) * H
    dcx = S.xmin + (S.xmax - S.xmin) * rng.uniform(0.12, 0.32)
    dcy = max(R + 0.05 * H, S.crown_top + rng.uniform(8, 26) * k)
    S.disc = (dcx, dcy, R)
    glow = 9 * k
    bands = []
    if th["clouds"]:
        for fy, th_ in ((0.30, 2), (0.55, 1), (0.78, 2)):
            by = round(dcy + R * (fy + rng.uniform(-0.05, 0.05)))
            half = R * rng.uniform(0.7, 1.3)
            bx = dcx + rng.uniform(-0.4, 0.4) * R
            bands.append((by, by + max(1, round(th_ * k)), bx - half, bx + half))
    for y in range(max(0, int(dcy - R - glow)), min(deck_y, int(dcy + R + glow) + 1)):
        for x in range(max(0, int(dcx - R - glow)), min(W, int(dcx + R + glow) + 1)):
            d = math.hypot(x + 0.5 - dcx, y + 0.5 - dcy)
            o = y * W + x
            if d <= R:
                col = disc
                for y0, y1, x0, x1 in bands:
                    if y0 <= y < y1 and x0 <= x <= x1:
                        col = halo
                pix[o] = col
            elif d <= R + 1.5 * k:
                pix[o] = disc if dith(x, y, 0.5) else halo
            elif d <= R + glow:
                if dith(x, y, 0.5 * (1 - (d - R) / glow)):
                    pix[o] = halo

    far, near, mist = hx(th["far"]), hx(th["near"]), hx(th["mist"])

    def ridge(base, amps):
        ph = [rng.uniform(0, TAU) for _ in amps]
        wl = [W / 2.3, W / 5.5, W / 13.0]
        return [base - sum(a * k * math.sin(x / (w_ / TAU) + p)
                           for a, w_, p in zip(amps, wl, ph)) for x in range(W)]

    rf = ridge(deck_y - rng.uniform(20, 30) * k, (9, 5, 2))
    rn = ridge(deck_y - rng.uniform(7, 12) * k, (5, 3, 1.5))
    for x in range(W):
        for y in range(max(0, int(rf[x])), deck_y):
            o = y * W + x
            if y >= rn[x]:
                pix[o] = near
            elif y >= rn[x] - 4 * k:
                pix[o] = mist if dith(x, y, 0.55) else far
            else:
                pix[o] = far

    deck = [hx(v) for v in th["deck"]]
    edge, seam = hx(th["edge"]), hx(th["seam"])
    seams, yy, gap = set(), deck_y + 2.0, 3.0 * k
    while yy < H:
        seams.add(int(yy))
        gap *= 1.3
        yy += gap
    for y in range(deck_y, H):
        t = (y - deck_y) / max(1, H - 1 - deck_y) * 2
        i = min(int(t), 1)
        fr = t - i
        o = y * W
        for x in range(W):
            if y == deck_y:
                col = edge
            elif y in seams:
                col = seam
            else:
                col = deck[i + 1] if dith(x, y, fr) else deck[i]
                if h2(int(x / 9 + y * 3.1), y, seed + 21) < 0.035:
                    col = deck[min(2, i + 1)] if col is deck[i] else seam
            pix[o + x] = col

    scx, scy = S.xc + 5 * k, S.stand_bot + 1
    srx, sry = S.stand_w / 2 + 6 * k, 3.5 * k
    for y in range(int(scy - sry), min(H, int(scy + sry) + 1)):
        for x in range(int(scx - srx), int(scx + srx) + 1):
            if 0 <= x < W and ((x + 0.5 - scx) / srx) ** 2 + ((y + 0.5 - scy) / sry) ** 2 <= 1:
                if dith(x, y, 0.6):
                    pix[y * W + x] = seam

    for (x, y), col in S.back_limbs.items():
        if 0 <= x < W and 0 <= y < H:
            pix[y * W + x] = col

    img = Image.new("RGB", (W, H))
    img.putdata(pix)
    return img.convert("RGBA")


def paint_studio(S, bd, k):
    """Plain diffuse backdrop with ordered dithering (136 levels)."""
    W, H = S.W, S.H
    stops = [hx(v) for v in bd["ramp"]]
    n, L = len(stops) - 1, 136
    ramp = []
    for i in range(L):
        t = i / (L - 1) * n
        j = min(int(t), n - 1)
        f = t - j
        a, b = stops[j], stops[j + 1]
        ramp.append(tuple(round(a[ch] + (b[ch] - a[ch]) * f) for ch in range(3)))
    gx = (S.xmin + S.xmax) / 2 - 0.05 * H
    gy = S.crown_top + 0.45 * (S.rim_top - S.crown_top)
    ax, ay = 0.62 * H, 0.44 * H
    colg = [math.exp(-((x + 0.5 - gx) / ax) ** 2) for x in range(W)]
    vig = [0.10 * ((x + 0.5 - W / 2) / (W / 2)) ** 2 for x in range(W)]
    scx, scy = S.xc + 4 * k, S.stand_bot + 0.5
    srx, sry = S.stand_w / 2 + 12 * k, 5.5 * k
    pix = [None] * (W * H)
    for y in range(H):
        v = (y + 0.5) / H
        base = 0.08 + 0.30 * smooth(v / 0.88) - 0.10 * smooth((v - 0.88) / 0.12)
        rowg = 0.52 * math.exp(-((y + 0.5 - gy) / ay) ** 2)
        dy2 = ((y + 0.5 - scy) / sry) ** 2
        shadow_row = dy2 < 9
        o = y * W
        for x in range(W):
            t = base + rowg * colg[x] - vig[x]
            if shadow_row:
                dx = (x + 0.5 - scx) / srx
                if -1.6 < dx < 1.6:
                    t -= 0.16 * math.exp(-dx ** 4 - dy2)
            q = (0.0 if t < 0 else 1.0 if t > 1 else t) * (L - 1)
            i = int(q)
            if i < L - 1 and dith(x, y, q - i):
                i += 1
            pix[o + x] = ramp[i]
    for (x, y), col in S.back_limbs.items():
        if 0 <= x < W and 0 <= y < H:
            pix[y * W + x] = col
    img = Image.new("RGB", (W, H))
    img.putdata(pix)
    return img.convert("RGBA")

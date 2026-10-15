"""Frame composition, gusts and particles, moved verbatim from V1."""
from __future__ import annotations

import math

from .look import SPECIES
from .util import TAU


LEAF_SPIN = [
    [(0, -1, 1), (-1, 0, 1), (0, 0, 1), (1, 0, 1), (0, 1, 0)],
    [(-1, 0, 1), (0, 0, 1), (1, -1, 0)],
    [(-1, 0, 0), (0, 0, 1), (1, 0, 0)],
    [(-1, -1, 0), (0, 0, 1), (1, 0, 1)],
]
LEAF_REST = [(-1, 0, 0), (0, 0, 1), (1, 0, 1)]

NEEDLE_SPIN = [
    [(-1, 0, 0), (0, 0, 1), (1, 0, 1)],
    [(0, -1, 1), (0, 0, 1), (1, 1, 0)],
    [(-1, 0, 1), (0, 0, 0)],
    [(-1, 1, 0), (0, 0, 1), (1, -1, 1)],
]
NEEDLE_REST = [(0, 0, 0), (1, 0, 1)]


def surface_y(S, x):
    if abs(x - S.xc) < S.soil_half:
        return S.soil_top(x) - 1
    if abs(x - S.xc) < S.stand_w / 2 - 1:
        return S.stand_top
    return None


def make_particles(S, N):
    rng, k, W, H = S.rng, S.k, S.W, S.H
    leaves = []
    if S.species in ("pinus", "juniperus"):
        nleaves = rng.randint(1, 2)
    else:
        nleaves = rng.randint(3, 5)
    srcs = [p for p in S.pads_front if p.cy > S.yb - S.Ht * 0.8] or S.pads_front
    is_needle = SPECIES[S.species].get("particle") == "needle"
    for i in range(nleaves):
        p = rng.choice(srcs)
        x0 = p.cx + rng.uniform(-0.6, 0.6) * p.rx
        y0 = p.cy + p.ryb * 0.6
        drift = rng.uniform(0.08, 0.28) * S.wind_dir
        sway, cyc = rng.uniform(3, 7) * k, rng.uniform(1.0, 2.2)
        vy = rng.uniform(1.4, 1.9) * k
        for _ in range(6):
            est = int(max(10, (S.floor[1] - y0) / vy))
            xl = x0 + drift * est
            ly = surface_y(S, xl)
            if ly is None:
                ly = rng.uniform(*S.floor)
            fall = max(8, int((ly - y0) / vy))
            rest = int(rng.uniform(0.15, 0.3) * N)
            if fall + rest <= N - 2:
                break
            vy *= 1.3
        else:
            rest = max(2, N - 2 - fall)
        leaves.append(dict(x0=x0, y0=y0, ly=ly, fall=fall, rest=rest, drift=drift,
                           sway=sway, cyc=cyc, ph=rng.uniform(0, TAU),
                           t0=int(N * (i + rng.uniform(0.0, 0.6)) / nleaves),
                           spin=rng.randint(2, 3), needle=is_needle,
                           col=tuple(S.ix(v) for v in rng.choice(S.leaf_fall))))
    motes = []
    mcol = [S.ix(v) for v in S.mote]
    for _ in range(rng.randint(9, 14)):
        motes.append(dict(
            x=S.xc + rng.uniform(-0.42, 0.42) * W, y=rng.uniform(0.18, 0.76) * H,
            ax=rng.uniform(3, 12) * k, ay=rng.uniform(2, 8) * k,
            kx=rng.choice((1, 2)), ky=rng.choice((1, 2)), kb=rng.choice((1, 2, 3)),
            px=rng.uniform(0, TAU), py=rng.uniform(0, TAU), pb=rng.uniform(0, TAU)))
    return leaves, motes, mcol


def render_frames(S, fps, seconds, falling=True):
    N = max(2, round(fps * seconds))
    rng = S.rng
    wph = [rng.uniform(0, TAU) for _ in range(3)]
    wdir = S.wind_dir

    def gust(t):
        a = TAU * t / N
        w = 0.55 * math.sin(a + wph[0]) + 0.30 * math.sin(2 * a + wph[1]) \
            + 0.15 * math.sin(3 * a + wph[2])
        return (w + 0.3) / 1.3

    leaves, motes, mcol = make_particles(S, N)
    if not falling:
        leaves = []
    frames = []
    for f in range(N):
        im = S.bg.copy()
        for group in (S.pads_back, None, S.pads_front):
            if group is None:
                im.paste(S.mid[0], (0, 0), S.mid[1])
                continue
            for p in group:
                g = gust(f - p.lag * N)
                dx = round(p.amp * wdir * g)
                dy = 1 if (not p.back and g > 0.82 and p.amp > 1.15) else 0
                spr, msk = p.psprites[1] if g > 0.70 else p.psprites[0]
                im.paste(spr, (p.ox + dx, p.oy + dy), msk)
        if S.over is not None:     # front limbs that cross foliage (V2 only; None for V1)
            im.paste(S.over[0], (0, 0), S.over[1])
        px = im.load()
        for m in motes:
            b = math.sin(TAU * m["kb"] * f / N + m["pb"])
            if b < -0.1:
                continue
            x = int(m["x"] + m["ax"] * math.sin(TAU * m["kx"] * f / N + m["px"]))
            y = int(m["y"] + m["ay"] * math.sin(TAU * m["ky"] * f / N + m["py"]))
            if 0 <= x < S.W and 0 <= y < S.H:
                px[x, y] = mcol[0] if b > 0.6 else mcol[1]
        for L in leaves:
            age = (f - L["t0"]) % N
            if age >= L["fall"] + L["rest"]:
                continue
            spin_tbl = NEEDLE_SPIN if L["needle"] else LEAF_SPIN
            rest_tbl = NEEDLE_REST if L["needle"] else LEAF_REST
            if age < L["fall"]:
                q = age / L["fall"]
                x = L["x0"] + L["drift"] * age + L["sway"] * math.sin(TAU * L["cyc"] * q + L["ph"])
                y = L["y0"] + (L["ly"] - L["y0"]) * q
                shape = spin_tbl[(age // L["spin"]) % 4]
            else:
                x = L["x0"] + L["drift"] * L["fall"] + L["sway"] * math.sin(TAU * L["cyc"] + L["ph"])
                y = L["ly"]
                shape = rest_tbl
            dark, light = L["col"]
            for dx, dy, lit in shape:
                xx, yy = int(x) + dx, int(y) + dy
                if 0 <= xx < S.W and 0 <= yy < S.H:
                    px[xx, yy] = light if lit else dark
        frames.append(im)
    return frames

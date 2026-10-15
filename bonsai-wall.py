#!/usr/bin/env python3
"""
bonsai-wall - procedurally grown, animated pixel-art bonsai wallpaper for
Hyprland + awww.

Every run grows a new tree across six species - Japanese maple (Acer palmatum),
Japanese pine (Pinus), Shimpaku juniper (Juniperus), Japanese zelkova (Zelkova
serrata), dawn redwood (Metasequoia), or Japanese larch (Larix kaempferi) -
renders a seamless loop at a low "art" resolution and hands it to awww with
nearest-neighbour scaling.

  bonsai-wall                        grow a new tree on every output
  bonsai-wall --seed 4242            regrow a tree you liked (seed is printed)
  bonsai-wall --species pinus        force species (acer, pinus, juniperus,
                                     zelkova, metasequoia, larix)
  bonsai-wall --style bunjin         force architecture (chokkan, moyogi, slant,
                                     fukinagashi, hankengai, bunjin, broom,
                                     twin, clump, forest)
  bonsai-wall --leaf crimson         force a leaf/needle colour
  bonsai-wall --tone light           light backdrop (default: mostly dark)
  bonsai-wall --bg scene             sunset/night/mist landscape
  bonsai-wall --static               still image only: zero idle cost
  bonsai-wall --theme-from none      don't re-theme ML4W
  bonsai-wall --preview ~/tmp        render files only, don't touch wallpaper
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops

TAU = math.tau
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
LIGHT = (-0.8, -0.6)  # unit vector pointing *towards* the light (upper left)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# palettes (realistic botanical pigments & traditional ceramics)
# --------------------------------------------------------------------------
LEAVES = {
    # Acer palmatum / broadleaf deciduous
    "chartreuse": (["#233d1e", "#3d6829", "#659836", "#98c94e", "#d2eb7f"],
                   [("#3d6829", "#98c94e"), ("#659836", "#d2eb7f")]),
    "green": (["#1b362a", "#2e5736", "#4b7f41", "#7ab052", "#b5d676"],
              [("#2e5736", "#7ab052"), ("#6c7d36", "#b2be5e")]),
    "deshojo": (["#331018", "#5e1924", "#94272f", "#c9433d", "#eb7a62"],
                [("#5e1924", "#c9433d"), ("#782420", "#de6945")]),
    "red": (["#301119", "#5c1a24", "#96282b", "#cc4637", "#eb825e"],
            [("#5c1a24", "#cc4637"), ("#7a281d", "#dc6c3d")]),
    "crimson": (["#280d14", "#4f141e", "#821f26", "#b53530", "#de6852"],
                [("#4f141e", "#b53530"), ("#6b1d1b", "#c9523b")]),
    "burgundy": (["#1f0e14", "#3b1822", "#5c2531", "#823842", "#ad5c60"],
                 [("#3b1822", "#823842"), ("#4f2024", "#964844")]),
    "orange": (["#361912", "#6b2e1c", "#a84f24", "#db8032", "#f2b75e"],
               [("#6b2e1c", "#db8032"), ("#85471b", "#eba244")]),
    "yellow": (["#33230e", "#664816", "#a1761d", "#d6ab31", "#f2da74"],
               [("#664816", "#d6ab31"), ("#754719", "#e5b446")]),
    # Zelkova / Chinese Elm
    "zelkova_green": (["#193022", "#2b4f2f", "#45753c", "#6ea14e", "#a4c971"],
                      [("#2b4f2f", "#6ea14e"), ("#667030", "#a8ad53")]),
    "elm_amber": (["#301d10", "#5e3919", "#945f24", "#c48c34", "#e6ba5c"],
                  [("#5e3919", "#c48c34"), ("#73441b", "#d49c3d")]),
    "elm_bronze": (["#2b1612", "#52291d", "#7d4228", "#ab6337", "#d48f55"],
                   [("#52291d", "#ab6337"), ("#693520", "#bf7840")]),
    # Pinus (Black & White Pines - fall pairs are senescent brown/olive needles)
    "kuromatsu": (["#102119", "#1c3827", "#2d5437", "#46784b", "#6fa16a"],
                  [("#3d2b1d", "#6e4f35"), ("#2d5437", "#5c7844")]),
    "goyomatsu": (["#142629", "#223f40", "#36615d", "#558a7f", "#87baa9"],
                  [("#423324", "#785d42"), ("#36615d", "#6c8c78")]),
    "old_pine": (["#162619", "#284226", "#406635", "#638f49", "#94b86c"],
                 [("#4a3520", "#82603a"), ("#406635", "#7a8f49")]),
    # Juniperus (Shimpaku)
    "shimpaku": (["#13291c", "#22472b", "#376e3c", "#589952", "#88c476"],
                 [("#3d311f", "#705a3a"), ("#22472b", "#589952")]),
    "itoigawa": (["#18301b", "#2b5227", "#467d36", "#6fa84b", "#a3d171"],
                 [("#423622", "#78623e"), ("#2b5227", "#6fa84b")]),
    "winter_bronze": (["#1f2416", "#353f23", "#526133", "#788749", "#a4b36d"],
                      [("#453520", "#7a5e38"), ("#353f23", "#788749")]),
    # Metasequoia & Larix (Deciduous conifers)
    "fresh": (["#1b3a1e", "#2f6128", "#4f8e33", "#82bb4c", "#c2de85"],
              [("#2f6128", "#82bb4c"), ("#6f7f2c", "#b6c96a")]),
    "summer": (["#16291d", "#26482a", "#3d6d35", "#5f9447", "#96c073"],
               [("#26482a", "#5f9447"), ("#4a6b2a", "#87ac5c")]),
    "larch_olive": (["#242e14", "#425221", "#6c7d32", "#9eb04b", "#d0db78"],
                    [("#425221", "#9eb04b"), ("#6b581e", "#bda042")]),
    "larch_gold": (["#36240c", "#6b4914", "#a8771e", "#deaa33", "#f7d969"],
                   [("#6b4914", "#deaa33"), ("#805216", "#ebb942")]),
    "rust": (["#33170c", "#663012", "#a0531e", "#cf8033", "#eeb469"],
             [("#663012", "#cf8033"), ("#7c3c14", "#df9646")]),
}
LEAVES["turning"] = LEAVES["fresh"]
LEAVES["gold_tips"] = LEAVES["larch_olive"]
TIPS = {"turning": "rust", "gold_tips": "larch_gold", "old_pine": "elm_amber"}
DECIDUOUS_TIPS = {"turning": "rust", "gold_tips": "larch_gold"}

ACER_AUTUMN_MIX = ("green", "yellow", "orange", "red", "crimson")
ACER_AUTUMN_FALL = LEAVES["orange"][1] + LEAVES["red"][1] + LEAVES["yellow"][1][:1]
ZELKOVA_AUTUMN_MIX = ("zelkova_green", "yellow", "elm_amber", "elm_bronze")
ZELKOVA_AUTUMN_FALL = LEAVES["elm_amber"][1] + LEAVES["elm_bronze"][1] + LEAVES["yellow"][1][:1]
LARIX_AUTUMN_MIX = ("larch_olive", "larch_gold", "rust")
LARIX_AUTUMN_FALL = LEAVES["larch_gold"][1] + LEAVES["rust"][1][:1]
LEAVES["autumn"] = (None, ACER_AUTUMN_FALL)

BARK_SMOOTH = ["#2e2a2b", "#4d4745", "#756d66", "#a39a8f"]    # Maple / Zelkova grey
BARK_PINE = ["#211a18", "#3b2e29", "#5c4840", "#856b5e"]      # Fissured dark pine plate bark
BARK_JUNIPER = ["#291c16", "#473125", "#6e4d3a", "#997057"]   # Reddish-brown fibrous strip bark
BARK_SEQ = ["#2b1a14", "#4a2c1d", "#70472c", "#9c6d48"]       # Dawn redwood fibrous bark
BARK_LARCH = ["#261e1b", "#42342e", "#665147", "#8f7567"]     # Scaly grey-brown larch bark
SHARI = ["#57524b", "#827c72", "#b0a99d"]                     # Aged deadwood (contrasts light & dark)

SPECIES = {
    "acer": dict(
        styles={"moyogi": 24, "broom": 16, "slant": 14, "twin": 14, "clump": 12,
                "forest": 12, "fukinagashi": 8},
        leaves={"green": 20, "chartreuse": 12, "deshojo": 14, "red": 14, "crimson": 10,
                "burgundy": 8, "orange": 8, "yellow": 6, "autumn": 18},
        autumn_mix=ACER_AUTUMN_MIX, autumn_fall=ACER_AUTUMN_FALL,
        bark=BARK_SMOOTH, foliage="cloud", shari_p=0.0, jin_p=0.0, particle="leaf"),
    "pinus": dict(
        styles={"moyogi": 28, "chokkan": 14, "slant": 18, "bunjin": 16,
                "hankengai": 14, "twin": 10, "fukinagashi": 10},
        leaves={"kuromatsu": 48, "goyomatsu": 34, "old_pine": 18},
        bark=BARK_PINE, foliage="needle", shari_p=0.25, jin_p=0.50, particle="needle"),
    "juniperus": dict(
        styles={"moyogi": 26, "slant": 18, "hankengai": 20, "bunjin": 16,
                "fukinagashi": 14, "twin": 6},
        leaves={"shimpaku": 46, "itoigawa": 36, "winter_bronze": 18},
        bark=BARK_JUNIPER, foliage="scale", shari_p=0.65, jin_p=0.70, particle="needle"),
    "zelkova": dict(
        styles={"broom": 44, "moyogi": 18, "forest": 18, "twin": 10, "clump": 10},
        leaves={"zelkova_green": 36, "chartreuse": 14, "elm_amber": 18,
                "elm_bronze": 16, "autumn": 16},
        autumn_mix=ZELKOVA_AUTUMN_MIX, autumn_fall=ZELKOVA_AUTUMN_FALL,
        bark=BARK_SMOOTH, foliage="fine", shari_p=0.0, jin_p=0.0, particle="leaf"),
    "metasequoia": dict(
        styles={"chokkan": 36, "forest": 26, "moyogi": 20, "twin": 10, "clump": 8},
        leaves={"fresh": 26, "summer": 22, "turning": 22, "rust": 30},
        bark=BARK_SEQ, foliage="spray", shari_p=0.0, jin_p=0.10, particle="needle"),
    "larix": dict(
        styles={"moyogi": 28, "chokkan": 14, "slant": 18, "bunjin": 12, "forest": 16,
                "twin": 12},
        leaves={"fresh": 26, "gold_tips": 24, "larch_gold": 34, "rust": 16},
        autumn_mix=LARIX_AUTUMN_MIX, autumn_fall=LARIX_AUTUMN_FALL,
        bark=BARK_LARCH, foliage="larch", shari_p=0.0, jin_p=0.35, particle="needle"),
}
SPECIES_WEIGHTS = {
    "acer": 22, "pinus": 18, "metasequoia": 17, "juniperus": 15, "zelkova": 14, "larix": 14
}
ALL_STYLES = sorted({s for sp in SPECIES.values() for s in sp["styles"]})

SOIL = ["#221917", "#33251e", "#4a372d"]
AKADAMA = ["#593e2e", "#785640"]
MOSS = ["#385428", "#587d35", "#89ab4c"]
WOOD = ["#22160f", "#3a2418", "#573624", "#754c34"]
STONE = ["#3c3b40", "#5c5b61", "#828187"]

POTS = {  # deep, dark, mid, light, specular(None = matte unglazed)
    "shudei": ["#2e1812", "#4a271e", "#6b392b", "#8c4e3b", None],        # Un-glazed red Tokoname
    "clay": ["#35211b", "#50322a", "#6f4637", "#90604a", None],          # Warm terracotta clay
    "nanban": ["#141314", "#222022", "#343134", "#4d494d", None],        # Dark iron stoneware
    "charcoal": ["#17171a", "#26262b", "#3a3a41", "#55555e", None],      # Matte grey-black
    "umber": ["#1f1411", "#31211b", "#473026", "#5f4133", None],         # Dark roasted brown
    "shigaraki": ["#4f4233", "#73614b", "#998266", "#baa182", None],     # Speckled buff stoneware
    "cream": ["#6e6149", "#9d8e6f", "#c3b491", "#e2d6b9", None],         # Matte ivory
    "celadon": ["#2b4540", "#466b63", "#689489", "#96bdb1", "#d0e8df"],  # Seiji jade glaze
    "oribe": ["#142b1d", "#214730", "#336947", "#4d8f64", "#9ec9ab"],    # Deep green Oribe glaze
    "indigo": ["#1c2640", "#2f3f66", "#465b8c", "#6880b3", "#b0c2e3"],   # Glazed blue-indigo
    "namako": ["#152038", "#23375e", "#35558c", "#527cc2", "#a8c7f0"],   # Mottled flambé blue
    "cobalt": ["#141f45", "#1f3470", "#2c4c9c", "#4a6fc2", "#b8cbf2"],   # Ruri royal blue
}

BACKDROPS = {
    "ink": dict(tone="dark", ramp=["#0b0e17", "#131a29", "#1d2739", "#2b3749"],
                mote=("#c9d6ea", "#56657d")),
    "sumi": dict(tone="dark", ramp=["#0c0c0e", "#16161a", "#222228", "#32323a"],
                 mote=("#d8d8e0", "#62626e")),
    "slate": dict(tone="dark", ramp=["#0a1314", "#112022", "#1a2f31", "#284344"],
                  mote=("#cfe7df", "#557470")),
    "umber": dict(tone="dark", ramp=["#100e0d", "#1a1715", "#27221e", "#39312a"],
                  mote=("#f2dfc0", "#7d6c58")),
    "tokonoma": dict(tone="dark", ramp=["#120f0c", "#1f1914", "#2e261e", "#42362b"],
                     mote=("#ebd9be", "#786652")),
    "forest": dict(tone="dark", ramp=["#0b110e", "#121c17", "#1b2a22", "#283b30"],
                   mote=("#dcefcf", "#5f7a62")),
    "washi": dict(tone="light", ramp=["#b9b1a1", "#d3ccbc", "#e4ddcf", "#f1ece2"],
                  mote=("#fffdf7", "#f4efe4")),
    "shikkui": dict(tone="light", ramp=["#b8b5ad", "#cfccc4", "#e0ded7", "#efede8"],
                    mote=("#ffffff", "#e8e6e0")),
    "fog": dict(tone="light", ramp=["#aab3b5", "#c6cecf", "#d9dfdf", "#eaeeed"],
                mote=("#ffffff", "#eef2f1")),
    "sage": dict(tone="light", ramp=["#aab2a0", "#c5ccba", "#d8ddcd", "#e8ebdf"],
                 mote=("#fbfdf5", "#edf0e5")),
}

HARMONY_GROUPS = {
    "green_broad": dict(
        dark={"ink": 3, "tokonoma": 3, "sumi": 2, "slate": 2, "umber": 2},
        light={"washi": 3, "shikkui": 2, "fog": 1},
        pots={"shudei": 3, "celadon": 3, "cream": 2, "indigo": 2, "oribe": 2, "clay": 2}),
    "conifer": dict(
        dark={"tokonoma": 3, "sumi": 3, "ink": 3, "umber": 2, "slate": 1},
        light={"washi": 3, "shikkui": 3, "sage": 1},
        pots={"shudei": 4, "nanban": 4, "clay": 3, "umber": 3, "shigaraki": 3, "charcoal": 2}),
    "red_autumn": dict(
        dark={"sumi": 3, "ink": 3, "slate": 3, "forest": 2, "tokonoma": 2},
        light={"washi": 3, "shikkui": 2, "fog": 2, "sage": 1},
        pots={"cream": 3, "celadon": 3, "indigo": 3, "nanban": 2, "shigaraki": 2, "namako": 2}),
    "warm_autumn": dict(
        dark={"ink": 3, "sumi": 3, "slate": 2, "tokonoma": 2, "umber": 1},
        light={"washi": 2, "fog": 2, "shikkui": 2},
        pots={"cobalt": 3, "indigo": 3, "namako": 3, "nanban": 2, "oribe": 2, "charcoal": 2}),
}
LEAF_TO_HARMONY = {
    "chartreuse": "green_broad", "green": "green_broad", "zelkova_green": "green_broad",
    "fresh": "green_broad", "summer": "green_broad", "larch_olive": "green_broad",
    "kuromatsu": "conifer", "goyomatsu": "conifer", "old_pine": "conifer",
    "shimpaku": "conifer", "itoigawa": "conifer", "winter_bronze": "conifer",
    "deshojo": "red_autumn", "red": "red_autumn", "crimson": "red_autumn",
    "burgundy": "red_autumn", "autumn": "red_autumn",
    "orange": "warm_autumn", "yellow": "warm_autumn", "elm_amber": "warm_autumn",
    "elm_bronze": "warm_autumn", "larch_gold": "warm_autumn", "rust": "warm_autumn",
    "turning": "warm_autumn", "gold_tips": "warm_autumn",
}

THEMES = {
    "dusk": dict(
        sky=["#1a1d2c", "#23273d", "#312f4b", "#463e5c", "#634d6b", "#866173", "#a67577"],
        disc="#e8cda0", halo="#b3877f", far="#6a5068", near="#4a3b55", mist="#8c6a78",
        deck=["#3a2c36", "#2b2129", "#1d161c"], edge="#7a5d68", seam="#150f14",
        mote=["#f6e0b2", "#a88a8a"], stars=False, clouds=True, tint=(1.0, 0.97, 0.97)),
    "night": dict(
        sky=["#070b16", "#0b1222", "#101a2f", "#16243c", "#1d2f49", "#263b56", "#304862"],
        disc="#dfe4e4", halo="#3f556c", far="#223246", near="#18253a", mist="#2c4057",
        deck=["#1a2230", "#131a26", "#0c111a"], edge="#3d4e63", seam="#080b11",
        mote=["#e4f59c", "#6b7d58"], stars=True, clouds=False, tint=(0.66, 0.76, 0.95)),
    "mist": dict(
        sky=["#bfcdc8", "#c9d5cf", "#d3ddd6", "#dde4dc", "#e5e9e0"],
        disc="#f7f3e8", halo="#e8e7dc", far="#aebfb8", near="#98aba4", mist="#e1e6de",
        deck=["#7b6a5c", "#665748", "#524537"], edge="#a8988a", seam="#43382d",
        mote=["#ffffff", "#d0d8d2"], stars=False, clouds=False, tint=(1.02, 1.02, 1.02)),
}


def wpick(r, opts):
    return r.choices(list(opts), list(opts.values()))[0]


def choose_look(seed, leaf="random", tone="auto", bg="studio", theme="auto", pot=None,
                backdrop=None, species="random"):
    """Colour choices, on their own RNG stream so they don't reshape the tree."""
    r = random.Random(seed * 7919 + 17)
    if species in (None, "random"):
        species = wpick(r, SPECIES_WEIGHTS)
    if leaf in (None, "random"):
        leaf = wpick(r, SPECIES[species]["leaves"])
    if tone == "auto":
        tone = "light" if r.random() < 0.22 else "dark"
    if backdrop:
        tone = BACKDROPS[backdrop]["tone"]
    hm_key = "warm_autumn" if (species == "zelkova" and leaf == "autumn") else LEAF_TO_HARMONY.get(leaf, "green_broad")
    hm = HARMONY_GROUPS[hm_key]
    backdrop = backdrop or wpick(r, hm[tone])
    if bg == "scene" and theme == "auto":
        theme = "mist" if tone == "light" else r.choice(("dusk", "night"))
    if bg == "scene":
        ref = luma(hx(THEMES[theme]["deck"][0]))
    else:
        st = BACKDROPS[backdrop]["ramp"]
        ref = (luma(hx(st[1])) + luma(hx(st[2]))) / 2

    def contrast(g):
        return abs(sum(luma(hx(POTS[g][i])) for i in (1, 2, 3)) / 3 - ref)

    if pot is None:
        pool = dict(hm["pots"])
        if species in ("pinus", "juniperus", "larix") and r.random() < 0.85:
            unglazed = {k: v for k, v in pool.items() if POTS[k][4] is None}
            if unglazed:
                pool = unglazed
        ok = {g: w for g, w in pool.items() if contrast(g) >= 24}
        pot = wpick(r, ok) if ok else max(pool, key=contrast)
    return dict(species=species, leaf=leaf, tone=tone, bg=bg, backdrop=backdrop,
                theme=theme, pot=pot)


# --------------------------------------------------------------------------
# drawing primitives & foliage renderers
# --------------------------------------------------------------------------
def draw_limb(buf, pts, radii, seed, streaks=True, rough=0.0, shari_frac=0.0):
    """Stamp a tapered, cylinder-shaded limb into buf {(x,y): (depth, level)}.
    Negative levels (-1..-3) encode bleached deadwood (shari/jin).
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


class Pad:
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


# --------------------------------------------------------------------------
# scene construction
# --------------------------------------------------------------------------
class Scene:
    pass


def grow_scene(seed, W, H, look, xfrac=0.5):
    """build_scene, narrowing or sliding the composition so no pixels clip."""
    shrink, shift = 1.0, 0.0
    for _ in range(8):
        S = build_scene(seed, W, H, look, xfrac, shrink, shift)
        left, right = S.xmin, W - 1 - S.xmax
        if left >= 2 and right >= 2 and S.crown_top >= 0.02 * H:
            break
        span_w = S.xmax - S.xmin
        if span_w <= W - 6:
            shift += (right - left) * 0.5
        else:
            shrink *= max(0.58, min(0.90, (W - 8) / max(1.0, span_w)))
            shift += (right - left) * 0.35
    return S


def build_scene(seed, W, H, look, xfrac=0.5, shrink=1.0, shift=0.0):
    rng = random.Random(seed)
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
    k = H / 360.0
    species = look.get("species", "acer")
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
    S.species, S.style, S.caliper, S.mode = species, style, caliper, mode
    S.wind_dir = long_side if style == "fukinagashi" else rng.choice((-1, 1))

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
    S.deck_y, S.stand_top, S.stand_bot, S.rim_top = deck_y, stand_top, stand_bot, rim_top
    S.xc, S.stand_w, S.pot_w, S.soil_top, S.soil_half = xc, stand_w, pot_w, soil_top, soil_half

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

    front, back = {}, {}
    flute = []
    NX, NY, NR, PAR, KIND, SIDE, BK, CH, LID, ARC, CONV, PAD_ID = ([] for _ in range(12))
    cand = []
    for li, (pts, rad, ey, lbk) in enumerate(leaders):
        draw_limb(back if lbk else front, pts, rad, seed + li * 19,
                  rough=rough, shari_frac=shari_frac if li == 0 else shari_frac * 0.5)
        if mode == "tiers":
            flute.append((back if lbk else front, pts[0][0], rad[0], u(0, TAU)))
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
                draw_limb(front, jpts, [max(0.7, rad[-1] * 0.85 * (1 - q)) for q in jf],
                          seed + 91, streaks=False, shari_frac=1.0)
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
                draw_limb(front, jpts, [max(0.6, r0_j * (1 - q) ** 0.8) for q in jf],
                          seed + idx_j, streaks=False, shari_frac=1.0)

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
        draw_limb(back if a["back"] else front, pts, rad, seed,
                  streaks=rad[0] >= 2.5, rough=rough * 0.5)

    for buf, bx0, r0, fph in flute:
        y_fl = yb - u(0.16, 0.26) * Ht
        for (x, y), v in buf.items():
            if v[1] < 0 or y < y_fl or abs(x - bx0) > r0 * 2.2:
                continue
            g = math.sin((x - bx0) * 1.9 + fph)
            f = min(1.0, (y - y_fl) / (yb - y_fl))
            if g < -0.35 and h2(x, y, seed + 31) < 0.55 + 0.45 * f:
                buf[(x, y)] = (v[0], max(0, v[1] - 1))
            elif g > 0.75 and f > 0.35 and v[1] < 3:
                buf[(x, y)] = (v[0], v[1] + 1)

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
            draw_limb(front, tw, [0.8] * len(tw), seed, streaks=False)

    # Leaf colour per pad
    nph = (u(0, TAU), u(0, TAU))
    for p in pads:
        if len(ramps) == 1:
            p.ramp = p.ramp2 = ramps[0]
            p.mix = 0.0
            continue
        ty = min(1.0, max(0.0, (p.cy - y_top) / ch))
        c0 = cxat(p.cy)
        hw = max(1.0, half(p.cy, 1 if p.cx >= c0 else -1))
        outer = min(1.0, abs(p.cx - c0) / hw)
        nz = 0.5 + 0.3 * math.sin(p.cx / (31 * k) + nph[0]) * math.cos(p.cy / (23 * k) + nph[1]) \
            + 0.2 * math.sin((p.cx + p.cy) / (13 * k) + nph[1])
        v = 0.25 * (1 - ty) + 0.1 * outer + 0.75 * nz - (0.1 if p.back else 0.0) + u(-0.12, 0.12)
        i = max(0, min(len(ramps) - 1, int(v * len(ramps) - 0.4)))
        p.ramp = ramps[i]
        p.ramp2 = ramps[max(0, min(len(ramps) - 1, i + rng.choice((-1, 1))))]
        p.mix = 0.22

    # Render pad sprites & set sway amplitudes high enough to never round to 0
    renderers = {
        "spray": render_spray,
        "needle": render_needles,
        "scale": render_scale_pad,
        "larch": render_larch,
        "cloud": render_pad,
        "fine": render_pad,
    }
    p_left_est = min(p.cx - p.rx for p in pads)
    p_right_est = max(p.cx + p.rx for p in pads)
    for p in pads:
        rp = renderers.get(p.kind, render_pad)
        rp(p, seed + int(p.cx * 7 + p.cy * 13), rng)
        hf = max(0.0, min(1.0, (yb - p.cy) / Ht))
        raw_amp = (0.65 + 1.05 * hf + 0.55 * min(1.0, abs(p.cx - xb) / (0.6 * Ht))) \
            * (0.78 if p.back else 1.0)
        if p.kind in ("needle", "scale"):
            raw_amp *= 0.88
        p.amp = max(0.78 if p.back else 0.98, raw_amp)
        p.lag = (p.cx - p_left_est) / max(1.0, p_right_est - p_left_est) * 0.14

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


# --------------------------------------------------------------------------
# animation
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# outputs / awww glue
# --------------------------------------------------------------------------
def detect_outputs():
    try:
        r = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3)
        res = []
        for m in json.loads(r.stdout):
            w, h = int(m["width"]), int(m["height"])
            if int(m.get("transform", 0)) % 2 == 1:
                w, h = h, w
            res.append((m["name"], w, h))
        if res:
            return res
    except Exception:
        pass
    try:
        r = subprocess.run(["awww", "query"], capture_output=True, text=True, timeout=3)
        res = []
        for line in r.stdout.splitlines():
            m = re.search(r"([A-Za-z0-9._-]+):\s*(\d+)x(\d+)", line)
            if m:
                res.append((m.group(1), int(m.group(2)), int(m.group(3))))
        if res:
            return res
    except Exception:
        pass
    return [(None, 2560, 1440)]


def pick_scale(w, h, target=360):
    base = max(1, round(h / target))
    cands = [s for s in (base, base - 1, base + 1) if s >= 1 and 0.75 < h / s / target < 1.35]
    exact = [s for s in cands if h % s == 0]
    return (exact or cands or [base])[0]


def theme_image(S, frame, w, h, s, mode):
    fr = frame.convert("RGB")
    if mode == "leaves":
        r, g, b = ImageChops.difference(fr, S.bg.convert("RGB")).split()
        same = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v == 0 else 0)
        fr = Image.composite(fr.convert("L").convert("RGB"), fr, same)
    big = fr.resize((fr.width * s, fr.height * s), Image.NEAREST)
    ox, oy = (big.width - w) // 2, (big.height - h) // 2
    return big.crop((ox, oy, ox + w, oy + h))


def ml4w_script():
    found = shutil.which("ml4w-wallpaper")
    if found:
        return found
    p = Path.home() / ".config" / "ml4w" / "scripts" / "ml4w-wallpaper"
    return str(p) if p.exists() else None


def awww_ready():
    try:
        return subprocess.run(["awww", "query"], capture_output=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_daemon(wait=10.0):
    t0 = time.time()
    while time.time() - t0 < wait:
        if awww_ready():
            return
        time.sleep(0.3)
    subprocess.Popen(["awww-daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 5:
        if awww_ready():
            return
        time.sleep(0.2)
    sys.exit("bonsai-wall: awww-daemon is not reachable")


def main():
    ap = argparse.ArgumentParser(description="Procedural pixel-art bonsai wallpaper for awww.")
    ap.add_argument("--seed", type=int, help="grow a specific tree (printed on every run)")
    ap.add_argument("--species", default="random", choices=sorted(SPECIES) + ["random"],
                    help="acer, pinus, juniperus, zelkova, metasequoia, or larix")
    ap.add_argument("--leaf", default="random", choices=sorted(LEAVES) + ["random"],
                    help="leaf/needle colour; backdrop and pot are chosen to match")
    ap.add_argument("--tone", default="auto", choices=("auto", "dark", "light"),
                    help="backdrop tone (auto: ~78%% dark, ~22%% light)")
    ap.add_argument("--bg", default="studio", choices=("studio", "scene"),
                    help="plain diffuse backdrop (default) or the sunset/night landscape")
    ap.add_argument("--backdrop", choices=sorted(BACKDROPS), help="force a backdrop colour")
    ap.add_argument("--pot", choices=sorted(POTS), help="force a pot glaze/clay")
    ap.add_argument("--style", default="random", choices=ALL_STYLES + ["random"],
                    help="tree architecture (default: random per species)")
    ap.add_argument("--theme", default="auto", choices=sorted(THEMES) + ["auto"],
                    help="landscape theme for --bg scene")
    ap.add_argument("--fps", type=float, default=10.0, help="animation fps (default 10)")
    ap.add_argument("--seconds", type=float, default=12.0, help="loop length (default 12)")
    ap.add_argument("--static", action="store_true", help="still image, no animation")
    ap.add_argument("--pixel", type=int, help="screen pixels per art pixel (auto: ~360 art rows)")
    ap.add_argument("--x", type=float, default=0.5, help="horizontal tree position 0..1")
    ap.add_argument("--size", help="WxH, skip monitor detection (for previews)")
    ap.add_argument("--outputs", help="comma list of outputs to set (default: all)")
    ap.add_argument("--transition", default="fade", help="awww transition type")
    ap.add_argument("--transition-duration", type=float, default=1.2)
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds to wait before applying")
    ap.add_argument("--preview", metavar="DIR", help="write files to DIR, don't set wallpaper")
    ap.add_argument("--theme-from", choices=("leaves", "wallpaper", "none"), default="leaves",
                    help="ML4W colour theming source")
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1, 10**6)
    look = choose_look(seed, a.leaf, a.tone, a.bg, a.theme, a.pot, a.backdrop, a.species)
    look["style"] = None if a.style == "random" else a.style

    if a.size:
        w, h = (int(v) for v in a.size.lower().split("x"))
        outs = [(None, w, h)]
    else:
        outs = detect_outputs()
    if a.outputs:
        want = set(a.outputs.split(","))
        outs = [o for o in outs if o[0] in want] or outs

    cache = Path(a.preview).expanduser() if a.preview else \
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "bonsai-wall"
    cache.mkdir(parents=True, exist_ok=True)

    groups = {}
    for name, w, h in outs:
        groups.setdefault((w, h), []).append(name)
    made = []
    theme = None
    t_start = time.time()
    for (w, h), names in groups.items():
        s = a.pixel or pick_scale(w, h)
        cw, ch = -(-w // s), -(-h // s)
        S = grow_scene(seed, cw, ch, look, a.x)
        if a.static:
            frames = render_frames(S, 1, 1, falling=False)[:1]
            path = cache / f"bonsai-{seed}-{w}x{h}.png"
            frames[0].save(path, optimize=True)
        else:
            frames = render_frames(S, a.fps, a.seconds)
            path = cache / f"bonsai-{seed}-{w}x{h}.gif"
            frames[0].save(path, save_all=True, append_images=frames[1:], loop=0,
                           duration=round(1000 / a.fps), disposal=1, optimize=True)
            frames[0].convert("RGB").save(cache / f"still-{w}x{h}.png")
        made.append((path, names, s))
        if theme is None and a.theme_from != "none":
            theme = cache / f"theme-{w}x{h}.png"
            theme_image(S, frames[0], w, h, s, a.theme_from).save(theme)
        if a.preview:
            frames[0].convert("RGB").resize((cw * s, ch * s), Image.NEAREST) \
                .save(cache / f"preview-{seed}-{w}x{h}.png")
    gen_time = time.time() - t_start

    if not a.preview:
        if not shutil.which("awww"):
            sys.exit("bonsai-wall: awww not found (sudo pacman -S awww), "
                     f"or use --preview. Rendered: {made[0][0]}")
        if a.delay > 0:
            time.sleep(a.delay)
        ensure_daemon()
        for path, names, s in made:
            cmd = ["awww", "img", str(path), "--filter", "Nearest", "--resize", "crop",
                   "--transition-type", a.transition,
                   "--transition-duration", str(a.transition_duration)]
            if all(names):
                cmd += ["--outputs", ",".join(names)]
            subprocess.run(cmd, check=False)
        keep = {p.name for p, _, _ in made}
        for old in cache.glob("bonsai-*"):
            if old.name not in keep:
                old.unlink(missing_ok=True)
        (cache / "last_seed").write_text(f"{seed}\n")
        script = ml4w_script() if theme else None
        if script:
            log = open(cache / "ml4w-theme.log", "w")
            subprocess.Popen([script, str(theme), "--skip-wallpaper"], stdout=log, stderr=log,
                             start_new_session=True)

    info = ", ".join(f"{p.name} (x{s})" for p, _, s in made)
    where = f"{look['theme']} scene" if look["bg"] == "scene" else f"{look['backdrop']} backdrop"
    print(f"bonsai-wall: seed {seed}, {S.species} {S.style}, {look['leaf']} foliage, {where}, "
          f"{look['pot']} pot, {gen_time:.1f}s -> {info}")


if __name__ == "__main__":
    main()

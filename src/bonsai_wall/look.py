"""Palettes, species tables, HARMONY and choose_look, moved verbatim from V1."""
from __future__ import annotations

import random

from .util import hx, luma


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

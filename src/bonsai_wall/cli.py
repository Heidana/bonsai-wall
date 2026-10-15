"""bonsai-wall command line (V1 behaviour; see docs/v1_inventory.md section 2)."""
from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

from .animate import render_frames
from .look import ALL_STYLES, BACKDROPS, LEAVES, POTS, SPECIES, THEMES, choose_look
from .output import (awww_ready, detect_outputs, ensure_daemon, ml4w_script, pick_scale,
                     theme_image)
from .pipeline import grow_scene


def main():
    ap = argparse.ArgumentParser(description="Procedural pixel-art bonsai wallpaper for awww.")
    ap.add_argument("--seed", type=int, help="grow a specific tree (printed on every run)")
    ap.add_argument("--engine", default="v1", choices=("v1", "v2"),
                    help="tree engine (v2 arrives in a later phase; default v1)")
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
    if a.engine == "v2":
        sys.exit("bonsai-wall: --engine v2 is not implemented yet, use --engine v1")

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


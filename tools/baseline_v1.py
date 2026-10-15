#!/usr/bin/env python3
"""Baseline harness for V1.

Phase 0 numbers (perf, profile) come from the untouched root script bonsai-wall.py. From Phase 1
the sweep and the summary go through the package and measure the TreeScene IR
(bonsai_wall.metrics), so V1 and V2 are compared on the same projected 2D strokes.

  sweep    in-process: gif size, palette peak, changed px/frame, fit retries, IR metrics,
           structure_distance inputs, frame-0 PNGs for contact sheets
  perf     end-to-end CLI wall time of bonsai-wall.py (one core, --preview only) + determinism
  profile  in-process stage breakdown of bonsai-wall.py (one core)
  sheets   contact sheets per species (styles x 6 seeds) from the sweep's PNGs
  summary  docs/baseline/v1_baseline_summary.md from the CSVs

Never calls awww: every CLI run uses --preview.

Usage (fish):
  python tools/baseline_v1.py sweep
  python tools/baseline_v1.py perf
  python tools/baseline_v1.py profile
  python tools/baseline_v1.py sheets
  python tools/baseline_v1.py summary
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import itertools
import os
import statistics
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
V1_PATH = ROOT / "bonsai-wall.py"
OUT = ROOT / "out" / "baseline"
DOCS = ROOT / "docs" / "baseline"
SWEEP_CSV = DOCS / "v1_sweep.csv"
PERF_CSV = DOCS / "v1_perf.csv"
PROFILE_CSV = DOCS / "v1_profile.csv"
SILS = OUT / "silhouettes.npz"

SIZE_MAIN = "2560x1440"          # art 640x360 (same art grid as 4K)
SIZE_4K = "3840x2160"
SIZES_OTHER = ("3440x1440", "1920x1200", "1440x2560")   # 21:9, 16:10, portrait
SEEDS_MAIN = tuple(range(1, 31))
SEEDS_OTHER = (1, 2, 3)
SHEET_SEEDS = 6

_V1 = None


def v1():
    """The untouched root script, imported (Phase 0 reference for perf and profile)."""
    global _V1
    if _V1 is None:
        spec = importlib.util.spec_from_file_location("bw_v1", V1_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _V1 = m
    return _V1


def combos():
    from bonsai_wall.look import SPECIES
    return [(sp, st) for sp in sorted(SPECIES) for st in sorted(SPECIES[sp]["styles"])]


def art_size(m, size):
    w, h = (int(v) for v in size.split("x"))
    s = m.pick_scale(w, h)
    return w, h, s, -(-w // s), -(-h // s)


# --------------------------------------------------------------------------
# sweep worker (package, IR metrics)
# --------------------------------------------------------------------------
def run_one(task):
    from bonsai_wall import animate, metrics, output, pipeline
    from bonsai_wall.look import choose_look
    size, sp, st, seed, save_png = task
    w, h, s, cw, ch = art_size(output, size)
    look = choose_look(seed, "random", "auto", "studio", "auto", None, None, sp)
    look["style"] = st
    t0 = time.perf_counter()
    S = pipeline.grow_scene(seed, cw, ch, look, 0.5)
    t1 = time.perf_counter()
    frames = animate.render_frames(S, 10.0, 12.0)
    t2 = time.perf_counter()
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], loop=0,
                   duration=100, disposal=1, optimize=True)
    t3 = time.perf_counter()
    arr = np.stack([np.asarray(f) for f in frames])
    changed = (arr != np.roll(arr, 1, axis=0)).reshape(len(frames), -1).sum(1)
    lay = S.layout
    row = dict(size=size, art_w=cw, art_h=ch, scale=s, species=sp, style=st, seed=seed,
               leaf=look["leaf"], pot=look["pot"], gif_bytes=buf.tell(),
               palette_peak=len(S.pal), n_frames=len(frames),
               changed_mean=float(changed.mean()), changed_p95=float(np.percentile(changed, 95)),
               changed_max=int(changed.max()), builds=S.fit[0], final_shrink=S.fit[1],
               final_shift=S.fit[2], margin_left=S.xmin, margin_right=cw - 1 - S.xmax,
               crown_top=S.crown_top, pot_w=lay.pot_w, stand_w=lay.stand_w, rim_top=lay.rim_top,
               stand_top=lay.stand_top, design_ht=lay.Ht, xb=lay.xb, yb=lay.yb, xc=lay.xc,
               pot_style=lay.pot_style, stand_style=lay.stand_style, caliper=S.caliper,
               mode=S.mode, t_grow=t1 - t0, t_render=t2 - t1, t_gif=t3 - t2)
    met, grid, hist = metrics.scene_metrics(S.tree)
    row.update(met)
    if save_png:
        d = OUT / "frames"
        d.mkdir(parents=True, exist_ok=True)
        frames[0].convert("RGB").save(d / f"{sp}-{st}-{seed}.png")
    return row, np.packbits(grid), hist


def cmd_sweep():
    from bonsai_wall import metrics
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    cs = combos()
    tasks = [(SIZE_MAIN, sp, st, sd, sd <= SHEET_SEEDS) for sp, st in cs for sd in SEEDS_MAIN]
    tasks += [(sz, sp, st, sd, False) for sz in SIZES_OTHER for sp, st in cs for sd in SEEDS_OTHER]
    print(f"sweep: {len(tasks)} runs over {len(cs)} combos", flush=True)
    t0 = time.time()
    rows, sils = [], {}
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        for i, (row, packed, hist) in enumerate(pool.imap(run_one, tasks, chunksize=2)):
            rows.append(row)
            if row["size"] == SIZE_MAIN:
                key = f'{row["species"]}|{row["style"]}|{row["seed"]}'
                sils[key + "|g"] = packed
                sils[key + "|h"] = hist
            if i % 100 == 0:
                print(f"  {i}/{len(tasks)}  {time.time() - t0:.0f}s", flush=True)
    keys = list(rows[0])
    with open(SWEEP_CSV, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)
    np.savez_compressed(SILS, **sils)
    print(f"wrote {SWEEP_CSV} and {SILS} in {time.time() - t0:.0f}s")


# --------------------------------------------------------------------------
# perf: end-to-end CLI, pinned to one core, preview only
# --------------------------------------------------------------------------
def cli_run(size, sp, st, seed):
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as td:
        cmd = ["taskset", "-c", "0", sys.executable, str(V1_PATH), "--seed", str(seed),
               "--species", sp, "--style", st, "--size", size, "--preview", td]
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.perf_counter() - t0
        if r.returncode:
            raise SystemExit(f"CLI failed: {' '.join(cmd)}\n{r.stderr}")
        gif = next(Path(td).glob("bonsai-*.gif"))
        return dt, gif.stat().st_size, hashlib.sha256(gif.read_bytes()).hexdigest()


def cmd_perf():
    DOCS.mkdir(parents=True, exist_ok=True)
    cs = combos()
    jobs = [(SIZE_4K, sp, st, sd, 2) for sp, st in cs for sd in (1, 2)]
    jobs += [(sz, sp, st, 1, 1) for sz in SIZES_OTHER for sp, st in cs]
    rows = []
    for i, (size, sp, st, seed, reps) in enumerate(jobs):
        hs = []
        for rep in range(reps):
            dt, nb, hh = cli_run(size, sp, st, seed)
            hs.append(hh)
            rows.append(dict(size=size, species=sp, style=st, seed=seed, rep=rep,
                             wall_s=dt, gif_bytes=nb, sha=hh[:12],
                             identical_to_rep0=hh == hs[0]))
        if i % 20 == 0:
            print(f"  {i}/{len(jobs)}", flush=True)
    with open(PERF_CSV, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {PERF_CSV}")


def cmd_profile():
    """In-process stage breakdown at 4K, pinned to core 0, serial."""
    os.sched_setaffinity(0, {0})
    m = v1()
    w, h, s, cw, ch = art_size(m, SIZE_4K)
    rows = []
    for sp, st in combos():
        for seed in (1, 2):
            look = m.choose_look(seed, "random", "auto", "studio", "auto", None, None, sp)
            look["style"] = st
            t0 = time.perf_counter()
            S = m.grow_scene(seed, cw, ch, look, 0.5)
            t1 = time.perf_counter()
            frames = m.render_frames(S, 10.0, 12.0)
            t2 = time.perf_counter()
            buf = io.BytesIO()
            frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], loop=0,
                           duration=100, disposal=1, optimize=True)
            t3 = time.perf_counter()
            buf2 = io.BytesIO()
            frames[0].convert("RGB").save(buf2, format="PNG")
            m.theme_image(S, frames[0], w, h, s, "leaves").save(buf2, format="PNG")
            frames[0].convert("RGB").resize((cw * s, ch * s), Image.NEAREST).save(buf2, format="PNG")
            t4 = time.perf_counter()
            rows.append(dict(species=sp, style=st, seed=seed, grow_s=t1 - t0, frames_s=t2 - t1,
                             gif_s=t3 - t2, pngs_s=t4 - t3, total_s=t4 - t0))
    with open(PROFILE_CSV, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {PROFILE_CSV}")


# --------------------------------------------------------------------------
# contact sheets
# --------------------------------------------------------------------------
def cmd_sheets():
    m = v1()
    fr = OUT / "frames"
    tw, th = 320, 180
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for sp in sorted(m.SPECIES):
        styles = sorted(m.SPECIES[sp]["styles"])
        sheet = Image.new("RGB", (SHEET_SEEDS * tw, len(styles) * th), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for r, st in enumerate(styles):
            for c in range(SHEET_SEEDS):
                p = fr / f"{sp}-{st}-{c + 1}.png"
                if p.exists():
                    sheet.paste(Image.open(p).resize((tw, th), Image.LANCZOS), (c * tw, r * th))
            d.text((4, r * th + 4), f"{st}", fill=(255, 255, 255), font=font)
        out = OUT / f"sheet-v1-{sp}.png"
        sheet.save(out)
        print(out)


# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
def pct(v, p):
    return float(np.percentile(np.array(v, float), p))


def read(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def fl(r, k):
    return float(r[k])


def med(rs, k):
    v = [fl(r, k) for r in rs if r[k] not in ("", "nan") and fl(r, k) == fl(r, k)]
    return statistics.median(v) if v else float("nan")


def load_sils():
    from bonsai_wall import metrics
    z = np.load(SILS)
    out = {}
    for sp, st in combos():
        items = []
        for sd in SEEDS_MAIN:
            k = f"{sp}|{st}|{sd}"
            g = np.unpackbits(z[k + "|g"])[:metrics.GRID_W * metrics.GRID_H].astype(bool) \
                .reshape(metrics.GRID_H, metrics.GRID_W)
            items.append((g, z[k + "|h"]))
        out[(sp, st)] = items
    return out


def cmd_summary():
    from bonsai_wall import metrics
    sw = read(SWEEP_CSV)
    main = [r for r in sw if r["size"] == SIZE_MAIN]
    cs = combos()
    L = []
    A = L.append
    A("# V1 baseline (this machine)\n")
    A("Generated by `tools/baseline_v1.py summary` from `v1_sweep.csv`, `v1_perf.csv`, "
      "`v1_profile.csv`. Timing and determinism rows run the untouched `bonsai-wall.py`; the sweep, "
      "silhouette, named-miss, layout and structure-distance rows are measured from the V1 "
      "`TreeScene` IR (`bonsai_wall.metrics`) through the package, whose frames are byte-identical "
      "to the script (`tests/test_goldens.py`). Every CLI run uses `--preview`.\n")
    A(f"Sweep: {len(sw)} renders ({len(main)} at {SIZE_MAIN} = 640x360 art, "
      f"{len(sw) - len(main)} at other screen shapes), {len(cs)} species x style combos "
      f"with weight > 0.\n")

    perf = read(PERF_CSV)
    p4 = [fl(r, "wall_s") for r in perf if r["size"] == SIZE_4K]
    A("## End-to-end CLI time, 1 core (`taskset -c 0`), `--preview`\n")
    A("| size | runs | p50 s | p95 s | max s |\n| --- | --- | --- | --- | --- |")
    for sz in (SIZE_4K,) + SIZES_OTHER:
        v = [fl(r, "wall_s") for r in perf if r["size"] == sz]
        A(f"| {sz} | {len(v)} | {pct(v, 50):.2f} | {pct(v, 95):.2f} | {max(v):.2f} |")
    det = [r for r in perf if r["rep"] == "1"]
    same = sum(r["identical_to_rep0"] == "True" for r in det)
    A(f"\nDeterminism: {same}/{len(det)} repeated CLI runs produced a byte-identical GIF.\n")
    A(f"V2 budget (4K): p50 <= 4 s, p95 <= 8 s. V1 uses {pct(p4, 50):.2f} / {pct(p4, 95):.2f} s.\n")

    pr = read(PROFILE_CSV)
    A(f"## Stage breakdown at 4K (in-process, 1 core), mean over {len(pr)} runs\n")
    A("| stage | mean s | p95 s |\n| --- | --- | --- |")
    for k, nm in (("grow_s", "grow_scene (incl. retries, pad sprites, bg, palette)"),
                  ("frames_s", "render_frames (120 frames)"), ("gif_s", "GIF encode"),
                  ("pngs_s", "still + theme + preview PNG"), ("total_s", "total")):
        v = [fl(r, k) for r in pr]
        A(f"| {nm} | {statistics.mean(v):.2f} | {pct(v, 95):.2f} |")

    g = [fl(r, "gif_bytes") for r in main]
    cm = [fl(r, "changed_mean") for r in main]
    cp = [fl(r, "changed_p95") for r in main]
    pk = [fl(r, "palette_peak") for r in main]
    A("\n## Output size, palette, changed pixels (16:9, 640x360 art)\n")
    A("| metric | p5 | p50 | p95 | max | V2 budget |\n| --- | --- | --- | --- | --- | --- |")
    A(f"| GIF bytes | {pct(g, 5):.0f} | {pct(g, 50):.0f} | {pct(g, 95):.0f} | {max(g):.0f} | "
      f"<= V1 + 25% (p50 {pct(g, 50) * 1.25:.0f}, p95 {pct(g, 95) * 1.25:.0f}) |")
    A(f"| changed px / frame (mean) | {pct(cm, 5):.0f} | {pct(cm, 50):.0f} | {pct(cm, 95):.0f} | "
      f"{max(cm):.0f} | <= V1 + 25% (p50 {pct(cm, 50) * 1.25:.0f}) |")
    A(f"| changed px / frame (p95 frame) | {pct(cp, 5):.0f} | {pct(cp, 50):.0f} | "
      f"{pct(cp, 95):.0f} | {max(cp):.0f} | |")
    A(f"| palette peak | {pct(pk, 5):.0f} | {pct(pk, 50):.0f} | {pct(pk, 95):.0f} | {max(pk):.0f} | "
      f"<= 255 |")

    A("\n## Fit retries (V1 narrows/slides the composition after building)\n")
    multi = [r for r in sw if int(r["builds"]) > 1]
    shrunk = [r for r in sw if fl(r, "final_shrink") < 0.999]
    A(f"- {len(multi)}/{len(sw)} renders needed more than one build pass "
      f"({100 * len(multi) / len(sw):.1f}%); {len(shrunk)} ended with shrink < 1 "
      f"(V1 rescales the design to fit; V2 must not).")
    by = {}
    for r in multi:
        by[(r["species"], r["style"])] = by.get((r["species"], r["style"]), 0) + 1
    if by:
        top = sorted(by.items(), key=lambda kv: -kv[1])[:8]
        A("- Most affected combos: " + ", ".join(f"{a}/{b} x{n}" for (a, b), n in top))
    tight = [r for r in sw if min(fl(r, "margin_left"), fl(r, "margin_right")) < 2]
    A(f"- Renders with < 2 art px side margin after fitting: {len(tight)}.")

    A("\n## IR metrics per combo (front view, median over seeds 1-30)\n")
    A("From the projected strokes (limbs as discs) and pad extents (half-ellipses), not sprites. "
      "`inner open` = share of the inner crown core not covered by foliage. `lean` is meaningless "
      "for forest and clump (several trunks).\n")
    A("| species | style | H px | W/H | lean deg | apex off | fol. centroid | neg. space | taper | "
      "apex ratio | bends | inner open | pads | GIF KB |\n"
      "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for sp, st in cs:
        rs = [r for r in main if r["species"] == sp and r["style"] == st]
        A(f"| {sp} | {st} | {med(rs, 'tree_h'):.0f} | {med(rs, 'width_over_h'):.2f} | "
          f"{med(rs, 'lean_deg'):.1f} | {med(rs, 'apex_offset'):+.3f} | "
          f"{med(rs, 'foliage_centroid_h'):.2f} | {med(rs, 'negative_space'):.2f} | "
          f"{med(rs, 'taper'):.1f} | {med(rs, 'apex_ratio'):.2f} | {med(rs, 'bends'):.0f} | "
          f"{med(rs, 'inner_open'):.2f} | {med(rs, 'n_pads'):.0f} | "
          f"{med(rs, 'gif_bytes') / 1024:.0f} |")

    styles = sorted({st for _, st in cs})
    A("\n## V1's named misses, measured from the IR\n")
    A("Per style, pooled over species (all 30 seeds each). These are baseline values for the V2 style "
      "bands; they are not pass/fail.\n")
    A("### Windswept reads as slanting\n")
    A("| style | n | lean deg p10 / p50 / p90 | apex offset p50 | leeward lean (|offset| p50) |\n"
      "| --- | --- | --- | --- | --- |")
    for st in ("slant", "fukinagashi"):
        rs = [r for r in main if r["style"] == st]
        ln = [fl(r, "lean_deg") for r in rs]
        A(f"| {st} | {len(rs)} | {pct(ln, 10):.1f} / {pct(ln, 50):.1f} / {pct(ln, 90):.1f} | "
          f"{med(rs, 'apex_offset'):+.3f} | {statistics.median(abs(fl(r, 'apex_offset')) for r in rs):.3f} |")
    A("\nBands for windswept rest on these two (lean is a sanity check only): `leeward` = share of "
      "foliage area on the side the crown leans to; `window60` = largest share of length-weighted "
      "primary angles inside any 60 degree window.\n")
    A("| style | n | leeward p10 / p50 / p90 | window60 p10 / p50 / p90 |\n| --- | --- | --- | --- |")
    for st in ("slant", "fukinagashi", "moyogi"):
        rs = [r for r in main if r["style"] == st]
        lw = [fl(r, "leeward") for r in rs]
        w6 = [fl(r, "primary_window_60") for r in rs]
        A(f"| {st} | {len(rs)} | {pct(lw, 10):.2f} / {pct(lw, 50):.2f} / {pct(lw, 90):.2f} | "
          f"{pct(w6, 10):.2f} / {pct(w6, 50):.2f} / {pct(w6, 90):.2f} |")
    A("\n### Corkscrew trunks\n")
    A("Main trunk only (`strokes[0]`). `bends` = lateral lobes > 2 px off the base-apex chord; `amp / r` = "
      "mean lobe amplitude over the trunk base radius (how far the trunk swings compared with its own "
      "thickness, which is what makes a slender literati trunk read as a corkscrew); `H / base D` = tree "
      "height over trunk base diameter (spec bunjin band: >= 12); turns are measured over 4 px steps.\n")
    A("| style | n | bends p50 / p90 | bends per 100 px p50 | amp / r p50 / p90 | H / base D p50 | "
      "max turn deg p50 / p90 | twist deg per 100 px p50 / p90 |\n| --- | --- | --- | --- | --- | --- | --- | --- |")
    for st in styles:
        rs = [r for r in main if r["style"] == st]
        b_ = [fl(r, "bends") for r in rs]
        mt = [fl(r, "max_turn_deg") for r in rs]
        tw = [fl(r, "twist_deg_per_100px") for r in rs]
        ao = [fl(r, "bend_amp_over_r") for r in rs]
        A(f"| {st} | {len(rs)} | {pct(b_, 50):.0f} / {pct(b_, 90):.0f} | "
          f"{med(rs, 'bends_per_100px'):.2f} | {pct(ao, 50):.1f} / {pct(ao, 90):.1f} | "
          f"{med(rs, 'height_over_base_d'):.1f} | {pct(mt, 50):.1f} / {pct(mt, 90):.1f} | "
          f"{pct(tw, 50):.0f} / {pct(tw, 90):.0f} |")
    A("\nBroom's `strokes[0]` ends at the fork (0.3 H), so its taper and apex columns below describe "
      "the lower trunk only.\n")
    A("\n### Thick apex and taper (trunk radius at the tip over radius at 0.05 H; taper = r(0.05 H) / r(0.7 H))\n")
    A("| style | n | tip radius px p50 / p90 | apex ratio p50 / p90 | taper p10 / p50 | taper < 2.0 |\n"
      "| --- | --- | --- | --- | --- | --- |")
    for st in styles:
        rs = [r for r in main if r["style"] == st]
        tr = [fl(r, "trunk_r_tip") for r in rs]
        ar = [fl(r, "apex_ratio") for r in rs]
        tp = [fl(r, "taper") for r in rs]
        A(f"| {st} | {len(rs)} | {pct(tr, 50):.1f} / {pct(tr, 90):.1f} | {pct(ar, 50):.2f} / "
          f"{pct(ar, 90):.2f} | {pct(tp, 10):.1f} / {pct(tp, 50):.1f} | "
          f"{sum(t_ < 2.0 for t_ in tp)}/{len(tp)} |")
    A("\n### Apex foliage (width of the topmost pad)\n")
    A("| style | n | apex pad W / crown W p50 / p90 | apex pad W / median pad W p50 / p90 |\n"
      "| --- | --- | --- | --- |")
    for st in styles:
        rs = [r for r in main if r["style"] == st]
        c1 = [fl(r, "apex_pad_w_over_crown") for r in rs]
        c2 = [fl(r, "apex_pad_w_over_median") for r in rs]
        A(f"| {st} | {len(rs)} | {pct(c1, 50):.2f} / {pct(c1, 90):.2f} | {pct(c2, 50):.2f} / {pct(c2, 90):.2f} |")
    A("\n### Inner thinning (foliage coverage of the inner core vs the outer shell, pad extents)\n")
    A("| species | n | core covered p50 | shell covered p50 | core / shell p50 |\n"
      "| --- | --- | --- | --- | --- |")
    for sp in sorted({sp for sp, _ in cs}):
        rs = [r for r in main if r["species"] == sp and r["inner_cover"] not in ("", "nan")]
        ratio = [fl(r, "inner_cover") / fl(r, "shell_cover") for r in rs if fl(r, "shell_cover") > 0]
        A(f"| {sp} | {len(rs)} | {med(rs, 'inner_cover'):.2f} | {med(rs, 'shell_cover'):.2f} | "
          f"{statistics.median(ratio):.2f} |")
    A("\n### Cascade vs stand and canvas (semi-cascade, and the same measures for every style)\n")
    A("`stand clear` = stand top row minus lowest foliage or branch point (main trunk excluded); "
      "`canvas clear` = rows between the lowest point and the canvas bottom; overlap = tree pixels "
      "at or below the stand top inside the stand's width.\n")
    A("| scope | n | stand clear px min / p10 / p50 | canvas clear px min / p50 | "
      "stand overlap > 0 | foliage inside pot rect > 0 |\n| --- | --- | --- | --- | --- | --- |")
    for label, rs in (("hankengai (pinus, juniperus)", [r for r in main if r["style"] == "hankengai"]),
                      ("all other styles", [r for r in main if r["style"] != "hankengai"])):
        sc = [fl(r, "stand_clear") for r in rs]
        cc = [fl(r, "canvas_clear") for r in rs]
        A(f"| {label} | {len(rs)} | {min(sc):.1f} / {pct(sc, 10):.1f} / {pct(sc, 50):.1f} | "
          f"{min(cc):.1f} / {pct(cc, 50):.1f} | {sum(fl(r, 'stand_overlap_px') > 0 for r in rs)} | "
          f"{sum(fl(r, 'pad_in_pot_px') > 0 for r in rs)} |")

    A("\n## Layout the tree was fitted to (median over seeds 1-30, art px at 640x360)\n")
    A("V1 sizes the pot from the crown width, so `pot W / crown W` is a V1 design range; V2 gets the pot "
      "from the caliper class before the crown exists (DEVIATIONS D2/D4). `crown W` is the width of "
      "the projected strokes and pads.\n")
    A("| species | style | design H | pot W | pot W / design H | pot W / crown W | stand W | "
      "rim_top | trunk base y |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for sp, st in cs:
        rs = [r for r in main if r["species"] == sp and r["style"] == st]
        A(f"| {sp} | {st} | {med(rs, 'design_ht'):.0f} | {med(rs, 'pot_w'):.0f} | "
          f"{statistics.median(fl(r, 'pot_w') / fl(r, 'design_ht') for r in rs):.2f} | "
          f"{statistics.median(fl(r, 'pot_w') / fl(r, 'crown_w') for r in rs):.2f} | "
          f"{med(rs, 'stand_w'):.0f} | {med(rs, 'rim_top'):.0f} | {med(rs, 'yb'):.0f} |")
    A("\nV1 range by style, all species and seeds (min / p10 / p50 / p90 / max):\n")
    A("| style | n | pot W / design H | pot W / crown W |\n| --- | --- | --- | --- |")
    for st in styles:
        rs = [r for r in main if r["style"] == st]
        a1 = [fl(r, "pot_w") / fl(r, "design_ht") for r in rs]
        a2 = [fl(r, "pot_w") / fl(r, "crown_w") for r in rs]
        f5 = lambda v: " / ".join(f"{x:.2f}" for x in (min(v), pct(v, 10), pct(v, 50), pct(v, 90), max(v)))
        A(f"| {st} | {len(rs)} | {f5(a1)} | {f5(a2)} |")
    a1 = [fl(r, "pot_w") / fl(r, "design_ht") for r in main]
    a2 = [fl(r, "pot_w") / fl(r, "crown_w") for r in main]
    A(f"| all | {len(main)} | {f5(a1)} | {f5(a2)} |")

    A("\n## structure_distance baseline (median pairwise, seeds 1-30)\n")
    A("From the IR: mean of (1 - IoU of height-normalised silhouettes built from strokes and pad "
      "extents) and the total-variation distance of the length-weighted primary-branch angle histogram "
      "(24 bins; primaries are live order-1 strokes).\n")
    A("`raw` is the spec's definition. V1 mirrors each tree left or right at random, so `raw` counts a "
      "mirrored copy of the same tree as different. `canonical` flips each tree so its silhouette mass "
      "lies on the +x side first (DEVIATIONS D8, approved) and is the variety test.\n")
    A("**Target cap.** The target is 1.5 x V1's canonical median, capped at the *ceiling*: the median "
      "canonical distance between this combo's trees and the trees of the other styles of the same "
      "species. Variety inside a style must not exceed the distance between styles, or trees stop "
      "reading as that style. If V1 is already at or above the ceiling the target is V1's own median "
      "(no regression).\n")
    sils = load_sils()
    canon = {c: [metrics.canonical(g_, h_) for g_, h_ in items] for c, items in sils.items()}
    rows_t = []
    for sp, st in cs:
        own = canon[(sp, st)]
        pairs = list(itertools.combinations(range(len(own)), 2))
        raw = [metrics.structure_distance(*sils[(sp, st)][i], *sils[(sp, st)][j]) for i, j in pairs]
        can = [metrics.structure_distance(*own[i], *own[j]) for i, j in pairs]
        cross = [metrics.structure_distance(*a_, *b_) for st2 in (s for s_sp, s in cs if s_sp == sp and s != st)
                 for a_ in own for b_ in canon[(sp, st2)]]
        w, ceil = statistics.median(can), statistics.median(cross)
        target = min(1.5 * w, max(ceil, w))
        if 1.5 * w <= ceil:
            note = "uncapped"
        elif ceil >= w:
            note = f"capped: 1.5 x {w:.3f} = {1.5 * w:.3f} exceeds the cross-style median {ceil:.3f}"
        else:
            note = (f"V1 already above the cross-style median {ceil:.3f}; target = V1's median")
        rows_t.append((sp, st, statistics.median(raw), w, ceil, 1.5 * w, target, note))
    A("| species | style | raw median | canonical median | cross-style ceiling | 1.5 x canonical | "
      "target | cap justification |\n| --- | --- | --- | --- | --- | --- | --- | --- |")
    for sp, st, rw, w, ceil, t15, tg, note in rows_t:
        A(f"| {sp} | {st} | {rw:.3f} | {w:.3f} | {ceil:.3f} | {t15:.3f} | **{tg:.3f}** | {note} |")
    n_cap = sum(1 for r in rows_t if r[7] != "uncapped")
    A(f"\n{n_cap} of {len(rows_t)} combos are capped. Median of combo medians: raw "
      f"{statistics.median(r[2] for r in rows_t):.3f}, canonical "
      f"{statistics.median(r[3] for r in rows_t):.3f}.\n")
    out = DOCS / "v1_baseline_summary.md"
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    cmds = dict(sweep=cmd_sweep, perf=cmd_perf, profile=cmd_profile, sheets=cmd_sheets,
                summary=cmd_summary)
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]]()

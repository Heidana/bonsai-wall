#!/usr/bin/env python3
"""Phase 0 baseline harness for V1 (bonsai-wall.py, imported unmodified).

Measures V1 on this machine so V2 budgets have a real reference:
  sweep    in-process: gif size, palette peak, changed px/frame, rebuild/shrink stats,
           silhouette metrics, structure_distance inputs, frame-0 PNGs for contact sheets
  perf     end-to-end CLI wall time (pinned to one core, --preview only) + determinism
  profile  in-process stage breakdown (pinned to one core)
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
import json
import math
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
CALLS: list = []


def v1():
    """Load V1 unmodified; wrap build_scene only to count grow_scene's retries."""
    global _V1
    if _V1 is None:
        spec = importlib.util.spec_from_file_location("bw_v1", V1_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        orig = m.build_scene

        def counted(seed, W, H, look, xfrac=0.5, shrink=1.0, shift=0.0):
            CALLS.append((shrink, shift))
            return orig(seed, W, H, look, xfrac, shrink, shift)

        m.build_scene = counted
        _V1 = m
    return _V1


def combos():
    m = v1()
    return [(sp, st) for sp in sorted(m.SPECIES) for st in sorted(m.SPECIES[sp]["styles"])]


def art_size(m, size):
    w, h = (int(v) for v in size.split("x"))
    s = m.pick_scale(w, h)
    return w, h, s, -(-w // s), -(-h // s)


# --------------------------------------------------------------------------
# silhouette + metrics (V1 is 2D: derived from pad sprites and the static layer)
# --------------------------------------------------------------------------
GRID_W, GRID_H = 192, 144        # covers x in [xb-H, xb+H], y in [yb-H, yb+0.5H]
ANG_BINS = 24


def tree_masks(S):
    W, H = S.W, S.H
    fol = np.zeros((H, W), bool)
    for p in S.pads_back + S.pads_front:
        a = np.asarray(p.sprites[0].getchannel("A")) > 0
        x0, y0 = p.ox, p.oy
        xs0, ys0 = max(0, x0), max(0, y0)
        xs1, ys1 = min(W, x0 + a.shape[1]), min(H, y0 + a.shape[0])
        if xs1 > xs0 and ys1 > ys0:
            fol[ys0:ys1, xs0:xs1] |= a[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0]
    wood = np.asarray(S.mid[1]) > 0
    ycut = int(S.soil_top(S.xc) - 4 * S.k)     # drop soil, moss, rock, pot, stand
    wood = wood.copy()
    wood[ycut:, :] = False
    for (x, y) in S.back_limbs:
        if 0 <= x < W and 0 <= y < H and y < ycut:
            wood[y, x] = True
    return fol, wood


def hull_area(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return 0.0

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                                   - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(p)
        return h

    lo, up = half(pts), half(reversed(pts))
    poly = lo[:-1] + up[:-1]
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def silhouette_metrics(S):
    fol, wood = tree_masks(S)
    tree = fol | wood
    ys, xs = np.nonzero(tree)
    if not len(ys):
        return None
    top, xb, yb = int(ys.min()), S.xb, S.yb
    Ht = max(1.0, yb - top)
    apex_x = float(xs[ys <= top + 2].mean())
    fy = np.nonzero(fol)[0]
    cent = (yb - float(fy.mean())) / Ht if len(fy) else float("nan")
    pts = []
    for y in range(top, int(ys.max()) + 1):
        row = np.nonzero(tree[y])[0]
        if len(row):
            pts += [(int(row[0]), y), (int(row[-1]), y)]
    ha = hull_area(pts)
    neg = (ha - float(tree.sum())) / ha if ha > 0 else float("nan")
    # height-normalised silhouette grid
    x0, x1, y0, y1 = xb - Ht, xb + Ht, yb - Ht, yb + 0.5 * Ht
    box = (round(x0), round(y0), round(x1), round(y1))     # may leave the canvas: filled with 0
    im = Image.fromarray((tree * 255).astype(np.uint8)).crop(box).resize(
        (GRID_W, GRID_H), Image.BOX)
    grid = np.asarray(im) > 127
    # pad-centre angle histogram (V1 has no explicit primaries; pads are the proxy)
    hist = np.zeros(ANG_BINS)
    for p in S.pads_back + S.pads_front:
        ang = math.atan2(p.cx - xb, yb - p.cy)
        b = min(ANG_BINS - 1, int((ang + math.pi) / math.tau * ANG_BINS))
        hist[b] += p.rx * p.rx
    hist = hist / hist.sum() if hist.sum() else hist
    return dict(
        tree_h=Ht, width_over_h=float(xs.max() - xs.min() + 1) / Ht,
        lean_deg=abs(math.degrees(math.atan2(apex_x - xb, yb - top))),
        apex_offset=(apex_x - xb) / Ht, foliage_centroid_h=cent, negative_space=neg,
        n_pads=len(S.pads_back) + len(S.pads_front)), grid, hist


# --------------------------------------------------------------------------
# sweep worker
# --------------------------------------------------------------------------
def run_one(task):
    size, sp, st, seed, save_png = task
    m = v1()
    w, h, s, cw, ch = art_size(m, size)
    look = m.choose_look(seed, "random", "auto", "studio", "auto", None, None, sp)
    look["style"] = st
    CALLS.clear()
    t0 = time.perf_counter()
    S = m.grow_scene(seed, cw, ch, look, 0.5)
    t1 = time.perf_counter()
    frames = m.render_frames(S, 10.0, 12.0)
    t2 = time.perf_counter()
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], loop=0,
                   duration=100, disposal=1, optimize=True)
    t3 = time.perf_counter()
    arr = np.stack([np.asarray(f) for f in frames])
    changed = (arr != np.roll(arr, 1, axis=0)).reshape(len(frames), -1).sum(1)
    row = dict(size=size, art_w=cw, art_h=ch, scale=s, species=sp, style=st, seed=seed,
               leaf=look["leaf"], pot=look["pot"], gif_bytes=buf.tell(),
               palette_peak=len(S.pal), n_frames=len(frames),
               changed_mean=float(changed.mean()), changed_p95=float(np.percentile(changed, 95)),
               changed_max=int(changed.max()), builds=len(CALLS),
               final_shrink=CALLS[-1][0], final_shift=CALLS[-1][1],
               margin_left=S.xmin, margin_right=cw - 1 - S.xmax, crown_top=S.crown_top,
               pot_w=S.pot_w, stand_w=S.stand_w, rim_top=S.rim_top, stand_top=S.stand_top,
               design_ht=S.Ht, xb=S.xb, yb=S.yb, xc=S.xc, caliper=S.caliper, mode=S.mode,
               t_grow=t1 - t0, t_render=t2 - t1, t_gif=t3 - t2)
    sm = silhouette_metrics(S)
    grid = hist = None
    if sm:
        met, grid, hist = sm
        row.update(met)
    if save_png:
        d = OUT / "frames"
        d.mkdir(parents=True, exist_ok=True)
        frames[0].convert("RGB").save(d / f"{sp}-{st}-{seed}.png")
    return row, (np.packbits(grid) if grid is not None else None), hist


def cmd_sweep():
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
            if packed is not None and row["size"] == SIZE_MAIN:
                key = f'{row["species"]}|{row["style"]}|{row["seed"]}'
                sils[key + "|g"] = packed
                sils[key + "|h"] = hist
            if i % 100 == 0:
                print(f"  {i}/{len(tasks)}  {time.time() - t0:.0f}s", flush=True)
    keys = list(rows[0])
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
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


def tv(a, b):
    return 0.5 * float(np.abs(a - b).sum())


def structure_distance(g1, h1, g2, h2):
    inter = np.logical_and(g1, g2).sum()
    union = np.logical_or(g1, g2).sum()
    iou = inter / union if union else 1.0
    return 0.5 * ((1 - iou) + tv(h1, h2))


def cmd_summary():
    sw = read(SWEEP_CSV)
    main = [r for r in sw if r["size"] == SIZE_MAIN]
    z = np.load(SILS)
    L = []
    A = L.append
    A("# V1 baseline (this machine)\n")
    A("Generated by `tools/baseline_v1.py summary` from `v1_sweep.csv`, `v1_perf.csv`, "
      "`v1_profile.csv`. V1 is imported unmodified; every CLI run uses `--preview`.\n")
    A(f"Sweep: {len(sw)} renders ({len(main)} at {SIZE_MAIN} = 640x360 art, "
      f"{len(sw) - len(main)} at other screen shapes), {len(combos())} species x style combos "
      f"with weight > 0.\n")

    perf = read(PERF_CSV)
    p4 = [float(r["wall_s"]) for r in perf if r["size"] == SIZE_4K]
    A("## End-to-end CLI time, 1 core (`taskset -c 0`), `--preview`\n")
    A("| size | runs | p50 s | p95 s | max s |\n| --- | --- | --- | --- | --- |")
    for sz in (SIZE_4K,) + SIZES_OTHER:
        v = [float(r["wall_s"]) for r in perf if r["size"] == sz]
        A(f"| {sz} | {len(v)} | {pct(v, 50):.2f} | {pct(v, 95):.2f} | {max(v):.2f} |")
    det = [r for r in perf if r["rep"] == "1"]
    same = sum(r["identical_to_rep0"] == "True" for r in det)
    A(f"\nDeterminism: {same}/{len(det)} repeated CLI runs produced a byte-identical GIF.\n")
    A(f"V2 budget (4K): p50 <= 4 s, p95 <= 8 s. V1 uses {pct(p4, 50):.2f} / {pct(p4, 95):.2f} s.\n")

    pr = read(PROFILE_CSV)
    A("## Stage breakdown at 4K (in-process, 1 core), mean over "
      f"{len(pr)} runs\n")
    A("| stage | mean s | p95 s |\n| --- | --- | --- |")
    for k, nm in (("grow_s", "grow_scene (incl. retries, pad sprites, bg, palette)"),
                  ("frames_s", "render_frames (120 frames)"), ("gif_s", "GIF encode"),
                  ("pngs_s", "still + theme + preview PNG"), ("total_s", "total")):
        v = [float(r[k]) for r in pr]
        A(f"| {nm} | {statistics.mean(v):.2f} | {pct(v, 95):.2f} |")

    g = [int(r["gif_bytes"]) for r in main]
    cm = [float(r["changed_mean"]) for r in main]
    cp = [float(r["changed_p95"]) for r in main]
    pk = [int(r["palette_peak"]) for r in main]
    A("\n## Output size, palette, changed pixels (16:9, 640x360 art)\n")
    A("| metric | p5 | p50 | p95 | max | V2 budget |\n| --- | --- | --- | --- | --- | --- |")
    A(f"| GIF bytes | {pct(g, 5):.0f} | {pct(g, 50):.0f} | {pct(g, 95):.0f} | {max(g)} | "
      f"<= V1 + 25% (p50 {pct(g, 50) * 1.25:.0f}, p95 {pct(g, 95) * 1.25:.0f}) |")
    A(f"| changed px / frame (mean) | {pct(cm, 5):.0f} | {pct(cm, 50):.0f} | {pct(cm, 95):.0f} | "
      f"{max(cm):.0f} | <= V1 + 25% (p50 {pct(cm, 50) * 1.25:.0f}) |")
    A(f"| changed px / frame (p95 frame) | {pct(cp, 5):.0f} | {pct(cp, 50):.0f} | "
      f"{pct(cp, 95):.0f} | {max(cp):.0f} | |")
    A(f"| palette peak | {pct(pk, 5):.0f} | {pct(pk, 50):.0f} | {pct(pk, 95):.0f} | {max(pk)} | "
      f"<= 255 |")

    A("\n## Fit retries (V1 narrows/slides the composition after building)\n")
    multi = [r for r in sw if int(r["builds"]) > 1]
    shrunk = [r for r in sw if float(r["final_shrink"]) < 0.999]
    A(f"- {len(multi)}/{len(sw)} renders needed more than one `build_scene` pass "
      f"({100 * len(multi) / len(sw):.1f}%); {len(shrunk)} ended with shrink < 1 "
      f"(V1 rescales the design to fit; V2 must not).")
    by = {}
    for r in multi:
        by.setdefault((r["species"], r["style"]), 0)
        by[(r["species"], r["style"])] += 1
    if by:
        top = sorted(by.items(), key=lambda kv: -kv[1])[:8]
        A("- Most affected combos: " + ", ".join(f"{a}/{b} x{n}" for (a, b), n in top))
    tight = [r for r in sw if min(int(r["margin_left"]), int(r["margin_right"])) < 2]
    A(f"- Renders with < 2 art px side margin after fitting: {len(tight)}.")

    A("\n## Silhouette metrics per combo (front view, V1 2D; median over seeds 1-30)\n")
    A("`lean_deg`, `apex_offset`, `foliage_centroid_h`, `negative_space`, `width/H` computed from "
      "pad sprites + static layer above the soil. Approximate: V1 keeps no skeleton "
      "(see `docs/v1_inventory.md`).\n")
    A("| species | style | n | H px | W/H | lean deg | apex off | fol. centroid | neg. space | "
      "pads | GIF KB |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for sp, st in combos():
        rs = [r for r in main if r["species"] == sp and r["style"] == st and r.get("tree_h")]

        def med(k):
            vals = [float(r[k]) for r in rs if r[k] not in ("", "nan")]
            return statistics.median(vals) if vals else float("nan")
        A(f"| {sp} | {st} | {len(rs)} | {med('tree_h'):.0f} | {med('width_over_h'):.2f} | "
          f"{med('lean_deg'):.1f} | {med('apex_offset'):+.3f} | {med('foliage_centroid_h'):.2f} | "
          f"{med('negative_space'):.2f} | {med('n_pads'):.0f} | "
          f"{med('gif_bytes') / 1024:.0f} |")

    A("\n## Layout the tree was fitted to (median over seeds 1-30, art px at 640x360)\n")
    A("V1 sizes the pot from the crown width; V2 needs this as an input (DEVIATIONS D4).\n")
    A("| species | style | design H | pot W | pot W / design H | stand W | rim_top | trunk base y |"
      "\n| --- | --- | --- | --- | --- | --- | --- | --- |")
    for sp, st in combos():
        rs = [r for r in main if r["species"] == sp and r["style"] == st]

        def med2(f):
            return statistics.median(f(r) for r in rs)
        A(f"| {sp} | {st} | {med2(lambda r: float(r['design_ht'])):.0f} | "
          f"{med2(lambda r: float(r['pot_w'])):.0f} | "
          f"{med2(lambda r: float(r['pot_w']) / float(r['design_ht'])):.2f} | "
          f"{med2(lambda r: float(r['stand_w'])):.0f} | "
          f"{med2(lambda r: float(r['rim_top'])):.0f} | {med2(lambda r: float(r['yb'])):.0f} |")

    A("\n## structure_distance baseline (median pairwise, seeds 1-30)\n")
    A("Proxy definition (V1 has no 3D skeleton): mean of (1 - IoU of height-normalised "
      "silhouettes) and total-variation distance of the area-weighted pad-centre angle "
      "histogram (24 bins).\n")
    A("`raw` is the spec's definition. V1 mirrors each tree left or right at random, so `raw` "
      "counts a mirrored copy of the same tree as different, which inflates asymmetric styles "
      "(a 1.5x target above 1.0 is unreachable). `canonical` first flips each tree so its "
      "silhouette mass lies on the +x side, then applies the same formula. "
      "DEVIATIONS D8 proposes `canonical` as the variety test.\n")
    A("| species | style | raw median | canonical median | canonical p10 | canonical p90 | "
      "1.5x canonical target |\n| --- | --- | --- | --- | --- | --- | --- |")
    allraw, allcan = [], []
    for sp, st in combos():
        gs, hs = [], []
        for sd in SEEDS_MAIN:
            k = f"{sp}|{st}|{sd}"
            if k + "|g" in z.files:
                gs.append(np.unpackbits(z[k + "|g"])[:GRID_W * GRID_H].astype(bool)
                          .reshape(GRID_H, GRID_W))
                hs.append(z[k + "|h"])
        cg, ch_ = [], []
        for g_, h_ in zip(gs, hs):
            cols = np.nonzero(g_)[1]
            if len(cols) and cols.mean() < (GRID_W - 1) / 2 - 0.5:
                g_, h_ = g_[:, ::-1], h_[::-1]
            cg.append(g_)
            ch_.append(h_)
        pairs = list(itertools.combinations(range(len(gs)), 2))
        raw = [structure_distance(gs[i], hs[i], gs[j], hs[j]) for i, j in pairs]
        can = [structure_distance(cg[i], ch_[i], cg[j], ch_[j]) for i, j in pairs]
        allraw.append(statistics.median(raw))
        allcan.append(statistics.median(can))
        A(f"| {sp} | {st} | {allraw[-1]:.3f} | {allcan[-1]:.3f} | {pct(can, 10):.3f} | "
          f"{pct(can, 90):.3f} | {1.5 * allcan[-1]:.3f} |")
    A(f"\nMedian of combo medians: raw {statistics.median(allraw):.3f} "
      f"(min {min(allraw):.3f}, max {max(allraw):.3f}); canonical {statistics.median(allcan):.3f} "
      f"(min {min(allcan):.3f}, max {max(allcan):.3f}).\n")
    out = DOCS / "v1_baseline_summary.md"
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    cmds = dict(sweep=cmd_sweep, perf=cmd_perf, profile=cmd_profile, sheets=cmd_sheets,
                summary=cmd_summary)
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]]()

# STATE: handoff file

Read this first in every session. Update it at the end of every work session and at every gate.
Last updated: Phase 1 close-out (2026-10-15), after the D29 stand-overlap log and test.

## 1. Where we are

- **Current phase:** Phase 2 (biology core) is next and **not started**. Gate 1 and Phase 1 are accepted.
- **Branch to work on:** `phase-2-biology` (created from `main` at tag `phase1`). One branch per phase, small commits, stop at every gate.
- **Tags:** `v1-baseline` and `v1.0.0` (before V2 work), `gate1` (Phase 0 merged), `phase1` (Phase 1 merged).
- **Next gate:** Gate 2, after Phase 2. Do not start Phase 3 without approval.
- **Remote:** nothing has been pushed to GitHub. The permission layer denied `git push`; the user pushes, or allows it when asked.
- **Source of truth:** `docs/BONSAI_V2_SPEC.md` for how trees are generated; V1 behaviour (`bonsai-wall.py`) for everything else; **`docs/DEVIATIONS.md` takes precedence over the spec on any conflict.** Every newly approved deviation updates the spec in the same commit as `DEVIATIONS.md`.
- **Rules:** `CLAUDE.md` (biology never imports style or maintainer code; V1 stays runnable and byte-identical; Pillow + numpy only; one zipapp; fish in all user-facing commands; measure, don't assert; never touch the wallpaper, `--preview` only, never call awww; the user runs installs, never `sudo` or `pacman`).

## 2. Repository map

```
bonsai-wall.py            V1 reference script. UNTOUCHED (git blob 93dc777d24f2b3b822a5c4d38e5aa5e675dbdf11).
                          Goldens and the timing check compare against it. A test fails if it changes.
build.py                  builds dist/bonsai-wall (zipapp, reproducible). dist/ is gitignored.
pytest.ini                pythonpath = src tests
src/bonsai_wall/
  cli.py                  V1 CLI + --engine v1|v2 (v2 exits "not implemented yet")
  look.py                 palettes, SPECIES, HARMONY, choose_look (V1, verbatim)
  util.py                 helpers (hx, tint, dith, h2, spline, ...)
  layout.py               Layout (V1 output) and DesignSpace.from_layout
  ir.py                   TreeScene, Stroke, Pad, Flute, Leaf, validate()
  rng.py                  seed streams, hash_u01 (+ numpy variant). Only module that creates randomness in V2
  metrics.py              IR metrics shared by harness, tests and later the maintainer
  pipeline.py             grow_scene (V1): build -> prepare -> retry loop -> finish
  animate.py, output.py   V1 frames/particles; V1 monitors, scaling, awww glue
  render/                 limbs.py (draw_limb), pads.py (6 pad renderers), static.py (prepare/finish), backdrop.py
  v1/builder.py           V1 design-first builder, emits TreeScene
  v2/, debug/             empty packages (Phase 2 fills v2/)
tests/                    goldens, boundaries, IR, rng, layout, extensions, metrics, cli/build (268 tests, ~49 s)
tools/                    baseline_v1.py (V1 harness), compare_timing.py, make_goldens.py
docs/                     spec, DEVIATIONS, STATE (this), TUNING, DESIGN_SPACE, DEV, v1_inventory, baseline/
out/                      gitignored scratch for sheets and logs (out/baseline/sheet-v1-<species>.png)
```

Renderer input contract (what a tree engine must put in `TreeScene` so the unchanged V1 renderer works):
`strokes` (order matters; `meta["species"]` selects the bark ramp), `pads` (V1 ellipse parameters; `ramp` and
`ramp2` are indices below `meta["n_ramps"]`; `kind` in cloud, fine, scale, needle, larch, spray; `bake_seed`),
`flutes` (empty unless redwood), `trunk_bases` as (x, radius), `root_rules` with `style long_side shrink rough seed`,
`wind_dir` (+1 or -1), `layout` (a `Layout`), `meta` with `engine species style caliper mode n_ramps tip`.
`v1_rng` is V1 only; V2 passes `None` and the renderer then needs a stream from `rng.py` (**not wired yet**: `prepare()` currently
reads `tree.v1_rng`; Phase 2 must make it fall back to `rng.stream(seed, "render")`-derived draws or a `random.Random` seeded from the render stream, without changing V1).
There is no `bounds` field: the rendered `Scene` reports `xmin xmax crown_top` after baking (D14).

## 3. Results so far

### Phase 0 (V1 baseline, this machine; `docs/baseline/v1_baseline_summary.md`)

| Item | V1 |
| --- | --- |
| End-to-end 4K, 1 core | p50 1.40 s, p95 1.80 s (144 runs) |
| Stage means at 4K | GIF encode 0.86 s, `grow_scene` 0.31 s, PNGs 0.13 s, frames 0.05 s, total 1.36 s |
| GIF bytes (640x360 art) | p50 167 KB, p95 228 KB, max 270 KB |
| Changed px per frame (mean) | p50 129, p95 609, max 1058 |
| Palette peak | p50 103, p95 128, max 135 (limit 255) |
| Determinism | 72 of 72 repeated CLI runs byte-identical |
| Fit retries | 27 of 1404 renders (1.9%); 12 ended shrunk; 3 under 2 px side margin |
| Combos | 36 species x style combos with weight > 0 |
| Tree-making budget for V2 (D9) | about 2.9 s p50 and 6.8 s p95 (4 s and 8 s minus V1's output stages) |

### Phase 1 (refactor)

- Package, `TreeScene` IR, V1 builder behind it, zipapp, goldens, boundary tests, metrics, DesignSpace.
- Goldens: 96 of 96 frame-for-frame identical (20 seeds x 3 shapes + all 36 combos), also byte-identical GIF, still, theme and preview PNG through the installed zipapp.
- Timing, zipapp vs original script (4K, 1 core, interleaved): mean +2.0%, p50 +2.6%, p95 +0.8% (budget +-10%). `docs/baseline/p1_timing.csv`.
- Zipapp is 46 KB and the build is reproducible.
- V1's named misses re-measured from the IR: `docs/baseline/v1_named_misses.md`.
- `stand_overlap_px` mirrors the renderer's pot-hiding rule (D29): non-cascade overlaps went from 52 of 1020 to 2 of 1020 (flare discs hidden behind shallow pots). Proof test in `tests/test_metrics.py`; goldens unchanged. The V2 bounds validator (D28) must apply the same visibility rule.
- Variety baseline: canonical `structure_distance` per combo with capped 1.5x targets (29 of 36 capped; targets 1.06x to 1.5x V1, median 1.27x), in the baseline summary.
- V1 pot width and design height by style and caliper, and pot W / crown W ranges (V1 overall p10 0.50, p50 0.75, p90 1.01): baseline summary, Layout section.

## 4. Decisions

All in `docs/DEVIATIONS.md` (D1-D29), statuses recorded there. The ones that shape Phase 2:

- **D1** pine: `--species pinus` stays; leaf `kuromatsu` and `old_pine` use the black-pine profile, `goyomatsu` uses white pine (Phase 4). Suggested Phase 2 behaviour for `--engine v2 --leaf goyomatsu`: exit with a clear "white pine arrives in Phase 4" message.
- **D2/D4** layout runs before the tree; stand and deck are sized for the caliper class's maximum pot width; only pot width changes after simulation. `docs/DESIGN_SPACE.md` explains how design height is derived before a crown exists.
- **D3** pad IR keeps V1's ellipse parameters; the adapter fits `cx cy rx ryt ryb shear` to leaf clusters. Whether to build a mask renderer is a **Gate 2 decision**.
- **D5/D6** front-limb layer (`layer="over"`) and per-point shari band exist and are tested; empty on the V1 path.
- **D7/D28** never rescale; V2 needs a bounds validator over strokes and pads (build in Phase 2).
- **D8/D20/D27** variety: canonical metric, capped targets kept as defined; Gate 2 informational (plus within-style spread vs V1), Gate 3 enforced counting only seeds that pass the style bands, plus a cross-species distinctness check.
- **D10** `--season` table; winter bare for all deciduous species; larix summer falls back to `fresh`.
- **D11** Python 3.10 floor; numpy is a runtime dependency.
- **D17** the V2 run line adds engine, origin, simulated years, care profile (`none` until the maintainer exists) and action count.
- **D29** the stand-overlap metric ignores limb pixels the pot hides (also applies to the V2 bounds validator, D28).
- **D23-D26** windswept bands use leeward share and 60 degree primary window; corkscrew cap on `bend_amp_over_r`; `apex_pad_ratio` reported at Gate 2; no inner-thinning claim before an `interior_light` metric exists.

## 5. Open items

1. **Pad rendering (D3):** ellipse fit versus a mask-driven renderer. Decide at Gate 2 from the free-growth sheets.
2. **`interior_light` metric (D26):** build in Phase 2 from the light grid (core vs shell mean exposure Q).
3. **Band values set from the first V2 sheets:** corkscrew cap (D24), `apex_pad_ratio` band (D25).
4. **Renderer RNG for V2:** wire `prepare()` so V2 does not need `v1_rng` (see section 2). Also decide how the render and anim streams reach pad baking and particles.
5. **Layout for free growth:** no maintainer and no style exist in Phase 2. Suggested default: layout from the moyogi pot rules, medium caliper class, height band 0.30-0.60 of H, front azimuth 0, nursery or field origin. Record the choice in `DEVIATIONS.md` if it departs from this.
6. **Rounded larch forest metric:** none yet; define a conical-crown metric when forest styles arrive (Phase 4, enforced at Gate 3).
7. **README (D13):** references `screenshots/demo.gif`, `screenshots/gallery.png` and `LICENSE`, which are missing; the AUR package needs numpy and a new install path in Phase 5.
8. **GitHub:** nothing pushed. Ask the user.

## 6. Phase 2 plan (biology core)

Scope (spec, Implementation phases, P2): arena, rng, light, allocation, buds, shoots, wood, phenology, shedding; species **acer, zelkova and pinus with the black-pine profile** (leaf keys `kuromatsu` and `old_pine`; white pine in Phase 4); **nursery and field origins**; adapter; **no maintainer**. Also: the V2 run-line fields (D17) and the bounds validator (D28). Read before starting: spec sections Tree data model, Simulation timeline, Biology engine, Species profiles, Determinism, Validation; `docs/DEVIATIONS.md`; `docs/DESIGN_SPACE.md`; `docs/v1_inventory.md` section 12 (the seam); `docs/baseline/v1_named_misses.md`.

Ordered steps:

1. **Orient.** `git checkout phase-2-biology`, run the tests (expect 268 pass), skim the spec sections above. Create `docs/TUNING.md` entries only when a parameter changes (log each with its reason).
2. **Arena and read-only view.** `v2/arena.py`: `TreeArena` struct-of-arrays (spec, Tree data model) with stable ids, capacity doubling, `ReadOnlyTree` (numpy views with `writeable = False`, CSR children index). Tests: parent id < id, writes through the view raise.
3. **Species profiles.** `v2/species/`: `SpeciesProfile`, archetypes (broadleaf deciduous, pine), profiles for acer, zelkova, black pine. Start from the spec's numbers; the spec says they are tuning starting points.
4. **Origins and world.** `v2/environment.py` (nursery, field presets), `v2/world.py` (calendar loop from the spec's Annual cycle, streams from `rng.py`, per-entity draws through `hash_u01`).
5. **Biology, minimum first.** `v2/biology/`: `light`, `allocation`, `buds`, `shoots`, `wood`, `phenology`, `shedding`, in that order, each with unit tests. Biology imports only arena, species, environment and rng (the boundary test enforces it; extend `tests/test_boundaries.py` with real modules).
6. **Adapter and layout.** `v2/adapter.py`: projection at a fixed front, axes to strokes (centripetal Catmull-Rom, per-point radius), leaves to ellipse pads (fit `cx cy rx ryt ryb shear`), `trunk_bases`, `root_rules`, `wind_dir`, `meta` as in the contract above. A V2 layout stage that runs first (D4) and builds the `DesignSpace`. The **bounds validator** over strokes and pads (D28). Wire `--engine v2`, `--years`, `--dump DIR` (state, action log, growth strip PNG) and the new run-line fields.
7. **Stop-and-look checkpoint (mandatory).** As soon as **one species grows without crashing**, render a **growth strip at years 1, 3, 5, 10 and 20 before tuning any constant**. Look at it. Do not tune blind. Put it under `out/p2/` and note what you see in your working notes.
8. **Tune with evidence.** Change parameters only against the sheets and the metrics, one reason per change, each logged in `docs/TUNING.md` (date, phase, parameter, from, to, reason).
9. **Other two species.** Zelkova, then black pine (preformed candles, whorls, needles kept 2-3 years, no budding on bare wood).
10. **Invariants and determinism tests (200 seeds).** Spec Validation table: parent id < id; nothing live under dead wood; no foliage on dead wood; `leonardo` <= 1 + eps; no new buds on bare pine wood; turns <= kink limit; no geometry inside pot or stand; bounds inside the canvas. Determinism: same args twice gives identical GIF bytes; changing only look args gives an identical arena hash. Randomness only through `rng.py`.
11. **Measure.** 30 simulated years <= 2 s per tree (with the D9 breakdown: simulation, adapter, pad baking, GIF), end-to-end 4K, GIF size, changed pixels per frame, palette peak, `apex_pad_ratio`, `interior_light`, informational variety (canonical `structure_distance`, within-style spread vs V1).
12. **Sheets and self-check.** Free-growth contact sheet per species (6 seeds) and growth strips for each species. Self-check them (section 7) before reporting.
13. **Gate 2 report, then stop.** Do not start Phase 3.

Exit criteria (spec P2 plus the D-items): invariants pass; 30 simulated years <= 2 s; free-growth contact sheets and growth strips exist; V2 run-line fields printed; bounds validator in place; goldens still identical on the V1 path (run the whole suite); `apex_pad_ratio` and informational variety reported.

## 7. Gate 2 report contents and self-checks

Report (max 5 open questions): what was built; measured numbers vs budgets; contact-sheet and growth-strip paths; deviations from the spec with reasons (and the spec updated in the same commit as `DEVIATIONS.md`); open questions.

Must include: free-growth contact sheets per species; growth strips; invariant results (counts, seeds); timing vs the Phase 2 budget (30 simulated years <= 2 s, with the D9 breakdown); `apex_pad_ratio` per species (V1 reference 0.90-1.02 p50); informational variety with within-style spread vs V1; any new deviations; the D3 pad-renderer recommendation.

**Self-check each sheet before reporting.** Gate 2 asks whether free-grown trees look like real young trees of each species. Check:

- smooth taper, no width jumps;
- a clear leader with a fan of laterals;
- visible species habit: opposite pairs on maple, whorls on pine, zigzag twigs on zelkova;
- lower branches shaded out and shed over time;
- no spiral trunks and no rotational symmetry.

If a sheet fails a check, say so in the report instead of tuning silently past it.

## 8. Budgets (spec, Cost and Hard constraints)

| Budget | Limit |
| --- | --- |
| End-to-end at 4K, 1 core | p50 <= 4 s, p95 <= 8 s (V1: 1.40 / 1.80) |
| Phase 2 growth | 30 simulated years <= 2 s |
| GIF size and changed px per frame | <= V1 + 25% (V1 GIF p50 167 KB, p95 228 KB; changed px mean p50 129) |
| Palette | <= 255 (V1 max 135) |
| Determinism | same seed + engine version + args gives a byte-identical GIF |
| V1 path | goldens identical, timing within +-10% |

## 9. How to run things

Commands for tests, harness, build and install are in `docs/DEV.md` (fish syntax). Quick reference:

```fish
python -m pytest -q                       # all tests, about 48 s
python build.py                           # dist/bonsai-wall
python tools/baseline_v1.py sweep         # 1404 renders, about 4 min on 14 workers
python tools/baseline_v1.py summary       # rewrites docs/baseline/v1_baseline_summary.md
python tools/compare_timing.py            # zipapp vs untouched script, needs dist/ built
```

Environment: Python 3.14.8, Pillow 12.3.0, numpy 2.5.4, 16 cores, pytest 9.1.1 (no xdist). The user's shell is fish.

## 10. Practical notes for the next session

- Claude Code's Bash tool is not fish: write your own commands in POSIX syntax; keep everything you write into docs and messages fish-compatible (no heredocs, no `export VAR=value`).
- Scratch files go in the session scratchpad or `out/` (gitignored); never `/tmp` directly.
- Python 3.14 uses the `forkserver` start method for multiprocessing: worker functions must be importable and scripts need `if __name__ == "__main__"`.
- A background `pkill` pattern once killed more than intended; prefer targeted PIDs.
- The permission classifier occasionally returns "no verdict": retry the same command once. `git push` is denied by the permission layer; leave it to the user.
- Commits end with the attribution line given in the session's system reminder (currently `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`).
- Rendering for review: `--preview DIR` only (or in-process through `pipeline` and `animate`), never `awww`.

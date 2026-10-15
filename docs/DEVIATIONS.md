# Deviations from `docs/BONSAI_V2_SPEC.md`

Running log. Each entry: what the spec says, what V1 or the measurements show, what is proposed.
Status is `proposed` until the user approves at a gate. Numbers come from `docs/baseline/v1_baseline_summary.md`.

## Raised at Gate 1 (Phase 0)

| # | Topic | Spec says | Finding | Proposal | Status |
| --- | --- | --- | --- | --- | --- |
| D1 | Pine species | Separate profiles for Japanese black pine and white pine | V1 has one species `pinus`; black vs white is only the leaf key: `kuromatsu` (48), `goyomatsu` (34), `old_pine` (18) | Keep `--species pinus`. Profile from leaf: `kuromatsu` and `old_pine` -> black pine, `goyomatsu` -> white pine. The CLI and weights stay as in V1 | proposed (open question 1) |
| D2 | Pot width | "Pot width from trunk caliper class" is a V1 behaviour to keep | V1 derives pot width from the crown width (`2 * Wh`) times a style factor; caliper sets only the trunk base radius | Treat as new design: caliper class becomes the width driver in V2 (spec intent). Target distribution = V1's measured `pot W / design H` per style (baseline summary, Layout table) | proposed |
| D3 | `Pad` in the IR | `Pad` carries a coverage mask | V1's six pad renderers take an ellipse description plus shape parameters and generate their own pixels; none takes a mask | IR `Pad` keeps V1's parameters (see inventory section 12). The V2 adapter fits `cx cy rx ryt ryb shear` to leaf clusters. A mask-driven renderer is a separate, later decision | proposed (decide at Gate 2) |
| D4 | Layout before tree | `DesignSpace` comes from V1's layout before simulation | In V1 the layout is an output of the tree plan (pot and stand are sized from the crown). V2 cannot do that, because the maintainer prunes to a fixed space | New layout stage runs first: reuses V1's stand, deck, pot height and mound rules; pot style and a provisional width come from style and caliper class; the final width is set after simulation from the measured trunk base. Only pot width may change after simulation, so rim, stand and deck stay fixed | proposed (open question 2) |
| D5 | Branches in front of foliage | Strokes and pads interleaved by depth | V1 draws background(+back limbs) -> back pads -> static mid (front limbs, pot) -> front pads. A limb can never draw over a front pad | Add one static layer after front pads for front limbs that cross foliage. V1 leaves it empty, so goldens are unaffected | proposed (open question 3) |
| D6 | Shari in the renderer | "Renderer unchanged; shari bands come from the sim" | `draw_limb` takes one scalar `shari_frac` with a sine-wobbling centre, only for `r >= 2.8`; it cannot take a per-point band | Add an optional per-point band input to `draw_limb`; the existing path is untouched for V1 | proposed (open question 3) |
| D7 | "Never rescaled" | Tree grown to fit, never rescaled | V1 rescales in `grow_scene` (shrink <= 0.58 per step, slides, up to 8 builds). Measured: 27/1404 renders (1.9%) needed a retry, 12 ended shrunk, 3 ended with < 2 px side margin | The retry loop stays inside the V1 builder only. V2 asserts the bounds and relies on the show-prep session | proposed |
| D8 | `structure_distance` | Mean of (1 - IoU) and histogram distance of primary azimuths and elevations; V2 >= 1.5 x V1 | (a) V1 is 2D: no azimuths and no kept skeleton, so the histogram uses pad-centre angles instead. (b) V1 mirrors each tree at random; the raw metric calls a mirrored copy different. Raw windswept medians are 0.96 and a 1.5 x target would exceed the metric's maximum of 1.0 | Use the canonical variant (flip so the mass is on +x) for the variety test, for both engines. Baseline: median of combo medians 0.395 (raw 0.432); per-combo 1.5 x targets are in the summary. Re-measure V1 from the IR strokes in P1 and add the true primary histograms for V2 | proposed |
| D9 | Time budget | End-to-end p50 <= 4 s, p95 <= 8 s at 4K, one core | V1: p50 1.40 s, p95 1.80 s. Stage mean at 4K: GIF encode 0.86 s, `grow_scene` 0.31 s, PNGs 0.13 s, frames 0.05 s. The output stages (everything but `grow_scene`) take about 1.1 s at p50 | Arithmetic from those numbers: tree making (simulation + maintainer + adapter + pad baking) may use about 2.9 s at p50 and 6.8 s at p95. Spec P2's "30 simulated years <= 2 s" leaves about 0.9 s at p50 for maintainer + adapter + baking over a 15-60 year run. Tracked in every gate report | informational |
| D10 | Season | `--season` restricts `choose_look` to a season's palettes | V1 has no season variable; the leaf key implies a stage | Add a leaf -> season table (below), and a `season` argument to `choose_look` whose default path draws exactly as before | proposed |
| D11 | Dependencies and Python | Pillow + numpy; floor may rise to 3.10 | V1 needs only Pillow and `from __future__ import annotations`. This machine: Python 3.14.8, Pillow 12.3.0, numpy 2.5.4 | Floor 3.10. numpy becomes a runtime dependency: README and any package metadata must list `python-numpy`. The AUR package will need its dependency and install path updated in P5 | proposed |
| D12 | RNG and `--style` | Named streams, hash-RNG per entity | In V1, forcing `--style X` skips one draw, so the tree differs from the random run that picked X | Not fixable in V1 (seeds must keep reproducing). V2 style choice draws from its own stream so forcing a style does not reshuffle the tree | informational |
| D13 | Repository files | n/a | README references `screenshots/demo.gif`, `screenshots/gallery.png`, `LICENSE`; none are in the repo | Out of scope for V2; flagged for the P5 README work | informational |

### D10 proposal: leaf key -> render season

| Species | spring | summer | autumn |
| --- | --- | --- | --- |
| acer | chartreuse, deshojo | green, red, crimson, burgundy | orange, yellow, autumn |
| zelkova | chartreuse | zelkova_green | elm_amber, elm_bronze, autumn |
| metasequoia | fresh | summer | turning, rust |
| larix | fresh | (none) | gold_tips, larch_gold, rust |
| pinus, juniperus | any season, same look | | |

Winter (new `--season winter`, deciduous trees leafless) has no V1 leaf key; conifers use `winter_bronze` for juniper and their normal ramps otherwise.

## Open questions for Gate 1

See the Gate 1 report; they reference D1, D2/D4, D5/D6, D9 and D10.

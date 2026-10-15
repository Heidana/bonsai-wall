# DesignSpace: how the height is derived before any crown exists

Answers the Gate 1 request ("state how DesignSpace height is derived before any crown exists").
Code: `src/bonsai_wall/layout.py` (`Layout`, `DesignSpace.from_layout`). Test:
`tests/test_layout.py::test_design_space_depends_only_on_layout_rows`.

## What V1 does today

V1 never has a design space; it draws the crown first and sizes the pot from it:

```
Ht      = hfrac * H                      # hfrac drawn per style, a band below
Wh      = wr * Ht                        # half crown width, from the same style band
pot_w   = 2 * Wh * (style factor)        # the pot follows the crown
yb      = soil_top(xb) + 2k              # trunk base row, from the pot rim and mound
Ht      = min(Ht, yb - 0.07 * H)         # only the height is clipped to the free room
```

## What V2 does

Everything the design space needs is known before the first simulated year:

1. **Canvas.** `W`, `H`, `k = H / 360` come from the monitor and `pick_scale`; `--x` fixes the horizontal target.
2. **Deck and stand rows depend on `H` only.** `deck_y = 0.80 H`, `stand_bot = 0.925 H`, stand slab and leg thickness are fixed multiples of `k`.
3. **Pot rows depend on the style only.** Pot height and mound are drawn from the style's ranges (V1 values), so `rim_top`, `pot_bot` and `stand_top` are fixed before any crown exists.
4. **Pot width and stand width use the caliper class's maximum** (Gate 1 amendment to D2/D4). The caliper class is sampled once at layout. The stand is sized for the maximum pot width of that class, so after simulation only the pot width changes (within the class, from the measured trunk base); rim, stand and deck never move.
5. **Trunk base row** `yb = soil_top(xb) + 2k` follows from `rim_top` and the mound, so it is fixed too.

The design height is then pure geometry of rows 2, 3 and 5:

```
free_height = yb - 0.07 H                       # room between the trunk base and the top margin
target band = (lo, hi) * H, clipped to free_height   # (lo, hi) = the style's height band
```

This is V1's `Ht = min(hfrac * H, yb - 0.07 H)` with `hfrac` replaced by the style's band, so the maintainer
gets a target range instead of one drawn number. Nothing in it reads a crown; `DesignSpace.from_layout`
takes the layout and the band and nothing else.

Other fields: `left`/`right` = 4% / 96% of `W` (V1's side margins), `top_y = 0.07 H`, and `fall_floor = stand_top - 1`
(the lowest row a cascade may reach; V1 never checked this, V2 does).

## Style height bands taken from V1 (fractions of H)

| style | band | note |
| --- | --- | --- |
| chokkan | 0.48 - 0.60 | 0.54 - 0.66 for spray foliage (dawn redwood) |
| moyogi | 0.42 - 0.50 | |
| slant | 0.38 - 0.46 | |
| fukinagashi | 0.36 - 0.45 | |
| hankengai | 0.30 - 0.38 | cascade reach adds 0.45 Ht sideways |
| bunjin | 0.54 - 0.64 | |
| broom | 0.40 - 0.48 | |
| twin | 0.40 - 0.49 | |
| clump | 0.42 - 0.50 | |
| forest | 0.42 - 0.52 | 0.54 - 0.66 for spray foliage |

The measured V1 values (design height, pot width, pot W / design H, pot W / crown W, by style and by caliper class)
are in `docs/baseline/v1_baseline_summary.md`.

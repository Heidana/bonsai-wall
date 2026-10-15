# Bonsai Wallpaper V2 — Organic Growth Engine: Spec & Agent Prompt

Oct 15, 2026 · @Gergő

## How to use this doc

> **Precedence.** `docs/DEVIATIONS.md` takes precedence over this spec wherever the two conflict. Every newly approved deviation updates this spec in the same commit as `DEVIATIONS.md`, so the two do not drift. Each edit below carries its deviation id (D1, D2, ...).

Export this doc as Markdown and commit it to the V1 repo as `docs/BONSAI_V2_SPEC.md`; the agent treats it as the source of truth. Paste the kickoff prompt (next section) as the agent's first message.

The agent works in phases and stops at three review gates: V1 inventory + plan, first free-growth contact sheet, and style/species parity. Numbers in this spec are tuning starting points, not botanical measurements; the agent may change them but must log every change with its reason in `docs/TUNING.md`.

## Agent kickoff prompt

Paste this as the first message. It points the agent at the spec and stops it at Gate 1 before any engine code exists.

```text
You are implementing V2 of bonsai-wall in this repository. Read docs/BONSAI_V2_SPEC.md in full, then read bonsai-wall.py in full. The spec is the source of truth for how the tree is generated. V1's observable behaviour is the source of truth for everything else: CLI, colours, pots, stands, backdrops, animation, output files and the awww handoff.

Goal: replace V1's design-first tree builder (crown envelope -> foliage clusters -> skeleton fitted to them) with a growth-first simulation. A tree grows from a seedling under species biology (light competition, resource allocation, apical control, bud fates, tropisms, secondary thickening, branch shedding). A maintainer agent shapes it over simulated years using only real horticultural actions (cut, cut back, pinch, wire, defoliate, jin/shari, leader selection, sacrifice branches). Style comes from the origin environment plus the maintainer's design intent, never from drawing shapes directly.

Non-negotiable rules:
1. Biology code never imports style or maintainer code. The maintainer reads the tree through a read-only view and changes it only through the action API. It never moves nodes or adds branches.
2. V1 stays runnable via --engine v1 and its seeds keep reproducing until I approve removal.
3. Dependencies: Pillow + numpy only. Same seed + same engine version = identical output. All randomness flows from the seed through the named streams in spec section 'Determinism'.
4. Ship as a single executable file again (zipapp), installable with the same install -Dm755 command as V1.
5. My shell is fish. Every command in docs, README or messages to me must be fish-compatible. I run installs myself.
6. Measure, don't assert. Every claim about speed, file size, palette count, variety or style correctness comes from the harness, with numbers.

Process: work through the phases in the spec's 'Implementation phases' table, in order. At each GATE, stop and report: what was built, measured numbers vs budgets, contact-sheet paths, deviations from the spec with reasons, and open questions (max 5). Log every parameter change with its reason in docs/TUNING.md. Do not start the next phase without my approval.

Start with Phase 0 now and stop at Gate 1. Do not write engine code before Gate 1.
```

## Goals, non-goals, constraints

V2 changes how the tree is made, not what the wallpaper is: every V1 feature survives, and only the tree's structure now comes from simulated growth and care.

| Goal | How it is measured |
| --- | --- |
| Organic structure: taper, branch hierarchy, ramification, inner thinning and droop emerge from simulation, not templates | Realism metrics (Validation section) inside their bands for ≥ 90% of seeds |
| Real seed-to-seed variety, the main complaint about V1 | Median pairwise mirror-canonical structure distance per species × style ≥ 1.5 × V1's measured baseline, capped per combo at the cross-style ceiling (Validation; D8) |
| Every V1 architecture reads as itself, including V1's known misses: windswept reading as slanting, corkscrew literati trunks, rounded larch forests, cascades hitting the stand, no inner thinning, thick apex | Style acceptance bands, ≥ 90% of 50 seeds per combo |
| Full V1 parity | Parity table (next section) all green at Gate 3 |
| V1-class cost | End-to-end p50 ≤ 4 s, p95 ≤ 8 s at 3840×2160 on one core; GIF size and changed pixels per frame ≤ V1 + 25%; palette ≤ 255 colours |

Non-goals: botanical detail that cannot show at \~360 art rows; root-system simulation (nebari stays procedural, driven by trunk base and age); machine learning; GPU; showing growth inside the wallpaper loop (a time-lapse strip is a debug export only); a physics engine.

| Hard constraint | Rule |
| --- | --- |
| Separation | `biology` knows species and environment, never style. `maintainer` knows style and acts only through `actions`. Enforced by an import-boundary test and read-only arrays. |
| Dependencies | Pillow + numpy at runtime, nothing else. Python floor 3.10 (V1 was 3.8). numpy is a new runtime dependency and must be listed in the README and packaging (D11). |
| Determinism | Same seed + engine version + args → byte-identical GIF on the same machine. |
| Distribution | Single executable built with zipapp; same `install -Dm755` command as V1. |
| V1 retained | `--engine v1` reproduces V1 seeds until removal is approved. |
| Pixel integrity | The tree is grown to fit the layout in art-pixel units and is never rescaled after simulation. |
| Shell | Every documented command is fish-compatible. |

## V1 parity and the refactor seam

V2 replaces exactly one responsibility, building tree geometry inside `grow_scene`, and reuses everything downstream. Phase 1 makes that seam explicit and locks V1 with golden images before any new engine code exists.

V1 today: `choose_look()` (colours, own RNG stream) → `grow_scene(seed, w, h, look)` (style, crown envelope, foliage clusters, skeleton grown toward them, girth from carried foliage) → `render_frames()` → GIF → awww. The table reflects earlier sessions; Phase 0 verifies every row against the code and adds anything missing.

| Area | V1 behaviour (verify in Phase 0) | V2 requirement |
| --- | --- | --- |
| Species | Japanese maple, Japanese black and white pine (V1 has one `pinus` species; the profile follows the leaf key, see Species profiles; D1), Shimpaku juniper, Japanese zelkova, dawn redwood, Japanese larch | One biology profile each (Species section); V1 species weights kept |
| Architectures | Chokkan, moyogi, slanting, fukinagashi, hankengai, bunjin, broom, twin trunk, clump, forest; species × style weight table | Each = origin + maintainer program + intent bands (Style section); weight table kept |
| Colour | Leaf ramps per species and season, falling-leaf colours, `TIPS` tip colouring, `HARMONY` → backdrop, pot glaze, stand; unglazed pots for conifers \~85% | `choose_look()` unchanged, still on its own stream. Tip turning and leaf flips read sim data (exposure, age, outer/upper rank) instead of random masks |
| Backdrops | Studio gradient with dark corners, radial glow, contact shadow, ordered dithering; `--bg scene`; `--theme`; `--tone` (mostly dark) | Unchanged; glow centred on the measured crown |
| Pot, stand, ground | Pots: rect, oval, drum, flared and a rock slab; three stand styles (table, scroll, jiita); pot width follows the crown width in V1, not the caliper class; surface roots, moss, soil, stone | The layout stage runs before the tree (`DesignSpace`). Caliper class drives pot width; stand and deck are sized for the class's maximum pot width, so only the pot width changes after simulation, from the measured trunk base within the class (D2, D4) |
| Trunk detail | Species bark, buttressed redwood base, bleached jin and shari | Renderer unchanged; deadwood, shari bands and bark keys come from the sim |
| Animation | 12 s seamless loop at 10 fps; gusts travel across the crown, pads sway 1–2 art px, leaves flip pale; 3–4 falling leaves or needle slivers land on soil, stand or deck; dust motes; `--fps`, `--static` | Unchanged; falling leaves spawn from real leaf positions; optional skeleton-driven sway amplitude within the pixel budget |
| Output | \~360 art rows, integer nearest-neighbour scale per monitor; exact-index palette (V1 peak 136 of 255); transparent frame deltas; 150–250 KB GIF; still PNG for desktop theming; `last_seed` cache; monitors via `hyprctl`, fallback `awww query`; portrait screens | Unchanged |
| CLI | `--seed --species --style --leaf --tone --bg --backdrop --pot --theme --fps --static --x --pixel --size --preview --delay` | All kept with identical semantics; new flags in the Determinism section |
| Run line | Prints seed, species, style, leaf, pot, time | Adds engine, origin, simulated years, care profile, action count |

### The seam: `TreeScene` IR

Phase 1 splits V1 into look → layout → tree builder → `TreeScene` → renderer. The renderer may read only `TreeScene`, the look and the layout. The shape below is the adjusted IR implemented in `src/bonsai_wall/ir.py`: V1's pad renderers take ellipse parameters, not masks, and V1's limb rasteriser takes the extra parameters listed (D3, D14, D15).

```python
@dataclass(frozen=True)
class Stroke:                   # one draw_limb call
    pts: tuple                  # art px, y down
    radius: tuple               # per point
    seed: int                   # per-stroke jitter seed
    order: int                  # 0 trunk/leader, 1 primary (or jin), 2 secondary, 3 twig
    wood: str = "live"          # "live" | "jin" | "dead"
    bark: str = ""              # species key
    layer: str = "front"        # "back" (painted into the backdrop) | "front" | "over" (front limbs after the front pads)
    streaks: bool = True
    rough: float = 0.0
    shari_frac: float = 0.0     # V1: dead-bark band width fraction, 1.0 = jin
    shari: tuple | None = None  # V2: per-point (lo, hi) live-bark offsets of the dead band
    depth: tuple = ()           # V2: view depth per point; empty for V1

@dataclass(frozen=True)
class Leaf:
    x: float; y: float; depth: float
    exposure: float             # light Q from the sim, 0..1
    age: int                    # years (evergreens)
    rank: float                 # outer/upper rank 0..1, drives tip turning

@dataclass(frozen=True)
class Pad:                      # one foliage cluster, in V1's renderer parameters
    kind: str                   # cloud fine scale needle larch spray
    cx: float; cy: float; rx: float; ryt: float; ryb: float
    bias: float; grad: float; shear: float; droop: float
    back: bool
    ramp: int; ramp2: int; mix: float       # indices into the look's ramp list
    tip_start: float
    amp: float; lag: float                  # sway
    bake_seed: int
    leaves: tuple = ()          # V2: per-leaf exposure, age, rank
    mask: bytes | None = None   # V2, optional; ignored until a mask renderer is approved

@dataclass(frozen=True)
class Flute:                    # redwood trunk fluting, applied after `after` strokes were drawn
    layer: str; x0: float; r0: float; phase: float; y_start: float; after: int

@dataclass(frozen=True)
class TreeScene:
    seed: int
    strokes: tuple              # order preserved: V1 ties are resolved by draw order
    pads: tuple                 # builder order preserved: sprites are baked in this order
    flutes: tuple
    trunk_bases: tuple          # (x, base radius) per trunk
    root_rules: dict            # style, long_side, shrink, rough, seed: nebari rules
    wind_dir: int
    layout: object              # layout.Layout
    meta: dict                  # engine, species, style, caliper, mode, n_ramps, ...
    v1_rng: object = None       # V1 only: the shared Random hand-off, excluded from equality
```

| Refactor step | Exit check |
| --- | --- |
| 1. Move V1 into the package with no behaviour change | Frames identical for 20 seeds × 3 sizes vs the untouched script |
| 2. V1 builder emits `TreeScene`; renderer reads only IR + look + layout | Same goldens still identical; RNG call order preserved |
| 3. V2 builder emits the same IR behind `--engine v2` | Renders through the unchanged renderer |
| 4. Default flips to v2 after Gate 3 | V1 kept behind `--engine v1` |

## System architecture

Four layers with one-way dependencies: look and layout feed a simulation `World` where biology and the maintainer alternate; an adapter turns the final state into `TreeScene`; V1's renderer and animator draw it.

&#91;embedded content: V2 architecture · data flow and module boundaries\]

The maintainer reads the arena through a read-only view and changes it only through Actions. The renderer never sees the arena, only `TreeScene`, which the V1 builder also emits for `--engine v1`.

### Module layout

```text
bonsai-wall/
├── src/bonsai_wall/
│   ├── __main__.py            # zipapp entry point
│   ├── cli.py                 # V1 flags + new ones; --engine v1|v2
│   ├── look.py                # choose_look, palettes, HARMONY (moved from V1, unchanged)
│   ├── layout.py              # runs before the tree: canvas, pot/stand placement -> DesignSpace (free space, rim, pot base, edges); stand and deck sized for the caliper class's maximum pot width (D4)
│   ├── ir.py                  # TreeScene and friends, validation
│   ├── rng.py                 # seed streams + hash_u01(); the only module that creates randomness
│   ├── v1/builder.py          # V1 tree builder -> TreeScene (moved, not rewritten)
│   ├── v2/
│   │   ├── world.py           # World: trees, environment, light grid, calendar, run()
│   │   ├── arena.py           # TreeArena storage + ReadOnlyTree view
│   │   ├── environment.py     # origin presets: nursery, field, forest, ridge, cliff, stool, group
│   │   ├── biology/
│   │   │   ├── light.py       # shadow-propagation grid, exposure Q, best direction
│   │   │   ├── allocation.py  # basipetal Q, Borchert-Honda split, container cap
│   │   │   ├── buds.py        # fates, apical-control signal, latent/adventitious release, spurs
│   │   │   ├── shoots.py      # extension, phyllotaxis, tropisms, internode and leaf sizing
│   │   │   ├── wood.py        # cumulative pipe-model thickening, droop, wire set, deadwood decay
│   │   │   ├── phenology.py   # flushes, leaf colour state, senescence, needle retention
│   │   │   └── shedding.py    # carbon-balance branch death, live-tissue connectivity
│   │   ├── species/           # base archetypes + one profile module per species
│   │   ├── maintainer/
│   │   │   ├── perception.py  # hierarchy, branch metrics, conflicts, silhouette vs envelope
│   │   │   ├── intent.py      # DesignIntent sampled from style bands + DesignSpace
│   │   │   ├── program.py     # scheduled development steps per style
│   │   │   ├── rules.py       # reactive rule library -> candidate actions
│   │   │   ├── planner.py     # season gating, health budget, skill noise, selection, log
│   │   │   ├── actions.py     # the only mutating API; biology-consistent effects
│   │   │   └── front.py       # front selection
│   │   ├── styles/            # one module per style: origin, program, intent bands, metrics
│   │   └── adapter.py         # arena -> TreeScene: projection, axes, pads, leaves
│   ├── render/                # V1 renderer: reads TreeScene + look + layout only
│   ├── animate.py             # V1 frames, gusts, particles
│   ├── output.py              # GIF/PNG, awww, monitors, cache
│   └── debug/                 # overlays, growth strips, contact sheets, action-log viewer
├── tests/                     # unit, invariants, goldens, style bands, variety, perf, boundaries
├── tools/harness.py           # seed sweeps -> CSV + contact sheets
├── docs/                      # BONSAI_V2_SPEC.md, TUNING.md, v1_inventory.md
└── build.py                   # zipapp -> dist/bonsai-wall (single executable with shebang)
```

| Module | May import | Must not import |
| --- | --- | --- |
| `v2/biology/*` | arena, species, environment, rng | styles, maintainer, render, ir |
| `v2/maintainer/*` | ReadOnlyTree, actions, styles, species (read), rng | biology internals, arena write API |
| `v2/maintainer/actions.py` | arena, biology hooks (wound, bud release, wire, kill) | styles |
| `v2/adapter.py` | arena (read), ir, species render keys | maintainer, biology |
| `render/*`, `animate.py` | ir, look, layout | v1, v2 |

A test parses imports and fails on any violation. `ReadOnlyTree` exposes numpy views with `writeable = False`, so a maintainer write raises instead of silently working.

## Tree data model

A tree is a set of metamers (internode + node + its buds and leaves) held as struct-of-arrays numpy storage with stable integer ids. Every new metamer gets a higher id than its parent, so ascending id order is a valid root-to-tip pass and descending order a tip-to-root pass, with no explicit traversal.

```python
class TreeArena:
    # metamer arrays, index = metamer id; capacity doubles, ids are never reused
    parent: int32            # -1 for the root metamer
    axis: int32              # axis id: chain continuing one growth direction
    order: int8              # branching order, trunk = 0
    born: int16              # sim year created
    p0, p1: float32[n, 3]    # start / end position, art-px units, y up, origin at soil centre
    rest_dir: float32[n, 3]  # direction set in the wood (after droop and wire set)
    length: float32
    area: float32            # cumulative conductive area; radius = sqrt(area / pi)
    alive: bool
    dead_kind: int8          # 0 live, 1 shed naturally, 2 jin, 3 cut stub
    live_arc: float32[n, 2]  # live-bark arc in radians around the axis; (0, 2*pi) = no shari
    leaf_area: float32       # 0 = bare wood
    leaf_age: int8           # years (evergreens), reset on flush
    wire: int32              # -1 or index into wires

    # bud arrays, index = bud id
    bud_metamer: int32
    bud_kind: int8           # apical | lateral | latent | adventitious | spur
    bud_state: int8          # dormant | active | dead
    bud_dir: float32[m, 3]
    bud_age: int8
    bud_vigor: float32
    bud_q: float32           # light exposure at the bud
```

| Object | Holds |
| --- | --- |
| `Wire` | Metamer chain, target directions, year applied, set progress per metamer, removal flag |
| `MaintainerMemory` | Design intent, front azimuth, sacrifice-branch ids, active wires, stress, action log |
| `World` | Year, season, environment preset, light grid, trees (several for clump and forest), RNG streams |
| `ReadOnlyTree` | Read-only arena views plus derived children index (CSR), axes and hierarchy, rebuilt once per season step |

Units: 1 sim unit = 1 art pixel at render scale, so the adapter projects and never rescales. Removal sets `alive = False` over a subtree mask; storage is compacted only at serialization, never during a run, so ids and hash-RNG keys stay stable.

## Simulation timeline

A V2 tree lives 15–60 simulated years in five stages. The style picks the origin and the development program; the run stops at the render season implied by the look's leaf palette (fresh → spring, green → summer, autumn ramps → autumn, new leafless option → winter).

| Stage | Typical years | Environment | Maintainer |
| --- | --- | --- | --- |
| Origin | 5–25 | Style's origin preset: nursery bed, open field, forest understory, windy ridge, cliff ledge, stool bed, group planting | None for wild origins; a "grower" profile for nursery and field (trunk chops, sacrifice branches, caliper building) |
| Collection / potting | 1 | Container: vigor cap drops to pot capacity × root health; root health starts low and recovers over 1–2 years | Chooses the front, samples the design intent |
| Initial styling | 1–2 | Container | Structural: branch selection, trunk and primary wiring, leader selection, jin and shari |
| Development | 5–15 | Container | Ramification: cut back, pinch, rewire, remove sacrifice branches, balance vigor |
| Refinement | 3–10 | Container | Pad upkeep, thinning, defoliation where the species allows, silhouette held to the envelope |

Stage lengths are sampled per seed within the style's ranges. That adds variety and a natural link between age and character: older trees carry more droop, deadwood and finer ramification.

### Annual cycle

```python
CALENDAR = (LATE_WINTER, SPRING, EARLY_SUMMER, SUMMER, AUTUMN, WINTER)

for year in range(total_years):
    for season in CALENDAR:
        env.update(season, year)            # light directions, wind, canopy, snow load per origin preset
        if species.flushes_in(season, tree):
            light.recompute(world)          # shadow grid from current leaves and active buds
            allocation.compute(tree)        # basipetal Q, Borchert-Honda split, container cap
            buds.update_fates(tree)         # break / latent / die / spur; apical-control signal
            shoots.extend(tree)             # new metamers: phyllotaxis, tropisms, internode and leaf size
        if season in (SUMMER, AUTUMN):
            wood.thicken(tree)              # cumulative pipe model
            wood.droop_and_set(tree)        # load sag, wire set, deadwood decay
        phenology.step(tree, season)        # leaf colour state, senescence, needle retention
        if season is WINTER:
            shedding.step(tree)             # carbon-balance death, live-tissue connectivity
        maintainer.session(tree, season)    # perceive -> program + rules -> plan -> act; no-op when wild
        if year == total_years - 1 and season is look.render_season:
            break
    debug.snapshot(world, year)             # only with --dump
scene = adapter.to_scene(world)
```

No step reads the style. Multi-flush species (zelkova, dawn redwood, juniper) flush again in early summer and summer while allocated vigor stays above their flush threshold. Preformed species (pines) flush once, plus a short second flush after decandling.

## Biology engine

Growth follows the self-organizing tree model of Palubicki et al. (2009): buds compete for light, a Borchert–Honda pass distributes vigor from the base, and shoot size follows vigor. Bonsai realism comes from four additions: a container cap on total vigor, latent buds that pruning releases, cumulative thickening, and wood that sets after bending. All constants below are tuning start points.

### Light

A voxel grid with edge ≈ 1.5 × base internode length. Every leaf-bearing metamer and active bud casts shadow into a downward pyramid: layers q = 0…q\_max below it, lateral offsets |i|, |k| ≤ q, each voxel incremented by:

```latex
\Delta s = a \, b^{-q}
```

Exposure at a bud's voxel is Q = max(C − s + a, 0), with C the full-sun constant. Start with a = 1, b = 2, q\_max = 5, C = 1. Update incrementally when leaves or buds appear or go; recompute fully once a year to bound drift. Origin presets add static shadow (forest canopy band, cliff face) and solid voxels that block growth (rock, pot, stand). The environment direction d\_env points to the least-shadowed voxel of the 26-neighbourhood inside the bud's perception cone. Space-colonization markers (Runions et al. 2007) are an allowed alternative only for unbounded free space; markers shaped like the style's envelope would leak design into biology.

### Vigor allocation

A basipetal pass (ids descending) sums Q into every metamer. Base vigor is capped by the container:

```latex
v_{base} = \min\left(\alpha \, Q_{root},\; V_{cap}\right), \qquad V_{cap} = \kappa_{pot} \cdot h_{root}
```

In the ground V\_cap is effectively unbounded. In a pot, root health h\_root ∈ (0, 1\] drops after collection, repotting and heavy pruning, and recovers each year. An acropetal pass (ids ascending) splits vigor at each node between the continuing axis and its laterals:

```latex
v_c = v \cdot \frac{w_c}{\sum_j w_j}, \qquad w_{main} = \lambda \, Q_{main}, \quad w_{lat} = (1-\lambda)\, Q_{lat}
```

λ is the species' apical control, lowered with branch order and tree age. The maintainer cannot set it; it can only change the tree that λ acts on.

### Bud fates and apical control

An apical-control signal flows basipetally from active apices: A at a metamer = Σ over distal active apices of v\_apex × δ^distance, δ ≈ 0.8 per metamer. A lateral bud breaks when its vigor ≥ v\_min and A at its metamer ≤ A\_max(species); otherwise it turns latent. Latent buds stay viable for the species' latent longevity and break later when a cut or pinch removes the apices that kept A high. That is back-budding, with no special case.

Species with adventitious budding also sprout from old wood near large wounds, with probability ∝ local vigor × wound proximity. Buds below v\_min for N years die. On spur-forming species (larch), low-vigor buds become spurs: a needle tuft that does not extend. Evergreen metamers whose needles all exceed retention age lose their latent buds, so pines and junipers cannot back-bud on bare wood, again without a special case.

### Shoot extension

Metamer count and size scale with bud vigor; preformed species (pines) use last year's bud vigor:

```latex
n = \min\left(\lfloor v_b / v_{unit} \rfloor,\; n_{max}\right), \quad l = l_0 \left(\frac{v_b}{v_{ref}}\right)^{\gamma}, \quad A_{leaf} = A_0 \left(\frac{v_b}{v_{ref}}\right)^{\beta}
```

Low vigor gives short internodes and small leaves, so leaf reduction under a pot cap and cut-backs emerges instead of being scripted. Lateral buds are placed by phyllotaxis (opposite decussate, alternate distichous, spiral, terminal whorl). Each new metamer's direction:

```latex
\mathbf{d} = \operatorname{normalize}\left(w_p \mathbf{d}_{prev} + w_e \mathbf{d}_{env} + w_g \mathbf{g} + w_w \mathbf{u}_{wind}\right)
```

g points up for orthotropic axes and toward horizontal or slightly down for plagiotropic laterals, by species and order. The turn between consecutive metamers is clamped to a species kink limit; this is what prevents V1's corkscrew literati trunks.

### Wood

Thickening is cumulative: each wood season every metamer adds area in proportion to the leaf area it currently supports, and never loses area. Radius = sqrt(area / π). Taper, thick bases under sacrifice branches, and stubs that stay thick after a cut all follow.

```latex
\text{area}_{t+1} = \text{area}_t + c \cdot A_{leaf,\,distal}
```

Droop: each wood season `rest_dir` rotates downward by an angle ∝ M / r⁴ (M = distal load × lever arm), clamped per year, then sets. Old long branches sag the way aged bonsai do.

Wiring: the maintainer supplies target directions for a chain. Each wood season `rest_dir` moves toward the target at a rate ∝ r^−k (thicker sets slower), and the wire is flagged set within tolerance. The action API rejects bends tighter than R\_min = k\_bend × r, so thick trunks cannot take shapes real wood would not.

### Shedding, deadwood, live tissue

At year end a subtree dies when its mean Q per leaf-bearing metamer stays below θ\_shed for N consecutive years. Interior thinning and self-pruned lower trunks (literati origin) come from this. Dead wood persists by species: broadleaf dead branches drop within 1–3 years, conifer dead branches persist as natural jin.

Shari is a dead arc in `live_arc` along the trunk. A branch whose attachment angle falls outside its parent's live arc dies, so a live vein must stay continuous from roots to foliage.

### Stress

Removing more than the species' leaf-area budget in one year (start 30–40%) lowers next year's root health and therefore V\_cap; collection and repotting do the same. Development slows after heavy work, as it does on real trees, and this is the planner's main safety constraint.

## Species profiles

Each V1 species gets one frozen profile built on one of four archetypes (broadleaf deciduous, pine, scale conifer, deciduous conifer). Species differ in how they grow and respond to cuts, not just in colour; λ values are simulation start points, the rest reflects common horticultural behaviour.

| Species | Growth | Phyllotaxis / foliage | λ start | Old-wood budding | Foliage life | Deadwood | Maintainer specifics |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Japanese maple | Spring flush; second flush after defoliation | Opposite decussate; broad leaves | 0.58 | Moderate | Deciduous | Drops in 1–3 yrs; big cuts scar | Cut back to one leaf pair; partial defoliation in early summer on refined, healthy trees; wire when leafless |
| Japanese black pine | Preformed candles, one flush; short second flush after decandling | Needles in pairs; buds in terminal whorls | 0.62 | Only where needles remain | Needles 2–3 yrs | Persists as jin | Decandle strong areas in early summer; reduce whorls to 2 buds; pull old needles in autumn; never cut to bare wood |
| Japanese white pine | Preformed, one flush; no decandling | Needles in fives, blue-green | 0.56 | Only where needles remain | Needles 3–4 yrs | Persists as jin | Partial candle pinch in spring; reduce whorls to 2; keep inner needles |
| Shimpaku juniper | Several flushes | Scale foliage on fine, dense shoots | 0.55 | None on bare wood | Near tips only | Strongest: jin, shari, live veins | Thin by removing whole shoots, no tip pinching; keep foliage at every branch end; deadwood work |
| Japanese zelkova | Several flushes | Alternate distichous; small leaves | 0.48 | Strong, plus adventitious | Deciduous | Drops quickly | Broom program: chop, fan 5–9 leaders; clip-and-grow twigs; partial defoliation |
| Dawn redwood | Several flushes; excurrent leader | Opposite; branchlets shed whole in autumn | 0.66 | Strong | Deciduous | Drops | Keep one leader; pinch to hold flat tiers; buttressed base comes from the V1 renderer |
| Japanese larch | 1–2 flushes; long and short shoots | Spiral on long shoots, tufts on spurs | 0.62 | Moderate, mostly from spurs | Deciduous | Persists as jin | Cut long shoots back to spurs; wire in winter; jin common |

V1 has one `pinus` species and `--species pinus` stays. The profile follows the leaf key: `kuromatsu` and `old_pine` use the black-pine profile, `goyomatsu` uses white pine (D1).

```python
@dataclass(frozen=True)
class SpeciesProfile:
    key: str
    archetype: str                 # broadleaf | pine | scale_conifer | deciduous_conifer
    phyllotaxis: str               # opposite | alternate | spiral | whorl
    flushes: int
    preformed: bool
    spur_forming: bool
    apical_control: float          # lambda start
    a_max: float                   # apical-control threshold for lateral break
    v_min: float
    latent_years: int
    adventitious: float            # 0 = none
    l0: float; gamma: float        # internode length vs vigor
    a0: float; beta: float         # leaf area vs vigor
    n_max: int
    kink_deg: float                # max turn between consecutive metamers
    gravi_leader: float
    gravi_lateral: float
    photo: float
    foliage_years: float           # 0 = deciduous
    deadwood_years: float          # persistence of dead branches
    stress_budget: float           # max leaf-area fraction removed per year
    k_bend: float                  # min bend radius = k_bend * r
    set_rate_k: float              # wire set rate ~ r ** -set_rate_k
    render: RenderKeys             # bark key, V1 foliage renderer, allowed V1 leaf ramps
```

## Style templates

A style is three things: an origin environment that grows suitable raw material, a development program the maintainer follows, and intent bands that serve as both the maintainer's targets and the tests' acceptance criteria. Nothing in a style places geometry.

At potting the maintainer samples one target per band (seeded) and keeps it for the rest of the run, so care stays coherent from year to year. The envelope is the style silhouette fitted into the layout's `DesignSpace` (free area above the pot, plus the fall zone for cascades), which is how trees fit the canvas without rescaling. V1's species × style weight table still decides which combinations exist.

| Style | Origin (raw material) | Program highlights | Acceptance bands, front view |
| --- | --- | --- | --- |
| Formal upright (chokkan) | Nursery bed, overhead light, no wind | Keep one leader, remove competitors; primaries alternate left, right, back | Lean ≤ 5°; apex over base ± 0.05 H; taper ≥ 2.0; first branch at 25–35% H; alternation ≥ 80%; conical crown |
| Informal upright (moyogi) | Nursery, 1–2 trunk chops with new leaders | Wire 2–4 trunk bends, amplitude falling with height; keep branches on the outside of bends | 2–4 bends; apex offset ≤ 0.15 H; ≥ 70% of primaries on bend outsides; scalene-triangle crown |
| Slanting (shakan) | Nursery with one-sided light, or wired | Lowest primary opposite the lean; apex eases back toward vertical | Lean 15–40° from vertical; lowest primary on the opposite side |
| Windswept (fukinagashi) | Exposed ridge, 10–20 yrs of prevailing wind: shoots bend leeward, windward buds die, windward deadwood | Wire every primary leeward; keep windward jin | ≥ 80% of foliage leeward of the trunk base; primary azimuths within 60°; trunk leans leeward |
| Semi-cascade (hankengai) | Cliff ledge (rock on one side, gravity, snow load) or nursery stock wired down | Wire the trunk over the rim; let the tip rise slightly | Lowest foliage below the rim and above the pot base; no overlap with stand or canvas edge |
| Literati (bunjin) | Forest understory, 15–30 yrs: canopy shade, lower branches self-prune, trunk searches for light in long gentle curves | Keep 1–3 branches near the top, jin the rest; optional shari | Foliage centroid ≥ 0.7 H; ≤ 3 primaries; 2–4 bends within the kink limit; trunk height ≥ 12 × base diameter |
| Broom (hokidachi) | Field-grown | Chop at 1/3–1/2 of target height; fan 5–9 leaders from the chop zone; clip-and-grow | ≥ 5 leaders from a zone ≤ 0.1 H tall; lean ≤ 5°; dome crown, width / height 1.0–1.6 |
| Twin trunk (sokan) | Nursery; a low branch or basal shoot kept as a second trunk | Develop both; keep the second shorter and thinner | Split below 0.2 H; second trunk at 60–80% of height and 50–75% of caliper |
| Clump (kabudachi) | Stool bed: chopped near soil in year 2–4, many basal shoots | Keep an odd count of 3–7 trunks; outer trunks lean out | Odd count 3–7; height spread ≥ 25%; no trunk fully hidden behind another |
| Forest (yose-ue) | Group planting: separate arenas in one shared light grid, so outer trees lean outward on their own | Tallest tree about a third in from one side; heights fall outward; uneven spacing; front and back groups | 5–15 trees, odd; tallest at 0.25–0.45 of group width; conical crowns for larch and dawn redwood |
| Cascade (kengai), new after parity | Cliff ledge | Wire the trunk below the pot base; layout uses a tall pot set higher | Lowest foliage below the pot base; nothing off-canvas |

## Maintainer system

The maintainer is a seasonal agent with a fixed design intent: it perceives the tree, runs the style's scheduled program plus reactive rules, picks actions within season, species and health limits, and applies them through the action API. Its care profile lets it make mistakes (missed issues, timing errors); that is a variety source, not a bug.

### Session loop

```python
def session(tree: ReadOnlyTree, season, mem: MaintainerMemory, profile, rng):
    view = perceive(tree, mem.front)                     # metrics, conflicts, silhouette, vigor map
    cands = program.due(mem, season, view) + rules.propose(view, mem.intent, season)
    cands = [c for c in cands if allowed(c, season, tree.species, mem)]   # season + species gates
    for c in sorted(cands, key=lambda c: priority(c, view, profile, rng), reverse=True):
        if budget.fits(c, mem):                          # leaf-area, cut and wire budgets
            result = actions.apply(c)                    # may be rejected: bend radius, live vein
            mem.log(c, result)                           # rule id, year, season, targets, before/after
```

### Actions: the only way to change the tree

| Action | Effect on biology |
| --- | --- |
| `cut(metamer)` | Removes the distal subtree; leaves a stub that callus covers in proportion to vigor; lowers apical control below the cut so latent buds can release; adventitious chance near the wound |
| `cut_back(axis, keep_n)` | Shortens an axis to n metamers; deciduous to a bud pair facing the wanted way, conifers only to foliage |
| `pinch(bud)` | Removes a soft tip; local vigor moves to laterals at the next flush |
| `decandle(region)` | Black pine only, early summer: removes candles, triggers a weaker second flush with shorter needles |
| `thin(pad, fraction)` | Removes whole interior shoots; raises light inside the pad |
| `defoliate(region, fraction)` | Deciduous, early summer, healthy trees only: leaves removed, buds kept; costs stress budget |
| `wire(chain, targets)` | Sets target directions; rejected if any bend is tighter than R\_min; removed once set |
| `jin(metamer)` | Kills the subtree and keeps the wood as deadwood |
| `shari(trunk_span, arc)` | Narrows `live_arc`; rejected if it would sever every live path to a living branch |
| `chop(height)`, `select_leader(bud)` | Trunk reduction and new-leader selection in development |
| `mark_sacrifice(axis)`, `remove_sacrifice(axis)` | Lets a branch grow free to thicken the trunk below it, then removes or jins it |
| `repot()` | Root health drops, then recovers; never in the same year as heavy styling |

### Perception and reactive rules

Perception builds the hierarchy (trunk = thickest-continuation axis from the root), then per primary: attachment height ratio, azimuth relative to the front, elevation, length, thickness ratio to the trunk, and which side of a trunk bend it leaves from. It also computes projected crossings, pad density and interior Q, vigor by zone, and silhouette deviation from the envelope.

| Rule | Detects | Proposed action | Season gate |
| --- | --- | --- | --- |
| Competing leader | Two axes near the apex with similar vigor | Cut or jin the weaker; select leader | Late winter |
| Bar branch | Two primaries at about the same height on opposite sides | Remove one | Late winter |
| Whorl | 3+ branches from one node (inverse-taper risk) | Reduce to 2 | Late winter; pines autumn |
| Crossing or inward | Projected or 3D crossings; growth toward the trunk | Remove | Dormant |
| Front-pointing | Low-third branch aimed at the viewer | Remove or wire aside | Dormant |
| Inside of bend | Primary leaving the inside of a trunk curve | Remove | Dormant |
| Too thick | Branch radius > 1/3 of trunk radius at attachment | Remove, reduce, or jin on conifers | Dormant |
| Out of envelope | Shoot past the envelope | Cut back to a bud inside; conifers only to foliage | Growth season |
| Strong zone | Long internodes, high vigor | Cut back, pinch, decandle or thin, by species | Spring to early summer |
| Weak zone | Low vigor, low Q | Exempt from cuts; thin above it to let light in | Any |
| Dense pad | Interior Q below threshold | Thin from inside; remove twigs growing straight up or down from pads | Growth season |
| Angle off target | Primary or secondary angle vs intent | Wire: primaries down from the trunk, tips up | Dormant; conifers any |
| Wire set | Set progress complete | Remove wire | Any |
| Caliper reached | Trunk base hits the intent's caliper class | Remove sacrifice branch | Late winter |

### Budgets, care profiles, schools

Per year, leaf-area removal stays within the species stress budget. Development sessions make at most 3 structural cuts; initial styling may make more. Repotting happens every 2–5 years, never in a heavy-styling year.

| Care profile | Effect |
| --- | --- |
| `master` | Low miss rate, precise wiring, correct timing |
| `enthusiast` | Misses \~20% of issues, ±10° wiring error, occasional off-season work |
| `neglected` | Skips most sessions in the last 2–5 years: long shoots, overgrown pads |

School is `wire` (wiring-heavy, smooth curves, cloud pads) or `clip` (Lingnan clip-and-grow: few wires, angular ramification from repeated cut-back). Profile and school are random per seed by default (weighted toward `master`, and toward `wire` for conifers) and printed in the run line.

### Front selection

At potting, score 24 azimuths in projection: visible trunk movement, apex leaning slightly toward the viewer, no low branch aimed at the viewer, visible nebari spread, left-right balance, few crossings. Keep the best and re-check once after initial styling; every front-dependent rule uses it.

## Rendering pipeline

The renderer stays V1's; V2 changes only what it is fed. The adapter turns the final arena into `TreeScene` in five steps.

| Step | What the adapter does |
| --- | --- |
| Project | Orthographic projection at the chosen front azimuth onto the art grid; view depth kept per point; no scaling, since sim units are art pixels |
| Axes → strokes | Decompose into axes by thickest-child continuation; smooth each with a centripetal Catmull–Rom spline; emit per-point radius, depth, wood state, bark key and the visible shari band (the dead arc rotated into view) |
| Leaves → pads | Cluster projected leaf points by grid connectivity at pad scale; fit V1's ellipse parameters (`cx cy rx ryt ryb shear`) to each cluster (V1's pad renderers take no mask; an optional mask is carried but unused until a mask renderer is approved, D3); attach per-leaf exposure, age and outer/upper rank; take V1's foliage renderer key from the species |
| Particles | Falling-leaf spawn points = real leaf positions weighted by age and exposure; the species decides leaf or needle sliver |
| Sway | Per-pad compliance from its supporting chain, ∝ Σ L³ / r⁴, normalised so the median pad gets V1's amplitude; clamped to keep changed pixels per frame inside the budget |

Colour: V1's ramps and `HARMONY` stay; V2 supplies the data V1 had to fake. Tip turning (`TIPS`) uses rank and exposure, so outer and upper foliage turns first because it really is outer and upper. Pads with low interior Q and pads further back use darker ramp levels, which adds volume without adding colours.

Seasons: autumn shows deciduous leaves partly dropped, in proportion to the phenology state. The new winter option renders all deciduous species (maple, zelkova, dawn redwood, larch) bare, showing the ramification V2 actually grows; V1's skeleton was designed to hide behind pads. Evergreens look the same in winter apart from juniper's winter bronze, which V1 already has.

Drawing order: V1's four layers stay (backdrop with back limbs, back pads, the static mid layer with front limbs, front pads) plus a fifth after the front pads for front limbs that cross foliage. It is empty on the V1 path, so V1 output is unchanged (D5). The adapter assigns strokes to layers by view depth, so branches pass both in front of and behind foliage. `draw_limb` takes an optional per-point shari band for V2; without it V1's single-fraction behaviour is untouched (D6). Every colour still comes from V1's ramp system as exact palette indices; the harness reports the per-tree peak.

Layout: `DesignSpace` comes from V1's layout before simulation (pot rim, pot base, stand top, canvas edges, `--x`), so the maintainer prunes to fit. If final bounds still touch the pot, stand or an edge, a last "show prep" session cuts back to fit; the adapter never rescales. Cascade layouts must check the bottom edge, which V1 never did. Pot width is finalised from the measured trunk base inside the intent's caliper class, and V1's root renderer gets base radius and tree age for nebari.

## Determinism, CLI, state

Every random choice derives from the printed seed through named streams, and per-entity draws are hashed by id, so a local change (one rule tweak) changes the tree locally instead of reshuffling all of it.

```python
STREAMS = ("look", "layout", "origin", "biology", "maintainer", "render", "anim")

def stream(seed: int, name: str) -> np.random.Generator:
    # "look" and everything under --engine v1 keep V1's existing generator and derivation untouched
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, STREAM_IDS[name]])))

def hash_u01(seed: int, stream_id: int, *keys: int) -> float:
    # splitmix64 over (seed, stream, year, entity id, purpose) -> [0, 1); plus a vectorised numpy variant
```

Only `rng.py` creates randomness; a test fails on `random.`, `np.random` or time-based seeding in any other V2 module (moved V1 code keeps its own generator). Per-bud and per-metamer draws use `hash_u01` with ids, never a shared sequential stream. Sim paths avoid large threaded BLAS calls, whose summation order can vary; reproducibility is guaranteed per engine version on the same machine.

| New flag | Values | Default |
| --- | --- | --- |
| `--engine` | `v1`, `v2` | `v1` until Gate 3, then `v2` |
| `--care` | `master`, `enthusiast`, `neglected`, `random` | `random`, weighted |
| `--school` | `wire`, `clip`, `random` | `random` |
| `--season` | `spring`, `summer`, `autumn`, `winter`, `auto`, `random` | V1 behaviour (season implied by the leaf palette); `auto` = today's date, northern hemisphere; a value restricts `choose_look` to that season's palettes (table below; D10) |
| `--years` | integer | Sampled from the style's ranges |
| `--dump DIR` | path | Off; writes state, action log (JSONL) and a growth strip PNG |
| `--debug` | `light`, `vigor`, `envelope`, `actions` | Off; overlays on the still PNG |
| `--grow-ahead` | flag | Off; after setting the wallpaper, grows the next seed at low priority so the next keypress is instant |

V1 flags keep their semantics. A plain `bonsai-wall` stays fully random, and each output still gets its own tree.

Leaf → season table for `--season` (D10). The restriction filters the leaf pool after the same number of draws, so no other look field moves, and without `--season` `choose_look` draws exactly as V1.

| Species | spring | summer | autumn |
| --- | --- | --- | --- |
| acer | chartreuse, deshojo | green, red, crimson, burgundy | orange, yellow, autumn |
| zelkova | chartreuse | zelkova_green | elm_amber, elm_bronze, autumn |
| metasequoia | fresh | summer | turning, rust |
| larix | fresh | fresh (fallback) | gold_tips, larch_gold, rust |
| pinus, juniperus | any season, same look | | |

Winter: all deciduous species (acer, zelkova, metasequoia, larix) are drawn bare whatever leaf key was drawn; pinus and juniperus are unchanged. If a season leaves a species with no leaf key (larix summer), use the nearest other season's keys in the order spring, autumn.

State and cache: final arena + maintainer memory + world metadata serialise to `.npz` + JSON at `~/.cache/bonsai-wall/trees/<key>.npz`. The key hashes engine version, seed, species, style, origin, care, school, years, render season and `DesignSpace`, so re-rendering a tree with another backdrop, glaze, theme or pixel size skips the simulation. `ENGINE_VERSION` is printed in the run line and bumps whenever output for an existing seed changes.

## Validation

The same metric functions feed the maintainer's perception and the tests, so "this reads as a moyogi" is a measured claim. `tools/harness.py` sweeps seeds × species × styles × screen shapes (16:9, 21:9, 16:10, portrait) and writes one CSV of metrics, timings, GIF sizes and palette peaks plus the contact sheets; every gate report quotes it.

| Metric | Definition (front view unless noted) |
| --- | --- |
| `lean_deg` | Angle of the base → apex line from vertical |
| `apex_offset` | Horizontal apex offset ÷ tree height H |
| `taper` | Trunk radius at 0.05 H ÷ radius at 0.7 H |
| `bends`, `max_turn` | Trunk curvature sign changes with amplitude > 2 px; largest turn between consecutive metamers (3D) |
| `first_branch_h` | Height of the lowest primary ÷ H |
| `alternation`, `outside_bend` | Share of consecutive primaries on alternating sides; share leaving the outside of a bend |
| `thick_ratio` | Max primary radius ÷ trunk radius at attachment |
| `crossings` | Projected crossings of live branches with radius ≥ 1 px |
| `leeward` | Foliage area leeward of the trunk base ÷ total |
| `foliage_centroid_h` | Foliage area centroid height ÷ H |
| `envelope_iou` | Projected crown mask vs intent envelope |
| `negative_space` | Background pixels inside the crown's convex hull ÷ hull area |
| `leonardo` | Σ r\_child² ÷ r\_parent² at live junctions |
| `structure_distance` | Between two trees, mirror-canonical (each tree is flipped so its silhouette mass lies on +x first, because both engines mirror trees at random): mean of (1 − IoU of height-normalised silhouettes) and the total-variation distance of the length-weighted primary-branch angle histogram. Computed by `bonsai_wall/metrics.py` from the same projected 2D IR strokes and pad extents for both engines (D8) |

| Test | Pass condition |
| --- | --- |
| V1 goldens | Frames identical for 20 seeds × 3 sizes after every refactor step |
| Determinism | Same args twice → identical GIF bytes; changing only look args → identical arena hash |
| Invariants (property tests, 200 seeds) | parent id < id; nothing live under dead wood; no foliage on dead wood; `leonardo` ≤ 1 + ε; no new buds on bare pine or juniper wood; yearly leaf removal ≤ stress budget; turns ≤ kink limit; no geometry inside pot, stand or rock; bounds inside the canvas |
| Boundaries | Import rules hold; maintainer writes to arena arrays raise |
| Style bands | Every V1 species × style combo with weight > 0: 50 seeds, ≥ 90% inside all bands |
| Variety | Median pairwise canonical `structure_distance` over 30 seeds per combo ≥ min(1.5 × V1's, ceiling), where the ceiling is the median canonical distance between that combo's trees and trees of the other styles of the same species (or V1's own value if V1 is already above it). Each capped combo is justified in `docs/baseline/v1_baseline_summary.md` (D8) |
| Cost | 4K end-to-end p50 ≤ 4 s, p95 ≤ 8 s on one core; GIF size and changed pixels per frame ≤ V1 + 25%; palette ≤ 255, peak reported |
| Visual review | Contact sheet per species (styles × 6 seeds) and growth strips (every 5 years) at each gate |

## Implementation phases

Six phases plus a backlog, with three human gates; nothing merges past a gate without sign-off, and each phase ends with the harness green for everything built so far.

| Phase | Scope | Exit criteria | Gate |
| --- | --- | --- | --- |
| P0 Audit, no code changes | Read V1 fully. Write `docs/v1_inventory.md`: every CLI flag, species × style weights, palettes, `HARMONY`, pots, backdrops, foliage renderers, animation, layout rules, outputs, and the exact seam where tree geometry enters rendering. Measure V1's baseline on this machine (time, GIF size, changed pixels per frame, palette peak, `structure_distance`). List proposed deviations from this spec | Inventory, baseline CSV, adjusted IR, deviation list | **Gate 1** |
| P1 Refactor | Package layout, `TreeScene` IR, V1 builder behind it, zipapp build, golden and import-boundary tests | Goldens identical; V1 timing within ±10%; `dist/bonsai-wall` installs with `install -Dm755` |  |
| P2 Biology core | Arena, rng, light, allocation, buds, shoots, wood, phenology, shedding; maple, black pine, zelkova; nursery and field origins; adapter; no maintainer | Invariants pass; 30 simulated years ≤ 2 s; free-growth contact sheets and growth strips | **Gate 2**: do free-grown trees look like real young trees of each species? |
| P3 Maintainer core | Perception, intent, program, rules, planner, actions, front selection, action log; chokkan, moyogi and broom on the P2 species | Style bands pass for those combos; action logs read as plausible care |  |
| P4 Full coverage | White pine, juniper, dawn redwood, larch; forest, ridge, cliff, stool and group origins; multi-tree `World`; remaining styles; jin, shari, live veins; seasons including winter | Parity table all green; all style bands; variety ≥ 1.5 × V1; cost budgets met | **Gate 3**: parity and look sign-off |
| P5 Ship | Skeleton-driven sway if it fits the pixel budget; tree cache; `--grow-ahead`; README and docs with fish commands; default flips to v2 | V1 still reachable via `--engine v1`; release checklist done |  |
| P6 Backlog, on request only | Kengai; round, square and drum pots if V1 still lacks them; root-over-rock; living mode (one persisted tree that keeps growing and gets cared for across logins, following the real calendar) | Per item |  |

## References

Cited from memory without links; confirm details before quoting them in code comments or the README.

- Palubicki, W., Horel, K., Longay, S., Runions, A., Lane, B., Měch, R., Prusinkiewicz, P. (2009). Self-organizing tree models for image synthesis. ACM Transactions on Graphics 28(3), SIGGRAPH 2009. Core of the biology engine: light competition, Borchert–Honda allocation, shedding.
- Runions, A., Lane, B., Prusinkiewicz, P. (2007). Modeling trees with a space colonization algorithm. Eurographics Workshop on Natural Phenomena.
- Borchert, R., Honda, H. (1984). Control of development in the bifurcating branch system of Tabebuia rosea: a computer simulation. Botanical Gazette 145(2).
- Shinozaki, K., Yoda, K., Hozumi, K., Kira, T. (1964). A quantitative analysis of plant form: the pipe model theory. Japanese Journal of Ecology 14.
- Eloy, C. (2011). Leonardo's rule, self-similarity, and wind-induced stresses in trees. Physical Review Letters 107, 258101.
- Pirk, S. et al. (2012). Plastic trees: interactive self-adapting botanical tree models. ACM Transactions on Graphics 31(4), SIGGRAPH 2012.
- Stava, O. et al. (2014). Inverse procedural modelling of trees. Computer Graphics Forum 33(6). Useful if hand-tuning parameters stalls.
- Barthélémy, D., Caraglio, Y. (2007). Plant architecture: a dynamic, multilevel and comprehensive approach to plant form, structure and ontogeny. Annals of Botany 99(3).
- Prusinkiewicz, P., Lindenmayer, A. (1990). The Algorithmic Beauty of Plants. Springer.
- Naka, J. Y. (1973). Bonsai Techniques I. Style definitions and the classic pruning and wiring rules.

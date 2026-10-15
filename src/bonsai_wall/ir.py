"""TreeScene: the only thing the renderer receives from a tree builder.

Both engines emit it. V1's builder fills the V1-specific fields exactly as its
renderer needs them; V2's adapter fills the same fields from the simulation.
Order inside `strokes` and `pads` is significant for V1 (ties in limb shading
are resolved by draw order, pad sprites are baked in list order).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

LAYERS = ("back", "front", "over")     # over = front limbs drawn after front pads
WOODS = ("live", "jin", "dead")
PAD_KINDS = ("cloud", "fine", "scale", "needle", "larch", "spray")


@dataclass(frozen=True)
class Stroke:
    """One draw_limb call: a tapered, shaded limb along `pts` (art px, y down)."""
    pts: tuple
    radius: tuple
    seed: int                       # per-stroke jitter seed
    order: int                      # 0 trunk/leader, 1 primary, 2 secondary, 3 twig
    wood: str = "live"
    bark: str = ""                  # species key; the renderer maps it to a bark ramp
    layer: str = "front"
    streaks: bool = True
    rough: float = 0.0
    shari_frac: float = 0.0         # V1: dead-bark band width fraction (1.0 = jin)
    shari: tuple | None = None      # V2: per-point (lo, hi) live-bark offsets of the dead band
    depth: tuple = ()               # V2: view depth per point; () = unknown (V1)


@dataclass(frozen=True)
class Leaf:
    x: float
    y: float
    depth: float
    exposure: float                 # light Q from the sim, 0..1
    age: int                        # years (evergreens)
    rank: float                     # outer/upper rank 0..1, drives tip turning


@dataclass(frozen=True)
class Pad:
    """One foliage pad, in the form V1's pad renderers take (an ellipse, not a mask)."""
    kind: str
    cx: float
    cy: float
    rx: float
    ryt: float
    ryb: float
    bias: float
    grad: float
    shear: float
    droop: float
    back: bool
    ramp: int                       # index into the look's ramp list
    ramp2: int
    mix: float
    tip_start: float
    amp: float                      # sway amplitude, art px
    lag: float
    bake_seed: int
    leaves: tuple = ()              # V2: per-leaf exposure, age, rank
    mask: bytes | None = None       # V2, optional; ignored until a mask renderer exists


@dataclass(frozen=True)
class Flute:
    """Redwood trunk fluting, applied to the buffer after `after` strokes were drawn."""
    layer: str
    x0: float
    r0: float
    phase: float
    y_start: float
    after: int


@dataclass(frozen=True)
class TreeScene:
    seed: int
    strokes: tuple
    pads: tuple
    flutes: tuple
    trunk_bases: tuple              # (x, base radius) per trunk
    root_rules: dict                # style, long_side, shrink, rough, seed: nebari rules
    wind_dir: int
    layout: object                  # layout.Layout
    meta: dict
    v1_rng: object = field(default=None, compare=False, repr=False)   # V1 only: shared Random hand-off


def validate(scene: TreeScene) -> list:
    """Return a list of problems; empty means the scene is renderable."""
    bad = []
    if not scene.strokes:
        bad.append("no strokes")
    if not scene.pads:
        bad.append("no pads")
    if not scene.trunk_bases:
        bad.append("no trunk bases")
    for i, s in enumerate(scene.strokes):
        if len(s.pts) != len(s.radius) or len(s.pts) < 2:
            bad.append(f"stroke {i}: {len(s.pts)} points, {len(s.radius)} radii")
        if s.layer not in LAYERS:
            bad.append(f"stroke {i}: layer {s.layer!r}")
        if s.wood not in WOODS:
            bad.append(f"stroke {i}: wood {s.wood!r}")
        if s.shari is not None and len(s.shari) != len(s.pts):
            bad.append(f"stroke {i}: shari band length")
        if s.depth and len(s.depth) != len(s.pts):
            bad.append(f"stroke {i}: depth length")
        if any(not (r >= 0 and math.isfinite(r)) for r in s.radius):
            bad.append(f"stroke {i}: bad radius")
        if any(not (math.isfinite(p[0]) and math.isfinite(p[1])) for p in s.pts):
            bad.append(f"stroke {i}: non-finite point")
    nramp = scene.meta.get("n_ramps", 1)
    for i, p in enumerate(scene.pads):
        if p.kind not in PAD_KINDS:
            bad.append(f"pad {i}: kind {p.kind!r}")
        if not (p.rx > 0 and p.ryt > 0 and p.ryb > 0):
            bad.append(f"pad {i}: non-positive extent")
        if not (0 <= p.ramp < nramp and 0 <= p.ramp2 < nramp):
            bad.append(f"pad {i}: ramp index")
    for i, f in enumerate(scene.flutes):
        if not (0 <= f.after <= len(scene.strokes)):
            bad.append(f"flute {i}: after={f.after}")
    return bad

"""Canvas layout: pot, stand, deck and soil rows, plus the DesignSpace derived from them."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    """Everything the static layer and the backdrop need to know about the placement.

    All lengths in art px. `k = H / 360` scales V1's hand-tuned lengths.
    """
    W: int
    H: int
    k: float
    deck_y: int
    stand_top: int
    stand_bot: int
    rim_top: int
    pot_bot: int
    pot_w: int
    pot_h: int
    pot_style: str
    stand_style: str
    stand_w: float
    slab: int
    legs: int
    feet: int
    mound: float
    soil_half: float
    xc: float
    xb: float
    yb: float
    Ht: float

    def soil_top(self, x):
        q = (x - self.xc) / self.soil_half
        if abs(q) >= 1:
            return float(self.rim_top)
        return self.rim_top - self.mound * math.sqrt(1 - q * q)


TOP_MARGIN = 0.07        # V1: the tree top stays at least 0.07 H below the canvas top
SIDE_MARGIN = 0.04       # V1: crown span is kept inside 4%..96% of the width


@dataclass(frozen=True)
class DesignSpace:
    """What a maintainer prunes to. Derived from the layout alone, before any crown exists.

    free_height is the vertical room between the trunk base and the top margin; the
    target height is the style's height band (fractions of H) clipped to it. This is
    V1's rule `Ht = min(hfrac * H, yb - 0.07 H)` with hfrac as a band instead of a draw.
    """
    W: int
    H: int
    k: float
    xc: float
    base_x: float
    base_y: float
    rim_top: int
    pot_bot: int
    stand_top: int
    stand_bot: int
    deck_y: int
    pot_w: int
    soil_half: float
    top_y: float                    # highest allowed foliage row
    free_height: float
    left: float                     # free horizontal span for foliage
    right: float
    fall_floor: float               # lowest row a cascade may reach (just above the stand top)
    height_lo: float                # target height band in px
    height_hi: float

    @staticmethod
    def from_layout(lay: Layout, height_band=(0.30, 0.60)) -> "DesignSpace":
        top_y = TOP_MARGIN * lay.H
        free = lay.yb - top_y
        lo, hi = (min(f * lay.H, free) for f in height_band)
        return DesignSpace(
            W=lay.W, H=lay.H, k=lay.k, xc=lay.xc, base_x=lay.xb, base_y=lay.yb,
            rim_top=lay.rim_top, pot_bot=lay.pot_bot, stand_top=lay.stand_top,
            stand_bot=lay.stand_bot, deck_y=lay.deck_y, pot_w=lay.pot_w,
            soil_half=lay.soil_half, top_y=top_y, free_height=free,
            left=SIDE_MARGIN * lay.W, right=(1 - SIDE_MARGIN) * lay.W,
            fall_floor=lay.stand_top - 1, height_lo=lo, height_hi=hi)

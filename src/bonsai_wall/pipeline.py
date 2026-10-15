"""Scene pipeline: look -> tree builder -> TreeScene -> renderer."""
from __future__ import annotations

from .render.static import finish, prepare
from .v1.builder import build_tree


def grow_scene(seed, W, H, look, xfrac=0.5):
    """V1: build, rasterise to exact bounds, narrow or slide the composition until nothing clips.

    Mirrors the original grow_scene: up to 8 attempts, each re-running the builder from the
    seed with a smaller `shrink` or a `shift`. Only the final attempt gets a backdrop.
    S.fit = (attempts, shrink, shift) of the attempt that was kept.
    """
    shrink, shift = 1.0, 0.0
    for attempt in range(1, 9):
        tree = build_tree(seed, W, H, look, xfrac, shrink, shift)
        S = prepare(tree, look)
        S.fit = (attempt, shrink, shift)
        left, right = S.xmin, W - 1 - S.xmax
        if left >= 2 and right >= 2 and S.crown_top >= 0.02 * H:
            break
        span_w = S.xmax - S.xmin
        if span_w <= W - 6:
            shift += (right - left) * 0.5
        else:
            shrink *= max(0.58, min(0.90, (W - 8) / max(1.0, span_w)))
            shift += (right - left) * 0.35
    return finish(S)

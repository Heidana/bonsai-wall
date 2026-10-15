"""V1 goldens: the package must reproduce the untouched script frame for frame."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import golden_cases as gc
from bonsai_wall import animate, output, pipeline
from bonsai_wall.look import choose_look

ROOT = Path(__file__).resolve().parent.parent
GOLDENS = json.loads((ROOT / "tests" / "golden" / "v1_goldens.json").read_text())
# git blob hash of bonsai-wall.py at commit 11f4936 (the V1 reference the goldens come from)
V1_BLOB = "93dc777d24f2b3b822a5c4d38e5aa5e675dbdf11"


class PackageApi:
    pick_scale = staticmethod(output.pick_scale)
    choose_look = staticmethod(choose_look)
    grow_scene = staticmethod(pipeline.grow_scene)
    render_frames = staticmethod(animate.render_frames)


def case_id(c):
    return f'{c["seed"]}-{c["size"]}-{c["species"]}-{c["style"] or "random"}-{c["bg"]}'


def test_reference_script_untouched():
    data = (ROOT / "bonsai-wall.py").read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    assert blob == V1_BLOB, "bonsai-wall.py (the V1 reference) was modified"


def test_golden_set_shape():
    default = [c for c in GOLDENS if c["style"] is None]
    assert len(default) == 60 and len({c["seed"] for c in default}) == 20
    assert {c["size"] for c in default} == set(gc.SIZES)
    assert len(GOLDENS) - len(default) == 36        # every species x style combo


@pytest.mark.parametrize("case", GOLDENS, ids=case_id)
def test_frames_identical(case):
    S, frames = gc.run_case(PackageApi, {k: case[k] for k in ("seed", "size", "species", "style", "bg")})
    got = gc.digest(S, frames)
    want = {k: case[k] for k in got}
    assert got == want

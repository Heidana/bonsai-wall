"""The zipapp installs with install -Dm755 and matches the untouched script byte for byte."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    d = tmp_path_factory.mktemp("inst")
    dist = build.build(d / "dist" / "bonsai-wall")
    target = d / "bin" / "bonsai-wall"
    r = subprocess.run(["install", "-Dm755", str(dist), str(target)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return target


def run(cmd, out):
    r = subprocess.run(cmd + ["--preview", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.parametrize("extra", [[], ["--static"], ["--bg", "scene"], ["--species", "pinus", "--style", "hankengai"]])
def test_zipapp_matches_reference_script(installed, tmp_path, extra):
    args = ["--seed", "321", "--size", "1280x720"] + extra
    a, b = tmp_path / "ref", tmp_path / "new"
    a.mkdir(); b.mkdir()
    out_a = run([sys.executable, str(ROOT / "bonsai-wall.py")] + args, a)
    out_b = run([str(installed)] + args, b)
    assert out_a.split(", ")[:-2] == out_b.split(", ")[:-2]       # run line minus timing and file
    files = sorted(p.name for p in a.iterdir())
    assert files == sorted(p.name for p in b.iterdir()) and files
    for name in files:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_engine_flag(installed, tmp_path):
    r = subprocess.run([str(installed), "--engine", "v2", "--preview", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "not implemented" in r.stderr
    r = subprocess.run([str(installed), "--help"], capture_output=True, text=True)
    assert "--engine" in r.stdout


def test_build_is_reproducible(tmp_path):
    a = build.build(tmp_path / "a" / "bonsai-wall").read_bytes()
    b = build.build(tmp_path / "b" / "bonsai-wall").read_bytes()
    assert a == b and a.startswith(b"#!/usr/bin/env python3")

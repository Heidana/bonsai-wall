#!/usr/bin/env python3
"""Build dist/bonsai-wall: one executable zipapp (needs python3, Pillow and numpy at runtime).

Usage (fish):
  python build.py
  install -Dm755 dist/bonsai-wall ~/.local/bin/bonsai-wall
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXED_MTIME = 1760500000      # 2025-10-15, so the archive does not depend on build time

ENTRY = "from bonsai_wall.cli import main\n\nmain()\n"


def build(out: Path = ROOT / "dist" / "bonsai-wall") -> Path:
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / "app"
        shutil.copytree(ROOT / "src" / "bonsai_wall", stage / "bonsai_wall",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "__main__.py").write_text(ENTRY)
        for p in [stage, *stage.rglob("*")]:
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))
        out.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(stage, out, interpreter="/usr/bin/env python3", compressed=True)
    out.chmod(0o755)
    return out


if __name__ == "__main__":
    p = build()
    print(f"built {p} ({p.stat().st_size} bytes)")
    sys.exit(0)

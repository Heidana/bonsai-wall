"""Import boundaries (spec 'Module layout') and the randomness rule for V2 code."""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "src" / "bonsai_wall"

# (path prefix relative to the package, modules it must not import)
FORBIDDEN = (
    ("v2/biology/", ("v2.styles", "v2.maintainer", "render", "ir", "animate", "v1")),
    ("v2/maintainer/", ("v2.biology", "render", "animate", "v1")),
    ("v2/adapter.py", ("v2.maintainer", "v2.biology", "v1")),
    ("render/", ("v1", "v2")),
    ("animate.py", ("v1", "v2")),
)
# maintainer files other than actions.py may read the arena only through ReadOnlyTree
MAINTAINER_ARENA_NAMES = {"ReadOnlyTree"}


def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(path: Path, root: Path):
    """Yield (absolute module relative to the package or external, imported names)."""
    tree = ast.parse(path.read_text())
    me = module_name(path, root).split(".")
    pkg = me if path.name == "__init__.py" else me[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, ()
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod == "bonsai_wall" or mod.startswith("bonsai_wall."):
                mod = mod[len("bonsai_wall."):] if "." in mod else ""
            yield mod, tuple(a.name for a in node.names)
            if mod == "" or not mod:
                for a in node.names:
                    yield a.name, ()


def hits(mod: str, banned: str) -> bool:
    return mod == banned or mod.startswith(banned + ".")


def check_boundaries(root: Path):
    bad = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        for prefix, banned in FORBIDDEN:
            if not (rel == prefix or rel.startswith(prefix)):
                continue
            for mod, names in imports_of(path, root):
                for b in banned:
                    if hits(mod, b):
                        bad.append(f"{rel} imports {mod} (forbidden: {b})")
        if rel.startswith("v2/maintainer/") and rel != "v2/maintainer/actions.py":
            for mod, names in imports_of(path, root):
                if hits(mod, "v2.arena") and not set(names) <= MAINTAINER_ARENA_NAMES:
                    bad.append(f"{rel} imports {mod}: {names} (only ReadOnlyTree allowed)")
    return bad


def check_randomness(root: Path):
    """No random, secrets, numpy.random or wall-clock seeding in v2/ except v2-wide rng.py."""
    bad = []
    v2 = root / "v2"
    if not v2.exists():
        return bad
    for path in sorted(v2.rglob("*.py")):
        tree = ast.parse(path.read_text())
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in ("random", "secrets") or a.name == "numpy.random":
                        bad.append(f"{rel}: import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                m = node.module or ""
                if m.split(".")[0] in ("random", "secrets") or m == "numpy.random":
                    bad.append(f"{rel}: from {m} import ...")
            elif isinstance(node, ast.Attribute):
                if node.attr == "random" and isinstance(node.value, ast.Name) \
                        and node.value.id in ("np", "numpy"):
                    bad.append(f"{rel}:{node.lineno}: np.random")
                if node.attr in ("time", "time_ns") and isinstance(node.value, ast.Name) \
                        and node.value.id == "time":
                    bad.append(f"{rel}:{node.lineno}: time.{node.attr}")
                if node.attr in ("now", "utcnow") and isinstance(node.value, ast.Name) \
                        and node.value.id == "datetime":
                    bad.append(f"{rel}:{node.lineno}: datetime.{node.attr}")
    return bad


def test_real_tree_respects_boundaries():
    assert check_boundaries(PKG) == []


def test_real_tree_randomness_rule():
    assert check_randomness(PKG) == []


def test_renderer_does_not_import_engines():
    for path in list((PKG / "render").rglob("*.py")) + [PKG / "animate.py"]:
        for mod, _ in imports_of(path, PKG):
            assert not hits(mod, "v1") and not hits(mod, "v2"), (path, mod)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_checker_catches_violations(tmp_path):
    root = tmp_path / "bonsai_wall"
    write(root, "ir.py", "")
    write(root, "v2/__init__.py", "")
    write(root, "v2/biology/__init__.py", "")
    write(root, "v2/biology/light.py", "from ...ir import TreeScene\nfrom ..maintainer import actions\n")
    write(root, "v2/maintainer/__init__.py", "")
    write(root, "v2/maintainer/rules.py", "from ..arena import TreeArena\nfrom ..biology import wood\n")
    write(root, "v2/maintainer/okay.py", "from ..arena import ReadOnlyTree\n")
    write(root, "render/__init__.py", "")
    write(root, "render/bad.py", "from ..v1 import builder\nfrom .. import v2\n")
    write(root, "v2/rngleak.py", "import random\nimport numpy as np\nx = np.random.default_rng()\n"
                                  "import time\nt = time.time()\n")
    bad = "\n".join(check_boundaries(root))
    assert "v2/biology/light.py imports ir" in bad
    assert "v2/biology/light.py imports v2.maintainer" in bad
    assert "v2/maintainer/rules.py imports v2.arena" in bad
    assert "v2/maintainer/rules.py imports v2.biology" in bad
    assert "okay.py" not in bad
    assert "render/bad.py imports v1 " in bad
    assert "render/bad.py imports v2" in bad
    rnd = "\n".join(check_randomness(root))
    assert "import random" in rnd and "np.random" in rnd and "time.time" in rnd

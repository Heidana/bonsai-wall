"""Monitors, scaling, theming PNG and awww glue, moved verbatim from V1."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops


def detect_outputs():
    try:
        r = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3)
        res = []
        for m in json.loads(r.stdout):
            w, h = int(m["width"]), int(m["height"])
            if int(m.get("transform", 0)) % 2 == 1:
                w, h = h, w
            res.append((m["name"], w, h))
        if res:
            return res
    except Exception:
        pass
    try:
        r = subprocess.run(["awww", "query"], capture_output=True, text=True, timeout=3)
        res = []
        for line in r.stdout.splitlines():
            m = re.search(r"([A-Za-z0-9._-]+):\s*(\d+)x(\d+)", line)
            if m:
                res.append((m.group(1), int(m.group(2)), int(m.group(3))))
        if res:
            return res
    except Exception:
        pass
    return [(None, 2560, 1440)]


def pick_scale(w, h, target=360):
    base = max(1, round(h / target))
    cands = [s for s in (base, base - 1, base + 1) if s >= 1 and 0.75 < h / s / target < 1.35]
    exact = [s for s in cands if h % s == 0]
    return (exact or cands or [base])[0]


def theme_image(S, frame, w, h, s, mode):
    fr = frame.convert("RGB")
    if mode == "leaves":
        r, g, b = ImageChops.difference(fr, S.bg.convert("RGB")).split()
        same = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v == 0 else 0)
        fr = Image.composite(fr.convert("L").convert("RGB"), fr, same)
    big = fr.resize((fr.width * s, fr.height * s), Image.NEAREST)
    ox, oy = (big.width - w) // 2, (big.height - h) // 2
    return big.crop((ox, oy, ox + w, oy + h))


def ml4w_script():
    found = shutil.which("ml4w-wallpaper")
    if found:
        return found
    p = Path.home() / ".config" / "ml4w" / "scripts" / "ml4w-wallpaper"
    return str(p) if p.exists() else None


def awww_ready():
    try:
        return subprocess.run(["awww", "query"], capture_output=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_daemon(wait=10.0):
    t0 = time.time()
    while time.time() - t0 < wait:
        if awww_ready():
            return
        time.sleep(0.3)
    subprocess.Popen(["awww-daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 5:
        if awww_ready():
            return
        time.sleep(0.2)
    sys.exit("bonsai-wall: awww-daemon is not reachable")

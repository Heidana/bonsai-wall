# Development commands (fish)

```fish
# tests (about 50 s; the goldens are the slow part)
python -m pytest -q

# build the single executable, and try the install into a scratch directory
python build.py
install -Dm755 dist/bonsai-wall /tmp/bw-test/bin/bonsai-wall
/tmp/bw-test/bin/bonsai-wall --seed 4242 --size 1920x1080 --preview /tmp/bw-test/out

# the real install is yours to run
install -Dm755 dist/bonsai-wall ~/.local/bin/bonsai-wall

# V1 reference and goldens (only when the V1 reference changes on purpose)
python tools/make_goldens.py

# baseline harness and timing check
python tools/baseline_v1.py sweep
python tools/baseline_v1.py summary
python tools/compare_timing.py
```

Rules to remember: render with `--preview` only (never touch the wallpaper), no `sudo` or package-manager
commands from tooling, and `bonsai-wall.py` at the repository root is the untouched V1 reference that the
goldens and the timing check compare against; `tests/test_goldens.py` fails if it changes.

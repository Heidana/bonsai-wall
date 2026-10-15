# bonsai-wall V2

Spec: docs/BONSAI_V2_SPEC.md is the source of truth for how trees are generated.
V1 behaviour (bonsai-wall.py) is the source of truth for everything else:
CLI, colours, pots, backdrops, animation, output, awww handoff.

Rules:
1. Biology code never imports style or maintainer code. The maintainer reads the
   tree through a read-only view and changes it only through the action API.
2. V1 stays runnable via --engine v1 and its seeds keep reproducing.
3. Dependencies: Pillow + numpy only. Same seed + engine version = identical
   output. Randomness only through the named seed streams (spec: Determinism).
4. Ship as one executable (zipapp), installable with install -Dm755.
5. The user shell is fish. Commands in docs and messages must be fish-compatible
   (no heredocs, no export VAR=value). The user runs installs: never run sudo or
   pacman.
6. Measure, do not assert. Claims about speed, size, palette, variety or style
   correctness come from the harness, with numbers.
7. Never touch the wallpaper: render with --preview only, never call awww.

Process: follow the phases in the spec. One branch per phase, small commits.
Stop at every GATE and report what was built, measured numbers vs budgets,
contact-sheet paths, deviations with reasons, and up to 5 open questions. Log
every parameter change with its reason in docs/TUNING.md. Do not start the next
phase without approval.

Start every session by reading docs/STATE.md. Update it at the end of every work session and at every gate.

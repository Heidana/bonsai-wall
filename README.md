# bonsai-wall

Procedurally grown, animated pixel-art bonsai wallpapers for Hyprland and other
Wayland compositors, displayed with [awww](https://codeberg.org/LGFae/awww).

![An animated Japanese maple bonsai swaying in the wind](screenshots/demo.gif)

Every run grows a new tree: a species, an architecture, a crown shape, a branch
structure grown to reach its foliage, and a pot, stand and backdrop chosen to
match the leaf colour. The result is a seamless 12-second loop with wind
moving through the foliage, an occasional falling leaf or needle, and drifting
dust motes.

![Eight generated trees: maple, white pine, juniper, dawn redwood, zelkova, larch, literati pine and semi-cascade juniper](screenshots/gallery.png)

## Features

- **Six species:** Japanese maple (*Acer palmatum*), Japanese black and white
  pine (*Pinus*), Shimpaku juniper (*Juniperus*), Japanese zelkova (*Zelkova
  serrata*), dawn redwood (*Metasequoia glyptostroboides*) and Japanese larch
  (*Larix kaempferi*).
- **Ten architectures:** formal upright (chokkan), informal upright (moyogi),
  slanting, windswept (fukinagashi), semi-cascade (hankengai), literati
  (bunjin), broom, twin trunk, clump and forest planting.
- **Seasons:** spring and summer greens, autumn reds, golds and rust, mixed
  autumn canopies, and conifers whose needle tips are just starting to turn.
- **Matched colours:** the backdrop, pot glaze and stand are chosen to suit
  the foliage. Mostly dark backdrops, occasionally light ones.
- **Deadwood:** old pines, junipers and larches can carry bleached jin and shari.
- **Lightweight:** trees are drawn at about 360 rows and scaled up with
  nearest-neighbour filtering, so pixels stay crisp at any resolution. A 4K
  wallpaper typically takes about 2 seconds to generate, the GIF is around
  150–250 KB, and only a few hundred pixels change between frames.
- **Optional desktop theming** for [ML4W](https://github.com/mylinuxforwork/dotfiles)
  users (see below).

## Requirements

- Python 3.8 or newer and [Pillow](https://python-pillow.org/) (tested with Pillow 12)
- [awww](https://codeberg.org/LGFae/awww), the wallpaper daemon formerly called swww
- A Wayland compositor that awww supports (it needs the layer-shell protocol).
  Developed on Hyprland. Monitors are detected with `hyprctl`, falling back to
  `awww query` elsewhere.

## Install

**Arch Linux (AUR)**

```sh
paru -S bonsai-wall
```

**Manually**

```sh
sudo pacman -S --needed python-pillow awww      # or your distro's equivalents
git clone https://github.com/GITHUB_USER/bonsai-wall
install -Dm755 bonsai-wall/bonsai-wall.py ~/.local/bin/bonsai-wall
```

## Usage

```sh
bonsai-wall                                  # a new random tree on every monitor
bonsai-wall --seed 4242                      # regrow a tree you liked (the seed is printed)
bonsai-wall --species pinus --style bunjin   # force a species and/or architecture
bonsai-wall --leaf rust --tone light         # force a foliage colour or backdrop tone
bonsai-wall --bg scene                       # sunset, night or mist landscape instead
bonsai-wall --static                         # a still image: zero idle cost
bonsai-wall --preview ~/bonsai-test          # render files only, don't set the wallpaper
```

The last seed is also saved in `~/.cache/bonsai-wall/last_seed`.

| Option | What it does |
| --- | --- |
| `--seed N` | Grow a specific tree. |
| `--species` | `acer`, `pinus`, `juniperus`, `zelkova`, `metasequoia`, `larix` (default: random). |
| `--style` | `chokkan`, `moyogi`, `slant`, `fukinagashi`, `hankengai`, `bunjin`, `broom`, `twin`, `clump`, `forest` (default: random for the species). |
| `--leaf` | Foliage colour; backdrop and pot are matched to it. See `--help` for the list. |
| `--tone` | `dark`, `light` or `auto` (about 78% dark). |
| `--backdrop`, `--pot` | Force a backdrop colour or pot glaze. |
| `--bg` | `studio` (plain diffuse backdrop, default) or `scene` (landscape). |
| `--theme` | Landscape for `--bg scene`: `dusk`, `night`, `mist` or `auto`. |
| `--fps`, `--seconds` | Animation rate and loop length (default 10 fps, 12 s). |
| `--static` | Still image instead of an animation. |
| `--pixel N` | Screen pixels per art pixel (default: whatever gives about 360 rows). |
| `--x F` | Horizontal position of the tree, 0 to 1. |
| `--outputs A,B` | Only set these monitors. |
| `--transition`, `--transition-duration` | awww transition (default: 1.2 s fade). |
| `--delay S` | Wait before applying, e.g. at login. |
| `--size WxH` | Skip monitor detection (useful with `--preview`). |
| `--preview DIR` | Write files to `DIR` without touching the wallpaper. |
| `--theme-from` | ML4W theming source: `leaves` (default), `wallpaper` or `none`. |

## A new tree at login and on a keybind

**Hyprland, Lua config (0.55 and later)**, e.g. in `~/.config/hypr/custom.lua` on ML4W:

```lua
local bonsai = "/usr/bin/bonsai-wall"   -- or os.getenv("HOME") .. "/.local/bin/bonsai-wall"

hl.on("hyprland.start", function()
    hl.exec_cmd(bonsai .. " --delay 3")
end)

hl.bind("SUPER + ALT + N", hl.dsp.exec_cmd(bonsai), { description = "Grow a new bonsai" })
```

**Hyprland, classic config (`hyprland.conf`)**

```ini
exec-once = bonsai-wall --delay 3
bind = SUPER ALT, N, exec, bonsai-wall
```

Check that the key combination is free with `hyprctl binds`. On other
compositors, run `bonsai-wall` from your autostart; that setup is untested.

## ML4W colour theming

If the [ML4W dotfiles](https://github.com/mylinuxforwork/dotfiles) are
installed, bonsai-wall hands each new tree to ML4W's own theming step
(`ml4w-wallpaper <image> --skip-wallpaper`). That regenerates the colour scheme
with matugen, reloads the bar and notifications, and updates the lock-screen
images.

matugen normally takes its accent colour from the most prominent colour in the
image, which here would be the large dark backdrop. By default bonsai-wall
greys out the backdrop in the copy it hands to ML4W, so the foliage drives the
accent instead. Use `--theme-from wallpaper` for the plain image, or
`--theme-from none` to switch theming off.

On a Lua config, keep the login command inside `hl.on("hyprland.start", ...)`.
The theming step triggers `hyprctl reload`, so a command at the top level of the
config would run again on every reload.

## Files and disk use

Everything lives in `$XDG_CACHE_HOME/bonsai-wall` (usually `~/.cache/bonsai-wall`):
one GIF per monitor resolution (older ones are deleted on every run), a still
and a theming PNG per resolution, and `last_seed`. Expect about half a megabyte
in total. Folders you pass to `--preview` are never cleaned up.

## How it works

The seed picks a species and an architecture, which set the trunk system, a
crown envelope and the type of foliage: cloud pads, a continuous dome, pine
needle pads, juniper scale pads, larch tufts or flat redwood sprays. Foliage
clusters are placed inside the envelope, and a branch skeleton is grown towards
them, with each limb as thick as the foliage it carries. The pot, stand, soil,
moss and roots form a static layer; each foliage pad becomes a small sprite that
sways on its own phase of a looping gust. Frames are composed in a single
palette of at most 255 colours, written as a GIF whose frames store only the
pixels that change, and shown by awww with nearest-neighbour scaling.

## Credits

Designed and iterated by AUTHOR_NAME, with most of the code written by
Anthropic's Claude and Google's Gemini.

## License

[MIT](LICENSE)

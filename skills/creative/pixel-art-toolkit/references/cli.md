# CLI reference

```
python3 pixelart.py <command> [args]
```

Exit code is 0 on success; `check` returns 1 when it finds real problems.
Output paths default to the input path with a new extension (`heart.pix` →
`heart.png`) unless `-o/--out` is given.

Flag precedence everywhere: a command-line flag beats the file header, which
beats the built-in default. E.g. scale = `-s` → `scale:` header → 1.

`--clip NAME` works on `show`, `play`, `render`, `gif` and `sheet`: it narrows
the command to one named frame range from the file's `clip:` headers (see
[pix-format.md](pix-format.md#clips)). Single file only — with several inputs
there is no answer to "whose clips?", and it says so.

## `new` — start a file

```bash
python3 pixelart.py new goblin.pix --size 32          # 32x32 template
python3 pixelart.py new banner.pix --size 64x24
python3 pixelart.py new hero.pix --size 32 --mirror   # mirror: x, 16-cell rows
```

Writes a template with a starter palette (`o` outline, `b` body, `h` highlight,
`s` shadow) and an all-empty grid sized for you — with `--mirror` the rows are
already halved.

## `show` — terminal preview

```bash
python3 pixelart.py show examples/orb.pix
python3 pixelart.py show examples/coin.pix --frame 3
```

Truecolor preview using the `▀` half-block (two grid rows per terminal line),
on a checkerboard so transparency is visible. Needs a truecolor terminal
(iTerm2, kitty, Windows Terminal, most modern emulators). Prints
name/size/frames/colors after the image, plus `hold=` when that frame is held.
`--frame` past the end clamps to the last frame.

## `play` — animate in the terminal

```bash
python3 pixelart.py play examples/bounce.pix --fps 12
python3 pixelart.py play examples/coin.pix --times 3     # three passes, then stop
```

The same preview as `show`, redrawn in place. Honors each frame's hold, hides
the cursor while it runs, and stops on ctrl-c — either way the cursor comes
back and it prints `frames / ticks @ fps`. `--times 0` (default) runs until you
stop it.

This is the fastest way to judge timing: no export, no image viewer. When
output is not a terminal (a pipe, a log) it prints every frame once instead of
animating, so it stays safe in scripts.

## `render` — PNG

```bash
python3 pixelart.py render examples/heart.pix                 # heart.png, file's scale
python3 pixelart.py render examples/heart.pix -s 16 -o big.png
python3 pixelart.py render examples/coin.pix --frame 2        # one frame
python3 pixelart.py render examples/coin.pix --frame all      # coin_000.png, coin_001.png, …
python3 pixelart.py render examples/potion.pix --bg "#1b1b22" # flatten alpha
```

- Output is 8-bit RGBA PNG, nearest-neighbor scaled — crisp pixels at any `-s`.
- `--frame all` on a single-frame file just renders frame 0 to one file.
- `--bg` composites every pixel over that color (kills transparency; useful for
  previews on a known background and mandatory knowledge for GIF, below).

## `gif` — animated GIF

```bash
python3 pixelart.py gif examples/coin.pix --fps 12            # coin.gif
python3 pixelart.py gif examples/ghost.pix --fps 4
python3 pixelart.py gif walk1.pix walk2.pix walk3.pix -o walk.gif
python3 pixelart.py gif examples/potion.pix --bg "#1b1b22"    # see alpha note
```

- One file: its frames become the animation. Several files: all frames of all
  files, in order, palettes merged (codes renamed on conflict — see
  [palettes.md](palettes.md)) and holds carried along.
- `--fps` sets the length of one **tick**: `tick = round(100 / fps)` cs, so
  real playback rates are quantized: 12 fps → 8 cs ≈ 12.5 fps, 24 fps → 4 cs
  = 25 fps. 8/10/20/25/50 fps are exact.
- A frame's delay is `tick × its hold`, written per frame. The summary line
  shows the tick total when any frame is held: `coin.gif  6 frames (9 ticks)`.
  See [animation.md](animation.md) for authoring holds.
- All frames must be the same size; a mismatched set is an error rather than a
  corrupt GIF (give the files a `size:` head).
- `--loop 0` (default) loops forever; `--loop N` writes N into the GIF loop
  extension (players treat it as "repeat N more times").
- **Alpha is 1-bit in GIF**: any pixel with alpha < 128 becomes fully
  transparent, alpha ≥ 128 becomes fully opaque. Semi-transparent palette
  entries (like the potion glass) look wrong unless you flatten with `--bg`
  or a `bg:` header.
- Color budget: 256 opaque colors, 255 if any transparency is used. Exceeding
  it is an error (merge fewer files, or reduce the palette).

## `sheet` — sprite sheet PNG

```bash
python3 pixelart.py sheet examples/*.pix -o sheet.png --cols 5 --pad 1 -s 6
python3 pixelart.py sheet examples/grass.pix examples/grass.pix --cols 2  # seam check
python3 pixelart.py sheet hero.pix -o hero.png --cols 10 --pad 1 --meta   # + hero.json
python3 pixelart.py sheet hero.pix --clip walk -o walk_strip.png          # one clip
```

Lays sprites left-to-right, top-to-bottom. **Every frame** of every input is a
cell, so animations contribute all their frames (that is how you bake an
animation strip for a game engine). Held frames appear **once** — a strip
stores poses, and the engine gets its timing from the holds. Cells are the
size of the largest sprite;
smaller sprites sit in the top-left of their cell. `--pad` inserts transparent
gutters (in grid cells, so they scale with `-s`). Scale/bg default to the
first file's header.

`--meta` also writes a JSON sidecar beside the PNG (`hero.png` → `hero.json`)
holding every frame's rect in image pixels, its hold, the clip ranges and the
pivot — the timing a PNG cannot carry. Several input files each become one clip
named after the file, so packing a directory into an atlas gives you a clip per
sprite for free. Schema and example:
[animation.md](animation.md#handing-it-to-an-engine).

## `check` — validate

```bash
python3 pixelart.py check examples/ghost.pix
```

Reports per file: size, frame count, palette size, then

- `timing: holds …` — the per-frame holds and the tick total, when any frame is
  held (informational, exit 0),
- `pivot: X,Y` and `clip NAME: frames A-B (N frame(s), T ticks)` — one line per
  clip (informational, exit 0),
- `ERROR: clip '…' covers frames A-B but the file has N` — a stale clip range,
  usually because frames were removed (exit 1),
- `ERROR: codes not in palette` — cells that will silently render transparent
  (exit 1),
- `ERROR: frame N: WxH but size says …` — a frame disagreeing with `size:`
  (defensive: parsing normalizes frames to `size:`, so seeing this means the
  file was produced by something other than this parser; exit 1),
- `ERROR: frames differ in size` — a multi-frame file `gif` would reject; add a
  `size:` head to normalize them (exit 1),
- `note: unused palette codes` — dead palette entries (informational, exit 0).

Run it after every hand-edit; it catches typos like `r` vs `R` instantly.

## `png2pix` — trace a PNG back into a grid

```bash
python3 pixelart.py png2pix logo.png                 # logo.pix, 1 cell per pixel
python3 pixelart.py png2pix photo.png --size 32      # downsample to 32 wide first
```

Reads 8-bit non-interlaced RGB/RGBA/grayscale PNGs (i.e. anything `render`
wrote, and most exports from other editors — but not palette-indexed or 16-bit
PNGs). Every distinct RGBA value becomes a palette code, assigned `a`–`z`,
`A`–`Z`, `0`–`9`, then `c62`, `c63`, … Pixels with alpha < 8 become `.`.
`--size N` nearest-neighbor downsamples to N pixels wide, keeping aspect.

Anti-aliased sources produce dozens of near-duplicate codes; clean them up with
`reduce` (below) or by hand ([quantization.md](quantization.md)).

## `reduce` — requantize a high-color file

```bash
python3 pixelart.py reduce traced.pix                  # in place, 24-color budget
python3 pixelart.py reduce traced.pix -o clean.pix     # keep the original
python3 pixelart.py reduce traced.pix --colors 16
python3 pixelart.py reduce glass.pix --alpha-cut 8     # keep deliberate translucency
```

Rebuilds the palette as one ramp per material — codes come out as `b`, `b2`,
`b3` … (bare code lightest, rising number darker) grouped and commented in the
written file, so masking and palette swaps work again.

- `--colors` is the budget, **capped at 24**; higher values clamp, lower ones
  are honored.
- **Files already within budget are returned unchanged** — running this on a
  hand-authored sprite is a no-op, not a slow way to lose colors. With `-o` the
  file is still written (copied verbatim) so pipelines don't break; without it,
  the input is left byte-identical.
- `--alpha-cut` (default 128) is the trace-cleanup setting: partial alpha in a
  trace is anti-aliasing, so those cells are dropped and everything kept is
  flattened to opaque. Lower it when translucency is deliberate.
- Deterministic: the same input always yields the same palette, so the output
  is safe to commit and re-generate in CI.
- Prints before/after color counts and mean per-pixel error out of 255.

Why and how it chooses colors: [quantization.md](quantization.md).

## Putting it together

```bash
python3 pixelart.py new imp.pix --size 32 --mirror
$EDITOR imp.pix
python3 pixelart.py check imp.pix && python3 pixelart.py show imp.pix
python3 pixelart.py render imp.pix -s 8
python3 pixelart.py play imp.pix --fps 6      # judge the timing, then commit to a GIF
python3 pixelart.py gif imp.pix --fps 6
```

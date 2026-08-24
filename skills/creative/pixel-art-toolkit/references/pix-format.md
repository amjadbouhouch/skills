# The `.pix` format

A `.pix` file is plain UTF-8 text with three sections in order: a **head** of
`key: value` lines, a **palette**, and one or more **pixel grids** (frames).
Only the pixels section is mandatory in practice — a file with no palette
parses, it just renders fully transparent.

```
name: heart              <- head: key/value metadata
size: 32x32
scale: 10

palette:                 <- palette section starts here
o = #4a0d1c
r = #e63946

pixels:                  <- grid section starts here
.,.,o,o,.
.,o,r,r,o
---                      <- frame separator: this file is a 2-frame animation
.,o,o,.,.
.,r,r,o,.
```

## Comments and whitespace

- A line starting with `#` or `//` is a comment.
- A trailing comment starts at ` #` or ` //` — the marker **must be preceded by
  whitespace**. `r = #e63946   # lips` keeps the color and drops the note;
  `r = #e63946# lips` is a parse error because the second `#` glues onto the value.
- A `#` that begins a valid hex color (`#fff`, `#e63946`, `#00000080`) is never
  treated as a comment marker, which is what makes `r = #e63946 # note` safe.
- Whitespace around cells, codes and values is ignored: `r , g ,  b` equals `r,g,b`.
- Blank lines are ignored everywhere.

## Head

Any `key: value` line before the palette section. A head line without a colon
is an error (reported with its line number). Recognized keys:

| Key | Example | Meaning |
|---|---|---|
| `name` | `name: heart` | sprite name; used in messages and default frame names |
| `size` | `size: 32x32` | target size — frames are **padded or cropped** (bottom/right) to exactly this, after mirroring. Also accepts `32*32`, `32,32`, or a single `32` for a square |
| `scale` | `scale: 10` | default pixel size used by `render`/`gif`/`sheet` when `-s` is not given |
| `mirror` | `mirror: x` | rows hold only part of the image; see below |
| `bg` | `bg: #1b1b22` | flatten transparency onto this color when rendering (CLI `--bg` overrides) |
| `pivot` | `pivot: 16,30` | the sprite's origin in grid cells — where an engine hangs it (feet, hand, muzzle). Not clamped: an anchor may sit outside the canvas |
| `clip` | `clip: walk 2-7` | a named frame range. **The one head key that may repeat** — see below |

Unknown keys are not an error — they are kept in `doc.meta` and otherwise
ignored, so you can stash `author:`, `license:` or anything else in a file.

### Clips

One `.pix` file holds a character's whole vocabulary; `clip:` names the ranges
inside it, so `idle`, `walk` and `attack` stop being three files with three
copies of the same palette.

```
clip: idle 0-1          # frame indexes, 0-based, INCLUSIVE
clip: walk 2-7
clip: hit 8             # a lone index is a one-frame clip
```

- Names are tokens without commas or whitespace; defining one twice is an
  error. Definition order is preserved (`doc.clips` is ordered).
- Clips land in `doc.clips` as `{"walk": (2, 7)}`, **not** in `doc.meta` —
  `meta` is one value per key and clips repeat.
- Ranges are *not* validated at parse time. A clip pointing past the last frame
  loads fine and `check` reports it as an error, because a stale clip must
  never stop you from opening the file that would tell you about it. Using
  such a clip (`--clip`, `Anim.clip`) does raise.
- Overlapping clips are allowed — a `hit` frame can also belong to `attack`.

`--clip NAME` restricts `show`, `play`, `render`, `gif` and `sheet` to one
clip; `Anim.clip(name)` is the same thing in Python. See [cli.md](cli.md) and
[animation.md](animation.md#clips-one-file-per-character).

## Palette

Starts at a line reading `palette:` or `colors:` (case-insensitive). Each entry
is `code = color` or just `code color` (whitespace-separated works too).

- A **code** is any token without commas: `r`, `R`, `sk1`, `hair`. `.` is
  reserved for the empty cell and rejected as a code. Codes are case-sensitive
  (`r` and `R` are different colors — a common convention: lowercase base,
  uppercase for its shadow/highlight variant).
- Defining the same code twice keeps the **last** definition.
- **Color** syntax (see [palettes.md](palettes.md) for the full story):
  - hex: `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`
  - decimal: `230,57,70` or `230,57,70,128` (values clamped to 0–255)
  - named: `red`, `navy`, `tan`, `none`, … (the built-in list is in `NAMED_COLORS`)

## Pixels

Starts at a line reading `pixels:` or `grid:`. Each line is one row of
comma-separated cells. A cell is a palette code, or `.` / empty for
transparent. Rows of one frame may have different lengths — shorter rows are
padded with empty cells to the widest row of that frame.

A cell whose code is missing from the palette renders transparent; it is not a
parse error, but `pixelart.py check file.pix` reports it, so run `check` after
hand-editing.

### Frames

A line starting with 3 or more `-`, `=` or `~` (`---`, `====`, `~~~`)
separates frames. All frames share the head and palette. Frames may have
different authored sizes; `size:` normalizes them if present.

A separator may carry a **hold** — how many ticks its frame lasts, where a
tick is one `1/fps`:

```
pixels:
hold: 3              <- times the FIRST frame (own line, before its rows)
.,.,r,r,.
--- hold: 2          <- times the frame this separator opens
.,r,r,r,.
--- 4                <- bare number, same as 'hold: 4'
.,r,.,r,.
---                  <- no directive: 1 tick
.,.,r,.,.
```

Both spellings mean the same thing: `hold: N` on a separator times the frame
that *follows* it, and a bare `hold: N` line inside a frame times the frame
it sits in — which is the only way to time the first frame. `N` is an integer
of at least 1. Holds are how variable timing works; no frame is ever
duplicated. Details and where holds are honored: [animation.md](animation.md).

`hold:` in the **head** is an error, since a hold times one frame rather than
the whole file. Any other `key: value` line in the pixels section is an error
too (it is almost always a misspelled `hold:`).

## Mirroring

`mirror:` lets you author half (or a quarter) of a symmetric sprite. It is
applied per frame, before `size:` padding/cropping. Values: `x`, `y`, `xy`.

**`mirror: x`** — each row holds the LEFT half; the right half is the reverse.

- Even target width: author `W/2` cells. `size: 32x32` → 16 cells per row.
- Odd target width: author `(W+1)/2` cells and the last authored column becomes
  the **shared center column** (not duplicated). This kicks in exactly when
  `size` width equals `2*cells - 1`. `size: 15x15` → 8 cells per row.
- No `size:`? Rows are always fully doubled (no shared-center detection).

**`mirror: y`** — same idea top-to-bottom: authored rows are followed by the
same rows reversed, with a shared center row when `size` height equals
`2*rows - 1`.

**`mirror: xy`** — `x` first, then `y`: author the TOP-LEFT quadrant.
`examples/sparkle.pix` authors an 8×8 quadrant for a 15×15 sprite — both the
last column and last row sit on the mirror axes.

Symmetry is a constraint as much as a shortcut: a mirrored file cannot hold
left-lit shading. See "Shading under mirror" in [shading.md](shading.md).

## Round-tripping

`Sprite.to_pix(palette, scale=8, mirror="")` writes this format back out.
`mirror="x"` stores only the left `ceil(w/2)` columns, `"y"` the top
`ceil(h/2)` rows, `"xy"` the top-left quadrant — each producing a file that
re-parses to the identical sprite (both even and odd sizes). The palette
written is filtered to the codes the sprite actually uses.

`Anim.to_pix(palette, scale=0, mirror="")` writes a multi-frame file: the same
head plus `pivot:` and one `clip:` line per clip, a palette covering the codes
used by *any* frame, holds emitted as `hold: N`, and every frame halved when
mirrored. The result re-parses to the same frames, timing, clips and pivot —
and re-emitting it is byte-identical.

## Parse errors you can hit

| Message | Cause |
|---|---|
| `line N: expected 'key: value', got …` | a head line without `:` (often a typo before `palette:`) |
| `line N: expected 'code = color', got …` | palette line with no separator |
| `line N: bad palette code '…'` | code contains a comma, or is `.` |
| `line N: bad frame directive …` | text after a `---` that is not `hold: N` |
| `line N: hold must be at least 1` | `hold: 0` or a negative hold |
| `line N: 'hold:' … belongs in the pixels section` | `hold:` used in the head |
| `line N: unknown frame directive …` | a `key: value` line in the pixels section that is not `hold:` |
| `line N: expected 'clip: NAME FIRST[-LAST]'` | a clip with no range, or a non-numeric one |
| `line N: clip '…' ends before it starts` | reversed range (`3-1`) |
| `line N: clip '…' defined twice` | two clips share a name |
| `line N: expected 'pivot: X,Y'` | pivot with one value, or three |
| `bad hex color / bad rgb(a) color` | malformed color value |
| `no pixel rows found (missing 'pixels:' section?)` | grid section absent or empty |

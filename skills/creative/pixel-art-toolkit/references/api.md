# Python API

```python
from pixelart import Sprite, Palette, Doc, Anim, load_pix, parse_pix
from pixelart import sheet, sheet_layout, merge_docs, merge_anim
from pixelart import keys, ease, lerp, EASE_KINDS
from pixelart import png_bytes, read_png, gif_bytes, ansi_preview, png_to_doc
```

Everything operates on a grid of string **codes**; colors only enter the
picture at output time, when a `Palette` translates codes to RGBA. That split
is the core design: you can reshade, palette-swap, or merge sprites without
touching pixels.

## Mutating vs. pure — read this first

Most `Sprite` methods mutate in place **and** return `self`, so they chain:

```python
s.disc(15, 15, 10, "b").outline("o").mirror_x()
```

Six methods return a **new** sprite and leave the original untouched —
assign the result or lose it:

| Pure (returns new) | Mutating (returns self) |
|---|---|
| `copy()` | `set px clear rect frame line disc ellipse circle flood replace` |
| `rotate_cw()` / `rotate(deg)` | `outline shade remap blit` |
| `shift(dx, dy)` | `mirror_x mirror_y flip_x flip_y` |
| `resized(w, h)` | |
| `bend(offsets)` / `smear(dx, dy)` | |

```python
s = s.rotate_cw()          # right
s.rotate_cw()              # WRONG: result discarded
```

`Anim` follows the same split: `hold`/`set_holds` mutate and chain, while
`copy`, `reverse`, `ping_pong`, `map` and slicing return a new `Anim`.

## Palette

A `dict` subclass mapping `code -> (r, g, b, a)`.

```python
pal = Palette.of({"o": "#22252b", "b": "#4cc9f0", "g": (46, 204, 113, 255)})
pal.set("w", "#fff").set("t", "#ffffff80")   # chainable; parses any color syntax
pal.rgba("b")        # (76, 201, 240, 255)
pal.rgba("nope")     # (0, 0, 0, 0) — unknown codes and "." are transparent
pal.to_pix()         # "o = #22252b\nb = #4cc9f0\n…" — the .pix palette section
```

`parse_color(text)` and `hexstr(rgba)` convert both ways; `over(src, dst)` is
straight-alpha compositing (used by `bg` flattening).

## Sprite

```python
s = Sprite(32)               # 32x32, empty
s = Sprite(48, 24, fill="b", name="banner")
```

`s.w`, `s.h`, `s.name`, and `s.g` (the raw `list[list[str]]`, row-major —
fine to poke directly for custom effects).

### Reading

- `get(x, y)` — code at cell; out-of-bounds returns `"."` instead of raising.
  Every drawing primitive relies on this: **drawing off-canvas is silently
  clipped**, never an error.
- `inside(x, y)`, `codes()` (unique non-empty codes in scan order).

### The `only=` mask

`set`, `rect`, `line`, `disc`, `circle` accept `only=` — a code or
tuple/list/set of codes. The cell is painted **only if it currently holds one
of those codes**. This is the workhorse for shading and detailing, because it
turns any earlier paint into a stencil:

```python
s.disc(15, 15, 11, "r")             # ball
s.disc(11, 10, 4, "w", only="r")    # highlight, guaranteed to stay inside the ball
s.disc(11, 10, 9, "x", only=("r", "w"))  # multi-code mask
```

### Drawing primitives

| Call | Notes |
|---|---|
| `set(x, y, code, only=None)` | one cell |
| `px(code, x0, y0, x1, y1, …)` | many cells, one code, flat coordinate list |
| `clear(code=".")` | fill everything |
| `rect(x, y, w, h, code, only=None)` | filled rectangle |
| `frame(x, y, w, h, code)` | 1px rectangle border |
| `line(x0, y0, x1, y1, code, only=None)` | Bresenham line |
| `disc(cx, cy, r, code, only=None)` | filled circle; float center/radius — `disc(15.5, 15.5, 8)` centers on a 32px canvas, `disc(15, 15, 8)` centers on 31px. The 0.5 cell tolerance gives pixel-art-friendly round shapes |
| `ellipse(cx, cy, rx, ry, code, only=None)` | filled ellipse — `disc` is the `rx == ry` case. Squash and stretch: grow one radius as you shrink the other. A zero radius degenerates to a 1px line rather than an error |
| `circle(cx, cy, r, code, only=None)` | 1px ring |
| `flood(x, y, code, diagonal=False)` | flood fill the connected region of whatever code sits at the seed |
| `replace(old, new)` | recolor every cell holding `old` |

### `outline(code, empty=".", diagonal=True)`

Adds `code` to every **empty** cell touching a non-empty cell — the outline
grows *outward* by one pixel. Consequences:

- Leave a 1px empty margin or the outline clips at the canvas edge.
- Call it **last**: it treats every non-empty code as body, including shadows
  and highlights (that's usually what you want).
- Existing `code` cells don't retrigger it, so calling twice thickens by
  exactly one more ring.
- `diagonal=False` gives 4-connected (thinner, more broken) contours.

### `shade(code, dx=0, dy=1, empty=".", only=None)`

Rim shading: repaints non-empty cells whose neighbor at `(x - dx, y - dy)` is
empty. Mnemonic: **`(dx, dy)` points at the light source, and the rim on the
far side gets painted.**

```python
s.shade("d", dx=-2, dy=-2, only="b")   # light from top-left -> bottom-right rim turns dark
s.shade("h", dx=2, dy=2, only="b")     # same geometry mirrored: top-left rim highlight
s.shade("d", dx=0, dy=-1, only="b")    # underside shadow (light from straight above)
```

Larger magnitudes probe farther, painting a thicker rim (2 usually reads as
1–2px). Combine passes at different vectors to bend the rim around a corner
(see `examples/gen_examples.py`, heart). Always pass `only=` unless you truly
want eyes and highlights repainted too. Call before `outline()` — after it,
edge cells no longer border empty space, so `shade` finds nothing (which is
also the trick that makes *selout* work, see [shading.md](shading.md)).

### Transforms

- `mirror_x()` / `mirror_y()` — copy left half onto right / top onto bottom
  (overwrites the other half; the file-format mirror is built on the same idea).
- `flip_x()` / `flip_y()` — reverse in place.
- `rotate_cw()` — 90° clockwise, **returns new** (dimensions swap).
- `rotate(deg, pivot=None, only=None, fill=".")` — any angle, clockwise,
  nearest-neighbor, **returns new**. `pivot` is `(x, y)` in grid cells (floats
  fine) and defaults to the canvas center; `only=` turns just those codes and
  anchors the rest, moved cells winning overlaps. Unlike `rotate_cw` the canvas
  does **not** grow, so pad with `resized()` before an off-axis turn. Quarter
  turns are exact — `rotate(90)` on a square equals `rotate_cw()`. Sampling is
  inverse (destination → source), so the result has no holes.

`only=` selects by **code, not by region** — a cart whose two wheels share
`t/k/m` cannot spin them on separate hubs, because one `rotate(only=…)` swings
every wheel cell around the one pivot you gave (and chaining a second call
rotates the already-moved cells again). Use `only=` for a single region on a
single pivot (a turret on a hull); for repeated parts, build the part as its
own sprite, rotate that, and `blit` it wherever it belongs:

```python
turned = wheel.rotate(deg)
frame = body.copy().blit(turned, 7, 15).blit(turned, 23, 15)
```

The same caveat applies to `bend(only=…)`.
- `shift(dx, dy, fill=".")` — translate, **returns new**; content moved off-canvas is lost.
- `bend(offsets, axis="y", fill=".", only=None)` — displace each row (or column
  with `axis="x"`) by its own amount, **returns new**. `offsets` is a callable
  taking the row/column index, or one number per row/column; floats round.
  `only=` (a code or tuple) moves just those cells and anchors the rest, and
  moved cells win where they overlap an anchored one. Off-canvas content is
  lost like `shift`, so leave margin. Sway, wave, wobble, shear — see
  [animation.md](animation.md#motion-helpers).
- `smear(dx, dy, code=None, steps=0)` — motion-smear frame, **returns new**:
  a copy of the sprite at every offset from `(dx, dy)` back to origin, the
  crisp original drawn last. The trail follows the vector you pass, so a
  rightward-moving sprite wants a negative `dx`. `code` paints the trail one
  flat color; `None` elongates in the sprite's own colors. `steps=0` picks
  enough copies to leave no gaps. Smear **before** `outline()` — see
  [animation.md](animation.md#motion-helpers).
- `resized(w, h, fill=".")` — pad/crop bottom-right, **returns new**.
- `blit(other, x, y, skip_empty=True)` — stamp another sprite; with
  `skip_empty=True` the other sprite's empty cells don't erase.
- `remap({"old": "new", …})` — bulk-rename codes (like `replace` for many).

### Output

- `rows_text()` — the raw comma grid (used for extra animation frames).
- `to_pix(palette=None, scale=8, mirror="")` — full `.pix` text. Passing the
  palette embeds it, filtered to used codes. `mirror="x"` writes only the left
  half, `"y"` the top half, `"xy"` the top-left quadrant (all correct for even
  and odd sizes). For a multi-frame file use `Anim.to_pix`.
- `to_rgba(palette, bg=None)` — `list[list[rgba]]`, optionally flattened over `bg`.
- `save_png(path, palette, scale=1, bg=None)`.
- `Sprite.from_rows(rows, name="")` — build from `list[list[str]]`; ragged
  rows are padded.

## Doc — a parsed .pix file

```python
doc = load_pix("examples/coin.pix")   # or parse_pix(text)
doc.frames      # list[Sprite]
doc.sprite      # frames[0]
doc.palette     # Palette
doc.holds       # list[int], one per frame (all 1 unless the file sets holds)
doc.clips       # ordered {name: (first, last)} from the clip: headers
doc.meta        # dict of head keys, e.g. doc.meta["author"] if you added one
doc.name, doc.scale, doc.bg, doc.pivot   # typed accessors with defaults
doc.anim        # the frames as an Anim (timing, clips + every output format)
doc.bad_clips() # clip names whose range falls outside the frame list
doc.save_png("coin.png", scale=8, frame=2)
```

`clips` is not in `meta` — `meta` holds one value per key and `clip:` repeats.
`bad_clips()` exists because an out-of-range clip is a `check` error, not a
parse error: a stale clip must never stop you loading the file that would tell
you about it.

## Anim — a timeline

A frame list plus its **holds**: how many ticks each frame occupies, where a
tick is one `1/fps`. Holds are how variable timing is expressed, and they
survive a round-trip through `.pix` (see [animation.md](animation.md)).

```python
anim = Anim(frames, palette, holds=None, name="", scale=1, clips=None, pivot=None)
anim = doc.anim                        # from a loaded file
anim = Anim.from_keys(KEYS, make_frame)   # from a keyframe table
```

`len(anim)`, `anim[2]`, iteration and slicing all work; `anim[1:4]` returns a
new `Anim` carrying the matching holds.

`anim.clips` is an ordered `{name: (first, last)}` of frame ranges and
`anim.pivot` is the origin in grid cells — both ride along to `to_pix` and the
sheet sidecar.

| Call | Notes |
|---|---|
| `hold(i, n=2)` | frame `i` lasts `n` ticks; negative `i` counts from the end. Chainable |
| `set_holds([…])` | all holds at once. Chainable |
| `holds` / `ticks` | the list, and its sum |
| `delays(fps=8)` | per-frame GIF delays in centiseconds |
| `clip(name)` | **new** Anim of that clip's frames, holds included, named after the clip. `KeyError` names the clips you do have; `IndexError` if the range is stale |
| `clip_ticks(name)` | tick total of one clip |
| `reverse()` | **new** Anim, holds reversed too |
| `ping_pong()` | **new** Anim: `A B C D` → `A B C D C B`, no endpoint played twice |
| `map(fn)` | **new** Anim with `fn(frame)` applied to a copy of every frame; `fn` may mutate and return the frame, return a new one, or return `None` |
| `copy()` | **new** Anim, frames copied |
| `Anim.from_keys(table, fn, n=0, kind="linear", loop=False, **kw)` | build frames by calling `fn(*pose)` per sampled pose; `**kw` goes to the constructor (`palette=`, `name=`, `scale=`, `clips=`, `pivot=`) |
| `Anim.from_doc(doc)` | same as `doc.anim` |

Clips are ranges of frame *indexes*, so only `copy` and `map` preserve them —
`reverse`, `ping_pong`, `clip` and slicing all change frame order or count,
which would leave the ranges pointing at the wrong poses, so they drop the clip
map. `pivot` survives every one of them.

Output — `palette` and `scale` fall back to the ones the `Anim` carries:

```python
anim.to_pix(palette=None, scale=0, mirror="")   # holds, clips and pivot included
anim.to_rgba(palette=None, bg=None)             # list of to_rgba() results
anim.save_pix("a.pix")                          # mirror= halves EVERY frame
anim.save_gif("a.gif", fps=12, loop=0, bg=None) # per-frame delays from the holds
anim.save_sheet("strip.png", cols=6, pad=1, meta=False)   # one cell per pose
anim.save_pngs("f.png")                         # f_000.png, f_001.png, … -> list of paths
anim.sheet_meta(cols=0, pad=0, scale=0, image="")         # the sidecar, as a dict
```

`save_sheet(meta=True)` writes that dict beside the PNG (`strip.png` →
`strip.json`); it returns the image path either way. Everything geometric in it
is in **image pixels**, already scaled — `rect` is `[x, y, w, h]`, ready to
slice the PNG. Divide by `scale` for grid cells. The rects come from
`sheet_layout`, the same function `sheet` draws with, so the JSON cannot drift
from the image. Schema: [animation.md](animation.md#handing-it-to-an-engine).

## Motion

Parameter-level helpers — nothing here interpolates pixels, which at pixel-art
resolutions turns crisp frames to mush. You interpolate the *numbers you draw
from*.

- `lerp(a, b, t)` — linear blend.
- `ease(t, kind="linear")` — reshape 0..1. `kind` is a name from `EASE_KINDS`
  (`linear`, `in`, `out`, `in_out`, `in_cubic`, `out_cubic`, `back_in`,
  `back_out`) or your own callable; `t` is clamped for the named ones. The
  `back_*` pair returns values outside 0..1 on purpose — anticipation and
  follow-through.
- `keys(table, n=0, kind="linear", loop=False)` — sample a keyframe table into
  `n` tuples. `table` holds one tuple of numbers per pose (a bare number counts
  as a 1-tuple, and every pose needs the same width). `n=0`, or `n` equal to
  the number of poses, returns the poses untouched — the common case. `loop=True`
  treats the table as a cycle and never emits the wrap frame twice. Easing
  applies **within each segment**, so `in_out` over many poses pulses.

## Module functions

- `sheet(sprites, cols=0, pad=0, pad_code=".") -> Sprite` — grid montage;
  cells sized to the largest sprite; `cols=0` = single row.
- `sheet_layout(sprites, cols=0, pad=0) -> dict` — the geometry `sheet` draws
  with, in **grid cells**: `cols rows cell_w cell_h pad w h origins`, where
  `origins[i]` is sprite `i`'s top-left. Use it to describe a sheet you built
  with your own schema.
- `merge_docs(docs) -> (list[Sprite], Palette)` — flatten docs into one
  namespace, renaming conflicting codes (`d` used for two different colors →
  the second becomes `d2`). Codes that agree on the color are shared.
- `merge_anim(docs, names=None) -> Anim` — the same merge with the timing kept:
  every file's frames end to end, holds concatenated. What multi-file `gif` and
  `sheet` run on. Several docs in: each becomes one clip, named from `names`
  (the CLI passes file stems) or its `name:` head, deduplicated with `_2`. One
  doc in: its own clips survive untouched.
- `png_bytes(rows, scale=1) -> bytes` / `read_png(path) -> rows` — RGBA rows
  to/from PNG (see [internals.md](internals.md) for the constraints).
- `gif_bytes(frames_rows, scale=1, delay_cs=10, loop=0) -> bytes` — animated
  GIF; `frames_rows` is a list of `to_rgba()` results. `delay_cs` is one delay
  for every frame, or a list of one per frame (what `Anim.delays()` returns).
  Frames must all be the same size; a mismatch raises instead of writing a
  corrupt file.
- `ansi_preview(sprite, palette) -> str` — the `show` command's truecolor string.
- `png_to_doc(path, target=0) -> Doc` — the `png2pix` tracer.
- `new_template(w, h, name, mirror) -> str` — the `new` command's file body.

## A complete programmatic sprite

```python
from pixelart import Palette, Sprite

pal = Palette.of({"o": "#20122b", "b": "#7b2cbf", "l": "#b06be0", "w": "#f3e9ff"})
s = Sprite(24, 24, name="gem")
s.disc(11.5, 11.5, 8, "b")
s.shade("o", dx=-2, dy=-2, only="b")      # dark rim away from the light — but see
s.replace("o", "l2")                      # oops, "o" is my outline code; rename
pal.set("l2", "#4a1a78")
s.disc(8.5, 8.5, 3, "l", only="b")        # light pool
s.px("w", 7, 7, 8, 8)                     # specular
s.outline("o")
s.save_png("gem.png", pal, scale=8)
print(s.to_pix(pal))                      # hand-tweak it from here if you like
```

(The deliberate mistake above is worth internalizing: pick distinct codes for
outline vs. shadow *before* you start — `replace` bails you out, but names are
cheaper. See [palettes.md](palettes.md) for conventions.)

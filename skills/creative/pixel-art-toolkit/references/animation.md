# Animation

Frames live in one `.pix` file separated by `---` lines (or `===`/`~~~`), all
sharing the head and palette. The CLI turns them into GIFs or numbered PNGs;
`sheet` bakes them into strips for game engines.

```bash
python3 pixelart.py play examples/bounce.pix --fps 12    # watch it in the terminal
python3 pixelart.py gif examples/bounce.pix --fps 12     # animate
python3 pixelart.py show examples/bounce.pix --frame 3   # inspect one frame
python3 pixelart.py render examples/bounce.pix --frame all   # bounce_000.png …
python3 pixelart.py sheet examples/bounce.pix -o strip.png   # engine-ready strip
```

Reach for `play` first. Animation is mostly *watching*, and a loop in the
terminal costs nothing — no viewer, no alt-tab, no export. It honors holds,
stops on ctrl-c, and prints the tick count when it exits.

## Timing: ticks, holds, and what `--fps` really does

`--fps` sets the length of one **tick**. Every frame lasts a whole number of
ticks — its **hold** — so the two knobs are independent: `--fps` is the speed
of the whole animation, holds are the rhythm inside it.

GIF stores per-frame delay in centiseconds; `--fps N` makes one tick
`round(100 / N)` cs, so the tick snaps to the nearest 10ms step:

| asked | tick | actual |
|---|---|---|
| 24 fps | 4 cs | 25 fps |
| 12 fps | 8 cs | 12.5 fps |
| 10 fps | 10 cs | 10 fps (exact) |
| 8 fps | 12 cs | 8.33 fps |
| 4 fps | 25 cs | 4 fps (exact) |

So exact rates are the 100/k ones (50, 25, 20, 10, 5, 4, 2…). A frame with
`hold: 3` at 10 fps is stored as 30 cs; the delay is per frame in the GIF
stream, which is what makes holds free.

`--loop 0` (default) = forever; `--loop N` asks players for N extra repeats.

## Holds: variable timing without duplicate frames

A hold is written on the frame's separator, or on its own line inside the
frame (identical meaning — use whichever reads better):

```
pixels:
hold: 3            # the first frame hangs for 3 ticks
.,.,r,r,.
--- hold: 2        # this one lasts 2
.,r,r,r,.
--- 4              # bare number is the same as 'hold: 4'
.,r,.,r,.
---                # no directive = 1 tick
.,.,r,.,.
```

`hold: N` on the separator times **the frame the separator opens**, never the
one that just ended. `N` must be at least 1. Putting `hold:` in the head is an
error, because a hold times one frame rather than the file.

Holds replace the old copy-paste trick. The animation principle is unchanged —
*the pose you linger on is the one the eye reads* — but a held pose is now one
grid with a number on it instead of the same 32 rows pasted twice:

```bash
python3 pixelart.py check anim.pix      # timing: holds 3,1,1,2,1,1 = 9 ticks
python3 pixelart.py gif anim.pix --fps 10   # anim.gif  6 frames (9 ticks)
```

Where holds apply and where they don't:

| Command | Holds |
|---|---|
| `gif` | per-frame delay = tick × hold |
| `play` | each frame sleeps hold × tick |
| `check` | reported, with the tick total |
| `sheet` | not repeated on the strip — they travel in the `--meta` sidecar |
| `render --frame all` | **ignored** — one PNG per frame |

A sprite sheet deliberately does not repeat held frames. Engines want distinct
poses plus a timing table, not the same pose twice on the strip — which is what
`sheet --meta` writes (see [Handing it to an engine](#handing-it-to-an-engine)).

## Clips: one file per character

A character is not one animation, it is a vocabulary. `clip:` names ranges
inside a single file so `idle`, `walk` and `attack` share one head, one palette
and one canvas instead of being three files that drift apart:

```
name: hero
size: 20x24
pivot: 10,22            # origin: between the feet
clip: idle 0-2          # frame indexes, 0-based, inclusive
clip: walk 3-6
clip: attack 7-9
```

Then work one clip at a time — `--clip` is on `show`, `play`, `render`, `gif`
and `sheet`:

```bash
python3 pixelart.py check hero.pix                 # lists clips, frames, ticks
python3 pixelart.py play  hero.pix --clip walk     # just the walk cycle
python3 pixelart.py gif   hero.pix --clip attack -o attack.gif --fps 12
python3 pixelart.py sheet hero.pix --clip walk -o walk_strip.png
```

In Python, `anim.clip("walk")` returns those frames as an `Anim` of their own,
holds included, named after the clip:

```python
hero = load_pix("hero.pix").anim
hero.clip("walk").ping_pong().save_gif("walk.gif", fps=10)
for name in hero.clips:
    hero.clip(name).save_gif(f"{name}.gif", fps=10)
```

Clips are ranges of frame *indexes*, so anything that reorders or drops frames
drops the clip map with it (`reverse`, `ping_pong`, slicing) — the ranges would
otherwise point at the wrong poses. `copy` and `map` keep them. `pivot` always
rides along.

A range pointing past the last frame is **not** a parse error: the file still
loads and `check` reports it, because a stale clip must never stop you from
opening the file that would tell you about it. Overlapping clips are fine — a
`hit` frame can belong to `attack` too.

## Handing it to an engine

Holds solve timing inside `.pix`, but a PNG strip cannot carry a number. That
is what the sidecar is for:

```bash
python3 pixelart.py sheet hero.pix -o hero.png --cols 10 --pad 1 --meta -s 4
# hero.png   the atlas
# hero.json  where every frame is, how long it lasts, and the clip ranges
```

```json
{
  "format": "pixelart-sheet/1",
  "image": "hero.png",
  "scale": 4,
  "image_size": [844, 104],
  "cell": [80, 96],
  "grid": {"cols": 10, "rows": 1, "pad": 4},
  "pivot": [40, 88],
  "frames": [{"index": 0, "hold": 6, "rect": [4, 4, 80, 96]}, "…"],
  "clips": [{"name": "idle", "from": 0, "to": 2, "ticks": 13}, "…"]
}
```

Everything geometric is in **image pixels**, already scaled — `rect` is
`[x, y, w, h]`, ready to slice the PNG with no arithmetic. Divide by `scale`
for grid cells. `pivot` is relative to a frame's top-left, and is `null` when
the file sets none. The rects come from the same layout function `sheet` draws
with, so the JSON cannot drift from the image.

Multi-file `sheet` turns each input into one clip, named after the file, which
makes atlas packing a one-liner:

```bash
python3 pixelart.py sheet sprites/*.pix -o atlas.png --cols 8 --pad 1 --meta
# clips: {"slime": 0-1, "coin": 2-7, "ghost": 8-9}
```

(Colliding names get `_2`. A single file keeps its own clips instead.)

To build the sidecar yourself — a custom pipeline, a different schema —
`anim.sheet_meta(cols, pad, scale, image)` returns the dict and
`sheet_layout(sprites, cols, pad)` returns the raw cell geometry.

## Frame count: less is more

The examples on purpose use tiny counts:

- `slime.pix` — **2 frames**: rest and squash. An idle bob needs nothing more.
- `ghost.pix` — **2 frames**: dome drops 1px *and* the skirt teeth swap
  position. Two changes per frame beat one; the eye reads it as continuous
  waving.
- `coin.pix` — **6 frames**: a spin is width keyframes `11, 8, 4, 1, 4, 8` —
  the ellipse never turns, it just narrows through an edge-on frame and
  widens again. Add the shading flip (dark edge on the trailing side) and the
  brain supplies the rotation.
- `bounce.pix` — **6 frames** for a full bounce cycle.

## Squash & stretch (bounce.pix walkthrough)

The generator (`examples/gen_more.py`) drives one `ball()` function with a
keyframe table:

```python
#        cy    sq        sq > 0 squash, sq < 0 stretch
KEYS = [( 9.0,  0.0),    # apex: round, hangs
        (14.0, -0.6),    # falling: slight stretch
        (21.0, -1.2),    # fast: more stretch
        (24.6,  1.4),    # impact: wide squash on the ground
        (19.0, -0.9),    # rebound: stretch again
        (11.5, -0.3)]    # rising, relaxing back to round

frames = [ball(cy, sq) for cy, sq in KEYS]
```

Written today that loop is `Anim.from_keys`, which calls `ball(*pose)` once per
row of the table and hands back a timeline you can retime and export:

```python
anim = Anim.from_keys(KEYS, ball, palette=BALL, name="bounce", scale=10)
anim.hold(0, 2)                      # linger at the apex
anim.save_gif("bounce.gif", fps=12)
```

See [Motion helpers](#motion-helpers) for interpolating between poses when you
want more frames than poses.

The principles, each visible in the table:

- **Squash & stretch**: deformation along the motion axis, roughly volume
  preserving. `ellipse(cx, cy, rx, ry, code)` does it directly — grow one
  radius as you shrink the other:

  ```python
  rx, ry = r * (1 + 0.28 * sq), r * (1 - 0.28 * sq)   # sq>0 wide, sq<0 tall
  s.ellipse(15.5, cy, rx, ry, "b")
  ```

  `bounce.pix` predates the primitive and fakes it with two merged discs
  (stacked for a stretch, side by side for a squash, radius shrinking as
  `|sq|` grows). Both work; the ellipse is one call and exactly volume-tunable.
- **Spacing is timing**: positions bunch near the apex (9→14: slow) and spread
  near impact (14→21→24.6: fast). Same frame rate, felt acceleration. You
  animate *speed* with *distance between frames*, never with fps.
- **The pose sells the physics**: the only squash frame is the one touching
  the ground. Squash mid-air reads as jelly, not impact.
- **Secondary anchor**: the contact shadow is computed from height — wider and
  darker near the ground, gone at the apex. Ground the sprite or it floats.

## Looping discipline

A cycle's last frame must flow into its first: `bounce` ends at
`(11.5, -0.3)` rising, which leads back into the apex frame. When a loop
stutters, the almost-always cause is the first frame duplicated at the end
(A B C D A + loop restarts at A = double hold). End one step *before* the
wrap, never on it.

Ping-pong motions (pendulums, idle sways) don't need mirrored frame copies.
From the shell, author one direction and list files twice in reverse order:

```bash
python3 pixelart.py gif sway1.pix sway2.pix sway3.pix sway2.pix -o sway.gif --fps 8
```

(Multi-file `gif` concatenates *all frames of all files* in argument order,
merging palettes and holds — same file twice is legal.)

From Python, `ping_pong()` does the same thing and gets the endpoints right by
construction — `A B C D` becomes `A B C D C B`, turning at each end without
landing on it twice:

```python
doc.anim.ping_pong().save_gif("sway.gif", fps=8)
```

## Animating with the API vs. by hand

Procedural motion (physics, rotation, waves) belongs in a generator: write
`frame(i)` and hand the frames to an `Anim`, which is a frame list plus its
holds and knows every output format:

```python
from pixelart import Anim

anim = Anim([make_frame(i) for i in range(6)], pal, name="anim", scale=10)
anim.hold(2, 3)                      # frame 2 lasts 3 ticks
anim.save_pix("anim.pix")            # holds included, re-parses identically
anim.save_gif("anim.gif", fps=12)    # per-frame delays from the holds
anim.save_sheet("strip.png", cols=6) # one cell per pose
anim.save_pngs("frame.png")          # frame_000.png, frame_001.png, …
```

`doc.anim` gives you the same object for a file you loaded, so retiming an
existing animation is two lines:

```python
doc = load_pix("coin.pix")
doc.anim.hold(0, 3).hold(3, 2).save_pix("coin.pix")   # hang, then snap through
```

Character acting (blinks, expressions, attacks) is usually faster hand-edited:
`render --frame all`, study the stills, edit rows directly. `ghost.pix` is
fully hand-authored — read it with the fact in mind that each frame is only 16
short lines.

`Anim.to_pix(mirror="x")` halves **every** frame, so mirrored multi-frame files
round-trip. (`Sprite.to_pix` still halves only the single frame it writes,
which is all one sprite can do.)

## Motion helpers

These cover most procedural movement. None of them interpolate pixels — they
interpolate *parameters* and *offsets*, then you draw crisp frames from those.

**`keys(table, n=0, kind="linear", loop=False)`** samples a keyframe table.
With `n` omitted you get your poses back untouched, which is the default for a
reason: at 6-frame counts, hand-picked poses beat any interpolation. Ask for
more frames and it fills them in:

```python
keys([(0,), (10,)], 3)                    # [(0.0,), (5.0,), (10.0,)]
keys(KEYS, 12, "in_out", loop=True)       # 12-frame cycle from 6 poses
```

`loop=True` treats the table as a cycle — the last pose leads back into the
first and the wrap frame is never emitted twice, which is the looping rule
above enforced by the sampler. Easing is applied *within each segment*, so
`in_out` across many keys pulses (velocity hits zero at every pose); that is
what you want on a one- or two-segment move, and usually not what you want on
a six-pose cycle. Use `linear` there.

**`ease(t, kind)`** reshapes 0..1. `linear`, `in`, `out`, `in_out`,
`in_cubic`, `out_cubic`, `back_in`, `back_out` — or pass your own callable.
The `back_*` pair deliberately leaves the 0..1 range: that overshoot is
anticipation and follow-through. Spacing is still timing (see above); easing is
just a compact way to write the spacing.

**`Sprite.bend(offsets, axis="y", only=None)`** displaces each row (or column,
with `axis="x"`) by its own amount: sway, wave, wobble, shear. `offsets` is a
callable taking the row index, or one number per row. With `only=` just those
codes move and everything else anchors — a tree's leaves bending over a still
trunk, in one call:

```python
LEAF = ("G", "g", "l", "h")
def gust(sway):
    return tree.bend(lambda y: sway * ((38 - y) / 38) ** 0.7 if y < 38 else 0,
                     only=LEAF).outline("o")

Anim.from_keys([(0,), (1,), (3,), (3,), (2,), (1,), (0,), (-1,)],
               gust, palette=TREE, name="tree").save_pix("tree.pix")
```

Two things to know. `bend` returns a **new** sprite on the same canvas, so
leave margin — whatever leaves the grid is gone, exactly like `shift`
(`tree.pix` is 40 wide for a 32-wide tree so the lean has somewhere to go).
And where a moved cell lands on an anchored one, the moved cell wins: a bent
leaf covers the trunk, which is what you want for foliage. Bend before you
`outline()`, or the outline bends with the body.

**`Sprite.rotate(deg, pivot=None, only=None)`** turns by any angle, clockwise
— wheels, thrown axes, a swung sword. `rotate_cw` only does quarter turns:

```python
spin = Anim([wheel.rotate(a) for a in range(0, 360, 30)], pal, name="spin")
cart.rotate(15, pivot=(8, 20), only=("s", "S"))   # wheel turns, cart doesn't
```

`pivot` defaults to the canvas center and takes floats. Like `bend` it keeps
the canvas, so a square turned 45° clips its corners unless you `resized()`
first — and off-axis angles rasterize unevenly at these sizes. Use it for fast
motion (a projectile, a blur of a blade); for a slow, readable turn, hand-draw
the frames or rotate on a bigger canvas and scale down. Quarter turns are
exact: `rotate(90)` on a square is pixel-identical to `rotate_cw()`.

**`Sprite.smear(dx, dy, code=None, steps=0)`** builds the elongated frame that
sells speed better than more in-betweens. It unions a copy at every offset from
`(dx, dy)` back to origin, drawing the crisp original last, so the trail lies
in the direction you pass — for something moving right, pass a **negative** dx
to leave the streak behind it:

```python
dart.smear(-10, 0, "S")     # flat pale streak behind a rightward dart
dart.smear(-10, 0)          # code=None: elongate in its own colors
```

Smear *before* `outline()`. With `code=None` on an already-outlined sprite,
each copy's contour drags across the body of the next one and the streak comes
out the color of the outline.

## GIF disposal & transparency (why the background never smears)

Every frame is written full-size with disposal mode "restore to background",
so each frame fully replaces the previous one — no trails, and transparent
pixels stay genuinely transparent between frames. The cost is file size (no
delta encoding), which at sprite scales is irrelevant. Alpha is 1-bit; see
[palettes.md](palettes.md) for the flattening rules.

Every frame carries its own delay in that same block, which is where holds
land. All frames must be the same size — `gif` refuses a mismatched set rather
than writing a corrupt file, so give multi-file animations a `size:` head.

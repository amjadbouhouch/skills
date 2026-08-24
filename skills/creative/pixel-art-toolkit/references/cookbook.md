# Cookbook

Copy-paste recipes. Shell recipes run from the repo root; Python recipes assume
`from pixelart import *` works (run from the repo root or put `pixelart.py` on
your path).

## Recolor without touching pixels (palette swap)

```python
from pixelart import load_pix, Palette

doc = load_pix("examples/ghost.pix")
night = Palette(doc.palette)
night.set("b", "#5a79c9").set("d", "#3c56a0").set("p", "#7fa3e8")
doc.frames[0].save_png("ghost_night.png", night, scale=10)
```

For a permanent variant, copy the `.pix` file and edit only the palette block.

## Restructure colors (grid rewrite)

```python
s = doc.sprite.copy()
s.replace("p", "b")                 # remove the cheeks
s.remap({"w": "k", "k": "w"})       # swap two codes atomically (remap is one pass,
                                    # so a->b, b->a doesn't collide)
```

## Silhouette / flat icon version

```python
doc = load_pix("examples/heart.pix")
sil = doc.sprite.copy()
for c in sil.codes():
    sil.replace(c, "x")
sil.save_png("heart_sil.png", Palette.of({"x": "#1b1b22"}), scale=8)
```

## Drop shadow under a sprite

```python
doc = load_pix("examples/heart.pix")
sh = doc.sprite.copy()
for c in sh.codes():
    sh.replace(c, "sh")
out = sh.shift(2, 3)                    # shadow offset (shift returns NEW)
out.blit(doc.sprite, 0, 0)              # sprite on top; skip_empty keeps shadow visible
pal = Palette(doc.palette); pal.set("sh", "#00000055")
out.save_png("heart_shadow.png", pal, scale=8)   # PNG keeps the soft alpha
```

## Four facing directions from one sprite

```python
doc = load_pix("examples/sparkle.pix")
s = doc.sprite
views = {"n": s, "e": s.rotate_cw(), "s": s.rotate_cw().rotate_cw(),
         "w": s.rotate_cw().rotate_cw().rotate_cw()}
for k, v in views.items():
    v.save_png(f"sparkle_{k}.png", doc.palette, scale=8)
```

(For side-facing characters, `copy().flip_x()` is usually the right "west".)

## Compose a scene from sprites

```python
from pixelart import Sprite, load_pix, merge_docs

docs = [load_pix(p) for p in ("examples/grass.pix", "examples/mushroom.pix",
                              "examples/sparkle.pix")]
sprites, pal = merge_docs(docs)
grass, mush, spark = sprites
scene = Sprite(64, 48, name="scene")
for i in range(4):
    scene.blit(grass, i * 16, 32, skip_empty=False)   # tiled ground
scene.blit(mush, 16, 4)
scene.blit(spark, 44, 2)
scene.save_png("scene.png", pal, scale=4)
```

`merge_docs` guarantees the three files' palettes coexist even where they
reuse code letters.

## Check a tile really tiles

```bash
python3 pixelart.py sheet examples/grass.pix examples/grass.pix \
    examples/grass.pix examples/grass.pix --cols 2 -o tiled.png -s 8
```

Seams show up as vertical/horizontal lines in `tiled.png`. (Keep `--pad 0`,
the default — padding would hide the seam you're checking.)

## Bake an animation strip for a game engine

```bash
python3 pixelart.py sheet examples/coin.pix -o coin_strip.png --cols 6 -s 4
```

All 6 frames land left-to-right in one row: engine-ready, frame width =
`32 * 4`. Add `--meta` and the timing ships with it:

```bash
python3 pixelart.py sheet examples/coin.pix -o coin_strip.png --cols 6 -s 4 --meta
# coin_strip.json: frame rects in image pixels, holds, clip ranges, pivot
```

## Pack a directory into an atlas with a clip per sprite

```bash
python3 pixelart.py sheet sprites/*.pix -o atlas.png --cols 8 --pad 1 --meta
```

Each input file becomes one clip named after the file, so the sidecar tells the
engine where every sprite lives without a naming convention.

## One character, many animations, one file

```
name: hero
pivot: 10,22
clip: idle 0-2
clip: walk 3-6
clip: attack 7-9
```

```bash
python3 pixelart.py check hero.pix              # lists every clip + its ticks
python3 pixelart.py play  hero.pix --clip walk
python3 pixelart.py gif   hero.pix --clip attack -o attack.gif --fps 12
```

```python
hero = load_pix("hero.pix").anim
for name in hero.clips:                          # one GIF per clip
    hero.clip(name).save_gif(f"{name}.gif", fps=10)
```

## One-command dark-background previews

```bash
python3 pixelart.py render examples/potion.pix --bg "#1b1b22" -o preview.png
```

## Turn a GIF-unsafe sprite into a GIF-safe one

```bash
# potion.pix uses 55/99 alpha glass -> flatten while animating
python3 pixelart.py gif examples/potion.pix --bg "#1b1b22" -o potion.gif
```

## Trace, clean, reshade a logo

```bash
python3 pixelart.py png2pix logo.png --size 24
python3 pixelart.py check logo.pix        # lists the junk codes
```

```python
doc = load_pix("logo.pix")
s = doc.sprite
s.remap({"e": "b", "f": "b", "g": "d"})   # fold AA fringe codes into real ones
print(s.to_pix(doc.palette))              # save, then delete unused palette lines
```

## Thicken an outline

```python
s.outline("o")      # 1px ring
s.outline("o")      # second call adds exactly one more ring
```

## Glow instead of outline

```python
pal.set("g1", "#ffd23f88").set("g2", "#ffd23f33")   # fading halo
s.outline("g1")
s.outline("g2")
# render to PNG (alpha!) or flatten with bg for GIF
```

## Terminal preview inside your own script

```python
from pixelart import ansi_preview
print(ansi_preview(s, pal))
```

## Emit a .pix animation from code

```python
from pixelart import Anim

anim = Anim([make_frame(i) for i in range(N)], pal, name="anim", scale=10)
anim.save_pix("anim.pix")            # holds included; mirror="x" halves every frame
```

## Retime an existing animation

```python
doc = load_pix("coin.pix")
doc.anim.hold(0, 3).hold(3, 2).save_pix("coin.pix")   # hang, then snap through
```

```bash
python3 pixelart.py check coin.pix     # timing: holds 3,1,1,2,1,1 = 9 ticks
python3 pixelart.py play coin.pix --fps 10   # watch it before exporting
```

## Drive frames from a keyframe table

```python
from pixelart import Anim

KEYS = [(9.0, 0.0), (21.0, -1.2), (24.6, 1.4), (19.0, -0.9)]   # cy, squash
Anim.from_keys(KEYS, ball, palette=pal).save_gif("bounce.gif", fps=12)
Anim.from_keys(KEYS, ball, n=12, loop=True, palette=pal).save_gif("smooth.gif")
```

## Sway, wave, or wobble part of a sprite

```python
LEAF = ("G", "g", "l", "h")
bent = tree.bend(lambda y: sway * ((38 - y) / 38) ** 0.7 if y < 38 else 0,
                 only=LEAF).outline("o")     # leaves move, trunk anchors
```

Leave canvas margin for the lean, and bend *before* outlining.

## Spin something

```python
from pixelart import Anim

blade = sword().resized(48, 48)                  # pad so 45° doesn't clip
Anim([blade.rotate(a) for a in range(0, 360, 30)], pal,
     name="spin", scale=4).save_gif("spin.gif", fps=12)
```

`rotate(90)` on a square is pixel-identical to `rotate_cw()`; off-axis angles
rasterize roughly, so save them for fast motion.

## Turn one part and leave the rest still

```python
hull.rotate(15, pivot=(17, 13), only=("g", "n"))   # turret swings, hull doesn't

# leaves sway, trunk holds. Clamp the base: a fractional power of a negative
# number is complex in Python, and rows below y=38 would go negative here.
tree.bend(lambda y: 3 * max(0.0, (38 - y) / 38) ** 0.7, only=LEAF)
```

## Motion-smear frame

```python
dart = raw_dart()                       # NOT outlined yet
dart.smear(-10, 0, "S").outline("o")    # pale streak behind a rightward dart
dart.smear(-10, 0).outline("o")         # elongate in its own colors
```

The trail follows the vector, so a rightward sprite wants a **negative** `dx`.
Smear before outlining — otherwise each copy's contour drags over the next and
the streak comes out outline-colored.

## Spin a repeated part (two wheels, one hub each)

`only=` matches by code, so both wheels would swing around whichever pivot you
pass. Rotate the part as its own sprite and stamp it:

```python
turned = wheel.rotate(deg)
frame = body.copy().blit(turned, 7, 15).blit(turned, 23, 15).outline("o")
```

## Ping-pong a one-way motion

```python
load_pix("sway.pix").anim.ping_pong().save_gif("sway.gif", fps=8)
```

## Validate everything before committing

```bash
for f in examples/*.pix; do python3 pixelart.py check "$f" || exit 1; done
```

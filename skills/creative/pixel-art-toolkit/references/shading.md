# Shading

Flat shapes read as stickers; shaded shapes read as *things*. This page is the
theory plus the exact toolkit calls, built around one worked example:

![orb stages](../examples/orb_stages.png)

`examples/orb_stages.png` — flat → ramp bands → dithered terminator →
specular + reflected rim → selout. Regenerate it with
`python3 examples/gen_more.py`; the final sprite is `examples/orb.pix`.

## 1. Commit to one light source

Pick a light direction before the first shading pass and never mix two.
Top-left is the genre default (matches how UIs and most game art are lit).
Everything below assumes it; flip the signs for other directions.

With this toolkit the light direction literally is a vector: `shade(code, dx,
dy)` paints the rim **facing away** from `(dx, dy)`. Keep a comment in your
gen scripts like `LIGHT = (-2, -2)  # from top-left` and derive every call
from it.

## 2. Build a ramp, not a lighter/darker pair

A **ramp** is the ordered run of colors one material uses, dark to light. The
orb uses six steps:

```
o  #131233   outline        (darkest step — never pure black)
s2 #2b2a66   core shadow    (violet lean)
s1 #31479c   shadow
b  #3f6fd1   base
l1 #5fa8e8   light
l2 #93dcf5   bright light   (cyan lean)
w  #f0fdff   specular       (near-white, still tinted)
```

Two rules make a ramp feel professional rather than airbrushed:

- **Hue-shift it.** Don't just darken the base toward black and lighten toward
  white — bend the hue as you go: shadows drift cool (toward blue/violet),
  lights drift toward the light's color (warm sun → yellowish, magic glow →
  whatever the glow is). In the orb: `#2b2a66` (shadow) is distinctly more
  violet than `#3f6fd1` (base), and `#93dcf5` leans cyan. A straight
  value-only ramp is the #1 "programmer art" tell.
- **Space values unevenly.** Bigger jumps near the shadow end, smaller near
  the light. 3–4 steps is plenty for 16px sprites; 5–6 for 32px hero pieces.
  More steps than that and you're painting, not pixeling.

More on constructing ramps in [palettes.md](palettes.md).

## 3. Block in the form (banding)

Shade in hard **bands**, one ramp step per band, following the volume. For
round forms the fastest tool is *nested offset discs* — each lighter step is a
smaller disc pushed toward the light, masked to the previous step:

```python
s.disc(15.5, 15.5, 13.2, "s2")                       # whole ball = darkest
s.disc(14.4, 14.4, 12.3, "s1", only="s2")
s.disc(13.2, 13.2, 10.7, "b",  only="s1")
s.disc(12.1, 12.1,  8.3, "l1", only="b")
s.disc(11.1, 11.1,  5.7, "l2", only="l1")
```

The `only=` chain guarantees each band paints strictly inside the last, so the
silhouette never changes. The same idea works for any shape: draw the darkest
version of the whole form, then progressively smaller/offset lighter passes.

For shapes where discs don't fit, `shade()` builds bands from the rim inward:

```python
s.shade("d", dx=-2, dy=-2, only="b")   # 1-2px dark rim, bottom-right
s.shade("d", dx=-1, dy=-3, only="b")   # second pass bends the band wider below
```

(That two-pass trick is exactly how `examples/gen_examples.py` shades the
heart.)

**The band boundary between light and shadow is called the terminator.** Keep
it hard almost everywhere — crisp terminators are what makes pixel art look
deliberate.

## 4. Dither the wide boundaries — sparingly

Where two bands meet across a *large, slowly-curving* area, a 1px checkerboard
fringe softens the jump without a new palette entry:

```python
NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

def dither(s, a, b):
    """Checker-blend the `a` side of every a|b boundary."""
    hits = [(x, y) for y in range(s.h) for x in range(s.w)
            if s.g[y][x] == a and not (x + y) % 2
            and any(s.get(x + dx, y + dy) == b for dx, dy in NEIGH4)]
    for x, y in hits:
        s.g[y][x] = b
    return s

dither(s, "b", "s1")     # soften base|shadow
dither(s, "s1", "s2")    # soften shadow|core-shadow
```

Guidelines:

- Dither only between **adjacent** ramp steps. Checkering distant colors reads
  as noise.
- Skip it entirely below ~24px sprites and on tight curves — stage 3 of the
  orb works because the ball is 26px across.
- One fringe row (as above) is usually enough; classic 50/25% multi-row
  dithers are for big backgrounds, not sprites.
- Texture is a legitimate second use: `examples/grass.pix` dithers the
  grass/dirt border to suggest crumbly soil.

## 5. Specular highlight

The hottest point is small, sits well inside the lightest band, offset toward
the light — never centered:

```python
s.disc(10.2, 9.4, 2.3, "w", only=("l2", "l1"))   # hotspot
s.px("w", 13, 6, 6, 13)                          # tiny satellite glints
```

Masking to the light bands keeps it physically plausible; the satellites are
pure style (glass/gem/slime read).

## 6. Reflected light (the shadow is not dead)

Bounce light lifts the extreme edge of the shadow side one ramp step. Since it
sits on the rim *away* from the key light, it's one `shade` call — same vector
as the shadow pass, lighter code, masked to the core shadow:

```python
s.shade("s1", dx=-2, dy=-2, only="s2")
```

Compare orb stages 3 and 4: the bottom-right edge stops being a dead silhouette
and starts turning. This single call is the highest value-per-character trick
in this file.

## 7. Outlines and selout

- Use a **hue-tinted dark** for the outline, not `#000` — the orb's `#131233`
  is "the ramp continued one step past the core shadow."
- Call `outline("o")` after all shading (it rings every non-empty cell).
- **Selout** (selective outline): the outline itself responds to light —
  lighter where the light hits it. Because `outline()` runs last, the outline
  cells are now the ones bordering empty space, so `shade` masked to the
  outline code hits exactly the lit arc:

```python
s.outline("o")
s.shade("s1", dx=2, dy=2, only="o")   # note: vector points AWAY from the light,
                                      # painting the rim that FACES the light
```

Stage 5 of the orb. At small sizes selout is the difference between "sprite on
a page" and "object in a scene". Skip it when the sprite must sit on wildly
varying backgrounds (UI icons) — a uniform dark outline separates better.

## 8. Anti-patterns

- **Pillow shading**: concentric rings of light centered on the shape, i.e.
  shading the *outline* instead of a *light source*. It's what the nested-disc
  technique produces if you forget the per-step offsets — every band centered,
  no terminator, form gone. If your highlight is in the middle, you're
  pillowing.
- **Banding against the outline**: bands that run exactly parallel to the
  contour for long stretches merge visually with the outline into fat stripes.
  Break the parallel run: vary band width, or let the band cut across.
- **Over-dithering**: checkerboard everywhere destroys the crisp terminator
  that says "pixel art". If a boundary is shorter than ~6px, leave it hard.
- **Pure black outline + pure white highlight** on a colorful sprite: both
  read as holes punched through the image. Tint both ends of the ramp.
- **Two light sources**: a top-left highlight with a bottom-left selout means
  nothing can be read as volume. One key light; the only cheat allowed is
  reflected light (§6), one step, shadow side.

## 9. Shading under `mirror:`

A `mirror: x` file is forced symmetric, so it **cannot** hold left-lit
shading — only vertical light (light from straight above/below) survives the
reflection. Your options, in order of preference:

1. **Vertical light only** in mirrored files: `shade(code, dx=0, dy=-1)`
   (underside shadow) and top highlights are symmetric and safe.
   `examples/mushroom.pix` does exactly this: `shade("R", dx=0, dy=-2)` under
   the cap, spots placed on the authored left half.
2. **Author mirrored, shade unmirrored**: build symmetric geometry with the
   API, then apply directional shading *after* `mirror_x()`, and export with
   `to_pix()` (no `mirror=` arg — the file stores both halves).
3. **Emissive subjects** dodge the problem: `examples/sparkle.pix` is
   `mirror: xy` and needs no direction because its "light" radiates from its
   own center (§2 ramp still applies, radially).

## 10. Cheat sheet

| Effect | Call (light from top-left) |
|---|---|
| dark rim (form shadow) | `s.shade("dark", dx=-2, dy=-2, only="body")` |
| underside shadow | `s.shade("dark", dx=0, dy=-1, only="body")` |
| top-left highlight rim | `s.shade("light", dx=2, dy=2, only="body")` |
| reflected light | `s.shade("mid", dx=-2, dy=-2, only="darkest")` |
| specular | small `disc(…, "white", only=lights)` offset to the light |
| soften terminator | `dither(s, "base", "shadow")` (§4 helper) |
| selout | after `outline("o")`: `s.shade("mid", dx=2, dy=2, only="o")` |

# Quantization: rescuing a high-color file

Some `.pix` files arrive with roughly one palette entry per pixel — anything
traced from a raster with `png2pix`, or exported from an image generator and
then traced. They render fine and `check` passes them, but they are rasters in
a text costume. This page is what a real case taught us, and how
`pixelart.py reduce` works.

```bash
python3 pixelart.py reduce traced.pix                  # in place, 24-color budget
python3 pixelart.py reduce traced.pix -o clean.pix     # keep the original
python3 pixelart.py reduce traced.pix --colors 16
python3 pixelart.py reduce glass.pix --alpha-cut 8     # keep deliberate translucency
```

## Recognizing the problem

The case that drove this was a 64×67 traced soldier: **1634 palette entries for
1864 filled cells.**

| Symptom | How to measure |
|---|---|
| ~1 color per pixel | `check` prints the palette size; compare to `w × h` |
| codes used once | count cell occurrences per code — 1518 of 1634 appeared exactly once |
| no color repeats spatially | 99% of filled cells matched **no** orthogonal neighbor |
| nothing is fully opaque | 3 of 1634 entries had alpha 255; the rest were `fd`, `fc`, `f8` — anti-aliasing and lossy-resave fringe |
| codes named `c62`, `c63`, … | that is `png_to_doc`'s own code generator: the file is a trace |

What such a file forfeits, all of it silently:

- **GIF is impossible.** 1519 distinct RGB values against GIF's 255-color
  ceiling — `gif_bytes` raises. The sprite can never animate.
- **Recolors are dead.** A palette swap means editing 1634 lines.
- **`only=` masking and `shade()` are inert**, because they key on *shared*
  codes and no two cells share one.
- **Diffs are unreadable**, which is most of the reason to keep art as text.

`check` reporting the file as clean is not a contradiction: it validates
structure (unknown codes, unused entries, size agreement), and has no opinion
on palette density. A file can satisfy every rule and still violate every
design assumption of the format.

## Why blind median cut is the wrong tool

Median cut is the obvious answer and it fails in an instructive way. It splits
color-space boxes by **spread**, ignoring how many pixels are in them. On the
soldier it spent 8 of 24 slots separating 112 near-identical cream pixels while
461 near-black pixels shared a single slot. Mean per-pixel error 9.9/255.

Frequency-weighted variants do not save it either: in a traced file almost every
color appears exactly once, so frequency carries no signal.

## What works: budget follows the pixels

`reduce` does three things:

1. **Bucket every cell into a material family.** Dark (`V < 13`), neutral
   (`S < 16`) and pale tints (`S < 28, V > 78`) are their own families at any
   hue; everything else falls into one of 12 hue sectors. Families are the unit
   of *naming*, so this doubles as the code-naming scheme.
2. **Allocate the budget across families**, one step minimum each, the rest
   proportional to `population ** 0.5`. The damping matters: undamped, the
   largest family eats the budget; with it, a 400-cell material and a 40-cell
   material both get a usable ramp. Families too small to earn a slot
   (< 0.5% of cells) are folded into their nearest neighbor first.
3. **k-means inside each family**, in RGBA, seeded on luminance percentiles —
   no RNG, so the same input always produces the same palette. Each family's
   clusters are then sorted light → dark and named `b`, `b2`, `b3` …

Result on the soldier: **1634 → 24 colors, mean per-pixel error 7.0/255**,
single-pixel color noise down from 99% of cells to 34%, file from 44 KB/1708
lines to 11 KB/108 lines. Visually indistinguishable at 1×.

```
b  b2 b3 b4 b5   brown, orange, skin
o  o2 o3 o4      dark / outline
y  y2 y3 y4      yellow, khaki, olive
n  n2 n3         neutral (gun metal)
u  u2 u3         blue (jacket)
r  r2 r3         red (bandana)
w  w2            pale tint (webbing, sling)
```

That grouped, commented palette is the actual deliverable. A 24-color file with
opaque names like `c17` would be smaller but no more editable; ramps named per
material are what make `shade(only=…)` and palette swaps work again.

## Lessons worth keeping

**RMS error is not perceptual quality.** Moving the brown|yellow sector
boundary from 45° to 36° *raised* measured error from 7.17 to 7.48, and looked
clearly better: at 45° the tan pack and canvas webbing were swallowed by the
browns and the pack lost its material identity. Squared error rewards spending
slots on large regions; a viewer notices small regions that read as a distinct
*material*. When the metric and your eye disagree, trust your eye and keep the
metric for regressions.

**k-means deletes small distinctive materials.** A 21-cell cream highlight
inside an 800-cell brown family is an outlier that minimizing squared error
will always absorb. The fix is not more clusters, it is *segmenting before
clustering* — which is why pale tints get their own family regardless of hue.

**A reducer must be a no-op on files that do not need it.** `reduce` returns
early when a file is already within budget, so all twelve hand-authored
examples pass through byte-identical. Without that guard, tiny-family folding
cost `btr82.pix` one of its 16 colors — a lossy edit disguised as a cleanup.
Any lossy tool applied to already-clean input should refuse to act, not act
slightly.

**Alpha needs an explicit policy, not an average.** In a traced file every
partial alpha is fringe, so the default `--alpha-cut 128` drops the invisible
cells and flattens the rest to fully opaque — otherwise averaging leaks entries
like `#0e08039b` into the palette and leaves ghost pixels. But deliberate
translucency exists too (`examples/potion.pix` glass at 33% alpha), so lowering
the cut preserves averaged alpha instead. One switch, two honest behaviors;
guessing per-cluster from the alpha value alone gets both wrong.

**Determinism is a build-step requirement.** Seed k-means from luminance
percentiles rather than at random. A converter that emits a different palette
on every run cannot be checked into a repo or re-run in CI.

## What `reduce` does not do

- **De-speckling.** Voting isolated pixels to their neighbors' majority would
  have changed 67 cells on the soldier (noise 34% → 28%). That edits artwork
  rather than palette, so it is deliberately out of scope — do it by hand if a
  sprite needs it.
- **Re-shading.** Quantization cannot invent a ramp the trace never had. A
  reduced file is a good starting point for real shading work, not a substitute
  ([shading.md](shading.md)).
- **Recanvasing.** Odd sizes and missing margins are left alone so the output
  stays a drop-in replacement for the original.

## Doing it by hand instead

For a small trace, `remap` is enough — fold the anti-aliasing codes into the
real ones and delete the dead palette lines that `check` lists as unused:

```python
doc = load_pix("logo.pix")
doc.sprite.remap({"e": "b", "f": "b", "g": "d"})
print(doc.sprite.to_pix(doc.palette))
```

Hand-tuning the family bands to a specific subject also beats the generic
sectors — the first version of this tool used bands read off the soldier's own
hue census (a dedicated *skin* family, a *cream webbing* family) and scored
7.1 against the generic 7.5 before the alpha policy closed the gap. If one
sprite matters enough, read its hue histogram and pick the bands yourself.

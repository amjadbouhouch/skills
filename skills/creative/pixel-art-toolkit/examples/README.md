# Examples

> Maintainer-owned fixtures and learning material. User-generated assets and
> temporary AI-agent output belong in the consuming project or a temporary
> directory, not here. See [output location policy](../docs/workflow.md#output-location-policy).

Every sprite ships as editable `.pix` text plus a rendered PNG/GIF. Generator
scripts build the procedural ones — regenerate after editing them:

```bash
python3 examples/gen_examples.py   # heart, slime, coin, mushroom
python3 examples/gen_more.py       # orb (+ stages), bounce, potion, grass, tree
python3 examples/gen_btr82.py      # top-down arcade BTR-82
python3 examples/gen_explosion.py  # animated arcade explosion + sprite sheet
```

`ghost.pix` and `sparkle.pix` are hand-authored — edit the files directly.

| File | Size / frames | What it teaches | Docs |
|---|---|---|---|
| `heart.pix` | 32×32 | disc + manual V-fill, 2-pass `shade`, specular | [shading](../docs/shading.md) |
| `mushroom.pix` | 32×32, `mirror: x` | vertical-only shading under symmetry | [shading §9](../docs/shading.md) |
| `ghost.pix` | 16×16, 2 fr, `mirror: x` | hand-authored file, idle bob + skirt wave | [pix-format](../docs/pix-format.md), [animation](../docs/animation.md) |
| `sparkle.pix` | 15×15, `mirror: xy` | odd size = shared center row/column, emissive ramp | [pix-format](../docs/pix-format.md) |
| `orb.pix` | 32×32 | the full shading study; stages in `orb_stages.png` | [shading](../docs/shading.md) |
| `potion.pix` | 32×32 | semi-transparent colors; PNG alpha vs GIF `--bg` | [palettes](../docs/palettes.md) |
| `grass.pix` | 16×16 | seamless tile, dither as texture | [cookbook](../docs/cookbook.md) |
| `tree.pix` | 40×64, 8 fr | directional gust, elastic recovery, fixed trunk and roots | [animation](../docs/animation.md) |
| `slime.pix` | 32×32, 2 fr | minimal idle animation | [animation](../docs/animation.md) |
| `coin.pix` | 32×32, 6 fr | spin via width keyframes | [animation](../docs/animation.md) |
| `bounce.pix` | 32×32, 6 fr | squash & stretch, spacing, contact shadow | [animation](../docs/animation.md) |
| `explosion.pix` | 32×32, 10 fr | anticipation, expanding fireball, shock ring, smoke breakup | [animation](../docs/animation.md) |
| `btr82.pix` | 64×96 | layered vehicle construction, angular armor, top-down lighting | [palettes](../docs/palettes.md) |
| `soldier.pix` | 64×67 | detailed figure on 24 per-material ramps, requantized from a trace | [quantization](../docs/quantization.md) |

> **`soldier.pix` started as a 1634-entry trace** — roughly one palette color
> per pixel, which cannot animate (GIF caps at 255 colors), cannot be recolored,
> and defeats `only=` masking. `pixelart.py reduce` rebuilt it as 24 material
> ramps at a mean per-pixel error of 7.0/255: visually indistinguishable, 4×
> smaller, 108 lines instead of 1708. [quantization.md](../docs/quantization.md)
> has the method and the lessons.

Validate everything and render the overview sheet (cells size to the
largest sprite, so mixing 16px and 96px art leaves gutters — that is `sheet`
working as documented, not a bug):

```bash
for f in examples/*.pix; do python3 pixelart.py check "$f"; done
python3 pixelart.py sheet \
  examples/{heart,mushroom,ghost,sparkle,orb,potion,grass,tree,slime,coin,bounce,explosion,btr82,soldier}.pix \
  -o examples/sheet.png --cols 5 --pad 1 -s 6
```

`sheet` sizes every cell to the largest sprite, so a montage mixing 16px tiles
with the 64×96 vehicle carries wide gutters — documented behavior, not a bug.

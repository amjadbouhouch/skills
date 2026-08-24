# Workflow & best practices

How the pieces are meant to be used together, and the habits that keep sprites
consistent as a set grows.

## Output location policy

Treat this repository as a tool dependency when creating art for another
project. Store generated `.pix`, PNG, GIF, sprite-sheet, and helper-script files
inside that target project, preferably under its existing asset directory.

AI agents creating user assets must not write to `examples/`, modify `docs/`,
or change other tracked files in this repository. If no target project or
output path is available, create a temporary directory with `mktemp -d`, keep
all work there, and report final absolute paths. Always pass `-o/--out` to
commands that produce rendered output.

```bash
PIXELART_TOOL=/path/to/pixelart.py
TARGET_ASSETS=/path/to/game/assets

python3 "$PIXELART_TOOL" check "$TARGET_ASSETS/tree.pix"
python3 "$PIXELART_TOOL" render "$TARGET_ASSETS/tree.pix" \
  -o "$TARGET_ASSETS/tree.png"
```

Files under `examples/` are maintained fixtures and learning material. Change
them only when explicitly developing this framework or its example suite.

## The core loop

```bash
python3 pixelart.py new imp.pix --size 32 --mirror   # 1. scaffold
$EDITOR imp.pix                                      # 2. edit text
python3 pixelart.py check imp.pix                    # 3. catch typos
python3 pixelart.py show imp.pix                     # 4. eyeball in terminal
python3 pixelart.py render imp.pix                   # 5. PNG when it's real
```

A tight loop for step 2–4 (re-render on every save):

```bash
while true; do clear; python3 pixelart.py show imp.pix; sleep 1; done
```

(or `fswatch -o imp.pix | xargs -n1 -I{} python3 pixelart.py show imp.pix`
if you have fswatch).

## Choosing a canvas size

| Size | Good for | Palette budget |
|---|---|---|
| 8×8 | tiles, particles, font glyphs | 2–3 colors |
| 16×16 | icons, tiles, small mobs (`ghost`, `grass`) | 3–5 |
| 32×32 | characters, items, hero props (most examples) | 5–8 |
| 48–64 | portraits, bosses | 8–12 |

Smaller than you think is right: pixel art reads through silhouette and
contrast, and every doubling quadruples the cells you must control. Start at
16 or 32; scale the *output* with `-s`, never the canvas.

Leave a **1px empty margin** inside the canvas — `outline()` grows outward and
clips silently at the edge, and sheets/gifs look cramped without breathing
room. (The heart uses rows 5–30 of its 32 — the margin is part of the design.)

## Order of operations for a single sprite

1. **Silhouette first.** Block the whole shape in one mid color. If it doesn't
   read as the subject at 1× (`show`), no amount of shading will save it.
2. **Big color regions** — split the silhouette into materials (`only=` masks
   or hand-recoloring regions).
3. **Shading** — one light source, ramp bands, `shade()` rims
   ([shading.md](shading.md)).
4. **Details** — eyes, bubbles, glints. Details after shading, so they sit on
   finished forms.
5. **`outline()` last**, then selout.

The same order holds for hand-editing: it's much easier to recolor cells of a
correct silhouette than to reshape a shaded sprite.

## Hand grid vs. API — pick per sprite

- **Hand-author** (`.pix` in an editor) when the sprite is small, asymmetric
  in detail, or "acting" (faces, poses). `ghost.pix` took its final form in a
  text editor — 8-cell rows are perfectly editable.
- **Generate** (`Sprite` API) when the form is geometric (coin, orb), when
  frames are functions of parameters (bounce physics, spin widths — a keyframe
  table through `Anim.from_keys`), or when many sprites share structure. Keep the generator next to its output in the
  consuming project. The script *is* the source; the `.pix` is a build artifact
  you can still hand-tweak afterwards. `examples/gen_*.py` follows this pattern
  only for repository-maintained examples.
- The hybrid is the sweet spot: generate geometry, `print(s.to_pix(pal))`,
  paste into a file, hand-finish the 5% the code got wrong.

## Version control

The format is designed to diff:

- One row per line means a pixel edit is a one-line diff; palette edits don't
  touch the grid at all. Recolors show up as palette-only diffs
  ([palettes.md](palettes.md)).
- Commit `.pix` files always; commit PNG/GIF outputs only if they're consumed
  directly (e.g. by a README). Regenerable art is build output.
- Keep `size:` headers in files — they make bad merges fail loudly in `check`
  (row count mismatch) instead of silently rendering shifted.

## Consistency across a set

- **Shared conventions beat shared files**: same outline hex everywhere, same
  light direction everywhere, same scale per category (all tiles 16, all
  characters 32). A sheet of mixed-light sprites looks broken even when each
  sprite is individually fine.
- Run `sheet` on everything as a review step — inconsistencies that hide in
  single renders jump out in a grid:

  ```bash
  python3 pixelart.py sheet examples/*.pix -o review.png --cols 5 --pad 1 -s 4
  ```
- `check` everything in CI or a pre-commit hook:

  ```bash
  for f in examples/*.pix; do python3 pixelart.py check "$f" || exit 1; done
  ```

## Rescuing a traced file

`png2pix` is a starting point, not a converter — real PNGs carry
anti-aliasing, which becomes dozens of single-use codes:

```bash
python3 pixelart.py png2pix logo.png --size 32   # downsample while tracing
python3 pixelart.py check logo.pix               # count the damage
```

### Strip an opaque background before tracing

A subject on a studio backdrop (AI renders, product shots) must lose the
backdrop **before** `png2pix` — traced in, the backdrop becomes palette codes
that `reduce` merges with the subject's own grays, and no later cleanup
separates them.

Flood fill from the border pixels, but with an **absolute background model,
never neighbor-relative tolerance**. A fill that accepts any neighbor within
Δ of the pixel it grew from drifts without bound through anti-aliased edges —
on a 1122×1402 test it consumed 99.6% of the image, subject included. Small
steps, unlimited cumulative drift.

Build the model by measurement, not guessing:

1. Sample the border pixels: chroma (`max(r,g,b) − min(r,g,b)`) range and
   channel ordering.
2. Probe a few subject pixels for a separating feature. Grays split by
   *temperature*: a cool backdrop has `b ≥ r`, warm subject grays (gun metal,
   leather shadow) have `b < r` — that ordering saves subject pixels chroma
   alone cannot.
3. Set the chroma cutoff with slack for the gradient's center, which is
   usually farther from the border samples than the border's own spread
   (measured 18 at the border, 23 mid-frame; 32 worked).
4. BFS from the border, admitting only pixels the model accepts. Subject
   pixels that match the model but sit *inside* the silhouette are safe — the
   fill cannot reach them.

Removed-area percentage is the sanity check: subject-sized (30–70%) is
plausible, ~100% means the model or the fill leaked.

After trace + `reduce`, despeckle: edge anti-aliasing leaves a few isolated
cells, and `reduce` deliberately never edits artwork. Deleting filled cells
with zero orthogonal filled neighbors is safe and enough.

### Size the trace from the smallest detail, not the subject

The canvas table above is for *authoring*. Tracing inverts the logic: `--size`
is bounded from below by the smallest feature that must survive, because
nearest-neighbor downsampling averages a feature away long before `reduce`
ever sees it. A feature needs **3–4 cells** to read; from the source
measurements:

```
target size ≥ source size × 3 / detail's pixel span in the source
```

Case that taught this: a 1254×1254 wraith with a ~40px chain. Traced at 64,
the chain landed at ~2px and vanished; the reduced sprite looked like `reduce`
had eaten it. It hadn't — rendering the *traced* `.pix` showed the chain was
already gone before quantization. Retraced at 128 (links ≈4px), the same
`reduce --colors 24` kept a full gold/bone ramp for it, because the
material-family segmentation protects small distinctive materials once their
pixels exist.

So when a detail is missing after conversion, establish blame in this order:

1. Render the **traced** file. Detail absent → trace resolution; retrace
   larger. Do not fight `reduce` for pixels that were never there.
2. Detail present in the trace but merged after `reduce` → quantization;
   see [quantization.md](quantization.md) for hand-tuned families or `remap`.

Cleanup sequence that works:

1. `--size` small enough that each intended pixel is one cell — but no
   smaller than the detail bound above.
2. In Python: `doc = load_pix("logo.pix")`, then merge stray codes into their
   nearest real color with `sprite.replace("q", "b")` (or `remap` with a
   dict), and delete the dead palette lines (`check` lists them as unused).
3. Re-shade by hand — traced gradients never survive quantization.

### When the trace is huge

Past a few dozen stray codes, manual `replace` calls stop scaling — a trace can
carry roughly one palette entry per pixel, which forfeits GIF, recolors, and
masking all at once. `pixelart.py reduce` requantizes such a file into
per-material ramps:

```bash
python3 pixelart.py reduce traced.pix -o clean.pix
```

[quantization.md](quantization.md) covers how it picks its palette, why blind
median cut fails at this, and the judgment calls involved (RMS error versus
perceptual quality, alpha policy, why it refuses to touch files that are
already clean).

## Common mistakes, quick diagnosis

| Symptom | Cause / fix |
|---|---|
| sprite renders but some cells invisible | code missing from palette — `check` names them |
| outline missing on one side | shape touches canvas edge; grow canvas or shift content (`shift(1, 1)` returns a NEW sprite) |
| mirrored sprite is 2× too wide | rows hold full width but `mirror: x` is set — halve the rows or drop the header |
| mirrored sprite missing center column | width is even but you authored the shared-center layout; set `size:` to the odd width you meant |
| GIF shows solid color where glass should be | 1-bit alpha; flatten with `--bg`/`bg:` ([palettes.md](palettes.md)) |
| GIF errors "supports 255 colors" | traced/photo palette; reduce before animating |
| shading appears on the wrong side | `shade`'s `(dx, dy)` points **at the light**, painted rim is opposite ([api.md](api.md)) |
| `rotate_cw()`/`rotate()`/`shift()`/`bend()`/`smear()` "did nothing" | they return new sprites; assign the result |
| animation pops at loop point | first frame duplicated at end — drop the last frame, or build the cycle with `ping_pong()` / `keys(loop=True)` ([animation.md](animation.md)) |
| animation is evenly paced but lifeless | every frame is 1 tick; hold the poses that should read longer ([animation.md](animation.md#holds-variable-timing-without-duplicate-frames)) |
| `gif` refuses: "every GIF frame must be the same size" | frames authored at different sizes; add a `size:` head to normalize them |
| bent sprite loses its edge | `bend` keeps the canvas; grow it first, and bend before `outline()` |
| rotated sprite lost its corners | `rotate` keeps the canvas too; `resized()` bigger before an off-axis turn |
| smear came out the color of the outline | smeared after `outline()`; smear first, outline the result |
| engine gets the frames but not the timing | `sheet --meta` writes the sidecar; a PNG cannot carry a hold ([animation.md](animation.md#handing-it-to-an-engine)) |
| `check` errors on a clip after editing frames | stale `clip:` range; renumber it to the frames that are left |
| clips vanished after `ping_pong()`/`reverse()` | those renumber frames, so the ranges are dropped by design ([api.md](api.md)) |

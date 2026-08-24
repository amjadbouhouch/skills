---
name: pixel-art-toolkit
description: Use it when creating, editing, validating, rendering, animating, or converting pixel-art sprites, icons, tiles, GIFs, and sprite sheets with an editable .pix text format and bundled zero-dependency Python CLI. Do not use it for ordinary raster illustration or photorealistic image generation.
---

# Pixel Art Toolkit

Create production-ready pixel art with the bundled `scripts/pixelart.py` tool. It uses only Python's standard library and produces editable `.pix` sources, PNGs, animated GIFs, sprite sheets, and JSON sheet metadata.

## Keep output in the user's project

Treat this skill directory as a read-only tool dependency.

- Put generated `.pix`, PNG, GIF, sprite-sheet, metadata, and generator files in the user's target project, preferably its existing asset directory.
- If no target project or output path exists, use a temporary directory created with `mktemp -d` and report its absolute path.
- Always pass `-o/--out` to `render`, `gif`, `sheet`, `png2pix`, and `reduce`. Never rely on outputs beside bundled examples.
- Never modify this skill's `examples/` or `references/` while creating user assets.

Resolve `PIXELART_TOOL` to this skill's `scripts/pixelart.py`. Use `python3`; no package installation is required.

```bash
python3 "$PIXELART_TOOL" --help
```

## Choose authoring mode

- Write `.pix` directly for small sprites, expressive asymmetric poses, and palette-focused edits.
- Write a Python generator beside target assets and import bundled API for geometric forms, repeated structures, or parameterized animation.
- Use `png2pix` followed by `reduce` when converting an existing PNG. Treat tracing as a starting point; clean silhouette, palette, and shading afterward.
- Use a hybrid when useful: generate structure, emit `.pix`, then hand-finish deliberate pixels.

Read only relevant references:

- Core workflow and canvas choices: [references/workflow.md](references/workflow.md)
- `.pix` syntax, frames, holds, clips, pivots, and mirroring: [references/pix-format.md](references/pix-format.md)
- CLI commands and flags: [references/cli.md](references/cli.md)
- Palette ramps, alpha, and recoloring: [references/palettes.md](references/palettes.md)
- Lighting, dithering, outlines, and selout: [references/shading.md](references/shading.md)
- Timing, loops, clips, GIFs, and engine handoff: [references/animation.md](references/animation.md)
- Programmatic drawing and transforms: [references/api.md](references/api.md)
- Common generation recipes: [references/cookbook.md](references/cookbook.md)
- Cleaning high-color traces: [references/quantization.md](references/quantization.md)
- Encoder behavior or framework maintenance: [references/internals.md](references/internals.md)

## Creation loop

1. Establish target path, canvas size, intended use, viewpoint, style constraints, background/alpha needs, and required outputs. Use supplied references. Ask only when missing choices would materially change result.
2. Start smaller than instinct suggests: usually 16×16 for icons/tiles, 32×32 for characters/items, 48–64 for detailed subjects. Keep one empty pixel around silhouette when outlining.
3. Build silhouette first. Confirm it reads at 1× before adding detail.
4. Add large material regions, then coherent palette ramps from one light direction.
5. Add sparse details, controlled dithering, highlights, and reflected light. Outline last; use selective outlining where it improves form.
6. Validate every `.pix`, preview it, render with explicit output path, and visually inspect final raster. Revise visible defects rather than stopping after successful command execution.

```bash
python3 "$PIXELART_TOOL" check "$TARGET_ASSETS/hero.pix"
python3 "$PIXELART_TOOL" show "$TARGET_ASSETS/hero.pix"
python3 "$PIXELART_TOOL" render "$TARGET_ASSETS/hero.pix" \
  -o "$TARGET_ASSETS/hero.png"
```

Keep edges crisp: no anti-aliasing, fractional scaling, blurred resizing, or accidental high-color gradients. Scale rendered output by integer nearest-neighbor factors; do not inflate source canvas merely to obtain a larger display image.

## Animation and engine output

Use holds for timing instead of duplicate frames. Keep loops free of duplicate terminal frames. Use named clips and pivots when one file contains several actions.

```bash
python3 "$PIXELART_TOOL" gif "$TARGET_ASSETS/hero.pix" --clip walk --fps 12 \
  -o "$TARGET_ASSETS/hero-walk.gif"
python3 "$PIXELART_TOOL" sheet "$TARGET_ASSETS/hero.pix" --meta \
  -o "$TARGET_ASSETS/hero-sheet.png"
```

GIF supports 1-bit transparency and at most 255 opaque colors when transparency is present. Flatten intentional semi-transparency with `--bg`, or prefer PNG/sprite-sheet output.

## Conversion

```bash
python3 "$PIXELART_TOOL" png2pix "$TARGET_ASSETS/source.png" --size 32 \
  -o "$TARGET_ASSETS/source.pix"
python3 "$PIXELART_TOOL" reduce "$TARGET_ASSETS/source.pix" --colors 16 \
  -o "$TARGET_ASSETS/source-clean.pix"
```

Strip any opaque backdrop before tracing — flood fill from the border using an absolute background model (chroma bound + channel ordering measured from the image), never neighbor-relative tolerance, which drifts through anti-aliased edges and eats the subject. Details in [references/workflow.md](references/workflow.md).

Pick `--size` from the smallest detail that must survive, not from the canvas table: a feature needs 3–4 cells to read, so `target size ≥ source size × 3 / detail's pixel span in the source`. When a small feature (chain, pendant, eye) is missing after `reduce`, render the traced `.pix` first — if the feature is already gone there, the trace resolution is the culprit; retrace larger instead of adjusting `reduce`.

After conversion, run `check`, inspect palette for single-use colors, repair silhouette, and reshade deliberately. Do not present raw tracing as finished pixel art.

## Finish

Report absolute paths for editable source and every requested output. State canvas size, frame/clip count when animated, and any important export constraint such as flattened transparency.

# Palettes & color

A palette is a mapping `code -> RGBA`. Codes live in the grid; colors live in
one place. That separation is why palette swaps, shading passes, and merges
are all trivial here — treat the palette as the *material list* of a sprite.

## Color syntax

Accepted everywhere a color appears (`.pix` palette lines, `bg:`, `--bg`,
`Palette.set`, `parse_color`):

| Form | Example | Notes |
|---|---|---|
| `#rgb` | `#f80` | expands per digit → `#ff8800`, opaque |
| `#rgba` | `#f808` | ditto with alpha → `#ff880088` |
| `#rrggbb` | `#e63946` | opaque |
| `#rrggbbaa` | `#bfe6ff55` | real alpha — see the alpha section |
| decimal | `230,57,70` / `230,57,70,128` | components clamped to 0–255 |
| named | `red`, `navy`, `skin`, `none` | table below |

Named colors (deliberately game-flavored, not CSS):

```
black white gray/grey silver
red darkred orange yellow lime green darkgreen
teal cyan blue navy purple pink
brown tan skin
none            <- fully transparent (useful for bg:)
```

They are starter training wheels — real sprites deserve their own hex ramps.

## Code naming conventions

Codes are free-form tokens (anything without a comma, except `.`). Conventions
that keep files readable:

- **One letter per material**, lowercase: `b` body, `s` stem, `g` grass.
- **Case pairs for ramp steps**: `r` base red, `R` its shadow (mushroom does
  this). For longer ramps, suffix numbers: `s1`, `s2` (orb).
- **`o` for outline** across all your files — it makes `sheet`/`gif` merges
  cleaner (shared code + same color = no rename).
- Multi-character codes are fine (`sk1`, `hair`) — columns just get wider.
  Every cell costs `len(code)+1` characters per row, so short codes keep grids
  scannable.
- Reserve `.` mentally for "hole in the sprite", never "background color". If
  the sprite needs a background, give it a code or use `bg:`.

## Building a ramp

Work in HSV/HSL mentally, output hex:

1. Pick the **base** at full material saturation, mid value.
2. **Shadow steps**: value −15…25% per step, saturation up a touch, hue
   rotated 10–25° toward blue/violet (for neutral scenes) — never just
   "darker".
3. **Light steps**: value +10…20%, saturation *down*, hue rotated toward the
   light color (yellow for sun, cyan for moonlight/magic).
4. **Outline** = one step past the darkest shadow.

The orb ramp annotated (hue °, sat %, val %):

```
w  #f0fdff  H187 S 6 V100   <- near-white, still cyan-tinted
l2 #93dcf5  H195 S40 V 96
l1 #5fa8e8  H208 S59 V 91
b  #3f6fd1  H220 S70 V 82   <- base
s1 #31479c  H228 S69 V 61
s2 #2b2a66  H241 S58 V 40   <- hue keeps rotating cold
o  #131233  H242 S64 V 20
```

Hue climbs monotonically 187° → 242° across the whole ramp; that slide is the
"expensive" look. Compare a naive ramp made by darkening `#3f6fd1` in place —
same hue 220 all the way down — and the shadow side turns to mud.

How many colors? 16×16 sprite: 3–5 including outline. 32×32: 5–8. If `check`
prints `unused palette codes`, delete them — palette hygiene is free. If a file
arrives with *hundreds* of entries it was traced from a raster, not authored —
[quantization.md](quantization.md) explains how to rebuild it into ramps.

## Sharing palettes across files

Option 1 — **one Python palette, many sprites** (the generator pattern):

```python
RAMP = Palette.of({"o": "#131233", "b": "#3f6fd1", "s1": "#31479c"})
for spr in (make_helmet(), make_shield(), make_boots()):
    spr.save_png(f"{spr.name}.png", RAMP, scale=8)
    open(f"{spr.name}.pix", "w").write(spr.to_pix(RAMP))   # embeds only used codes
```

Option 2 — **let `merge_docs` reconcile at the end.** `sheet` and multi-file
`gif` already call it. Rules it applies, in order:

1. Same code + same color in both files → shared, nothing changes.
2. Different code, same color → both codes kept (they don't conflict).
3. **Same code, different color** → the later file's code is renamed with a
   numeric suffix (`d` → `d2`, then `d3`, …) and its grid is rewritten to
   match. Files can never tint each other.

So two files both using `o = #22252b` merge losslessly, while `heart.pix`'s
`d = #a01930` and `slime.pix`'s `d = #276b34` coexist as `d` and `d2`. The
practical consequence: **agree on outline/shadow hexes across a project** and
merged sheets stay small; disagree and they merely get renamed — never wrong,
just noisier.

## Alpha: PNG vs GIF

- **PNG** output is full 8-bit alpha. Semi-transparent codes like the potion's
  glass `G = #bfe6ff55` composite correctly over whatever you put the PNG on.
- **`bg:` / `--bg` flattening** happens *before* encoding, using straight-alpha
  `over()` compositing. `bg: none` is legal and a no-op.
- **GIF** has 1-bit alpha: after flattening (if any), alpha < 128 becomes a
  fully transparent index, alpha ≥ 128 becomes fully opaque **with the alpha
  simply dropped** — `#bfe6ff55` would render as solid `#bfe6ff`, which is
  probably not what you meant. Rule of thumb: a `.pix` that uses fractional
  alpha should either carry a `bg:` header or only ever be rendered to PNG.
- GIF color budget: 256 distinct opaque RGB values, 255 if any pixel is
  transparent (index 0 is reserved for transparency). `gif_bytes` raises if
  you exceed it; `png2pix`-traced files are the usual culprits, and
  `pixelart.py reduce` is the fix ([quantization.md](quantization.md)).

## Palette swaps (free recolors)

Because grids store codes, a recolor is a new palette, not new pixels:

```python
doc = load_pix("examples/ghost.pix")
night = Palette(doc.palette)                      # copy
night.set("b", "#5a79c9").set("d", "#3c56a0").set("p", "#7fa3e8")
doc.frames[0].save_png("ghost_night.png", night, scale=10)
```

Or in a `.pix` file: duplicate the file and edit only the palette block — the
grid diff stays empty, which makes recolors reviewable in git at a glance.
For *structural* swaps (same colors, different assignment), `remap`/`replace`
rewrite the grid instead. Choosing which side to edit — palette or grid — is
90% of recolor hygiene.

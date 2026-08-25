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
2. **Shadow steps**: value −15…25% per step, hue rotated 10–25° toward
   blue/violet (for neutral scenes) — never just "darker". Saturation moves
   whichever way keeps the step *readable*: up for saturated mid-tone
   materials (slime `#4fbb62` S58 → `#276b44` S64), down once value drops far
   enough that high saturation would read as a black hole (orb S70 → S69 → S59).
3. **Light steps**: value +10…20%, saturation *down*, hue rotated toward the
   light color (yellow for sun, cyan for moonlight/magic).
4. **Outline** = one step past the darkest shadow.

**Warm-shadow exception.** "Shadows drift cool" assumes a neutral scene lit by
one white-ish light. Self-luminous and metallic materials invert it — their
shadow is *less* incandescent, not colder, so the hue rotates warm (down
through orange into red). Gold rotates 46° → 39° → 36° (`coin.pix`), a fire
ball 27° → 22° → 18° (`bounce.pix`), an explosion slides 52° → 321° across the
whole heat range (`explosion.pix`). Rule of thumb: rotate toward the *absence*
of the light source. Neutral object, cool light absence → violet. Emitter,
absence of emission → down the blackbody ramp.

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

## Hue relations between materials

Ramps handle one material. A sprite with several needs its *base* hues to
relate too, or it reads as a pile of unrelated objects. The examples all follow
one shape: **one dominant hue, its analogous neighbours, one distant accent.**

| sprite | dominant | analogous | distant accent |
|---|---|---|---|
| `tree.pix` | foliage 126° | — | bark 25° (101° away) |
| `grass.pix` | blades 123° | — | dirt 27° (96° away) |
| `mushroom.pix` | cap 4° | stem 34°, gills 30° | — |
| `potion.pix` | liquid 328° | — | cork 29°, glass 203° |
| `btr82.pix` | olive hull 84° | camo 95°, 107° | glass 192°, hazard 10° |
| `soldier.pix` | leather 27° | khaki 37° | insignia red 4°, trousers 221° |

Working rules:

- **Analogous = within 30°.** Materials that belong to the same object (cap and
  stem, hull and camo patches) sit inside one 30° window. They read as one
  thing lit by one light.
- **One accent, and keep it small.** The distant hue goes on the focal few
  pixels — eyes, insignia, hazard stripe, a glass highlight. Measured shares:
  `btr82`'s hazard red is 29 of 3930 filled pixels (**0.7%**) across 2 of its
  16 codes; `ghost`'s blush is 4 of 186 (**2.2%**). Under ~5% it reads as a
  focal point; past ~25% the composition splits in two and you have two
  subjects instead of one.
- **Budget by size.** 16×16: one dominant family, accent only if it's a handful
  of pixels (`heart` and `slime` are single-family; `ghost` adds a 4-pixel
  blush 64° off). 32×32: dominant + one accent. 64px+: add the analogous
  neighbours.
- **Accents beat saturation for attention.** A distant hue at moderate
  saturation pulls the eye harder than the dominant hue cranked to S100, and it
  doesn't wreck the ramp. Prefer hue contrast over saturation contrast.
- **Outlines: tinted, and usually in the dominant family.** `o` is the cold
  dark end of the dominant ramp (`ghost` 233°, `slime` 158°, `orb` 242°) — never
  neutral black. Pushing it further than the ramp's own end is fine when the
  sprite needs to sit on a busy background: `potion`'s `#1d1030` is 64° off its
  magenta liquid, which lets glass, cork, and liquid share one outline. See the
  `merge_docs` note below for why agreeing on one outline hex per project also
  keeps merged sheets small.

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

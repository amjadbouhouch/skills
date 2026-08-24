# Internals

`pixelart.py` has zero dependencies: PNG and GIF are written (and PNG read)
from scratch with `zlib` and `struct`. This page explains those encoders — both
as documentation of the limits you'll hit and as a compact reference to two
file formats worth knowing.

## PNG writer — `png_bytes(rows, scale=1)`

Output is always **8-bit RGBA, color type 6, non-interlaced** — the simplest
universally-supported flavor:

```
89 50 4E 47 0D 0A 1A 0A      signature
IHDR  width height 8 6 0 0 0 (bit depth 8, color type 6 = truecolor+alpha)
IDAT  zlib-compressed scanlines, one chunk
IEND
```

- Every scanline is prefixed with filter type `0` (None). Real encoders choose
  per-row filters to help compression; for flat-color pixel art the win is
  small and `zlib.compress(..., 9)` on raw rows is plenty.
- **Nearest-neighbor scaling is done in the raw bytes**: each pixel's 4 bytes
  are repeated `scale` times, each row `scale` times, *then* compressed. Crisp
  pixels at any size, and the repetition compresses to almost nothing.
- Chunk framing: `len (4BE) + tag (4) + data + crc32(tag + data)`.

## PNG reader — `read_png(path)`

Reads the subset needed to round-trip its own output plus common editor
exports: **8-bit** grayscale (type 0), RGB (2), RGBA (6), non-interlaced.
Rejected: palette-indexed (3), gray+alpha (4), 16-bit, interlaced (Adam7).

It does implement **all five scanline filters** (None/Sub/Up/Average/Paeth),
reconstructing each row against the previous — necessary because real-world
encoders always filter. Grayscale expands to opaque RGBA on the way out, so
callers only ever see `(r, g, b, a)` rows.

If `png2pix` says `unsupported PNG (bits=… type=3 …)`, re-export the source as
32-bit/RGBA ("save as PNG-24/32" in most editors).

## GIF writer — `gif_bytes(frames_rows, scale, delay_cs, loop)`

GIF89a with one **global color table** (GCT) shared by all frames:

```
GIF89a
logical screen descriptor    W, H, GCT flag + size bits
global color table           2^n RGB triples, zero-padded
[NETSCAPE2.0 app extension]  written when >1 frame or loop==0; loop count LE16
per frame:
  graphic control extension  disposal=2 (restore to background),
                             transparency flag + index 0, delay in cs
  image descriptor           full-frame (0,0,W,H), no local table
  LZW-compressed indices     min code size byte + 255-byte sub-blocks
trailer 3B
```

Design decisions and their consequences:

- **Color table**: all frames are scanned first; distinct opaque RGB values
  get indices. If any pixel has alpha < 128, index 0 is reserved as the
  transparent color (a black entry never drawn), leaving **255** usable
  colors, else **256**. Exceeding the budget raises — no silent quantization.
  The table is padded to the next power of two, as the format requires.
- **1-bit alpha** is a GIF format fact, not a shortcut: a pixel is either the
  transparent index or an opaque color. The threshold here is 128. Flatten
  semi-transparency first ([palettes.md](palettes.md)).
- **Disposal 2** (restore to background) between frames means every frame
  redraws fully — no delta frames, no trails, transparency-safe. Simple and
  correct; file size is the tradeoff and it's negligible at sprite sizes.
- Scaling repeats indices horizontally and rows vertically before compression,
  same trick as PNG.

## The LZW encoder — `_lzw(indices, min_code_size)`

GIF's variant of LZW with variable-width codes, written LSB-first
(`_BitsLSB` accumulates bits little-endian and flushes bytes):

- Alphabet starts at `2^min_code_size` symbols plus two specials: CLEAR and
  END. `min_code_size = max(2, bits_needed_for_palette)`.
- Standard greedy match: extend the current sequence while it exists in the
  table; emit the longest match's code; add `match + next` as a new entry.
- **Code width grows when the table outgrows it** — with the subtle off-by-one
  every GIF implementer trips over: the width bump happens at
  `next_code > (1 << code_size)` rather than `>=`, because the *decoder*
  builds each table entry one step behind the encoder ("decoder lags one
  entry" in the source). Get this wrong and most viewers show garbage after
  the first few rows.
- At 4095 entries (12-bit max) the encoder emits CLEAR and resets the table —
  the simple, always-correct policy.
- Compressed bytes are chopped into ≤255-byte sub-blocks, each prefixed by its
  length, terminated by a zero block.

## Alpha compositing — `over(src, dst)`

Straight (non-premultiplied) source-over, used by `bg:` flattening:

```
a_out = a_s + a_d(1 - a_s)
c_out = (c_s·a_s + c_d·a_d(1 - a_s)) / a_out
```

Fast paths for fully opaque / fully transparent sources; fully transparent
result short-circuits to `(0,0,0,0)`. Rounding is per-channel `round()` —
composites are stable but not bit-exact against premultiplied pipelines; fine
for flattening, don't build a blend engine on it.

## Terminal preview — `ansi_preview`

Each terminal character cell shows **two** grid rows using `▀` (upper half
block): foreground color = top pixel, background color = bottom pixel, via
24-bit SGR codes (`38;2;r;g;b` / `48;2;r;g;b`). Transparent cells render as a
two-tone checkerboard (computed per 2×2 block) so holes are distinguishable
from dark paint. Requires truecolor support; under plain 16-color terminals
you'll see approximated colors or escape junk.

## Performance envelope

Everything is pure-Python lists of strings — clarity over speed:

- Costs scale with `w·h` per operation (drawing, shading, outline are all
  full-grid or region scans). At the intended sizes (≤64px, a few dozen
  frames) everything is instant; at 512×512 traced photos you'll feel it.
- `png2pix` on large PNGs is the slowest path (per-pixel dict work after
  full-image unfiltering). Use `--size` to downsample early.
- Memory: a cell is a Python string reference (~8 bytes) — a 64×64 sprite is
  trivial, a 4096×4096 grid is not the tool for that.

## Extending the module

Patterns that fit the existing design if you add features:

- New drawing primitives: take `(…, code, only=None)`, route through
  `self.set(x, y, code, only)` to inherit clipping + masking, `return self`.
- New output formats: consume `to_rgba()` rows (the palette/code layer stays
  untouched). That's exactly how PNG, GIF and ANSI already share everything
  upstream of encoding.
- New file-format keys: parse_pix already keeps unknown head keys in
  `doc.meta` — a tool reading `doc.meta["hitbox"]` needs no parser changes.

#!/usr/bin/env python3
"""Build shinobi.pix - 32x32 character, 4-frame idle (headband tail only).

A worked example of the hue rules in references/palettes.md:

  dominant   indigo garb   218 -> 232 -> 247 -> 256 deg   (38 deg across the ramp)
  analogous  steel wraps   208 -> 222                     (24 deg off the garb base)
  accent     scarf red     358 -> 352 -> 340              (120 deg off, ~10% of pixels)

10 codes on a 32x32 sprite - two over the budget palettes.md gives for this
size, spent on the third ramp step the scarf needs to read as cloth. Everything
sits in one figure lit from the upper left.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from pixelart import Anim, Palette, Sprite  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

PAL = Palette.of({
    "o":  "#150f26",   # outline: coldest end of the garb ramp, never black
    "gd": "#241f4a",   # garb shadow  (H247 S58 V29)
    "g":  "#343c73",   # garb base    (H232 S55 V45)
    "gl": "#526e9e",   # garb light   (H218 S48 V62)
    "wd": "#4c5770",   # wrap shadow  (H222 S32 V44) - analogous, desaturated
    "w":  "#7d94a8",   # wraps/sash   (H208 S26 V66)
    "rd": "#66122e",   # scarf shadow (H340 S82 V40)
    "r":  "#9e2030",   # scarf        (H352 S80 V62) - the accent
    "rl": "#c7383c",   # scarf light  (H358 S72 V78)
    "e":  "#faf6e1",   # eyes
})


def shinobi(tail_dy=(0, 0, 0, 0)) -> Sprite:
    """tail_dy: row offset per tail segment. The figure itself never moves."""
    s = Sprite(32, 32, name="shinobi")
    y = 0

    # ---- hood ------------------------------------------------------------
    s.rect(12, 4 + y, 8, 1, "g")                        # crown, stepped in twice
    s.rect(11, 5 + y, 10, 1, "g")
    s.rect(10, 6 + y, 12, 8, "g")                       # cowl block
    s.rect(11, 14 + y, 10, 1, "g")                      # jaw

    # eye slit: two whites on the dark cowl, shadowed bridge between them
    s.rect(12, 10 + y, 2, 2, "e")
    s.rect(18, 10 + y, 2, 2, "e")
    s.rect(14, 10 + y, 4, 2, "gd")
    s.rect(11, 12 + y, 10, 1, "gd")                     # seam where the mask folds

    # ---- headband + trailing scarf --------------------------------------
    s.rect(10, 8 + y, 13, 2, "r")
    s.rect(10, 9 + y, 13, 1, "rd")                      # band underside
    s.rect(11, 8 + y, 5, 1, "rl")                       # lit half of the band

    # Segments overlap by one column and step down one row each, so adjacent
    # rows may never differ by more than 2 or the cloth visibly comes apart.
    # That is why the offsets are a hand-checked table, not drift * segment.
    tail = [(23, 8, 3), (25, 9, 3), (27, 10, 3), (29, 11, 2)]
    for (tx, ty, n), dy in zip(tail, tail_dy):
        s.rect(tx, ty + y + dy, n, 2, "r")
        s.rect(tx, ty + y + dy + 1, n, 1, "rd")

    # ---- torso -----------------------------------------------------------
    s.rect(14, 15 + y, 4, 1, "g")                       # neck
    s.rect(10, 16 + y, 12, 8, "g")                      # chest to hips
    s.set(10, 16 + y, ".").set(21, 16 + y, ".")         # sloped shoulders
    s.set(10, 19 + y, ".").set(21, 19 + y, ".")         # waist pulls in one pixel
    s.set(10, 20 + y, ".").set(21, 20 + y, ".")

    s.rect(10, 21 + y, 12, 2, "w")                      # sash
    s.rect(10, 22 + y, 12, 1, "wd")
    s.rect(14, 21 + y, 3, 3, "w")                       # knot, hanging past the sash
    s.set(15, 23 + y, "wd")

    # ---- arms ------------------------------------------------------------
    # Arms are painted in the SHADOW step, not the base: value separates them
    # from the chest with no interior line, which would read as a gap at 32px.
    for ax in (8, 22):
        s.rect(ax, 17 + y, 2, 5, "gd")                  # upper arm
        s.rect(ax, 22 + y, 2, 2, "wd")                  # forearm wrap
        s.rect(ax, 24 + y, 2, 1, "w")                   # fist, wrapped

    # ---- legs ------------------------------------------------------------
    for lx in (11, 17):
        s.rect(lx, 24 + y, 4, 6, "g")
        s.rect(lx, 27 + y, 4, 1, "w")                   # shin wrap
        s.rect(lx, 29 + y, 4, 1, "gd")                  # tabi boot
    s.rect(15, 24 + y, 2, 5, ".")                       # gap between the legs

    # ---- light from the upper left ---------------------------------------
    s.shade("gd", dx=-2, dy=-2, only="g")               # far rim darkens
    s.shade("gl", dx=2, dy=2, only="g")                 # near rim catches light
    s.shade("wd", dx=-2, dy=-2, only="w")
    s.rect(11, 6 + y, 3, 2, "gl")                       # cowl highlight
    s.outline("o")
    return s


# lifted -> level -> dropped, ping-ponged into lift level drop level. Row gaps
# stay <= 2 in every pose; verified by gen_shinobi's own connectivity check.
KEYS = [(0, -1, -1, -2), (0, 0, 0, 0), (0, 0, 1, 1)]
anim = Anim([shinobi(k) for k in KEYS], PAL, name="shinobi", scale=10).ping_pong()

for pose in KEYS:                                       # cloth stays one piece
    ys = [b + d for b, d in zip((8, 9, 10, 11), pose)]
    gaps = [abs(b - a) for a, b in zip(ys, ys[1:])]
    assert max(gaps) <= 2, f"tail tears at {pose}: gaps {gaps}"

path = os.path.join(HERE, "shinobi.pix")
with open(path, "w", encoding="utf-8") as f:
    f.write(anim.to_pix())
print("wrote", path)
anim[0].save_png(os.path.join(HERE, "shinobi.png"), PAL, scale=10)
print("wrote", os.path.join(HERE, "shinobi.png"))
anim.save_gif(os.path.join(HERE, "shinobi.gif"), fps=4)
print("wrote", os.path.join(HERE, "shinobi.gif"))

#!/usr/bin/env python3
"""Build the example .pix files with the Sprite API (shows the programmatic side)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from pixelart import Palette, Sprite  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def write(name, text):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", path)


# ---------------------------------------------------------------- heart (32x32)
pal = Palette.of({"o": "#4a0d1c", "r": "#e63946", "d": "#a01930", "w": "#ffd7dd"})
h = Sprite(32, 32, name="heart")
h.disc(9.5, 12, 6.5, "r").disc(21.5, 12, 6.5, "r")
for y in range(12, 29):                              # V-shaped bottom
    t = (y - 12) / 16
    lo, hi = round(3 + t * 12.5), round(28 - t * 12.5)
    for x in range(lo, hi + 1):
        h.set(x, y, "r")
h.shade("d", dx=-2, dy=-2, only="r")                 # rim facing away from the light
h.shade("d", dx=-1, dy=-3, only="r")
h.disc(9.5, 9, 2.4, "w", only="r")                   # specular highlight
h.disc(8.5, 8, 1.2, "w", only=("r", "w"))
h.outline("o")
write("heart.pix", h.to_pix(pal, scale=10))

# --------------------------------------------------------------------- slime (anim)
pal = Palette.of({"o": "#123018", "g": "#4fbb62", "l": "#8ff09a", "d": "#276b34",
                  "w": "#ffffff", "k": "#111111"})


def slime(squash: int) -> Sprite:
    s = Sprite(32, 32)
    top, w = 8 + squash, 12 + squash
    for y in range(top, 28):
        t = (y - top) / (28 - top)
        half = round(w * (0.45 + 0.75 * t ** 0.6))
        for x in range(16 - half, 16 + half):
            s.set(x, y, "g")
    s.disc(11, top + 4, 3, "l")
    for y in range(23, 28):                     # base shadow
        for x in range(32):
            if s.get(x, y) == "g":
                s.set(x, y, "d")
    ey = top + 6
    for ex in (12, 19):
        s.rect(ex, ey, 3, 4, "w")
        s.rect(ex + 1, ey + 1, 2, 2, "k")
    s.px("k", 15, ey + 6, 16, ey + 6, 14, ey + 5, 17, ey + 5)   # smile
    return s.outline("o")


frames = [slime(0), slime(3)]
doc = frames[0].to_pix(pal, scale=10)
write("slime.pix", doc.rstrip("\n") + "\n---\n" + frames[1].rows_text() + "\n")

# ---------------------------------------------------------------------- coin (spin)
pal = Palette.of({"o": "#4a2c00", "y": "#ffd23f", "a": "#c98a12", "w": "#fff6c8"})
out = []
for wid in (11, 8, 4, 1, 4, 8):
    s = Sprite(32, 32)
    for y in range(6, 26):
        t = abs((y - 15.5) / 10.0)
        half = max(1, round(wid * (1 - t * t) ** 0.5))
        for x in range(16 - half, 16 + half):
            s.set(x, y, "y")
    for y in range(6, 26):
        for x in range(16, 32):
            if s.get(x, y) == "y" and s.get(x + 1, y) != "y":
                s.set(x, y, "a")
    if wid > 3:
        s.rect(13, 12, 2, 6, "w")
    out.append(s.outline("o"))
head = out[0].to_pix(pal, scale=10).rstrip("\n")
write("coin.pix", head + "\n" + "".join("---\n" + f.rows_text() + "\n" for f in out[1:]))

# ------------------------------------------------------- mushroom (mirror-x export)
pal = Palette.of({"o": "#2b1219", "r": "#e04a3f", "R": "#a52b26", "w": "#fff3e2",
                  "s": "#f2dcc0", "d": "#c9a98a"})
m = Sprite(32, 32, name="mushroom")
for y in range(4, 17):                                  # cap dome
    t = (y - 4) / 12
    half = round(3 + 12.5 * (t ** 0.55))
    for x in range(16 - half, 16 + half):
        m.set(x, y, "r")
for y in range(16, 28):                                 # stem
    half = 5 if y < 24 else 6 + (y - 24) // 2
    for x in range(16 - half, 16 + half):
        m.set(x, y, "s")
# only the left half survives the mirror, so shade/spot on the left or vertically
m.disc(9, 9, 2.0, "w", only="r").disc(13, 5, 1.2, "w", only="r")
m.disc(4, 13, 1.5, "w", only="r")
m.shade("R", dx=0, dy=-2, only="r")
m.shade("d", dx=2, dy=0, only="s")
m.rect(0, 16, 32, 1, "R", only="s")                     # cap gill line
m.outline("o")
write("mushroom.pix", m.to_pix(pal, scale=10, mirror="x"))

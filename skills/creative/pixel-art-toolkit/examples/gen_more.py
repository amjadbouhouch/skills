#!/usr/bin/env python3
"""Build the second batch of examples: shading, animation, alpha, tiles, scenery.

    orb.pix     - shading study: 6-step ramp, dithered terminator, selout
    bounce.pix  - 6-frame bouncing ball (squash & stretch)
    potion.pix  - semi-transparent glass (PNG alpha; GIF needs --bg)
    grass.pix   - 16x16 seamless terrain tile with dithered transition
    tree.pix    - 40x64, 8-frame tall tree swaying in wind

Also renders examples/orb_stages.png, the step-by-step strip used by
docs/shading.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from pixelart import Palette, Sprite, sheet  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def write(name, text):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", path)


def dither(s, a, b):
    """Checkerboard-blend the `a` side of every a|b boundary (1px fringe).
    Classic way to soften a band edge without adding a palette color."""
    hits = []
    for y in range(s.h):
        for x in range(s.w):
            if s.g[y][x] != a or (x + y) % 2:
                continue
            if any(s.get(x + dx, y + dy) == b for dx, dy in NEIGH4):
                hits.append((x, y))
    for x, y in hits:
        s.g[y][x] = b
    return s


# ----------------------------------------------------------------- orb (32x32)
# Light sits up-left. Ramp: s2 -> s1 -> b -> l1 -> l2 -> w, hue-shifted
# (shadows lean violet, lights lean cyan) instead of plain darker/lighter blue.
ORB = Palette.of({
    "o":  "#131233",   # outline: darkest ramp step, not pure black
    "s2": "#2b2a66",   # core shadow (violet lean)
    "s1": "#31479c",   # shadow
    "b":  "#3f6fd1",   # base
    "l1": "#5fa8e8",   # light
    "l2": "#93dcf5",   # bright light (cyan lean)
    "w":  "#f0fdff",   # specular
})


def orb(stage: int = 5) -> Sprite:
    """stage 1=flat, 2=+ramp bands, 3=+dither, 4=+specular & rim, 5=+selout."""
    s = Sprite(32, 32, name="orb")
    cx = cy = 15.5
    if stage < 2:
        s.disc(cx, cy, 13.2, "b")
        return s.outline("o")
    # nested discs, each smaller and pushed toward the light
    s.disc(cx, cy, 13.2, "s2")
    s.disc(cx - 1.1, cy - 1.1, 12.3, "s1", only="s2")
    s.disc(cx - 2.3, cy - 2.3, 10.7, "b", only="s1")
    s.disc(cx - 3.4, cy - 3.4, 8.3, "l1", only="b")
    s.disc(cx - 4.4, cy - 4.4, 5.7, "l2", only="l1")
    if stage >= 3:                       # soften the two widest terminators
        dither(s, "b", "s1")
        dither(s, "s1", "s2")
    if stage >= 4:
        s.disc(10.2, 9.4, 2.3, "w", only=("l2", "l1"))   # specular hotspot
        s.px("w", 13, 6, 6, 13)                          # sparkle satellites
        s.shade("s1", dx=-2, dy=-2, only="s2")           # reflected rim light
    s.outline("o")
    if stage >= 5:
        s.shade("s1", dx=2, dy=2, only="o")              # selout: lit-side outline
    return s


final = orb()
write("orb.pix", final.to_pix(ORB, scale=10))
strip = sheet([orb(i) for i in range(1, 6)], cols=5, pad=2)
strip.save_png(os.path.join(HERE, "orb_stages.png"), ORB, scale=6)
print("wrote", os.path.join(HERE, "orb_stages.png"))

# ------------------------------------------------------------- bounce (6 frames)
# Squash & stretch: the ball keeps its volume but not its shape. Spacing does
# the timing: frames bunch up near the top (slow) and spread out near impact.
BALL = Palette.of({
    "o": "#3a1404", "b": "#f4801f", "d": "#c2571b",
    "l": "#ffc14d", "w": "#fff3d9", "g": "#2c2c34",
})


def ball(cy: float, sq: float) -> Sprite:
    """sq > 0 squash (wide), sq < 0 stretch (tall), 0 round. Ground at y=28."""
    s = Sprite(32, 32)
    r = 6.4 - abs(sq) * 0.9
    if sq > 0:      # two discs side by side merge into a wide blob
        s.disc(15.5 - sq * 2.2, cy, r, "b").disc(15.5 + sq * 2.2, cy, r, "b")
    elif sq < 0:    # stacked discs make a tall blob
        s.disc(15.5, cy + sq * 2.2, r, "b").disc(15.5, cy - sq * 2.2, r, "b")
    else:
        s.disc(15.5, cy, r, "b")
    s.shade("d", dx=-2, dy=-2, only="b")            # shadow rim, light up-left
    s.disc(13 - sq, cy - r * 0.42, r * 0.55, "l", only="b")
    s.disc(12 - sq, cy - r * 0.55, r * 0.26, "w", only=("l", "b"))
    # contact shadow: darker + wider the closer the ball is to the ground
    near = max(0.0, 1.0 - (26 - cy) / 18.0)
    half = round(3 + 5 * near)
    if near > 0.05:
        s.rect(16 - half, 29, half * 2, 1, "g")
    return s.outline("o")


KEYS = [(9.0, 0.0), (14.0, -0.6), (21.0, -1.2), (24.6, 1.4), (19.0, -0.9), (11.5, -0.3)]
frames = [ball(cy, sq) for cy, sq in KEYS]
head = frames[0].to_pix(BALL, scale=10).rstrip("\n")
write("bounce.pix", head + "\n" + "".join("---\n" + f.rows_text() + "\n" for f in frames[1:]))

# ------------------------------------------------------------- potion (32x32)
# Semi-transparent glass: PNG keeps real alpha; GIF is 1-bit alpha, so animate
# or gif this only with --bg (or a bg: header) to flatten first.
POTION = Palette.of({
    "o": "#1d1030",            # outline
    "G": "#bfe6ff55",          # glass (33% alpha)
    "e": "#e8f7ff99",          # glass edge highlight (60% alpha)
    "p": "#c2317e",            # potion body
    "P": "#8f1f5c",            # potion shadow
    "m": "#f26fae",            # potion surface
    "w": "#ffe3f2",            # bubbles / sparkle
    "k": "#8b5a2b",            # cork
    "K": "#5e3a18",            # cork shadow
})

pot = Sprite(32, 32, name="potion")
pot.disc(15.5, 19.5, 9.6, "G")                        # round flask body
pot.rect(12, 6, 8, 6, "G")                            # neck
for y in range(11, 15):                               # flare neck into body
    hw = 4 + (y - 10)
    pot.rect(16 - hw, y, hw * 2, 1, "G")
pot.rect(12, 3, 8, 4, "k").rect(12, 5, 8, 2, "K", only="k")   # cork
for y in range(17, 29):                               # liquid fills lower body
    for x in range(32):
        if pot.get(x, y) == "G":
            pot.set(x, y, "p")
pot.rect(4, 17, 24, 1, "m", only="p")                 # liquid surface line
pot.shade("P", dx=-2, dy=-2, only="p")                # liquid shadow rim
pot.px("w", 12, 20, 18, 23, 14, 25).px("w", 19, 19)   # bubbles
pot.line(9, 12, 9, 22, "e", only="G")                 # glass shine, left wall
pot.line(10, 10, 10, 13, "e", only="G")
pot.outline("o")
write("potion.pix", pot.to_pix(POTION, scale=10))

# ------------------------------------------------------------- grass (16x16 tile)
# Seamless: every feature is placed with x % 16 / y % 16 arithmetic, so edges
# continue into the next copy. Check with:  sheet grass.pix grass.pix --cols 2
TILE = Palette.of({
    "g": "#3f9d44", "G": "#2f7a37", "h": "#63c74d",
    "d": "#8a5a34", "D": "#6b422a", "p": "#a9713f",
})

t = Sprite(16, 16, name="grass")
t.rect(0, 0, 16, 10, "g")
t.rect(0, 10, 16, 6, "d")
for x in range(16):                                   # ragged, wrap-safe soil line
    if (x * 5) % 3 == 0:
        t.set(x, 10, "g")
    if (x * 7) % 4 == 0:
        t.set(x, 9, "d")
dither(t, "d", "g")                                   # soften the transition
for x, y in ((2, 2), (7, 4), (12, 1), (10, 6), (4, 7), (14, 5)):
    t.px("h", x, y, (x + 1) % 16, y)                  # light grass tufts (wrap x)
for x, y in ((1, 5), (9, 2), (13, 8), (6, 8)):
    t.set(x, y, "G")                                  # dark grass specks
for x, y in ((3, 12), (8, 14), (13, 11), (1, 14), (11, 13)):
    t.set(x, y, "D")                                  # dirt clumps
t.px("p", 5, 11, 6, 11, 12, 15, 13, 15)               # pebbles
write("grass.pix", t.to_pix(TILE, scale=10))

# ---------------------------------------------------------- tall tree (32x64)
# A taller canvas gives the silhouette room to read without making the trunk
# as wide as the canopy. Light comes from the upper-left, matching the orb.
TREE = Palette.of({
    "o": "#172117",   # outline
    "G": "#285238",   # leaf shadow
    "g": "#3f7f45",   # leaf base
    "l": "#69a94f",   # leaf light
    "h": "#a1cf63",   # leaf sparkle
    "B": "#3b2418",   # bark shadow
    "b": "#684126",   # bark base
    "t": "#986238",   # bark light
})

tree = Sprite(32, 64, name="tree")

# Overlapping discs form one irregular, tapered crown rather than a single
# geometric blob. Outer rim shading unifies the clusters.
for cx, cy, radius in (
    (15.5, 7.5, 5.5),
    (10.0, 14.0, 7.0), (21.0, 14.5, 7.0),
    (6.5, 23.0, 6.5), (15.5, 21.5, 9.0), (25.0, 23.5, 6.0),
    (10.0, 30.0, 7.5), (20.5, 30.5, 8.0),
):
    tree.disc(cx, cy, radius, "g")
tree.shade("G", dx=-2, dy=-2, only="g")

# Broad light pools and sparse sparkle pixels keep foliage readable at 1x.
tree.disc(10.0, 12.0, 3.5, "l", only="g")
tree.disc(6.5, 21.0, 3.0, "l", only="g")
tree.disc(15.0, 18.0, 3.2, "l", only="g")
tree.disc(12.0, 27.0, 2.5, "l", only="g")
tree.px("h", 8, 10, 9, 10, 5, 20, 13, 16, 10, 26)
tree.px("G", 21, 11, 24, 20, 18, 27, 23, 30, 7, 29)

# Forked branches emerge from a narrow trunk. Roots flare at ground level.
tree.line(15, 39, 7, 27, "b").line(16, 39, 24, 25, "b")
tree.line(14, 37, 10, 31, "t").line(17, 37, 21, 30, "B")
for y in range(32, 59):
    half = 2 + (y - 32) // 12
    center = 15 if y < 45 else 16
    tree.rect(center - half, y, half * 2 + 1, 1, "b")
tree.shade("B", dx=-2, dy=-1, only="b")
tree.line(13, 37, 13, 54, "t", only="b")
tree.line(14, 45, 14, 57, "t", only="b")
tree.line(12, 58, 7, 61, "b").line(18, 58, 24, 61, "b")
tree.line(12, 59, 9, 61, "t").line(19, 59, 22, 61, "B")

# Split foliage from wood before outlining. Wind moves leaves only; trunk,
# branches, and roots stay pixel-identical in every frame.
foliage = Sprite(32, 64)
wood = Sprite(32, 64)
for y in range(tree.h):
    for x, code in enumerate(tree.g[y]):
        if code in ("G", "g", "l", "h"):
            foliage.set(x, y, code)
        elif code != ".":
            wood.set(x, y, code)


def wind_frame(sway: int) -> Sprite:
    frame = Sprite(40, 64, name="tree")
    for y in range(foliage.h):
        bend = ((38 - y) / 38) ** 0.7 if y < 38 else 0.0
        dx = round(sway * bend)
        for x, code in enumerate(foliage.g[y]):
            if code != ".":
                frame.set(x + 4 + dx, y, code)
    frame.blit(wood, 4, 0)
    return frame.outline("o")


# Prevailing wind: fast rightward impulse, brief peak load, slower elastic
# recovery, then a small counter-sway before next gust.
WIND_SWAY = (0, 1, 3, 3, 2, 1, 0, -1)
wind_frames = [wind_frame(sway) for sway in WIND_SWAY]
head = wind_frames[0].to_pix(TREE, scale=8).rstrip("\n")
write("tree.pix", head + "\n" + "".join(
    "---\n" + frame.rows_text() + "\n" for frame in wind_frames[1:]
))

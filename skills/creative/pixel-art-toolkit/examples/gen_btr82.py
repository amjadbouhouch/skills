#!/usr/bin/env python3
"""Generate an arcade BTR-82 sprite viewed directly from above."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from pixelart import Palette, Sprite  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))

PALETTE = Palette.of({
    "o": "#172018",   # armor outline
    "s": "#344329",   # armor shadow
    "b": "#566b36",   # armor base
    "l": "#78904b",   # armor light
    "h": "#aab56b",   # edge highlight
    "cd": "#2c3b28",  # dark camouflage
    "ct": "#8a7442",  # tan camouflage
    "ts": "#675732",  # tan shadow
    "ro": "#111613",  # tire outline
    "r": "#252b27",   # tire rubber
    "rl": "#414940",  # tire highlight
    "m": "#777b68",   # metal
    "md": "#3d433b",  # dark metal
    "g": "#355861",   # glass/optics
    "gl": "#75a7a5",  # optic glint
    "x": "#9d352c",   # identification red
    "xl": "#d75a42",  # identification highlight
})


def polygon(sprite, points, code, only=None):
    """Fill polygon using even-odd scanline intersections."""
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(sprite.h - 1, max(ys)) + 1):
        intersections = []
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            if (yi > y) != (yj > y):
                x = xi + (y - yi) * (xj - xi) / (yj - yi)
                intersections.append(x)
            j = i
        intersections.sort()
        for i in range(0, len(intersections) - 1, 2):
            x0 = int(intersections[i] + 0.999999)
            x1 = int(intersections[i + 1])
            for x in range(x0, x1 + 1):
                sprite.set(x, y, code, only=only)
    return sprite


def rounded_rect(sprite, x, y, w, h, radius, code):
    sprite.rect(x + radius, y, w - radius * 2, h, code)
    sprite.rect(x, y + radius, w, h - radius * 2, code)
    sprite.disc(x + radius, y + radius, radius, code)
    sprite.disc(x + w - radius - 1, y + radius, radius, code)
    sprite.disc(x + radius, y + h - radius - 1, radius, code)
    sprite.disc(x + w - radius - 1, y + h - radius - 1, radius, code)
    return sprite


def wheel(sprite, x, y, left):
    """Build one chunky tire with tread and armored hub."""
    rounded_rect(sprite, x, y, 10, 15, 3, "ro")
    rounded_rect(sprite, x + 1, y + 1, 8, 13, 2, "r")
    # Tread catches light on vehicle's left side.
    edge_x = x + 1 if left else x + 7
    sprite.rect(edge_x, y + 3, 2, 3, "rl", only="r")
    sprite.rect(edge_x, y + 9, 2, 3, "rl", only="r")
    sprite.rect(x + 3, y + 5, 4, 5, "md")
    sprite.rect(x + 4, y + 6, 2, 3, "m")


def panel(sprite, x, y, w, h):
    sprite.frame(x, y, w, h, "s")
    sprite.line(x + 2, y + 2, x + w - 3, y + 2, "l", only="b")


def build_btr82():
    s = Sprite(64, 96, name="btr82")

    # Eight wheels sit behind hull armor.
    for y in (19, 36, 53, 70):
        wheel(s, 4, y, True)
        wheel(s, 50, y, False)

    # Angular hull. Outer shadow band remains visible on lower-right edge.
    outer = [(27, 7), (36, 7), (48, 17), (53, 31), (53, 77),
             (47, 88), (16, 88), (10, 77), (10, 31), (15, 17)]
    inner = [(27, 9), (35, 9), (46, 18), (50, 31), (50, 76),
             (45, 85), (17, 85), (13, 76), (13, 31), (18, 18)]
    polygon(s, outer, "o")
    polygon(s, inner, "s")
    polygon(s, [(26, 10), (34, 10), (44, 19), (48, 32), (48, 74),
                (43, 82), (18, 82), (15, 74), (15, 31), (20, 18)], "b")

    # Top-left armor bevel and front glacis.
    polygon(s, [(20, 18), (27, 10), (30, 10), (22, 23), (18, 37),
                (15, 37), (15, 31)], "l", only="b")
    s.line(24, 13, 34, 13, "h", only=("b", "l"))
    s.line(18, 23, 15, 36, "h", only=("b", "l"))
    polygon(s, [(21, 18), (42, 18), (47, 31), (16, 31)], "l", only="b")
    polygon(s, [(24, 20), (39, 20), (43, 29), (19, 29)], "ct",
            only=("b", "l"))
    s.line(20, 29, 43, 29, "ts", only="ct")

    # Camouflage patches remain broad enough to read at gameplay scale.
    s.disc(18, 44, 8, "cd", only=("b", "l"))
    s.disc(22, 49, 6, "cd", only=("b", "l"))
    s.disc(45, 59, 7, "ct", only=("b", "l"))
    s.disc(40, 64, 5, "ct", only=("b", "l"))
    s.disc(20, 76, 7, "ct", only=("b", "l"))
    s.disc(47, 37, 5, "cd", only=("b", "l"))

    # Driver and commander's hatches.
    polygon(s, [(20, 22), (27, 21), (28, 28), (19, 28)], "o")
    polygon(s, [(21, 23), (26, 23), (26, 26), (20, 26)], "g")
    s.line(21, 23, 25, 23, "gl", only="g")
    polygon(s, [(36, 21), (43, 22), (44, 28), (35, 28)], "o")
    polygon(s, [(37, 23), (42, 23), (43, 26), (37, 26)], "g")
    s.set(38, 23, "gl", only="g")

    # Turret base, faceted cupola, centered 30 mm cannon.
    s.disc(31.5, 40.5, 12.5, "o")
    s.disc(31.5, 40.5, 10.8, "s")
    s.disc(30.2, 39.0, 9.3, "b", only="s")
    polygon(s, [(24, 34), (29, 30), (37, 32), (41, 38),
                (39, 46), (31, 50), (23, 45), (21, 39)], "l", only="b")
    polygon(s, [(33, 33), (39, 37), (39, 45), (32, 48)], "cd",
            only=("b", "l"))
    s.disc(31, 39, 4, "o")
    s.disc(31, 39, 3, "b")
    s.rect(28, 11, 7, 25, "o")
    s.rect(30, 10, 3, 25, "md")
    s.rect(30, 9, 3, 3, "m")
    s.rect(30, 13, 1, 20, "h", only="md")
    s.rect(26, 35, 3, 5, "g")
    s.set(26, 35, "gl")
    s.rect(37, 38, 3, 3, "md")

    # Troop roof hatches with hinges and handles.
    panel(s, 18, 53, 13, 15)
    panel(s, 33, 53, 13, 15)
    s.line(24, 54, 24, 66, "cd")
    s.line(39, 54, 39, 66, "cd")
    s.rect(20, 58, 5, 2, "m")
    s.rect(35, 58, 5, 2, "m")
    s.px("h", 19, 54, 29, 54, 34, 54, 44, 54)

    # Engine deck, cooling slats, rear access hardware.
    s.rect(18, 71, 28, 11, "s")
    s.rect(19, 71, 26, 2, "l")
    for x in range(20, 45, 4):
        s.rect(x, 74, 2, 6, "o")
        s.rect(x, 74, 1, 5, "md")
    s.rect(14, 68, 3, 13, "o")
    s.rect(15, 69, 2, 11, "m")
    s.rect(46, 71, 3, 8, "cd")

    # Arcade identification stripe and tiny rear lights.
    s.rect(14, 49, 4, 2, "x")
    s.rect(14, 49, 2, 1, "xl")
    s.rect(46, 49, 3, 2, "x")
    s.rect(46, 49, 2, 1, "xl")
    s.rect(17, 83, 4, 2, "x")
    s.rect(42, 83, 4, 2, "x")
    s.set(18, 83, "xl")
    s.set(43, 83, "xl")

    # Rivets and panel seam accents.
    s.px("h", 17, 34, 17, 41, 17, 58, 17, 66,
         46, 33, 46, 45, 46, 68, 20, 84, 31, 84)
    s.px("o", 22, 32, 41, 32, 20, 69, 43, 69, 31, 52)
    return s


def main():
    sprite = build_btr82()
    pix_path = os.path.join(HERE, "btr82.pix")
    png_path = os.path.join(HERE, "btr82.png")
    with open(pix_path, "w", encoding="utf-8") as output:
        output.write(sprite.to_pix(PALETTE, scale=4))
    sprite.save_png(png_path, PALETTE, scale=4)
    print("wrote", pix_path)
    print("wrote", png_path)


if __name__ == "__main__":
    main()

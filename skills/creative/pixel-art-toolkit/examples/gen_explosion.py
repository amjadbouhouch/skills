#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pixelart import Palette, Sprite, gif_bytes, png_bytes, sheet


OUT = Path(__file__).resolve().parent
W = H = 32
CX, CY = 15, 16

PAL = Palette.of({
    "k": "#24101d",
    "r": "#8f1d2c",
    "d": "#d33a1b",
    "o": "#ff7618",
    "y": "#ffc52b",
    "p": "#ffe991",
    "w": "#fffbe0",
    "s": "#382a38",
    "m": "#62404a",
})


def blob(s, cx, cy, r, code, lobes=()):
    s.disc(cx, cy, r, code)
    for dx, dy, rr in lobes:
        s.disc(cx + dx, cy + dy, rr, code)


def sparks(s, points, code="y"):
    for x, y in points:
        s.set(x, y, code)


def make_frame(i):
    s = Sprite(W, H, name=f"explosion_{i:02d}")

    if i == 0:
        s.px("p", 15, 15, 14, 16, 15, 16, 16, 16, 15, 17)
        s.px("w", 15, 16)
        sparks(s, [(11, 13), (19, 14), (12, 20)], "o")

    elif i == 1:
        s.line(15, 11, 15, 21, "r")
        s.line(10, 16, 20, 16, "r")
        blob(s, CX, CY, 4.0, "k", [(-3, 1, 2), (3, -1, 2)])
        blob(s, CX, CY, 3.5, "o", [(-3, 1, 1.5), (3, -1, 1.5)])
        s.disc(CX, CY, 2.5, "y")
        s.disc(CX, CY, 1.2, "w")
        sparks(s, [(8, 12), (22, 13), (20, 21), (10, 23)], "y")

    elif i == 2:
        for x, y in [(15, 5), (15, 27), (4, 16), (27, 16), (7, 8), (24, 7), (25, 24), (6, 25)]:
            s.line(CX, CY, x, y, "r")
        blob(s, CX, CY, 7.0, "k", [(-5, -2, 3), (5, 1, 3), (-2, 5, 3), (2, -5, 3)])
        blob(s, CX, CY, 6.0, "d", [(-4, -2, 2.5), (4, 1, 2.5), (-2, 4, 2.5), (2, -4, 2.5)])
        blob(s, CX, CY, 4.5, "o", [(-3, 0, 2), (3, 0, 2)])
        s.disc(CX - 1, CY, 3.2, "y")
        s.disc(CX - 1, CY - 1, 1.8, "w")
        sparks(s, [(4, 11), (27, 10), (29, 19), (3, 21)], "o")

    elif i == 3:
        blob(s, CX, CY, 9.2, "k", [(-7, -2, 4), (7, 1, 4), (-3, 7, 4), (2, -7, 4)])
        blob(s, CX, CY, 8.2, "r", [(-6, -2, 3.5), (6, 1, 3.5), (-3, 6, 3.5), (2, -6, 3.5)])
        blob(s, CX, CY, 6.8, "d", [(-5, 0, 3), (5, 0, 3), (0, -5, 3)])
        blob(s, CX, CY, 5.0, "o", [(-3, 1, 2.5), (3, -1, 2.5)])
        s.disc(CX - 1, CY - 1, 3.5, "y")
        s.disc(CX - 2, CY - 2, 1.7, "w")
        sparks(s, [(2, 9), (28, 7), (30, 23), (4, 28), (8, 4)], "y")

    elif i == 4:
        blob(s, CX, CY, 10.0, "k", [(-8, -1, 4), (8, 0, 4), (-4, 8, 4), (4, -8, 4), (6, 6, 3)])
        blob(s, CX, CY, 8.8, "r", [(-7, -1, 3.4), (7, 0, 3.4), (-4, 7, 3.4), (4, -7, 3.4)])
        blob(s, CX + 1, CY, 7.0, "d", [(-5, 2, 3), (4, -3, 3), (3, 5, 3)])
        blob(s, CX, CY, 5.4, "o", [(-3, -2, 2.8), (3, 2, 2.8)])
        s.disc(CX - 1, CY - 1, 3.7, "y")
        s.disc(CX - 2, CY - 2, 1.5, "p")
        sparks(s, [(1, 14), (29, 12), (28, 27), (7, 30), (3, 4), (22, 2)], "o")

    elif i == 5:
        blob(s, CX, CY, 10.4, "k", [(-8, -2, 3.8), (8, -2, 3.8), (-6, 7, 3.5), (6, 7, 3.5), (0, -9, 3.5)])
        blob(s, CX, CY, 9.2, "r", [(-7, -2, 3), (7, -2, 3), (-5, 6, 3), (5, 6, 3), (0, -8, 3)])
        s.circle(CX, CY, 7.6, "d")
        s.circle(CX, CY, 6.4, "o")
        blob(s, CX, CY + 1, 4.2, "s", [(-3, 1, 2.5), (3, 0, 2.5)])
        s.disc(CX - 1, CY - 1, 2.2, "m")
        sparks(s, [(2, 7), (27, 5), (30, 18), (25, 29), (3, 27)], "y")

    elif i == 6:
        for x, y, rr in [(8, 13, 4), (14, 9, 4.5), (21, 12, 4), (10, 20, 4.5), (19, 21, 5)]:
            s.disc(x, y, rr + 1, "k")
            s.disc(x, y, rr, "r")
            s.disc(x, y, max(1.5, rr - 2), "d")
        blob(s, 15, 16, 5, "s", [(-3, 0, 3), (3, 1, 3)])
        s.disc(14, 14, 2.5, "m")
        s.px("o", 6, 11, 24, 9, 27, 20, 7, 25)
        s.px("y", 2, 17, 29, 14, 23, 28)

    elif i == 7:
        for x, y, rr in [(8, 15, 3.2), (13, 10, 4), (20, 11, 3.5), (11, 20, 4), (19, 20, 4.5)]:
            s.disc(x, y, rr + 1, "k")
            s.disc(x, y, rr, "s")
            s.disc(x - 1, y - 1, max(1, rr - 2), "m")
        s.px("d", 4, 10, 25, 7, 27, 22, 6, 27)
        s.px("o", 2, 19, 29, 16, 23, 29)

    elif i == 8:
        for x, y, rr in [(10, 16, 3), (14, 10, 3.5), (20, 12, 3), (13, 21, 3.5), (20, 20, 3)]:
            s.disc(x, y, rr + 1, "k")
            s.disc(x, y, rr, "s")
            s.disc(x - 1, y - 1, 1.3, "m")
        s.px("d", 5, 8, 26, 6, 28, 24)
        s.px("o", 3, 23, 24, 29)

    elif i == 9:
        for x, y, rr in [(11, 17, 2.3), (15, 11, 2.7), (20, 14, 2.2), (16, 21, 2.5)]:
            s.disc(x, y, rr + 1, "k")
            s.disc(x, y, rr, "s")
            s.set(x - 1, y - 1, "m")
        s.px("r", 6, 7, 26, 9, 27, 25)
        s.px("d", 4, 24, 23, 29)

    return s


frames = [make_frame(i) for i in range(10)]

head = (
    "name: explosion\n"
    "size: 32x32\n"
    "scale: 8\n\n"
    "palette:\n"
    + PAL.to_pix()
    + "\n\npixels:\n"
    + frames[0].rows_text()
)
body = "".join("\n---\n" + frame.rows_text() for frame in frames[1:])
(OUT / "explosion.pix").write_text(head + body + "\n")

rgba = [frame.to_rgba(PAL) for frame in frames]
(OUT / "explosion.gif").write_bytes(gif_bytes(rgba, scale=8, delay_cs=8, loop=0))
(OUT / "explosion.png").write_bytes(png_bytes(frames[4].to_rgba(PAL), scale=8))

strip = sheet(frames, cols=10, pad=0)
(OUT / "explosion_sheet.png").write_bytes(png_bytes(strip.to_rgba(PAL), scale=4))

print(OUT / "explosion.pix")
print(OUT / "explosion.gif")
print(OUT / "explosion.png")
print(OUT / "explosion_sheet.png")

#!/usr/bin/env python3
"""
pixelart - tiny pixel-art mini-framework. Zero dependencies (stdlib only).

Grid model: every cell holds a short *code* (a palette key). "." = empty.
Rows are comma separated, one row per line. Palette maps code -> RGBA.

    .pix file
    ---------
    name: heart
    size: 32x32
    scale: 8
    mirror: x            # rows hold the left half only, right is mirrored
    bg: #00000000        # optional flatten background

    palette:
    r = #e63946
    d = #7a1522
    w = #fff

    pixels:
    .,.,r,r,r,.,.,.
    .,r,w,r,r,r,.,.
    --- hold: 2          # frame separator (animation); this frame lasts 2 ticks
    .,.,d,d,d,.,.,.

CLI
    pixelart.py render s.pix [-o out.png] [-s 8] [--frame all]
    pixelart.py show   s.pix                  # truecolor terminal preview
    pixelart.py play   s.pix [--fps 8]        # animate in the terminal
    pixelart.py gif    s.pix [--fps 8]
    pixelart.py sheet  a.pix b.pix -o sheet.png [--cols 4]
    pixelart.py new    s.pix [--size 32] [--mirror]
    pixelart.py check  s.pix
    pixelart.py png2pix in.png [-o out.pix]   # trace a PNG back into a grid
    pixelart.py reduce in.pix [--colors 24]   # requantize a traced file

API
    from pixelart import Sprite, Palette, Anim
    s = Sprite(32, 32)
    s.disc(15, 15, 10, "r"); s.outline("d"); s.mirror_x()
    s.save_png("out.png", pal, scale=8)
    Anim.from_keys([(9, 0), (24, 1.4)], make_frame, n=6).save_gif("out.gif", pal)
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import os
import re
import struct
import sys
import time
import zlib
from collections import deque

EMPTY = "."
TRANSPARENT = (0, 0, 0, 0)
SHEET_META_FORMAT = "pixelart-sheet/1"

NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "gray": "#808080", "grey": "#808080",
    "silver": "#c0c0c0", "red": "#e63946", "darkred": "#7a1522", "orange": "#f4801f",
    "yellow": "#ffd23f", "lime": "#8ac926", "green": "#2a9d3f", "darkgreen": "#14532d",
    "teal": "#219ebc", "cyan": "#4cc9f0", "blue": "#1d3fb0", "navy": "#0b1447",
    "purple": "#7b2cbf", "pink": "#ff8fab", "brown": "#8b5a2b", "tan": "#d9a066",
    "skin": "#ffcaa0", "none": "#00000000",
}


# --------------------------------------------------------------------------- color

def parse_color(text: str) -> tuple[int, int, int, int]:
    """'#rgb' / '#rgba' / '#rrggbb' / '#rrggbbaa' / 'red' / '230,57,70' -> RGBA."""
    s = text.strip()
    if s.lower() in NAMED_COLORS:
        s = NAMED_COLORS[s.lower()]
    if "," in s:
        parts = [int(p) for p in s.split(",")]
        if len(parts) == 3:
            parts.append(255)
        if len(parts) != 4:
            raise ValueError(f"bad rgb(a) color: {text!r}")
        return tuple(max(0, min(255, p)) for p in parts)  # type: ignore[return-value]
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s) + "ff"
    elif len(s) == 4:
        s = "".join(c * 2 for c in s)
    elif len(s) == 6:
        s += "ff"
    elif len(s) != 8:
        raise ValueError(f"bad hex color: {text!r}")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    except ValueError:
        raise ValueError(f"bad hex color: {text!r}") from None


def hexstr(rgba) -> str:
    r, g, b, a = rgba
    return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")


def over(src, dst):
    """Straight-alpha 'src over dst' composite."""
    sa = src[3] / 255.0
    if sa >= 1.0:
        return src
    if sa <= 0.0:
        return dst
    da = dst[3] / 255.0
    oa = sa + da * (1 - sa)
    if oa <= 0:
        return TRANSPARENT
    out = [round((src[i] * sa + dst[i] * da * (1 - sa)) / oa) for i in range(3)]
    return (out[0], out[1], out[2], round(oa * 255))


class Palette(dict):
    """code -> RGBA. Unknown codes and EMPTY resolve to transparent."""

    def set(self, code: str, color) -> "Palette":
        self[code] = color if isinstance(color, tuple) else parse_color(color)
        return self

    def rgba(self, code: str):
        if code == EMPTY or code == "":
            return TRANSPARENT
        return self.get(code, TRANSPARENT)

    @classmethod
    def of(cls, mapping) -> "Palette":
        p = cls()
        for k, v in dict(mapping).items():
            p.set(k, v)
        return p

    def to_pix(self) -> str:
        pad = max((len(k) for k in self), default=1)
        return "\n".join(f"{k.ljust(pad)} = {hexstr(v)}" for k, v in self.items())


# -------------------------------------------------------------------------- sprite

class Sprite:
    """A grid of palette codes with drawing primitives."""

    def __init__(self, w: int = 32, h: int | None = None, fill: str = EMPTY, name: str = ""):
        h = w if h is None else h
        if w < 1 or h < 1:
            raise ValueError("sprite must be at least 1x1")
        self.w, self.h, self.name = w, h, name
        self.g = [[fill] * w for _ in range(h)]

    # ---- basics
    def __repr__(self):
        return f"<Sprite {self.w}x{self.h} {self.name!r}>"

    def copy(self) -> "Sprite":
        s = Sprite(self.w, self.h, name=self.name)
        s.g = [row[:] for row in self.g]
        return s

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x: int, y: int) -> str:
        return self.g[y][x] if self.inside(x, y) else EMPTY

    def set(self, x: int, y: int, code: str, only=None) -> "Sprite":
        """Set one cell. `only` restricts painting to cells already holding
        that code (or one of a tuple of codes) - i.e. masked painting."""
        if self.inside(x, y) and (only is None or self.g[y][x] == only
                                 or (isinstance(only, (tuple, list, set)) and self.g[y][x] in only)):
            self.g[y][x] = code
        return self

    def px(self, code: str, *xy) -> "Sprite":
        """px('r', 1,2, 3,4, ...) - set many points with one code."""
        it = iter(xy)
        for x, y in zip(it, it):
            self.set(x, y, code)
        return self

    def clear(self, code: str = EMPTY) -> "Sprite":
        self.g = [[code] * self.w for _ in range(self.h)]
        return self

    # ---- shapes
    def rect(self, x: int, y: int, w: int, h: int, code: str, only=None) -> "Sprite":
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, code, only)
        return self

    def frame(self, x: int, y: int, w: int, h: int, code: str) -> "Sprite":
        for xx in range(x, x + w):
            self.set(xx, y, code)
            self.set(xx, y + h - 1, code)
        for yy in range(y, y + h):
            self.set(x, yy, code)
            self.set(x + w - 1, yy, code)
        return self

    def line(self, x0: int, y0: int, x1: int, y1: int, code: str, only=None) -> "Sprite":
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        while True:
            self.set(x0, y0, code, only)
            if x0 == x1 and y0 == y1:
                return self
            e2 = err * 2
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx: float, cy: float, r: float, code: str, only=None) -> "Sprite":
        rr = (r + 0.5) ** 2
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if (x - cx) ** 2 + (y - cy) ** 2 <= rr:
                    self.set(x, y, code, only)
        return self

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, code: str,
                only=None) -> "Sprite":
        """Filled ellipse. `disc` is the rx == ry case; this one squashes and
        stretches, which is what deformation frames are made of."""
        ax = max(abs(rx) + 0.5, 0.5)
        ay = max(abs(ry) + 0.5, 0.5)
        for y in range(int(cy - ay) - 1, int(cy + ay) + 2):
            for x in range(int(cx - ax) - 1, int(cx + ax) + 2):
                if ((x - cx) / ax) ** 2 + ((y - cy) / ay) ** 2 <= 1.0:
                    self.set(x, y, code, only)
        return self

    def circle(self, cx: float, cy: float, r: float, code: str, only=None) -> "Sprite":
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if abs(d - r) <= 0.5:
                    self.set(x, y, code, only)
        return self

    def flood(self, x: int, y: int, code: str, diagonal: bool = False) -> "Sprite":
        target = self.get(x, y)
        if target == code or not self.inside(x, y):
            return self
        steps = _NEIGH8 if diagonal else _NEIGH4
        q = deque([(x, y)])
        while q:
            cx, cy = q.popleft()
            if not self.inside(cx, cy) or self.g[cy][cx] != target:
                continue
            self.g[cy][cx] = code
            for dx, dy in steps:
                q.append((cx + dx, cy + dy))
        return self

    def replace(self, old: str, new: str) -> "Sprite":
        for row in self.g:
            for i, c in enumerate(row):
                if c == old:
                    row[i] = new
        return self

    def outline(self, code: str, empty: str = EMPTY, diagonal: bool = True) -> "Sprite":
        """Ring `code` around every non-empty cell (classic pixel-art contour)."""
        steps = _NEIGH8 if diagonal else _NEIGH4
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] != empty:
                    continue
                if any(self.get(x + dx, y + dy) not in (empty, code)
                       for dx, dy in steps):
                    add.append((x, y))
        for x, y in add:
            self.g[y][x] = code
        return self

    def shade(self, code: str, dx: int = 0, dy: int = 1, empty: str = EMPTY,
              only=None) -> "Sprite":
        """Inner rim shading: recolor filled cells whose (x-dx, y-dy) neighbor is
        empty - i.e. the edge facing away from a light source at (+dx, +dy)."""
        hits = [(x, y) for y in range(self.h) for x in range(self.w)
                if self.g[y][x] != empty and self.get(x - dx, y - dy) == empty]
        for x, y in hits:
            self.set(x, y, code, only)
        return self

    # ---- transforms
    def mirror_x(self) -> "Sprite":
        """Copy the left half onto the right half."""
        for row in self.g:
            for x in range(self.w // 2):
                row[self.w - 1 - x] = row[x]
        return self

    def mirror_y(self) -> "Sprite":
        for y in range(self.h // 2):
            self.g[self.h - 1 - y] = self.g[y][:]
        return self

    def flip_x(self) -> "Sprite":
        self.g = [row[::-1] for row in self.g]
        return self

    def flip_y(self) -> "Sprite":
        self.g = self.g[::-1]
        return self

    def rotate_cw(self) -> "Sprite":
        s = Sprite(self.h, self.w, name=self.name)
        s.g = [[self.g[self.h - 1 - y][x] for y in range(self.h)] for x in range(self.w)]
        return s

    def rotate(self, deg: float, pivot=None, only=None, fill: str = EMPTY) -> "Sprite":
        """Rotate by any angle, clockwise, nearest-neighbor. Wheels, swung
        swords, tumbling debris - `rotate_cw` only does quarter turns.

        `pivot` is (x, y) in grid cells and defaults to the canvas center;
        floats are fine. `only=` rotates just those codes and leaves the rest
        anchored (a wheel turning under a still cart), moved cells winning any
        overlap.

        Returns a NEW sprite on the SAME canvas - unlike `rotate_cw`, nothing
        grows, so a square turned 45 degrees clips its corners unless you pad
        first with `resized()`. Off-axis angles also rasterize unevenly at
        pixel-art sizes: prefer hand-drawn frames for a slow, readable turn and
        keep this for fast motion, or work at a larger canvas."""
        px, py = ((self.w - 1) / 2.0, (self.h - 1) / 2.0) if pivot is None else pivot
        rad = math.radians(deg)
        cos, sin = math.cos(rad), math.sin(rad)

        def moves(c):
            if only is None:
                return True
            return c == only or (isinstance(only, (tuple, list, set)) and c in only)

        out = Sprite(self.w, self.h, fill, self.name)
        if only is not None:                      # anchored cells stay put
            for y in range(self.h):
                for x in range(self.w):
                    c = self.g[y][x]
                    if c != EMPTY and not moves(c):
                        out.g[y][x] = c
        for y in range(self.h):
            dy = y - py
            for x in range(self.w):
                dx = x - px
                sx = round(px + dx * cos + dy * sin)      # sample backwards, so
                sy = round(py - dx * sin + dy * cos)      # the result has no holes
                if not self.inside(sx, sy):
                    continue
                c = self.g[sy][sx]
                if c != EMPTY and moves(c):
                    out.g[y][x] = c
        return out

    def shift(self, dx: int, dy: int, fill: str = EMPTY) -> "Sprite":
        s = Sprite(self.w, self.h, fill, self.name)
        for y in range(self.h):
            for x in range(self.w):
                s.set(x + dx, y + dy, self.g[y][x])
        return s

    def bend(self, offsets, axis: str = "y", fill: str = EMPTY, only=None) -> "Sprite":
        """Displace each row (axis='y') or column (axis='x') by its own amount:
        sway, wave, wobble, shear. `offsets` is a callable taking the row/column
        index, or a sequence of one offset per row/column; floats are rounded.

        With `only=` (a code or tuple of codes) just those cells move and the
        rest stay put as an anchor - a tree's leaves bending over a still
        trunk. Moved cells win where the two overlap.

        Returns a NEW sprite on the same canvas, so leave margin: whatever
        leaves the grid is lost, exactly like `shift`. `fill` is what the
        vacated cells show; empty source cells never move (they would punch
        holes in the cells that stayed)."""
        if axis not in ("x", "y"):
            raise ValueError("axis must be 'x' or 'y'")
        n = self.h if axis == "y" else self.w
        if callable(offsets):
            offs = [offsets(i) for i in range(n)]
        else:
            offs = list(offsets)
            if len(offs) != n:
                raise ValueError(f"bend needs {n} offsets for axis={axis!r}, got {len(offs)}")
        try:
            offs = [round(o) for o in offs]
        except TypeError:
            raise ValueError(
                "bend offsets must be real numbers. A fractional power of a "
                "negative number is complex in Python, which is the usual "
                "cause: clamp the base first, e.g. "
                "`max(0.0, (h - y) / h) ** 0.7`.") from None

        def moves(code):
            if only is None:
                return True
            return code == only or (isinstance(only, (tuple, list, set)) and code in only)

        s = Sprite(self.w, self.h, fill, self.name)
        held = []
        for y in range(self.h):
            for x in range(self.w):
                c = self.g[y][x]
                if c == EMPTY:
                    continue
                if not moves(c):
                    s.g[y][x] = c
                elif axis == "y":
                    held.append((x + offs[y], y, c))
                else:
                    held.append((x, y + offs[x], c))
        for x, y, c in held:
            s.set(x, y, c)
        return s

    def smear(self, dx: int, dy: int, code: str | None = None,
              steps: int = 0) -> "Sprite":
        """Stretch the sprite along a vector into a motion-smear frame - the
        single elongated frame that sells fast movement better than more
        in-betweens.

        Unions a copy of the sprite at every offset from `(dx, dy)` back to
        `(0, 0)`, drawing the untouched original last so it stays crisp. The
        trail therefore lies in the direction you pass: for something moving
        right, pass a NEGATIVE dx to leave the streak behind it.

        `code` paints the trail in one flat color (classic pale streak);
        `None` keeps each cell's own code, which elongates the sprite instead.
        `steps` is how many copies to lay down - 0 picks enough to leave no
        gaps. Same canvas, so the trail clips at the edge like `shift`.

        Smear BEFORE `outline()`. With `code=None` on an already-outlined
        sprite, each copy's contour is dragged across the body of the next one
        and the streak comes out the color of the outline."""
        out = Sprite(self.w, self.h, EMPTY, self.name)
        if not dx and not dy:
            out.g = [row[:] for row in self.g]
            return out
        steps = int(steps) or max(abs(int(dx)), abs(int(dy)))
        for t in range(steps, 0, -1):             # far end first, origin last
            ox, oy = round(dx * t / steps), round(dy * t / steps)
            for y in range(self.h):
                for x in range(self.w):
                    c = self.g[y][x]
                    if c != EMPTY:
                        out.set(x + ox, y + oy, code or c)
        for y in range(self.h):
            for x in range(self.w):
                c = self.g[y][x]
                if c != EMPTY:
                    out.g[y][x] = c
        return out

    def blit(self, other: "Sprite", x: int = 0, y: int = 0, skip_empty: bool = True) -> "Sprite":
        for yy in range(other.h):
            for xx in range(other.w):
                c = other.g[yy][xx]
                if skip_empty and c == EMPTY:
                    continue
                self.set(x + xx, y + yy, c)
        return self

    def resized(self, w: int, h: int, fill: str = EMPTY) -> "Sprite":
        s = Sprite(w, h, fill, self.name)
        for y in range(min(h, self.h)):
            for x in range(min(w, self.w)):
                s.g[y][x] = self.g[y][x]
        return s

    def remap(self, mapping: dict) -> "Sprite":
        """Rename palette codes in place (mapping: old -> new)."""
        for row in self.g:
            for i, c in enumerate(row):
                if c in mapping:
                    row[i] = mapping[c]
        return self

    def codes(self) -> list[str]:
        seen = {}
        for row in self.g:
            for c in row:
                if c != EMPTY:
                    seen[c] = 1
        return list(seen)

    # ---- output
    def rows_text(self) -> str:
        return "\n".join(",".join(row) for row in self.g)

    def to_pix(self, palette: Palette | None = None, scale: int = 8, mirror: str = "") -> str:
        head = [f"name: {self.name or 'sprite'}", f"size: {self.w}x{self.h}", f"scale: {scale}"]
        if mirror:
            head.append(f"mirror: {mirror}")
        out = "\n".join(head)
        if palette:
            used = Palette((c, palette.rgba(c)) for c in self.codes())
            out += "\n\npalette:\n" + used.to_pix()
        return out + "\n\npixels:\n" + _half(self, mirror).rows_text() + "\n"

    def to_rgba(self, palette: Palette, bg=None) -> list[list[tuple]]:
        bgc = None if bg is None else (bg if isinstance(bg, tuple) else parse_color(bg))
        rows = []
        for row in self.g:
            out = []
            for c in row:
                px = palette.rgba(c)
                out.append(px if bgc is None else over(px, bgc))
            rows.append(out)
        return rows

    def save_png(self, path: str, palette: Palette, scale: int = 1, bg=None) -> str:
        with open(path, "wb") as f:
            f.write(png_bytes(self.to_rgba(palette, bg), scale))
        return path

    @classmethod
    def from_rows(cls, rows: list[list[str]], name: str = "") -> "Sprite":
        w = max((len(r) for r in rows), default=1)
        s = cls(w, max(1, len(rows)), name=name)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                s.g[y][x] = c or EMPTY
        return s


_NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
_NEIGH8 = _NEIGH4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _half(s: Sprite, mirror: str = "") -> Sprite:
    """The authored quadrant of a sprite about to be written with `mirror:`.
    Keeps ceil(size/2) so odd sizes re-parse with a shared center row/column."""
    m = (mirror or "").lower()
    w = (s.w + 1) // 2 if "x" in m else s.w
    h = (s.h + 1) // 2 if "y" in m else s.h
    if w == s.w and h == s.h:
        return s
    out = Sprite(w, h, name=s.name)
    out.g = [row[:w] for row in s.g[:h]]
    return out


# ----------------------------------------------------------------------- document

class Doc:
    """Parsed .pix file: metadata + palette + one or more frames."""

    def __init__(self, frames: list[Sprite], palette: Palette, meta: dict | None = None,
                 holds: list[int] | None = None,
                 clips: dict[str, tuple[int, int]] | None = None):
        self.frames = frames
        self.palette = palette
        self.meta = meta or {}
        self.holds = list(holds) if holds else [1] * len(frames)
        self.clips = dict(clips) if clips else {}
        if len(self.holds) != len(frames):
            raise ValueError(f"{len(self.holds)} holds for {len(frames)} frames")

    @property
    def sprite(self) -> Sprite:
        return self.frames[0]

    @property
    def pivot(self):
        """The sprite's origin in grid cells, or None. Not clamped to the
        canvas - an anchor may sit outside it."""
        v = self.meta.get("pivot")
        return _parse_pivot(v) if v else None

    @property
    def anim(self) -> "Anim":
        """The frames as a timeline (holds, clips, GIF/sheet export, cycle ops)."""
        return Anim(self.frames, self.palette, self.holds, self.name, self.scale,
                    self.clips, self.pivot)

    def bad_clips(self) -> list[str]:
        """Clips whose range falls outside the frame list. Reported by `check`
        rather than refused at parse time, so a stale clip never stops you from
        loading the file that would tell you about it."""
        n = len(self.frames)
        return [name for name, (a, b) in self.clips.items() if a >= n or b >= n]

    @property
    def name(self) -> str:
        return self.meta.get("name", "sprite")

    @property
    def scale(self) -> int:
        return int(self.meta.get("scale", 1))

    @property
    def bg(self):
        b = self.meta.get("bg")
        return parse_color(b) if b else None

    def save_png(self, path: str, scale: int | None = None, frame: int = 0) -> str:
        return self.frames[frame].save_png(path, self.palette, scale or self.scale, self.bg)


_MARK = re.compile(r"\s+(#|//)")
_HEXTOK = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z])")


def _strip_comment(line: str) -> str:
    """Drop a trailing comment. A '#' that starts a hex color is not a comment,
    so 'r = #e63946   # lips' keeps the color and loses the note."""
    i = 0
    while True:
        m = _MARK.search(line, i)
        if not m:
            return line.strip()
        mark = m.end() - len(m.group(1))
        if m.group(1) == "#" and _HEXTOK.match(line, mark):
            i = mark + 1
            continue
        return line[:m.start()].strip()


_SEP = re.compile(r"^([-=~]{3,})\s*(.*)$")
_HOLD = re.compile(r"^(?:hold\s*:\s*)?(\d+)$", re.I)


_CLIP = re.compile(r"^(\S+)\s+(\d+)(?:\s*-\s*(\d+))?$")


def _parse_clip(text: str, lineno: int) -> tuple[str, int, int]:
    """'walk 2-7' -> ('walk', 2, 7). A lone index is a one-frame clip."""
    text = text.strip()
    m = _CLIP.match(text)
    if not m:
        raise ValueError(f"line {lineno}: expected 'clip: NAME FIRST[-LAST]' "
                         f"(frame indexes, 0-based, inclusive), got {text!r}")
    name, first = m.group(1), int(m.group(2))
    last = int(m.group(3)) if m.group(3) is not None else first
    if "," in name or name == EMPTY:
        raise ValueError(f"line {lineno}: bad clip name {name!r}")
    if last < first:
        raise ValueError(f"line {lineno}: clip {name!r} ends before it starts "
                         f"({first}-{last})")
    return name, first, last


def _parse_pivot(text: str, lineno: int = 0) -> tuple[int, int]:
    """'16,30' -> (16, 30). The sprite's origin, in grid cells."""
    parts = [p.strip() for p in text.replace("x", ",").split(",") if p.strip()]
    where = f"line {lineno}: " if lineno else ""
    if len(parts) != 2:
        raise ValueError(f"{where}expected 'pivot: X,Y', got {text!r}")
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        raise ValueError(f"{where}pivot needs two whole numbers, got {text!r}") from None


def _parse_hold(text: str, lineno: int) -> int:
    m = _HOLD.match(text)
    if not m:
        raise ValueError(f"line {lineno}: bad frame directive {text!r} "
                         f"(expected 'hold: N')")
    n = int(m.group(1))
    if n < 1:
        raise ValueError(f"line {lineno}: hold must be at least 1, got {n}")
    return n


def parse_pix(text: str, name: str = "") -> Doc:
    meta: dict[str, str] = {}
    meta_line: dict[str, int] = {}
    clips: dict[str, tuple[int, int]] = {}
    palette = Palette()
    frames: list[list[list[str]]] = [[]]
    holds: list[int] = [1]
    section = "head"

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#") or line.startswith("//"):
            continue
        line = _strip_comment(line)
        if not line:
            continue
        low = line.lower().rstrip(":")
        if line.endswith(":") and low in ("palette", "colors", "pixels", "grid"):
            section = "palette" if low in ("palette", "colors") else "pixels"
            continue

        if section == "head":
            if ":" not in line:
                raise ValueError(f"line {lineno}: expected 'key: value', got {line!r}")
            k, v = line.split(":", 1)
            key = k.strip().lower()
            if key == "hold":
                raise ValueError(f"line {lineno}: 'hold:' times one frame, so it "
                                 f"belongs in the pixels section (on a frame's "
                                 f"'---' separator, or on its own line), not the head")
            if key == "clip":
                name, first, last = _parse_clip(v, lineno)
                if name in clips:
                    raise ValueError(f"line {lineno}: clip {name!r} defined twice")
                clips[name] = (first, last)
                continue
            meta[key] = v.strip()
            meta_line[key] = lineno

        elif section == "palette":
            parts = line.split("=", 1) if "=" in line else line.split(None, 1)
            if len(parts) != 2:
                raise ValueError(f"line {lineno}: expected 'code = color', got {line!r}")
            code, color = parts[0].strip(), parts[1].strip()
            if not code or "," in code or code == EMPTY:
                raise ValueError(f"line {lineno}: bad palette code {code!r}")
            palette.set(code, color)

        else:  # pixels
            sep = _SEP.match(line)
            if sep:
                frames.append([])
                holds.append(_parse_hold(sep.group(2), lineno) if sep.group(2) else 1)
                continue
            if ":" in line and "," not in line:      # 'hold: 3' times this frame
                k, v = line.split(":", 1)
                if k.strip().lower() != "hold":
                    raise ValueError(f"line {lineno}: unknown frame directive "
                                     f"{k.strip()!r} (expected 'hold: N')")
                holds[-1] = _parse_hold(v.strip(), lineno)
                continue
            frames[-1].append([c.strip() or EMPTY for c in line.split(",")])

    keep = [i for i, f in enumerate(frames) if f]
    frames = [frames[i] for i in keep]
    holds = [holds[i] for i in keep]
    if not frames:
        raise ValueError("no pixel rows found (missing 'pixels:' section?)")

    if "pivot" in meta:
        _parse_pivot(meta["pivot"], meta_line.get("pivot", 0))   # fail on a typo now
    w_t, h_t = _parse_size(meta.get("size"))
    mirror = meta.get("mirror", "").lower().replace(",", "").strip()
    sprites = []
    for i, rows in enumerate(frames):
        if "x" in mirror:
            rows = [_mirror_row(r, w_t) for r in rows]
        if "y" in mirror:
            n = len(rows)
            keep = n - 1 if (h_t and h_t == n * 2 - 1) else n
            rows = rows + [r[:] for r in reversed(rows[:keep])]
        s = Sprite.from_rows(rows, name=meta.get("name", name))
        if w_t or h_t:
            s = s.resized(w_t or s.w, h_t or s.h)
        s.name = f"{s.name}#{i}" if len(frames) > 1 else s.name
        sprites.append(s)
    return Doc(sprites, palette, meta, holds, clips)


def _parse_size(val: str | None):
    if not val:
        return (0, 0)
    v = val.lower().replace("*", "x").replace(",", "x").replace(" ", "")
    if "x" in v:
        a, b = v.split("x", 1)
        return (int(a), int(b))
    return (int(v), int(v))


def _mirror_row(row: list[str], w_target: int) -> list[str]:
    n = len(row)
    if w_target and w_target == n * 2 - 1:      # shared center column
        return row + row[-2::-1]
    return row + row[::-1]                      # even width


def load_pix(path: str) -> Doc:
    with open(path, encoding="utf-8") as f:
        return parse_pix(f.read(), name=os.path.splitext(os.path.basename(path))[0])


# --------------------------------------------------------------------- motion

_BACK = 1.70158

_EASE = {
    "linear":    lambda t: t,
    "in":        lambda t: t * t,
    "out":       lambda t: 1 - (1 - t) ** 2,
    "in_out":    lambda t: 2 * t * t if t < 0.5 else 1 - 2 * (1 - t) ** 2,
    "in_cubic":  lambda t: t ** 3,
    "out_cubic": lambda t: 1 - (1 - t) ** 3,
    "back_in":   lambda t: t * t * ((_BACK + 1) * t - _BACK),
    "back_out":  lambda t: 1 + (1 - t) ** 2 * ((_BACK + 1) * (t - 1) + _BACK),
}


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease(t: float, kind="linear") -> float:
    """Reshape 0..1. `kind` is a name from EASE_KINDS or your own callable.
    `back_in`/`back_out` leave the 0..1 range on purpose - that overshoot is
    anticipation and follow-through."""
    if callable(kind):
        return kind(t)
    fn = _EASE.get(kind)
    if fn is None:
        raise ValueError(f"unknown ease {kind!r}; try: {', '.join(_EASE)}")
    return fn(max(0.0, min(1.0, t)))


EASE_KINDS = tuple(_EASE)


def keys(table, n: int = 0, kind="linear", loop: bool = False) -> list[tuple]:
    """Sample a keyframe table into `n` parameter tuples.

    `table` holds one tuple of numbers per pose (a bare number counts as a
    1-tuple). `n=0` - or n equal to the number of poses - returns the poses
    untouched, which is the common case: hand-picked poses beat interpolation
    at pixel-art frame counts. Larger n interpolates between them, eased.

    `loop=True` treats the table as a cycle: the last pose leads back into the
    first and the wrap frame is never emitted twice (see the looping-discipline
    rule in docs/animation.md)."""
    rows = [tuple(k) if isinstance(k, (tuple, list)) else (k,) for k in table]
    if not rows:
        raise ValueError("empty keyframe table")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("every keyframe needs the same number of values")
    k = len(rows)
    if n < 0:
        raise ValueError("n must be >= 0")
    if not n or (n == k and not loop):
        return rows
    out = []
    for i in range(n):
        if loop:
            u = i * k / n
            j = int(u) % k
            nxt = (j + 1) % k
        elif k == 1:
            u, j, nxt = 0.0, 0, 0
        else:
            u = i * (k - 1) / (n - 1) if n > 1 else 0.0
            j = min(int(u), k - 2)
            nxt = j + 1
        t = ease(u - int(u) if loop else u - j, kind)
        out.append(tuple(lerp(a, b, t) for a, b in zip(rows[j], rows[nxt])))
    return out


class Anim:
    """A list of frames plus their holds - the timeline of one animation.

    A *hold* is how many ticks a frame occupies; a tick is one `1/fps`. Holds
    are how variable timing is done: no frame is ever duplicated, and the count
    survives a round-trip through `.pix` as `hold: N`.

    `clips` names frame ranges inside the timeline (`{"walk": (2, 7)}`), so one
    file holds a character's whole vocabulary; `pivot` is the origin an engine
    should hang the sprite from. Both ride along to `to_pix` and the sheet
    sidecar.

    Mutating (returns self, chainable): `hold`, `set_holds`.
    Pure (returns a new Anim): `copy`, `reverse`, `ping_pong`, `map`, `clip`,
    slicing. Only `copy` and `map` keep the clip map - everything else changes
    frame order or count, which would leave the ranges pointing at the wrong
    poses, so they drop it.
    """

    def __init__(self, frames: list[Sprite], palette: Palette | None = None,
                 holds: list[int] | None = None, name: str = "", scale: int = 1,
                 clips: dict[str, tuple[int, int]] | None = None, pivot=None):
        frames = list(frames)
        if not frames:
            raise ValueError("an Anim needs at least one frame")
        self.frames = frames
        self.palette = palette
        self.name = name or frames[0].name or "anim"
        self.scale = int(scale) or 1
        self.clips = dict(clips) if clips else {}
        self.pivot = tuple(pivot) if pivot else None
        self.holds = [1] * len(frames)
        if holds is not None:
            self.set_holds(holds)

    def __repr__(self):
        f = self.frames[0]
        clips = f" {len(self.clips)} clips" if self.clips else ""
        return (f"<Anim {self.name!r} {len(self.frames)} frames "
                f"{f.w}x{f.h} {self.ticks} ticks{clips}>")

    def __len__(self):
        return len(self.frames)

    def __iter__(self):
        return iter(self.frames)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return Anim(self.frames[i], self.palette, self.holds[i], self.name,
                        self.scale, None, self.pivot)
        return self.frames[i]

    # ---- clips
    def clip(self, name: str) -> "Anim":
        """The frames of one named clip, as an Anim of its own."""
        if name not in self.clips:
            have = ", ".join(self.clips) or "none"
            raise KeyError(f"no clip {name!r} (defined: {have})")
        first, last = self.clips[name]
        if last >= len(self.frames):
            raise IndexError(f"clip {name!r} covers frames {first}-{last} but "
                             f"there are only {len(self.frames)}")
        out = self[first:last + 1]
        out.name = name
        return out

    def clip_ticks(self, name: str) -> int:
        first, last = self.clips[name]
        return sum(self.holds[first:last + 1])

    # ---- timing
    @property
    def ticks(self) -> int:
        return sum(self.holds)

    def hold(self, i: int, n: int = 2) -> "Anim":
        """Make frame `i` last `n` ticks. Negative indexes count from the end."""
        if n < 1:
            raise ValueError("hold must be at least 1")
        self.holds[i] = int(n)
        return self

    def set_holds(self, holds) -> "Anim":
        holds = [int(h) for h in holds]
        if len(holds) != len(self.frames):
            raise ValueError(f"{len(holds)} holds for {len(self.frames)} frames")
        if any(h < 1 for h in holds):
            raise ValueError("every hold must be at least 1")
        self.holds = holds
        return self

    def delays(self, fps: float = 8.0) -> list[int]:
        """Per-frame GIF delays in centiseconds. See docs/animation.md for why
        the base tick snaps to 10ms steps."""
        if fps <= 0:
            raise ValueError("fps must be positive")
        base = max(1, round(100 / fps))
        return [base * h for h in self.holds]

    # ---- structure
    def copy(self) -> "Anim":
        return Anim([f.copy() for f in self.frames], self.palette, self.holds,
                    self.name, self.scale, self.clips, self.pivot)

    def reverse(self) -> "Anim":
        return Anim(self.frames[::-1], self.palette, self.holds[::-1],
                    self.name, self.scale, None, self.pivot)

    def ping_pong(self) -> "Anim":
        """A B C D -> A B C D C B: play out and back without landing on either
        endpoint twice, so the loop does not stutter at the turns."""
        mid = slice(len(self) - 2, 0, -1)
        return Anim(self.frames + self.frames[mid], self.palette,
                    self.holds + self.holds[mid], self.name, self.scale,
                    None, self.pivot)

    def map(self, fn) -> "Anim":
        """Run `fn(frame)` over every frame - outline them all, shift them all.
        `fn` may mutate and return the frame or return a new one."""
        out = []
        for f in self.frames:
            c = f.copy()
            r = fn(c)
            out.append(c if r is None else r)
        return Anim(out, self.palette, self.holds, self.name, self.scale,
                    self.clips, self.pivot)

    @classmethod
    def from_keys(cls, table, fn, n: int = 0, kind="linear", loop: bool = False,
                  **kw) -> "Anim":
        """Build frames from a keyframe table: `fn(*pose)` per sampled pose.
        See `keys()` for the sampling rules."""
        return cls([fn(*pose) for pose in keys(table, n, kind, loop)], **kw)

    @classmethod
    def from_doc(cls, doc: "Doc") -> "Anim":
        return cls(doc.frames, doc.palette, doc.holds, doc.name, doc.scale,
                   doc.clips, doc.pivot)

    # ---- output
    def _pal(self, palette: Palette | None) -> Palette:
        pal = self.palette if palette is None else palette
        if pal is None:
            raise ValueError("no palette: pass one, or build the Anim with one")
        return pal

    def to_pix(self, palette: Palette | None = None, scale: int = 0,
               mirror: str = "") -> str:
        """Every frame in one `.pix` text, holds included. Unlike
        `Sprite.to_pix`, `mirror=` halves *all* the frames."""
        pal = self.palette if palette is None else palette
        f0 = self.frames[0]
        head = [f"name: {self.name}", f"size: {f0.w}x{f0.h}",
                f"scale: {scale or self.scale or 8}"]
        if mirror:
            head.append(f"mirror: {mirror}")
        if self.pivot:
            head.append(f"pivot: {self.pivot[0]},{self.pivot[1]}")
        for name, (first, last) in self.clips.items():
            head.append(f"clip: {name} {first}" + (f"-{last}" if last != first else ""))
        out = "\n".join(head)
        if pal:
            used = Palette()
            for f in self.frames:
                for c in f.codes():
                    used.setdefault(c, pal.rgba(c))
            out += "\n\npalette:\n" + used.to_pix()
        blocks = []
        for f, h in zip(self.frames, self.holds):
            pre = f"hold: {h}\n" if h > 1 else ""
            blocks.append(pre + _half(f, mirror).rows_text())
        return out + "\n\npixels:\n" + "\n---\n".join(blocks) + "\n"

    def to_rgba(self, palette: Palette | None = None, bg=None) -> list[list[list[tuple]]]:
        pal = self._pal(palette)
        return [f.to_rgba(pal, bg) for f in self.frames]

    def save_pix(self, path: str, palette: Palette | None = None, scale: int = 0,
                 mirror: str = "") -> str:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_pix(palette, scale, mirror))
        return path

    def save_gif(self, path: str, palette: Palette | None = None, fps: float = 8.0,
                 scale: int = 0, loop: int = 0, bg=None) -> str:
        data = gif_bytes(self.to_rgba(palette, bg), scale or self.scale,
                         self.delays(fps), loop)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def sheet_meta(self, cols: int = 0, pad: int = 0, scale: int = 0,
                   image: str = "") -> dict:
        """The sidecar for `save_sheet` with the same arguments: where every
        frame sits in the PNG, how long it lasts, and the clip ranges. All
        rects and the pivot are in **image pixels** - divide by `scale` for
        grid cells."""
        sc = scale or self.scale or 1
        lay = sheet_layout(self.frames, cols, pad)
        return {
            "format": SHEET_META_FORMAT,
            "name": self.name,
            "image": image,
            "scale": sc,
            "image_size": [lay["w"] * sc, lay["h"] * sc],
            "cell": [lay["cell_w"] * sc, lay["cell_h"] * sc],
            "grid": {"cols": lay["cols"], "rows": lay["rows"], "pad": pad * sc},
            "pivot": [self.pivot[0] * sc, self.pivot[1] * sc] if self.pivot else None,
            "frames": [
                {"index": i, "hold": h,
                 "rect": [x * sc, y * sc, f.w * sc, f.h * sc]}
                for i, (f, h, (x, y)) in enumerate(
                    zip(self.frames, self.holds, lay["origins"]))
            ],
            "clips": [
                {"name": n, "from": a, "to": b,
                 "ticks": sum(self.holds[a:b + 1])}
                for n, (a, b) in self.clips.items()
            ],
        }

    def save_sheet(self, path: str, palette: Palette | None = None, cols: int = 0,
                   pad: int = 0, scale: int = 0, bg=None, meta: bool = False) -> str:
        """One cell per frame, left to right. Holds are not repeated - a strip
        stores poses, and the timing travels in the sidecar `meta=True` writes
        next to the PNG (`strip.png` -> `strip.json`)."""
        big = sheet(self.frames, cols, pad)
        out = big.save_png(path, self._pal(palette), scale or self.scale, bg)
        if meta:
            side = os.path.splitext(out)[0] + ".json"
            with open(side, "w", encoding="utf-8") as f:
                json.dump(self.sheet_meta(cols, pad, scale,
                                          os.path.basename(out)), f, indent=2)
                f.write("\n")
        return out

    def save_pngs(self, path: str, palette: Palette | None = None, scale: int = 0,
                  bg=None) -> list[str]:
        """`out.png` -> `out_000.png`, `out_001.png`, … one file per frame."""
        pal = self._pal(palette)
        base, ext = os.path.splitext(path)
        done = []
        for i, f in enumerate(self.frames):
            done.append(f.save_png(f"{base}_{i:03d}{ext or '.png'}", pal,
                                   scale or self.scale, bg))
        return done


# ---------------------------------------------------------------------------- png

def png_bytes(rows: list[list[tuple]], scale: int = 1) -> bytes:
    """Encode RGBA rows (list of rows of (r,g,b,a)) as a PNG, nearest-neighbor scaled."""
    scale = max(1, int(scale))
    h, w = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        line = bytearray()
        for px in row:
            line += bytes(px) * scale
        for _ in range(scale):
            raw.append(0)          # filter type: none
            raw += line
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", w * scale, h * scale, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def read_png(path: str) -> list[list[tuple]]:
    """Minimal PNG reader: 8-bit RGB/RGBA/gray, non-interlaced."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w = 8, bytearray(), 0
    h = bits = ctype = 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            w, h, bits, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if bits != 8 or inter or ctype not in (0, 2, 6):
                raise ValueError(f"unsupported PNG (bits={bits} type={ctype} interlace={inter})")
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    nch = {0: 1, 2: 3, 6: 4}[ctype]
    raw = zlib.decompress(bytes(idat))
    stride = w * nch
    prev = bytearray(stride)
    out = []
    p = 0
    for _ in range(h):
        ft = raw[p]; p += 1
        cur = bytearray(raw[p:p + stride]); p += stride
        for i in range(stride):
            a = cur[i - nch] if i >= nch else 0
            b = prev[i]
            c = prev[i - nch] if i >= nch else 0
            if ft == 1:
                cur[i] = (cur[i] + a) & 0xFF
            elif ft == 2:
                cur[i] = (cur[i] + b) & 0xFF
            elif ft == 3:
                cur[i] = (cur[i] + ((a + b) >> 1)) & 0xFF
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 0xFF
        row = []
        for x in range(w):
            o = x * nch
            if nch == 1:
                v = cur[o]; row.append((v, v, v, 255))
            elif nch == 3:
                row.append((cur[o], cur[o + 1], cur[o + 2], 255))
            else:
                row.append((cur[o], cur[o + 1], cur[o + 2], cur[o + 3]))
        out.append(row)
        prev = cur
    return out


# ---------------------------------------------------------------------------- gif

class _BitsLSB:
    def __init__(self):
        self.acc = self.n = 0
        self.buf = bytearray()

    def write(self, code: int, size: int):
        self.acc |= code << self.n
        self.n += size
        while self.n >= 8:
            self.buf.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def done(self) -> bytes:
        if self.n:
            self.buf.append(self.acc & 0xFF)
            self.acc = self.n = 0
        return bytes(self.buf)


def _lzw(indices, min_code_size: int) -> bytes:
    clear, end = 1 << min_code_size, (1 << min_code_size) + 1
    bits = _BitsLSB()
    table: dict[tuple, int] = {}
    code_size = min_code_size + 1
    nxt = end + 1

    def reset():
        nonlocal table, code_size, nxt
        table = {(i,): i for i in range(clear)}
        code_size = min_code_size + 1
        nxt = end + 1

    reset()
    bits.write(clear, code_size)
    buf: tuple = ()
    for px in indices:
        cand = buf + (px,)
        if cand in table:
            buf = cand
            continue
        bits.write(table[buf], code_size)
        if nxt <= 4095:
            table[cand] = nxt
            nxt += 1
            if nxt > (1 << code_size) and code_size < 12:   # decoder lags one entry
                code_size += 1
        else:
            bits.write(clear, code_size)
            reset()
        buf = (px,)
    if buf:
        bits.write(table[buf], code_size)
    bits.write(end, code_size)
    return bits.done()


def _subblocks(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 255):
        part = data[i:i + 255]
        out.append(len(part))
        out += part
    out.append(0)
    return bytes(out)


def gif_bytes(frames_rows: list[list[list[tuple]]], scale: int = 1,
              delay_cs=10, loop: int = 0) -> bytes:
    """Animated GIF89a from RGBA frames. Alpha is 1-bit (a < 128 -> transparent).
    `delay_cs` is one delay for every frame, or a list of one per frame."""
    if not frames_rows:
        raise ValueError("no frames")
    scale = max(1, int(scale))
    h, w = len(frames_rows[0]), len(frames_rows[0][0])
    W, H = w * scale, h * scale
    for i, rows in enumerate(frames_rows):
        if len(rows) != h or any(len(r) != w for r in rows):
            raise ValueError(f"frame {i} is not {w}x{h}: every GIF frame must be "
                             f"the same size (give the .pix files a 'size:' head)")

    if isinstance(delay_cs, (list, tuple)):
        delays = [max(1, min(65535, int(d))) for d in delay_cs]
        if len(delays) != len(frames_rows):
            raise ValueError(f"{len(delays)} delays for {len(frames_rows)} frames")
    else:
        delays = [max(1, min(65535, int(delay_cs)))] * len(frames_rows)

    colors: dict[tuple, int] = {}
    has_alpha = False
    for rows in frames_rows:
        for row in rows:
            for px in row:
                if px[3] < 128:
                    has_alpha = True
                else:
                    colors.setdefault(px[:3], 0)
    order = list(colors)
    limit = 255 if has_alpha else 256
    if len(order) > limit:
        raise ValueError(f"GIF supports {limit} colors, sprite uses {len(order)}")
    base = 1 if has_alpha else 0
    index = {c: i + base for i, c in enumerate(order)}
    ncolors = len(order) + base
    bits = max(1, (max(1, ncolors - 1)).bit_length())
    table_size = 1 << bits

    gct = bytearray()
    if has_alpha:
        gct += b"\x00\x00\x00"
    for c in order:
        gct += bytes(c)
    gct += b"\x00" * (3 * (table_size - ncolors))

    out = bytearray(b"GIF89a")
    out += struct.pack("<HH", W, H)
    out += bytes([0x80 | ((bits - 1) & 0x07), 0, 0])
    out += gct
    if len(frames_rows) > 1 or loop == 0:
        out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"

    min_code = max(2, bits)
    for rows, delay in zip(frames_rows, delays):
        out += b"\x21\xf9\x04"
        out += bytes([(2 << 2) | (1 if has_alpha else 0)])   # restore-to-bg + transparency
        out += struct.pack("<H", delay) + bytes([0, 0])
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, W, H) + b"\x00"
        idx = []
        for row in rows:
            line = [0 if px[3] < 128 else index[px[:3]] for px in row]
            if scale > 1:
                line = [v for v in line for _ in range(scale)]
            for _ in range(scale):
                idx.extend(line)
        out += bytes([min_code]) + _subblocks(_lzw(idx, min_code))
    out += b"\x3b"
    return bytes(out)


# ------------------------------------------------------------------- sheet / view

def merge_docs(docs: list["Doc"]) -> tuple[list[Sprite], Palette]:
    """Flatten several docs into one sprite list + palette, renaming codes that
    two files use for different colors (e.g. both using 'd')."""
    pal, sprites = Palette(), []
    for doc in docs:
        rename = {}
        for code, color in doc.palette.items():
            if pal.get(code, color) == color:
                pal[code] = color
                continue
            same = next((k for k, v in pal.items() if v == color), None)
            if same is None:
                n = 2
                while f"{code}{n}" in pal:
                    n += 1
                same = f"{code}{n}"
                pal[same] = color
            rename[code] = same
        for sp in doc.frames:
            sprites.append(sp.copy().remap(rename) if rename else sp)
    return sprites, pal


def merge_anim(docs: list["Doc"], names: list[str] | None = None) -> Anim:
    """`merge_docs` plus the timing: every file's frames end to end, holds kept,
    palettes merged. This is what multi-file `gif` and `sheet` run on.

    One file in: its own clips survive. Several: each file becomes one clip
    (named from `names`, or its `name:` head, deduplicated), so packing a
    directory into an atlas gives you a clip per sprite for free."""
    if not docs:
        raise ValueError("no docs")
    sprites, pal = merge_docs(docs)
    holds = [h for d in docs for h in d.holds]
    if len(docs) == 1:
        clips, pivot = docs[0].clips, docs[0].pivot
    else:
        clips, pivot, at = {}, docs[0].pivot, 0
        for i, d in enumerate(docs):
            base = (names[i] if names and i < len(names) else d.name) or f"clip{i}"
            name, n = base, 2
            while name in clips:
                name, n = f"{base}_{n}", n + 1
            clips[name] = (at, at + len(d.frames) - 1)
            at += len(d.frames)
    return Anim(sprites, pal, holds, docs[0].name, docs[0].scale, clips, pivot)


def sheet_layout(sprites: list[Sprite], cols: int = 0, pad: int = 0) -> dict:
    """Where `sheet()` puts each sprite, in grid cells. `sheet` and the sidecar
    both read this, so a rect in the JSON always matches the pixels."""
    if not sprites:
        raise ValueError("no sprites")
    cols = cols or len(sprites)
    rows = (len(sprites) + cols - 1) // cols
    cw = max(s.w for s in sprites)
    ch = max(s.h for s in sprites)
    return {
        "cols": cols, "rows": rows, "cell_w": cw, "cell_h": ch, "pad": pad,
        "w": cols * cw + pad * (cols + 1), "h": rows * ch + pad * (rows + 1),
        "origins": [(pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + pad))
                    for i in range(len(sprites))],
    }


def sheet(sprites: list[Sprite], cols: int = 0, pad: int = 0, pad_code: str = EMPTY) -> Sprite:
    lay = sheet_layout(sprites, cols, pad)
    out = Sprite(lay["w"], lay["h"], pad_code)
    for s, (x, y) in zip(sprites, lay["origins"]):
        out.blit(s, x, y, skip_empty=False)
    return out


def ansi_preview(sprite: Sprite, palette: Palette, checker=((40, 40, 46), (58, 58, 66))) -> str:
    """Two grid rows per terminal line using the upper half block."""
    def col(px, x, y):
        if px[3] < 16:
            return checker[(x // 2 + y // 2) % 2]
        return px[:3]
    lines = []
    for y in range(0, sprite.h, 2):
        buf = []
        for x in range(sprite.w):
            top = col(palette.rgba(sprite.get(x, y)), x, y)
            bot = col(palette.rgba(sprite.get(x, y + 1)), x, y + 1) if y + 1 < sprite.h else checker[0]
            buf.append(f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                       f"\x1b[48;2;{bot[0]};{bot[1]};{bot[2]}m▀")
        lines.append("".join(buf) + "\x1b[0m")
    return "\n".join(lines)


# ------------------------------------------------------------------------- png2pix

_CODE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def png_to_doc(path: str, target: int = 0) -> Doc:
    rows = read_png(path)
    h, w = len(rows), len(rows[0])
    if target:
        # nearest-neighbor downsample to target width, keeping aspect
        th = max(1, round(h * target / w))
        rows = [[rows[min(h - 1, y * h // th)][min(w - 1, x * w // target)]
                 for x in range(target)] for y in range(th)]
        h, w = th, target
    pal, codes = Palette(), {}
    grid = []
    for row in rows:
        line = []
        for px in row:
            if px[3] < 8:
                line.append(EMPTY)
                continue
            key = px
            if key not in codes:
                i = len(codes)
                code = _CODE_CHARS[i] if i < len(_CODE_CHARS) else f"c{i}"
                codes[key] = code
                pal.set(code, key)
            line.append(codes[key])
        grid.append(line)
    name = os.path.splitext(os.path.basename(path))[0]
    return Doc([Sprite.from_rows(grid, name)], pal, {"name": name, "size": f"{w}x{h}", "scale": "8"})


# ---------------------------------------------------------------------- quantize

MAX_REDUCE_COLORS = 24

# Hue sector -> code letter. 'o' is reserved for the dark bucket, 'n' for
# neutrals, 'w' for pale tints. The brown|yellow split sits at 36 deg so earth
# tones (leather, skin, wood) separate from khaki/olive instead of merging.
_SECTORS = ((15, "r"), (36, "b"), (70, "y"), (100, "l"), (150, "g"), (190, "t"),
            (215, "c"), (250, "u"), (280, "v"), (320, "p"), (345, "m"), (360, "r"))


def _family(rgba) -> str:
    """Bucket one color into a material family, by hue unless it is dark,
    neutral or a pale tint -- those read as their own materials at any hue."""
    h, s, v = colorsys.rgb_to_hsv(*[q / 255 for q in rgba[:3]])
    H, S, V = h * 360, s * 100, v * 100
    if V < 13:
        return "o"
    if S < 16:
        return "n"
    if S < 28 and V > 78:
        return "w"
    for hi, letter in _SECTORS:
        if H < hi:
            return letter
    return "r"


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _kmeans(colors: list, k: int, rounds: int = 40) -> list:
    """k-means over RGBA, seeded on luminance percentiles. No RNG, so a given
    input always yields the same palette."""
    uniq = set(colors)
    if k >= len(uniq):
        return [[c] for c in sorted(uniq, key=_lum)]
    order = sorted(colors, key=_lum)
    cent = [order[min(len(order) - 1, round((i + 0.5) * len(order) / k))] for i in range(k)]
    groups = [[] for _ in range(k)]
    for _ in range(rounds):
        groups = [[] for _ in range(k)]
        for c in colors:
            i = min(range(k), key=lambda j: sum((c[t] - cent[j][t]) ** 2 for t in range(4)))
            groups[i].append(c)
        new = [tuple(round(sum(c[t] for c in g) / len(g)) for t in range(4)) if g else cent[i]
               for i, g in enumerate(groups)]
        if new == cent:
            break
        cent = new
    return groups


def _allocate(pops: dict, total: int, damp: float = 0.5) -> dict:
    """Split `total` ramp steps across families, one minimum each, the rest by
    population**damp (damped so one huge family cannot eat the budget)."""
    keys = sorted(pops, key=lambda k: -pops[k])
    if len(keys) > total:
        return {k: 1 for k in keys[:total]}
    free = total - len(keys)
    w = {k: pops[k] ** damp for k in keys}
    tw = sum(w.values()) or 1.0
    raw = {k: free * w[k] / tw for k in keys}
    out = {k: 1 + int(raw[k]) for k in keys}
    for k in sorted(keys, key=lambda k: -(raw[k] - int(raw[k])))[:total - sum(out.values())]:
        out[k] += 1
    return out


def reduce_doc(doc: "Doc", ncolors: int = MAX_REDUCE_COLORS, alpha_cut: int = 128):
    """Requantize a doc onto at most `ncolors` colors, grouped into per-material
    ramps. Returns (frames, palette, groups, stats).

    Files already within budget are returned untouched, so running this on a
    hand-authored sprite is a no-op rather than a slow way to lose colors.

    `alpha_cut` defaults to 128 because that is the trace-cleanup case: in a
    traced file every partial alpha is anti-aliasing fringe, and keeping it
    leaves ghost pixels behind. Lower it (`--alpha-cut 8`) for a high-color file
    whose translucency is deliberate, e.g. glass.
    """
    ncolors = max(2, min(MAX_REDUCE_COLORS, int(ncolors)))
    cells = []
    dropped = 0
    for fi, fr in enumerate(doc.frames):
        for y in range(fr.h):
            for x in range(fr.w):
                if fr.g[y][x] == EMPTY:
                    continue
                c = doc.palette.rgba(fr.g[y][x])
                if c[3] < alpha_cut:
                    dropped += 1
                    continue
                cells.append((fi, x, y, c))
    if not cells:
        raise ValueError("nothing to reduce (all cells empty)")

    stats = {"cells": len(cells), "dropped": dropped, "before": len(doc.palette)}
    if len({c[3] for c in cells}) <= ncolors:
        stats.update(after=len(doc.palette), error=0.0, noop=True)
        return doc.frames, doc.palette, [], stats

    fam = {}
    for cell in cells:
        fam.setdefault(_family(cell[3]), []).append(cell)
    # a family too small to earn a slot is folded into its nearest neighbour
    floor = max(2, len(cells) // 200)
    small = [k for k, v in fam.items() if len(v) < floor]
    if small and len(small) < len(fam):
        mean = {k: tuple(sum(c[3][t] for c in v) / len(v) for t in range(4))
                for k, v in fam.items()}
        for k in small:
            near = min((j for j in fam if j not in small),
                       key=lambda j: sum((mean[k][t] - mean[j][t]) ** 2 for t in range(4)))
            fam[near] += fam.pop(k)

    # At the default cut every surviving cell was opaque-ish anti-aliasing, so the
    # output is flattened to fully opaque. Lower the cut and averaged alpha is kept.
    opaque = alpha_cut >= 128
    pal, groups, lookup = Palette(), [], {}
    for letter in sorted(fam, key=lambda k: -len(fam[k])):
        codes = []
        reps = []
        for g in _kmeans([c[3] for c in fam[letter]],
                         _allocate({k: len(v) for k, v in fam.items()}, ncolors)[letter]):
            if not g:
                continue
            m = [round(sum(c[t] for c in g) / len(g)) for t in range(4)]
            reps.append(tuple(m[:3]) + (255 if opaque else m[3],))
        for i, rgba in enumerate(sorted(reps, key=_lum, reverse=True)):
            code = letter if i == 0 else f"{letter}{i + 1}"
            pal.set(code, rgba)
            codes.append((code, rgba))
        lookup[letter] = codes
        groups.append((letter, [c for c, _ in codes]))

    frames = [Sprite(f.w, f.h, name=f.name) for f in doc.frames]
    err = 0.0
    for letter, members in fam.items():
        codes = lookup[letter]
        for fi, x, y, c in members:
            code, rgba = min(codes, key=lambda kc: sum((c[t] - kc[1][t]) ** 2 for t in range(4)))
            frames[fi].g[y][x] = code
            err += (sum((c[t] - rgba[t]) ** 2 for t in range(4)) / 4) ** 0.5
    stats.update(after=len(pal), error=err / len(cells), noop=False)
    return frames, pal, groups, stats


_FAMILY_LABEL = {"o": "dark / outline", "n": "neutral", "w": "pale tint", "r": "red",
                 "b": "brown, orange, skin", "y": "yellow, khaki, olive", "l": "lime",
                 "g": "green", "t": "teal", "c": "cyan", "u": "blue", "v": "violet",
                 "p": "purple", "m": "magenta"}


def reduced_pix(frames: list, palette: Palette, groups: list, name: str,
                scale: int = 8) -> str:
    """Serialize a reduce_doc() result, keeping the palette grouped by family
    with comments -- that grouping is what makes the file editable afterwards."""
    pad = max((len(c) for c in palette), default=1)
    out = [f"# {name} - requantized by 'pixelart.py reduce'.",
           "# One ramp per material: bare code is the lightest step, rising",
           "# number is darker (b, b2, b3 ...).",
           f"name: {name}", f"size: {frames[0].w}x{frames[0].h}", f"scale: {scale}",
           "", "palette:"]
    for letter, codes in groups or [(None, list(palette))]:
        for i, code in enumerate(codes):
            note = f"   # {_FAMILY_LABEL.get(letter, '')}" if i == 0 and letter else ""
            out.append(f"{code.ljust(pad)} = {hexstr(palette[code])}{note}")
        out.append("")
    out.append("pixels:")
    out.append("\n---\n".join(f.rows_text() for f in frames))
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------- template

TEMPLATE = """# {name} - edit the grid below. '.' = empty cell.
name: {name}
size: {w}x{h}
scale: 8
{mirror}
palette:
o = #22252b        # outline
b = #4cc9f0        # body
h = #ffffff        # highlight
s = #1d3fb0        # shadow

pixels:
{rows}
"""


def new_template(w: int = 32, h: int | None = None, name: str = "sprite", mirror: bool = False) -> str:
    h = w if h is None else h
    cols = (w + 1) // 2 if mirror else w
    rows = "\n".join(",".join([EMPTY] * cols) for _ in range(h))
    return TEMPLATE.format(name=name, w=w, h=h, rows=rows,
                           mirror="mirror: x\n" if mirror else "")


# ----------------------------------------------------------------------------- cli

def _pick_clip(anim: Anim, args, nfiles: int = 1) -> Anim:
    """Apply `--clip` if the command was given one."""
    name = getattr(args, "clip", None)
    if not name:
        return anim
    if nfiles > 1:
        raise SystemExit("--clip works on a single file (which file's clips?)")
    try:
        return anim.clip(name)
    except (KeyError, IndexError) as e:
        raise SystemExit(str(e).strip('"')) from None


def _out_path(given: str | None, src: str, ext: str) -> str:
    if given:
        return given
    return os.path.splitext(src)[0] + ext


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pixelart", description="pixel-art mini-framework")
    sub = ap.add_subparsers(dest="cmd", required=True)

    CLIP = "restrict to one named clip (single file only)"

    r = sub.add_parser("render", help="grid -> PNG")
    r.add_argument("file")
    r.add_argument("-o", "--out")
    r.add_argument("-s", "--scale", type=int, default=0, help="pixel size (default: file's scale)")
    r.add_argument("--bg", help="flatten onto this color")
    r.add_argument("--frame", default="0", help="frame index, or 'all'")
    r.add_argument("--clip", help=CLIP)

    sh = sub.add_parser("show", help="preview in terminal")
    sh.add_argument("file")
    sh.add_argument("--frame", type=int, default=0)
    sh.add_argument("--clip", help=CLIP)

    pl = sub.add_parser("play", help="animate in the terminal (ctrl-c to stop)")
    pl.add_argument("file")
    pl.add_argument("--fps", type=float, default=8.0)
    pl.add_argument("--times", type=int, default=0,
                    help="passes to play, 0 = until ctrl-c (default: %(default)s)")
    pl.add_argument("--clip", help=CLIP)

    g = sub.add_parser("gif", help="frames -> animated GIF")
    g.add_argument("files", nargs="+")
    g.add_argument("-o", "--out")
    g.add_argument("-s", "--scale", type=int, default=0)
    g.add_argument("--fps", type=float, default=8.0)
    g.add_argument("--loop", type=int, default=0)
    g.add_argument("--bg")
    g.add_argument("--clip", help=CLIP)

    st = sub.add_parser("sheet", help="many sprites -> one PNG sheet")
    st.add_argument("files", nargs="+")
    st.add_argument("-o", "--out", default="sheet.png")
    st.add_argument("--cols", type=int, default=0)
    st.add_argument("--pad", type=int, default=0)
    st.add_argument("-s", "--scale", type=int, default=0)
    st.add_argument("--bg")
    st.add_argument("--clip", help=CLIP)
    st.add_argument("--meta", action="store_true",
                    help="also write a JSON sidecar (frame rects, holds, clips, pivot)")

    n = sub.add_parser("new", help="write a blank .pix template")
    n.add_argument("file")
    n.add_argument("--size", default="32")
    n.add_argument("--mirror", action="store_true")

    c = sub.add_parser("check", help="validate a .pix file")
    c.add_argument("file")

    p2 = sub.add_parser("png2pix", help="PNG -> .pix grid")
    p2.add_argument("file")
    p2.add_argument("-o", "--out")
    p2.add_argument("--size", type=int, default=0, help="downsample to this width")

    rd = sub.add_parser("reduce", help="requantize a high-color .pix into material ramps")
    rd.add_argument("file")
    rd.add_argument("-o", "--out", help="default: overwrite the input")
    rd.add_argument("--colors", type=int, default=MAX_REDUCE_COLORS,
                    help=f"palette budget, max {MAX_REDUCE_COLORS} (default: %(default)s)")
    rd.add_argument("--alpha-cut", type=int, default=128,
                    help="cells below this alpha become transparent; lower it to "
                         "keep deliberate translucency (default: %(default)s)")

    a = ap.parse_args(argv)

    if a.cmd == "new":
        w, h = _parse_size(a.size)
        name = os.path.splitext(os.path.basename(a.file))[0]
        with open(a.file, "w", encoding="utf-8") as f:
            f.write(new_template(w, h, name, a.mirror))
        print(f"{a.file}  {w}x{h}{' (mirror x)' if a.mirror else ''}")
        return 0

    if a.cmd == "png2pix":
        doc = png_to_doc(a.file, a.size)
        out = _out_path(a.out, a.file, ".pix")
        with open(out, "w", encoding="utf-8") as f:
            f.write(doc.sprite.to_pix(doc.palette))
        print(f"{out}  {doc.sprite.w}x{doc.sprite.h}  {len(doc.palette)} colors")
        return 0

    if a.cmd == "reduce":
        doc = load_pix(a.file)
        frames, pal, groups, st = reduce_doc(doc, a.colors, a.alpha_cut)
        out = a.out or a.file
        name = os.path.splitext(os.path.basename(out))[0]
        if st["noop"]:
            budget = min(a.colors, MAX_REDUCE_COLORS)
            if os.path.abspath(out) != os.path.abspath(a.file):
                # -o asked for this file: still produce it, unchanged, so that
                # pipelines like "reduce a.pix -o b.pix && gif b.pix" work.
                with open(a.file, encoding="utf-8") as src, \
                        open(out, "w", encoding="utf-8") as f:
                    f.write(src.read())
                print(f"{out}: {st['before']} colors already within the "
                      f"{budget}-color budget - copied unchanged")
            else:
                print(f"{a.file}: {st['before']} colors already within the "
                      f"{budget}-color budget - unchanged")
            return 0
        with open(out, "w", encoding="utf-8") as f:
            f.write(reduced_pix(frames, pal, groups, name, doc.scale))
        print(f"{out}  {frames[0].w}x{frames[0].h}  "
              f"{st['before']} -> {st['after']} colors")
        print(f"  {st['cells']} cells, mean per-pixel error {st['error']:.1f}/255"
              + (f", {st['dropped']} near-invisible cells dropped" if st["dropped"] else ""))
        return 0

    if a.cmd == "sheet":
        docs = [load_pix(f) for f in a.files]
        stems = [os.path.splitext(os.path.basename(f))[0] for f in a.files]
        anim = _pick_clip(merge_anim(docs, stems), a, len(a.files))
        anim.scale = a.scale or docs[0].scale
        out = anim.save_sheet(a.out, anim.palette, a.cols, a.pad,
                              bg=a.bg or docs[0].bg, meta=a.meta)
        lay = sheet_layout(anim.frames, a.cols, a.pad)
        clips = f"  {len(anim.clips)} clips" if anim.clips else ""
        print(f"{out}  {lay['w']}x{lay['h']} cells  {len(anim)} sprites{clips}")
        if a.meta:
            print(f"{os.path.splitext(out)[0]}.json  sidecar")
        return 0

    if a.cmd == "gif":
        docs = [load_pix(f) for f in a.files]
        stems = [os.path.splitext(os.path.basename(f))[0] for f in a.files]
        anim = _pick_clip(merge_anim(docs, stems), a, len(a.files))
        bg = a.bg or docs[0].bg
        scale = a.scale or docs[0].scale
        out = _out_path(a.out, a.files[0], ".gif")
        with open(out, "wb") as fh:
            fh.write(gif_bytes(anim.to_rgba(bg=bg), scale, anim.delays(a.fps), a.loop))
        held = f" ({anim.ticks} ticks)" if anim.ticks != len(anim) else ""
        print(f"{out}  {len(anim)} frames{held}  "
              f"{anim.frames[0].w * scale}x{anim.frames[0].h * scale}")
        return 0

    doc = load_pix(a.file)

    if a.cmd == "show":
        view = _pick_clip(doc.anim, a)
        i = min(a.frame, len(view) - 1)
        s = view.frames[i]
        print(ansi_preview(s, doc.palette))
        hold = f"  hold={view.holds[i]}" if view.holds[i] > 1 else ""
        print(f"{view.name}  {s.w}x{s.h}  frames={len(view)}  "
              f"colors={len(doc.palette)}{hold}")
        return 0

    if a.cmd == "play":
        anim = _pick_clip(doc.anim, a)
        name = anim.name
        views = [ansi_preview(s, doc.palette) for s in anim.frames]
        lines = max(v.count("\n") + 1 for v in views)
        views = [v + "\n" * (lines - v.count("\n") - 1) for v in views]
        if not sys.stdout.isatty():
            for v in views:
                print(v)
            print(f"{name}  {len(anim)} frames (not a terminal: printed once)")
            return 0
        if a.fps <= 0:
            raise SystemExit("fps must be positive")
        tick = 1.0 / a.fps
        sys.stdout.write("\x1b[?25l")
        try:
            passes, first = 0, True
            while a.times <= 0 or passes < a.times:
                for v, hold in zip(views, anim.holds):
                    if not first:
                        sys.stdout.write(f"\x1b[{lines}A")
                    first = False
                    sys.stdout.write(v + "\n")
                    sys.stdout.flush()
                    time.sleep(tick * hold)
                passes += 1
        except KeyboardInterrupt:
            pass
        finally:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()
        print(f"{name}  {len(anim)} frames  {anim.ticks} ticks @ {a.fps} fps")
        return 0

    if a.cmd == "check":
        problems = []
        for i, s in enumerate(doc.frames):
            unknown = sorted(c for c in s.codes() if c not in doc.palette)
            if unknown:
                problems.append(f"frame {i}: codes not in palette: {', '.join(unknown)}")
        unused = sorted(set(doc.palette) - {c for s in doc.frames for c in s.codes()})
        w, h = _parse_size(doc.meta.get("size"))
        for i, s in enumerate(doc.frames):
            if (w and s.w != w) or (h and s.h != h):
                problems.append(f"frame {i}: {s.w}x{s.h} but size says {w}x{h}")
        sizes = {(s.w, s.h) for s in doc.frames}
        if len(sizes) > 1:
            problems.append("frames differ in size: "
                            + ", ".join(f"{w}x{h}" for w, h in sorted(sizes))
                            + " (gif needs one size; add a 'size:' head)")
        for name in doc.bad_clips():
            first, last = doc.clips[name]
            problems.append(f"clip {name!r} covers frames {first}-{last} but the "
                            f"file has {len(doc.frames)}")
        print(f"{a.file}: {doc.frames[0].w}x{doc.frames[0].h}, "
              f"{len(doc.frames)} frame(s), {len(doc.palette)} palette entries")
        if doc.holds != [1] * len(doc.frames):
            print("  timing: holds " + ",".join(str(h) for h in doc.holds)
                  + f" = {sum(doc.holds)} ticks")
        if doc.pivot:
            print(f"  pivot: {doc.pivot[0]},{doc.pivot[1]}")
        if doc.clips:
            anim = doc.anim
            for name, (first, last) in doc.clips.items():
                span = f"{first}-{last}" if last != first else f"{first}"
                ticks = ("" if name in doc.bad_clips()
                         else f", {anim.clip_ticks(name)} ticks")
                print(f"  clip {name}: frames {span} "
                      f"({last - first + 1} frame(s){ticks})")
        if unused:
            print("  note: unused palette codes: " + ", ".join(unused))
        for p in problems:
            print("  ERROR: " + p)
        return 1 if problems else 0

    # render
    scale = a.scale or doc.scale
    bg = a.bg or doc.bg
    view = _pick_clip(doc.anim, a)
    if a.frame == "all" and len(view) > 1:
        base = os.path.splitext(_out_path(a.out, a.file, ".png"))[0]
        for i, s in enumerate(view.frames):
            p = f"{base}_{i:03d}.png"
            s.save_png(p, doc.palette, scale, bg)
            print(f"{p}  {s.w * scale}x{s.h * scale}")
    else:
        i = 0 if a.frame == "all" else int(a.frame)
        s = view.frames[i]
        out = _out_path(a.out, a.file, ".png")
        s.save_png(out, doc.palette, scale, bg)
        print(f"{out}  {s.w * scale}x{s.h * scale}  (x{scale})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

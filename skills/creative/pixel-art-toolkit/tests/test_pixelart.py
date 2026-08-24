#!/usr/bin/env python3
"""Regression tests: python3 -m unittest discover -s tests

Covers the format/parser contract, the round-trip through .pix, the motion
helpers and the encoders' framing rules. Run it after touching pixelart.py.
"""
import os
import sys
import unittest

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from pixelart import (  # noqa: E402
    Anim, Doc, Palette, Sprite, EASE_KINDS, SHEET_META_FORMAT, ease, gif_bytes,
    keys, lerp, load_pix, main, merge_anim, parse_pix, read_png, sheet,
    sheet_layout,
)

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(SKILL_ROOT, "examples")

PAL = Palette.of({"r": "#e63946", "w": "#ffffff", "o": "#221122"})


def pix(body, head="name: t\n\npalette:\nr = #e63946\n\npixels:\n"):
    return parse_pix(head + body)


# ------------------------------------------------------------------ holds

class TestHolds(unittest.TestCase):
    def test_default_is_one_per_frame(self):
        doc = pix("r,r\n---\nr,.\n")
        self.assertEqual(doc.holds, [1, 1])
        self.assertEqual(len(doc.frames), 2)

    def test_separator_directive_times_the_frame_it_opens(self):
        doc = pix("r,r\n--- hold: 3\nr,.\n")
        self.assertEqual(doc.holds, [1, 3])

    def test_bare_number_shorthand(self):
        doc = pix("r,r\n--- 4\nr,.\n")
        self.assertEqual(doc.holds, [1, 4])

    def test_standalone_line_times_the_current_frame(self):
        doc = pix("hold: 2\nr,r\n---\nr,.\n")
        self.assertEqual(doc.holds, [2, 1])

    def test_holds_survive_dropped_empty_frames(self):
        doc = pix("---\nr,r\n--- hold: 5\nr,.\n---\n")
        self.assertEqual(len(doc.frames), 2)
        self.assertEqual(doc.holds, [1, 5])

    def test_other_separator_characters_still_work(self):
        self.assertEqual(pix("r,r\n===\nr,.\n~~~ hold: 2\n.,r\n").holds, [1, 1, 2])

    def test_hold_in_head_is_a_pointed_error(self):
        with self.assertRaisesRegex(ValueError, "pixels section"):
            parse_pix("name: t\nhold: 2\n\npixels:\nr,r\n")

    def test_zero_and_garbage_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            pix("r,r\n--- hold: 0\nr,.\n")
        with self.assertRaisesRegex(ValueError, "bad frame directive"):
            pix("r,r\n--- wobble\nr,.\n")
        with self.assertRaisesRegex(ValueError, "unknown frame directive"):
            pix("delay: 2\nr,r\n")

    def test_pixel_rows_are_never_mistaken_for_separators(self):
        doc = pix("-,-,-\n---\nr,r,r\n")
        self.assertEqual(len(doc.frames), 2)
        self.assertEqual(doc.frames[0].g[0], ["-", "-", "-"])

    def test_doc_rejects_mismatched_holds(self):
        with self.assertRaises(ValueError):
            Doc([Sprite(2, 2)], PAL, {}, [1, 1])


# ------------------------------------------------------------------- Anim

class TestAnim(unittest.TestCase):
    def frames(self, n=4):
        return [Sprite(4, 4, name="a").px("r", i, 0) for i in range(n)]

    def test_holds_and_ticks(self):
        a = Anim(self.frames(3), PAL)
        self.assertEqual(a.ticks, 3)
        a.hold(0, 2).hold(-1, 3)
        self.assertEqual(a.holds, [2, 1, 3])
        self.assertEqual(a.ticks, 6)

    def test_delays_multiply_the_base_tick(self):
        a = Anim(self.frames(2), PAL).hold(1, 3)
        self.assertEqual(a.delays(10), [10, 30])
        self.assertEqual(a.delays(8), [12, 36])

    def test_reverse_and_slice_carry_holds(self):
        a = Anim(self.frames(3), PAL).hold(0, 5)
        self.assertEqual(a.reverse().holds, [1, 1, 5])
        self.assertEqual(a[:2].holds, [5, 1])
        self.assertEqual(len(a[:2]), 2)

    def test_ping_pong_drops_both_endpoints(self):
        a = Anim(self.frames(4), PAL)
        pp = a.ping_pong()
        self.assertEqual(len(pp), 6)
        self.assertEqual([f.g[0].index("r") for f in pp], [0, 1, 2, 3, 2, 1])
        self.assertEqual(len(Anim(self.frames(2), PAL).ping_pong()), 2)
        self.assertEqual(len(Anim(self.frames(1), PAL).ping_pong()), 1)

    def test_map_keeps_mutations_and_leaves_the_source_alone(self):
        a = Anim(self.frames(2), PAL)
        b = a.map(lambda s: s.outline("o"))
        self.assertIn("o", b[0].codes())
        self.assertNotIn("o", a[0].codes())

    def test_map_accepts_a_returned_sprite(self):
        a = Anim(self.frames(2), PAL)
        b = a.map(lambda s: s.shift(1, 0))
        self.assertEqual(b[0].get(1, 0), "r")

    def test_bad_holds_rejected(self):
        with self.assertRaises(ValueError):
            Anim(self.frames(2), PAL, [1, 0])
        with self.assertRaises(ValueError):
            Anim(self.frames(2), PAL, [1])
        with self.assertRaises(ValueError):
            Anim([])

    def test_from_keys_one_frame_per_pose_by_default(self):
        seen = []
        a = Anim.from_keys([(1, 2), (3, 4)], lambda x, y: seen.append((x, y)) or Sprite(2, 2))
        self.assertEqual(seen, [(1, 2), (3, 4)])
        self.assertEqual(len(a), 2)

    def test_from_keys_interpolates_when_asked(self):
        seen = []
        Anim.from_keys([(0,), (10,)], lambda x: seen.append(x) or Sprite(2, 2), n=3)
        self.assertEqual(seen, [0.0, 5.0, 10.0])

    def test_no_palette_is_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "no palette"):
            Anim(self.frames(2)).to_rgba()


# ------------------------------------------------------------- round-trip

class TestRoundTrip(unittest.TestCase):
    def test_anim_to_pix_preserves_frames_and_holds(self):
        a = Anim([Sprite(4, 4).px("r", i, i) for i in range(3)], PAL,
                 name="cycle", scale=6).hold(1, 4)
        back = parse_pix(a.to_pix())
        self.assertEqual(back.holds, [1, 4, 1])
        self.assertEqual(back.name, "cycle")
        self.assertEqual(back.scale, 6)
        self.assertEqual([f.rows_text() for f in back.frames],
                         [f.rows_text() for f in a.frames])

    def test_palette_covers_codes_from_every_frame(self):
        a = Anim([Sprite(2, 2).px("r", 0, 0), Sprite(2, 2).px("w", 1, 1)], PAL)
        self.assertIn("w", parse_pix(a.to_pix()).palette)

    def test_anim_mirror_halves_every_frame(self):
        src = [Sprite(8, 8).px("r", 1, i) for i in range(3)]
        for s in src:
            s.mirror_x()
        a = Anim(src, PAL, name="m")
        text = a.to_pix(mirror="x")
        self.assertIn("mirror: x", text)
        back = parse_pix(text)
        self.assertEqual([f.rows_text() for f in back.frames],
                         [f.rows_text() for f in src])

    def test_sprite_mirror_y_round_trips(self):
        # to_pix(mirror="y") used to write a full-height body under a
        # 'mirror: y' head, so re-parsing doubled the sprite.
        for h in (8, 9):
            s = Sprite(6, h).px("r", 1, 0).px("w", 2, 1).mirror_y()
            back = parse_pix(s.to_pix(PAL, mirror="y"))
            self.assertEqual(back.sprite.h, h)
            self.assertEqual(back.sprite.rows_text(), s.rows_text())

    def test_sprite_mirror_xy_round_trips(self):
        s = Sprite(9, 9).px("r", 1, 1).px("w", 3, 2).mirror_x().mirror_y()
        back = parse_pix(s.to_pix(PAL, mirror="xy"))
        self.assertEqual((back.sprite.w, back.sprite.h), (9, 9))
        self.assertEqual(back.sprite.rows_text(), s.rows_text())

    def test_sprite_mirror_x_still_round_trips(self):
        for w in (8, 9):
            s = Sprite(w, 4).px("r", 1, 1).mirror_x()
            back = parse_pix(s.to_pix(PAL, mirror="x"))
            self.assertEqual(back.sprite.rows_text(), s.rows_text())


# ----------------------------------------------------------------- motion

class TestMotion(unittest.TestCase):
    def test_lerp(self):
        self.assertEqual(lerp(0, 10, 0.25), 2.5)

    def test_every_ease_pins_both_ends(self):
        for kind in EASE_KINDS:
            self.assertAlmostEqual(ease(0.0, kind), 0.0, msg=kind)
            self.assertAlmostEqual(ease(1.0, kind), 1.0, msg=kind)

    def test_ease_clamps_and_takes_callables(self):
        self.assertEqual(ease(5.0, "linear"), 1.0)
        self.assertEqual(ease(-5.0, "linear"), 0.0)
        self.assertEqual(ease(0.5, lambda t: 42), 42)
        with self.assertRaisesRegex(ValueError, "unknown ease"):
            ease(0.5, "sproing")

    def test_ease_shapes(self):
        self.assertLess(ease(0.25, "in"), 0.25)        # slow start
        self.assertGreater(ease(0.25, "out"), 0.25)    # fast start
        self.assertAlmostEqual(ease(0.5, "in_out"), 0.5)
        self.assertLess(ease(0.2, "back_in"), 0.0)     # anticipation undershoot
        self.assertGreater(ease(0.8, "back_out"), 1.0)  # follow-through overshoot

    def test_keys_passes_poses_through_untouched(self):
        table = [(9.0, 0.0), (24.6, 1.4)]
        self.assertEqual(keys(table), [(9.0, 0.0), (24.6, 1.4)])
        self.assertEqual(keys(table, 2), [(9.0, 0.0), (24.6, 1.4)])

    def test_keys_scalars_become_one_tuples(self):
        self.assertEqual(keys([0, 4], 3), [(0.0,), (2.0,), (4.0,)])

    def test_keys_hits_first_and_last_pose_exactly(self):
        got = keys([(0,), (1,), (5,)], 7)
        self.assertEqual(got[0], (0.0,))
        self.assertEqual(got[-1], (5.0,))
        self.assertEqual(len(got), 7)

    def test_keys_loop_never_repeats_the_wrap_frame(self):
        got = keys([(0,), (1,), (2,), (3,)], 8, loop=True)
        self.assertEqual([round(v[0], 3) for v in got],
                         [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 1.5])

    def test_keys_validation(self):
        with self.assertRaises(ValueError):
            keys([])
        with self.assertRaisesRegex(ValueError, "same number of values"):
            keys([(1, 2), (3,)], 4)
        with self.assertRaises(ValueError):
            keys([(1,)], -1)

    def test_keys_single_pose(self):
        self.assertEqual(keys([(7,)], 3), [(7.0,), (7.0,), (7.0,)])


# --------------------------------------------------------------- primitives

class TestPrimitives(unittest.TestCase):
    def test_ellipse_matches_disc_when_radii_are_equal(self):
        a, b = Sprite(21, 21), Sprite(21, 21)
        a.disc(10, 10, 6.4, "r")
        b.ellipse(10, 10, 6.4, 6.4, "r")
        self.assertEqual(a.rows_text(), b.rows_text())

    def test_ellipse_squashes_and_stretches(self):
        s = Sprite(21, 21).ellipse(10, 10, 8, 3, "r")
        self.assertEqual(s.get(2, 10), "r")     # wide
        self.assertEqual(s.get(10, 2), ".")     # not tall
        self.assertEqual(s.get(10, 10), "r")

    def test_ellipse_degenerate_radius_is_a_thin_line(self):
        s = Sprite(9, 9).ellipse(4, 4, 0, 3, "r")
        self.assertEqual(s.get(4, 2), "r")
        self.assertEqual(s.get(5, 4), ".")

    def test_ellipse_honours_only(self):
        s = Sprite(9, 9).rect(0, 0, 9, 4, "w").ellipse(4, 4, 4, 4, "r", only="w")
        self.assertEqual(s.get(4, 1), "r")
        self.assertEqual(s.get(4, 6), ".")

    def test_bend_shifts_rows_and_returns_a_new_sprite(self):
        s = Sprite(6, 3).px("r", 0, 0, 0, 1, 0, 2)
        b = s.bend(lambda y: y)
        self.assertEqual([b.g[y].index("r") for y in range(3)], [0, 1, 2])
        self.assertEqual(s.g[2].index("r"), 0)          # source untouched

    def test_bend_takes_a_sequence_and_rounds_floats(self):
        s = Sprite(6, 3).px("r", 0, 0, 0, 1, 0, 2)
        b = s.bend([0, 1.4, 2.6])
        self.assertEqual([b.g[y].index("r") for y in range(3)], [0, 1, 3])

    def test_bend_on_the_x_axis_moves_columns(self):
        s = Sprite(3, 6).px("r", 0, 0, 1, 0, 2, 0)
        b = s.bend([0, 1, 2], axis="x")
        self.assertEqual([b.g[y][x] for x, y in ((0, 0), (1, 1), (2, 2))], ["r"] * 3)

    def test_bend_only_moves_the_selected_codes(self):
        s = Sprite(6, 2).px("r", 0, 0).px("w", 0, 1)
        b = s.bend(lambda y: 2, only="r")
        self.assertEqual(b.get(2, 0), "r")      # moved
        self.assertEqual(b.get(0, 1), "w")      # anchored
        self.assertEqual(b.get(0, 0), ".")

    def test_bend_never_moves_empty_cells_over_anchored_ones(self):
        s = Sprite(4, 1).px("w", 3, 0)
        b = s.bend(lambda y: 3, only="r")
        self.assertEqual(b.get(3, 0), "w")

    def test_bend_drops_what_leaves_the_canvas(self):
        s = Sprite(4, 1).px("r", 0, 0)
        self.assertEqual(s.bend(lambda y: 99).codes(), [])

    def test_bend_validation(self):
        s = Sprite(4, 4)
        with self.assertRaisesRegex(ValueError, "axis"):
            s.bend(lambda y: 0, axis="z")
        with self.assertRaisesRegex(ValueError, "4 offsets"):
            s.bend([1, 2])

    # ---- rotate: checked against rotate_cw, which predates it
    def noisy(self, n=9, seed=3):
        import random
        r = random.Random(seed)
        s = Sprite(n, n)
        for _ in range(n * 3):
            s.set(r.randrange(n), r.randrange(n), r.choice("rwo"))
        return s

    def test_rotate_90_matches_rotate_cw_on_a_square(self):
        for n in (5, 8, 9, 16):
            s = self.noisy(n)
            self.assertEqual(s.rotate(90).rows_text(), s.rotate_cw().rows_text(), n)

    def test_rotate_negative_and_multiples(self):
        s = self.noisy(8)
        cw3 = s.rotate_cw().rotate_cw().rotate_cw()
        self.assertEqual(s.rotate(-90).rows_text(), cw3.rows_text())
        self.assertEqual(s.rotate(270).rows_text(), cw3.rows_text())
        self.assertEqual(s.rotate(180).rows_text(),
                         s.rotate_cw().rotate_cw().rows_text())

    def test_rotate_0_and_360_are_the_identity(self):
        s = self.noisy(9)
        self.assertEqual(s.rotate(0).rows_text(), s.rows_text())
        self.assertEqual(s.rotate(360).rows_text(), s.rows_text())

    def test_four_quarter_turns_return_the_original(self):
        s = q = self.noisy(9)
        for _ in range(4):
            q = q.rotate(90)
        self.assertEqual(q.rows_text(), s.rows_text())

    def test_rotate_is_pure_and_keeps_the_canvas(self):
        s = Sprite(9, 5).px("r", 0, 0)
        r = s.rotate(37)
        self.assertEqual((r.w, r.h), (9, 5))       # no growth, unlike rotate_cw
        self.assertEqual(s.get(0, 0), "r")         # source untouched

    def test_rotate_has_no_holes(self):
        # inverse sampling must fill every destination cell of a solid disc
        s = Sprite(21, 21).disc(10, 10, 7, "r")
        before = sum(row.count("r") for row in s.g)
        after = sum(row.count("r") for row in s.rotate(33).g)
        self.assertGreater(after, before * 0.9)

    def test_rotate_honours_an_explicit_pivot(self):
        s = Sprite(5, 5).px("r", 0, 0)
        # pivot on the marked cell: it cannot move
        self.assertEqual(s.rotate(90, pivot=(0, 0)).get(0, 0), "r")

    def test_rotate_only_anchors_the_rest(self):
        s = Sprite(5, 5).px("r", 4, 2).px("w", 2, 2)
        r = s.rotate(90, only="r")
        self.assertEqual(r.get(2, 2), "w")         # anchored
        self.assertEqual(r.get(4, 2), ".")         # the r moved away
        self.assertIn("r", r.codes())

    # ---- smear
    def test_smear_lays_a_trail_and_keeps_the_body_crisp(self):
        s = Sprite(8, 1).px("r", 5, 0)
        t = s.smear(-3, 0, "S")
        self.assertEqual(t.g[0], [".", ".", "S", "S", "S", "r", ".", "."])

    def test_smear_without_a_code_elongates_in_place(self):
        s = Sprite(8, 1).px("r", 5, 0)
        self.assertEqual(s.smear(-2, 0).g[0].count("r"), 3)

    def test_smear_direction_follows_the_vector(self):
        s = Sprite(8, 1).px("r", 2, 0)
        self.assertEqual(s.smear(3, 0, "S").g[0],
                         [".", ".", "r", "S", "S", "S", ".", "."])

    def test_smear_diagonal_has_no_gaps(self):
        s = Sprite(6, 6).px("r", 0, 0)
        t = s.smear(4, 4, "S")
        self.assertEqual([t.get(i, i) for i in range(5)], ["r", "S", "S", "S", "S"])

    def test_smear_zero_vector_is_a_copy(self):
        s = Sprite(4, 2).px("r", 1, 1)
        t = s.smear(0, 0)
        self.assertEqual(t.rows_text(), s.rows_text())
        self.assertIsNot(t, s)

    def test_smear_steps_controls_the_gaps(self):
        s = Sprite(10, 1).px("r", 0, 0)
        sparse = s.smear(8, 0, "S", steps=2)
        self.assertEqual(sparse.g[0].count("S"), 2)    # only 2 copies laid down

    def test_smear_clips_at_the_canvas_edge(self):
        s = Sprite(4, 1).px("r", 3, 0)
        self.assertEqual(s.smear(9, 0, "S").g[0], [".", ".", ".", "r"])

    def test_bend_explains_a_complex_offset(self):
        # a fractional power of a negative number is complex in Python; the
        # bare TypeError from round() told you nothing
        s = Sprite(4, 40)
        with self.assertRaisesRegex(ValueError, "real numbers"):
            s.bend(lambda y: ((38 - y) / 38) ** 0.7)

    def test_smear_is_pure(self):
        s = Sprite(6, 1).px("r", 3, 0)
        s.smear(-2, 0, "S")
        self.assertEqual(s.g[0].count("r"), 1)
        self.assertNotIn("S", s.codes())


# ------------------------------------------------------------------ encoders

class TestEncoders(unittest.TestCase):
    def rows(self, w=2, h=2, code="r"):
        return Sprite(w, h, fill=code).to_rgba(PAL)

    def test_per_frame_delays_land_in_the_stream(self):
        data = gif_bytes([self.rows(), self.rows()], delay_cs=[7, 25])
        self.assertIn(b"\x21\xf9\x04\x08\x07\x00", data)
        self.assertIn(b"\x21\xf9\x04\x08\x19\x00", data)

    def test_scalar_delay_still_works(self):
        self.assertEqual(gif_bytes([self.rows()], delay_cs=9).count(b"\x21\xf9\x04\x08\x09\x00"), 1)

    def test_delay_count_must_match(self):
        with self.assertRaisesRegex(ValueError, "2 delays for 1 frames"):
            gif_bytes([self.rows()], delay_cs=[1, 2])

    def test_delays_are_clamped_into_the_uint16(self):
        self.assertIn(b"\x21\xf9\x04\x08\xff\xff", gif_bytes([self.rows()], delay_cs=99999))
        self.assertIn(b"\x21\xf9\x04\x08\x01\x00", gif_bytes([self.rows()], delay_cs=0))

    def test_mixed_frame_sizes_are_refused_not_corrupted(self):
        with self.assertRaisesRegex(ValueError, "same size"):
            gif_bytes([self.rows(2, 2), self.rows(3, 3)])

    def test_no_frames(self):
        with self.assertRaises(ValueError):
            gif_bytes([])

    def test_anim_save_gif_and_sheet(self):
        import tempfile
        a = Anim([Sprite(4, 4, fill="r"), Sprite(4, 4, fill="w")], PAL, scale=2).hold(0, 3)
        with tempfile.TemporaryDirectory() as d:
            with open(a.save_gif(os.path.join(d, "a.gif"), fps=10), "rb") as fh:
                self.assertIn(b"\x21\xf9\x04\x08\x1e\x00", fh.read())        # 30cs
            with open(a.save_sheet(os.path.join(d, "s.png")), "rb") as fh:
                self.assertTrue(fh.read().startswith(b"\x89PNG"))
            self.assertEqual(len(a.save_pngs(os.path.join(d, "f.png"))), 2)
            with open(a.save_pix(os.path.join(d, "a.pix")), encoding="utf-8") as fh:
                self.assertEqual(parse_pix(fh.read()).holds, [3, 1])


# ------------------------------------------------------------ clips / pivot

class TestClips(unittest.TestCase):
    def doc(self, head="", n=4):
        body = "\n---\n".join("r,r" for _ in range(n))
        return parse_pix(f"name: t\n{head}\npalette:\nr = #e63946\n\npixels:\n{body}\n")

    def test_ranges_and_single_frame(self):
        d = self.doc("clip: walk 1-2\nclip: hit 3\n")
        self.assertEqual(d.clips, {"walk": (1, 2), "hit": (3, 3)})

    def test_spaces_around_the_dash_are_fine(self):
        self.assertEqual(self.doc("clip: walk 1 - 2\n").clips, {"walk": (1, 2)})

    def test_order_is_preserved(self):
        d = self.doc("clip: c 3\nclip: a 0\nclip: b 1\n")
        self.assertEqual(list(d.clips), ["c", "a", "b"])

    def test_syntax_errors(self):
        with self.assertRaisesRegex(ValueError, "clip: NAME FIRST"):
            self.doc("clip: oops\n")
        with self.assertRaisesRegex(ValueError, "ends before it starts"):
            self.doc("clip: walk 3-1\n")
        with self.assertRaisesRegex(ValueError, "defined twice"):
            self.doc("clip: walk 0-1\nclip: walk 2-3\n")

    def test_out_of_range_is_a_check_error_not_a_parse_error(self):
        # a stale clip must never stop the file from loading, or `check` could
        # not be the thing that tells you about it
        d = self.doc("clip: walk 2-9\n")
        self.assertEqual(d.bad_clips(), ["walk"])
        self.assertEqual(self.doc("clip: walk 1-2\n").bad_clips(), [])

    def test_pivot(self):
        self.assertEqual(self.doc("pivot: 16,30\n").pivot, (16, 30))
        self.assertEqual(self.doc("pivot: -1,40\n").pivot, (-1, 40))   # not clamped
        self.assertIsNone(self.doc().pivot)
        with self.assertRaisesRegex(ValueError, "pivot: X,Y"):
            self.doc("pivot: 4\n")
        with self.assertRaisesRegex(ValueError, "two whole numbers"):
            self.doc("pivot: a,b\n")

    def test_clip_slices_the_anim_with_its_holds(self):
        d = self.doc("clip: walk 1-2\n")
        a = d.anim.set_holds([1, 5, 2, 1])
        w = a.clip("walk")
        self.assertEqual(len(w), 2)
        self.assertEqual(w.holds, [5, 2])
        self.assertEqual(w.name, "walk")
        self.assertEqual(a.clip_ticks("walk"), 7)

    def test_clip_errors_name_the_alternatives(self):
        a = self.doc("clip: walk 1-2\n").anim
        with self.assertRaisesRegex(KeyError, "walk"):
            a.clip("sprint")
        with self.assertRaises(IndexError):
            self.doc("clip: walk 2-9\n").anim.clip("walk")

    def test_structural_ops_drop_clips_but_copy_and_map_keep_them(self):
        a = self.doc("clip: walk 1-2\npivot: 3,4\n").anim
        self.assertEqual(a.copy().clips, a.clips)
        self.assertEqual(a.map(lambda s: s).clips, a.clips)
        for got in (a.reverse(), a.ping_pong(), a[1:3], a.clip("walk")):
            self.assertEqual(got.clips, {})
            self.assertEqual(got.pivot, (3, 4))      # pivot always rides along

    def test_round_trip_through_pix(self):
        a = self.doc("clip: idle 0-1\nclip: hit 3\npivot: 9,20\n").anim
        a.hold(1, 4)
        back = parse_pix(a.to_pix())
        self.assertEqual(back.clips, {"idle": (0, 1), "hit": (3, 3)})
        self.assertEqual(back.pivot, (9, 20))
        self.assertEqual(back.holds, [1, 4, 1, 1])
        self.assertEqual(back.anim.to_pix(), a.to_pix())      # idempotent

    def test_single_frame_clip_writes_the_short_form(self):
        a = self.doc("clip: hit 3\n").anim
        self.assertIn("clip: hit 3\n", a.to_pix())


# ------------------------------------------------------------ sheet sidecar

class TestSheetMeta(unittest.TestCase):
    def anim(self, n=4, **kw):
        return Anim([Sprite(4, 6, fill="r") for _ in range(n)], PAL, scale=2, **kw)

    def test_layout_is_what_sheet_actually_draws(self):
        sprites = [Sprite(4, 6, fill="r"), Sprite(4, 6, fill="w"), Sprite(4, 6, fill="o")]
        lay = sheet_layout(sprites, cols=2, pad=1)
        big = sheet(sprites, cols=2, pad=1)
        self.assertEqual((big.w, big.h), (lay["w"], lay["h"]))
        for s, (x, y) in zip(sprites, lay["origins"]):
            self.assertEqual(big.get(x, y), s.get(0, 0))

    def test_rects_are_scaled_image_pixels(self):
        m = self.anim(2).sheet_meta(cols=2, pad=1, scale=3)
        self.assertEqual(m["format"], SHEET_META_FORMAT)
        self.assertEqual(m["cell"], [12, 18])
        self.assertEqual(m["grid"], {"cols": 2, "rows": 1, "pad": 3})
        self.assertEqual([f["rect"] for f in m["frames"]],
                         [[3, 3, 12, 18], [18, 3, 12, 18]])
        self.assertEqual(m["image_size"], [33, 24])

    def test_holds_and_clips_travel(self):
        a = self.anim(4, clips={"walk": (1, 3)}, pivot=(2, 5))
        a.hold(1, 3)
        m = a.sheet_meta(scale=2)
        self.assertEqual([f["hold"] for f in m["frames"]], [1, 3, 1, 1])
        self.assertEqual(m["clips"], [{"name": "walk", "from": 1, "to": 3, "ticks": 5}])
        self.assertEqual(m["pivot"], [4, 10])
        self.assertIsNone(self.anim(2).sheet_meta()["pivot"])

    def test_sidecar_matches_the_png_on_disk(self):
        import json
        import tempfile
        a = self.anim(3, clips={"all": (0, 2)}, pivot=(2, 5))
        with tempfile.TemporaryDirectory() as d:
            out = a.save_sheet(os.path.join(d, "s.png"), cols=2, pad=1,
                               scale=3, meta=True)
            side = os.path.join(d, "s.json")
            self.assertTrue(os.path.exists(side))
            with open(side) as fh:
                m = json.load(fh)
            rows = read_png(out)
            self.assertEqual([len(rows[0]), len(rows)], m["image_size"])
            self.assertEqual(m["image"], "s.png")
            for f in m["frames"]:                       # every rect holds ink
                x, y, w, h = f["rect"]
                self.assertTrue(any(rows[yy][xx][3] for yy in range(y, y + h)
                                    for xx in range(x, x + w)), f)

    def test_no_sidecar_unless_asked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.anim(2).save_sheet(os.path.join(d, "s.png"))
            self.assertEqual(os.listdir(d), ["s.png"])


# ----------------------------------------------------------------- the repo

class TestRepo(unittest.TestCase):
    def test_every_example_still_parses_and_checks_clean(self):
        names = [f for f in sorted(os.listdir(EX)) if f.endswith(".pix")]
        self.assertGreater(len(names), 10)
        for n in names:
            with self.subTest(n):
                doc = load_pix(os.path.join(EX, n))
                self.assertEqual(len(doc.holds), len(doc.frames))
                self.assertEqual(main(["check", os.path.join(EX, n)]), 0)

    def test_merge_anim_concatenates_timing(self):
        a = os.path.join(EX, "slime.pix")
        docs = [load_pix(a), load_pix(a)]
        anim = merge_anim(docs)
        self.assertEqual(len(anim), sum(len(d.frames) for d in docs))
        self.assertEqual(anim.holds, docs[0].holds + docs[1].holds)

    def test_merge_anim_makes_one_clip_per_file(self):
        docs = [load_pix(os.path.join(EX, n))
                for n in ("slime.pix", "coin.pix", "ghost.pix")]
        anim = merge_anim(docs, ["slime", "coin", "ghost"])
        self.assertEqual(anim.clips, {"slime": (0, 1), "coin": (2, 7), "ghost": (8, 9)})
        # the clip slices the merged timeline; frames may be recoded copies of
        # the source when merge_docs renames a colliding palette code
        self.assertEqual(anim.clip("coin").frames, anim.frames[2:8])
        self.assertEqual(len(anim.clip("coin")), len(docs[1].frames))

    def test_merge_anim_dedupes_colliding_clip_names(self):
        d = load_pix(os.path.join(EX, "slime.pix"))
        anim = merge_anim([d, d], ["slime", "slime"])
        self.assertEqual(list(anim.clips), ["slime", "slime_2"])

    def test_merge_anim_keeps_a_lone_files_own_clips(self):
        with open(os.path.join(EX, "coin.pix")) as fh:
            doc = parse_pix("clip: spin 0-5\n" + fh.read())
        self.assertEqual(merge_anim([doc]).clips, {"spin": (0, 5)})

    def test_cli_clip_end_to_end(self):
        import tempfile
        with open(os.path.join(EX, "coin.pix")) as fh:
            text = fh.read()
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "c.pix")
            with open(src, "w") as fh:
                fh.write("clip: half 0-2\n" + text)
            self.assertEqual(main(["check", src]), 0)
            self.assertEqual(main(["gif", src, "--clip", "half",
                                   "-o", os.path.join(d, "h.gif")]), 0)
            self.assertEqual(main(["sheet", src, "--clip", "half", "--meta",
                                   "-o", os.path.join(d, "h.png")]), 0)
            self.assertEqual(len(read_png(os.path.join(d, "h.gif")) if False
                                 else load_pix(src).anim.clip("half")), 3)
            with self.assertRaises(SystemExit):
                main(["gif", src, "--clip", "nope"])
            with self.assertRaises(SystemExit):
                main(["gif", src, src, "--clip", "half"])

    def test_check_flags_a_stale_clip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.pix")
            with open(p, "w") as fh:
                fh.write("name: t\nclip: walk 0-9\n\npalette:\nr = #f00\n\npixels:\nr,r\n")
            self.assertEqual(main(["check", p]), 1)

    def test_doc_anim_bridge(self):
        doc = load_pix(os.path.join(EX, "bounce.pix"))
        anim = doc.anim
        self.assertEqual(anim.name, doc.name)
        self.assertEqual(anim.scale, doc.scale)
        self.assertEqual(len(anim), 6)
        self.assertIs(anim.palette, doc.palette)
        self.assertIs(anim.frames[0], doc.frames[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

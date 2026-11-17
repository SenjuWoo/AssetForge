"""Cut-outs, pixel art and sheet slicing."""

import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    PIL_OK = True
except ImportError:  # pragma: no cover
    PIL_OK = False

from assetforge import sprites
from assetforge.images import ImageError, flat_pixels


def load(path):
    with Image.open(path) as image:
        image.load()
        return image.copy()


class FloodTests(unittest.TestCase):
    def grid(self, rows):
        width = len(rows[0])
        return bytearray(int(cell) for row in rows for cell in row), width, len(rows)

    def test_fills_only_the_connected_region(self):
        mask, w, h = self.grid(["11011",
                                "10010",
                                "11011"])
        filled = bytearray(len(mask))
        box, area = sprites.flood(mask, w, h, [(0, 0)], filled)
        self.assertEqual(area, 5)
        self.assertEqual(box, (0, 0, 1, 2))
        self.assertEqual(bytes(filled), bytes([1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0]))
        # The right-hand island was never reached.
        self.assertEqual(mask[3], 1)

    def test_goes_around_a_wall(self):
        mask, w, h = self.grid(["1111",
                                "0001",
                                "1111"])
        _, area = sprites.flood(mask, w, h, [(0, 0)])
        self.assertEqual(area, 9)

    def test_a_blocked_seed_fills_nothing(self):
        mask, w, h = self.grid(["01", "11"])
        self.assertIsNone(sprites.flood(mask, w, h, [(0, 0)]))


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class CutoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def subject(self, background=(255, 255, 255), size=(80, 60)) -> Path:
        """A red disc with a background-coloured hole, on a flat background."""
        image = Image.new("RGB", size, background)
        draw = ImageDraw.Draw(image)
        draw.ellipse((20, 10, 59, 49), fill=(200, 30, 30))
        draw.rectangle((36, 26, 43, 33), fill=background)
        path = self.dir / "subject.png"
        image.save(path)
        return path

    def test_background_goes_and_the_inside_hole_stays(self):
        info = sprites.cutout(self.subject(), self.dir / "cut.png", trim=False, feather=0)
        cut = load(self.dir / "cut.png")
        self.assertEqual(cut.mode, "RGBA")
        self.assertEqual(cut.getpixel((2, 2))[3], 0)            # background
        self.assertEqual(cut.getpixel((30, 30)), (200, 30, 30, 255))  # subject
        self.assertEqual(cut.getpixel((40, 30))[3], 255)        # the enclosed hole is kept
        self.assertEqual(info["background"], "#ffffff")
        self.assertGreater(info["removed_fraction"], 0.5)

    def test_key_mode_removes_the_colour_everywhere(self):
        sprites.cutout(self.subject(), self.dir / "cut.png", trim=False, feather=0, mode="key")
        self.assertEqual(load(self.dir / "cut.png").getpixel((40, 30))[3], 0)

    def test_trim_crops_to_the_subject_and_reports_where_it_was(self):
        info = sprites.cutout(self.subject(), self.dir / "cut.png", padding=3, feather=0)
        self.assertEqual((info["width"], info["height"]), (40 + 6, 40 + 6))
        self.assertEqual(info["offset"], [17, 7])
        self.assertEqual(info["anchor"], [23, 43])
        self.assertEqual(info["source_size"], [80, 60])

    def test_an_explicit_key_colour_is_used(self):
        source = self.subject(background=(10, 200, 10))
        info = sprites.cutout(source, self.dir / "cut.png", key="#0ac80a", trim=False)
        self.assertEqual(info["background"], "#0ac80a")
        self.assertEqual(load(self.dir / "cut.png").getpixel((1, 1))[3], 0)

    def test_soft_edges_lose_the_background_tint(self):
        # A half-covered edge pixel: 50% red over white.
        image = Image.new("RGB", (9, 9), (255, 255, 255))
        ImageDraw.Draw(image).rectangle((3, 3, 5, 5), fill=(200, 0, 0))
        image.putpixel((2, 4), (228, 128, 128))
        image.save(self.dir / "edge.png")
        sprites.cutout(self.dir / "edge.png", self.dir / "cut.png", trim=False, feather=1, tolerance=16)
        red, green, blue, alpha = load(self.dir / "cut.png").getpixel((2, 4))
        self.assertTrue(0 < alpha < 255, alpha)
        self.assertLess(green, 60)   # the white share is gone
        self.assertGreater(red, 180)

    def test_transparent_pixels_carry_the_subject_colour_not_the_background(self):
        sprites.cutout(self.subject(), self.dir / "cut.png", trim=False, feather=0)
        red, green, blue, alpha = load(self.dir / "cut.png").getpixel((19, 30))  # just left of the disc
        self.assertEqual(alpha, 0)
        self.assertGreater(red, green + 40)

    def test_an_already_transparent_picture_is_only_trimmed(self):
        image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 12, 19, 29), fill=(0, 0, 255, 255))
        image.save(self.dir / "clear.png")
        info = sprites.cutout(self.dir / "clear.png", self.dir / "cut.png", padding=0)
        self.assertFalse(info["keyed"])
        self.assertEqual((info["width"], info["height"]), (10, 18))

    def test_a_busy_border_is_reported(self):
        image = Image.new("RGB", (40, 40))
        image.putdata([((x * 37) % 256, (y * 91) % 256, (x * y) % 256) for y in range(40) for x in range(40)])
        image.save(self.dir / "busy.png")
        info = sprites.cutout(self.dir / "busy.png", self.dir / "cut.png", trim=False)
        self.assertTrue(any("border" in item for item in info["warnings"]))

    def test_a_picture_that_is_all_background_is_refused(self):
        Image.new("RGB", (20, 20), (9, 9, 9)).save(self.dir / "flat.png")
        with self.assertRaises(ImageError):
            sprites.cutout(self.dir / "flat.png", self.dir / "cut.png")
        self.assertFalse((self.dir / "cut.png").exists())

    def test_bad_values_are_refused(self):
        source = self.subject()
        for bad in ({"mode": "magic"}, {"tolerance": 999}, {"feather": 50}, {"key": "white"}, {"padding": -1}):
            with self.assertRaises(ImageError, msg=str(bad)):
                sprites.cutout(source, self.dir / "cut.png", **bad)


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class PixelArtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        image = Image.linear_gradient("L").resize((200, 100)).convert("RGB")
        ImageDraw.Draw(image).ellipse((60, 20, 140, 80), fill=(230, 40, 60))
        self.source = self.dir / "art.png"
        image.save(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scales_to_the_size_and_keeps_to_the_palette(self):
        info = sprites.pixelate(self.source, self.dir / "px.png", size=50, palette="pico8")
        self.assertEqual((info["width"], info["height"]), (50, 25))
        allowed = set(sprites.load_palette("pico8"))
        seen = {color[:3] for _, color in load(self.dir / "px.png").getcolors(maxcolors=4096)}
        self.assertTrue(seen <= allowed, seen - allowed)
        self.assertEqual(info["colors_used"], len(seen))

    def test_picks_its_own_colours_when_no_palette_is_named(self):
        info = sprites.pixelate(self.source, self.dir / "px.png", size=40, colors=4)
        self.assertLessEqual(info["colors_used"], 4)

    def test_alpha_becomes_on_or_off_and_empty_space_takes_no_colour(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse((8, 8, 55, 55), fill=(40, 200, 90, 255))
        image.save(self.dir / "a.png")
        info = sprites.pixelate(self.dir / "a.png", self.dir / "px.png", size=16, colors=2)
        out = load(self.dir / "px.png")
        self.assertEqual(set(flat_pixels(out.getchannel("A"))), {0, 255})
        # Both colours go to the subject; the empty area takes none of them.
        self.assertLessEqual(info["colors_used"], 2)
        for red, green, blue in {color[:3] for color, alpha in zip(flat_pixels(out), flat_pixels(out.getchannel("A"))) if alpha}:
            self.assertGreater(green, red + 60)

    def test_a_small_picture_is_not_enlarged(self):
        Image.new("RGB", (10, 6), (5, 5, 5)).save(self.dir / "s.png")
        info = sprites.pixelate(self.dir / "s.png", self.dir / "px.png", size=64)
        self.assertEqual((info["width"], info["height"]), (10, 6))

    def test_preview_is_an_exact_enlargement(self):
        info = sprites.pixelate(self.source, self.dir / "px.png", size=20, palette="gameboy",
                                preview=self.dir / "big.png", preview_scale=4)
        small, big = load(self.dir / "px.png"), load(self.dir / "big.png")
        self.assertEqual(big.size, (small.width * 4, small.height * 4))
        self.assertEqual(big.getpixel((9, 9)), small.getpixel((2, 2)))
        self.assertIn("preview", info)

    def test_is_deterministic(self):
        sprites.pixelate(self.source, self.dir / "a.png", size=32, palette="db16", dither=True)
        sprites.pixelate(self.source, self.dir / "b.png", size=32, palette="db16", dither=True)
        self.assertEqual((self.dir / "a.png").read_bytes(), (self.dir / "b.png").read_bytes())

    def test_a_palette_file_is_read(self):
        (self.dir / "two.hex").write_text("; a comment\n000000\nffffff\n", encoding="utf-8")
        self.assertEqual(sprites.load_palette(self.dir / "two.hex"), [(0, 0, 0), (255, 255, 255)])
        (self.dir / "g.gpl").write_text("GIMP Palette\nName: x\n#\n255 0 0\tred\n0 0 255 blue\n", encoding="utf-8")
        self.assertEqual(sprites.load_palette(self.dir / "g.gpl"), [(255, 0, 0), (0, 0, 255)])
        Image.new("RGB", (2, 1)).save(self.dir / "p.png")
        with self.assertRaises(ImageError):
            sprites.load_palette(self.dir / "p.png")  # one colour is not a palette

    def test_every_built_in_palette_parses(self):
        for name in sprites.PALETTES:
            colors = sprites.load_palette(name)
            self.assertEqual(len(colors), len(set(colors)), name)

    def test_bad_values_are_refused(self):
        for bad in ({"size": 2}, {"colors": 1}, {"palette": "nope"}, {"preview_scale": 99}):
            with self.assertRaises(ImageError, msg=str(bad)):
                sprites.pixelate(self.source, self.dir / "px.png", **bad)


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class SliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def sheet(self) -> Path:
        """Three 8x8 blobs on a 4x2 grid of 16x16 cells; the rest is empty."""
        image = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for column, row, color in ((0, 0, (255, 0, 0, 255)), (2, 0, (0, 255, 0, 255)), (1, 1, (0, 0, 255, 255))):
            draw.rectangle((column * 16 + 4, row * 16 + 4, column * 16 + 11, row * 16 + 11), fill=color)
        path = self.dir / "sheet.png"
        image.save(path)
        return path

    def test_grid_by_columns_and_rows_skips_empty_cells(self):
        result = sprites.slice_sheet(self.sheet(), self.dir / "frames", columns=4, rows=2)
        self.assertEqual([(f["x"], f["y"], f["w"], f["h"]) for f in result["frames"]],
                         [(0, 0, 16, 16), (32, 0, 16, 16), (16, 16, 16, 16)])
        self.assertEqual(load(self.dir / "frames" / "sheet_001.png").getpixel((8, 8)), (0, 255, 0, 255))

    def test_grid_by_cell_size_can_keep_empty_cells(self):
        result = sprites.slice_sheet(self.sheet(), self.dir / "frames", cell_width=16, cell_height=16, keep_empty=True)
        self.assertEqual(len(result["frames"]), 8)

    def test_auto_finds_each_island_in_reading_order(self):
        result = sprites.slice_sheet(self.sheet(), self.dir / "frames", mode="auto")
        self.assertEqual([(f["x"], f["y"], f["w"], f["h"]) for f in result["frames"]],
                         [(4, 4, 8, 8), (36, 4, 8, 8), (20, 20, 8, 8)])

    def test_auto_drops_specks(self):
        image = load(self.sheet())
        image.putpixel((60, 30), (255, 255, 255, 255))
        image.save(self.dir / "speck.png")
        result = sprites.slice_sheet(self.dir / "speck.png", self.dir / "frames", mode="auto", min_area=4)
        self.assertEqual(len(result["frames"]), 3)

    def test_auto_needs_transparency(self):
        Image.new("RGB", (32, 32), (9, 9, 9)).save(self.dir / "opaque.png")
        with self.assertRaises(ImageError):
            sprites.slice_sheet(self.dir / "opaque.png", self.dir / "frames", mode="auto")

    def test_grid_without_a_layout_is_refused(self):
        with self.assertRaises(ImageError):
            sprites.slice_sheet(self.sheet(), self.dir / "frames")
        with self.assertRaises(ImageError):
            sprites.slice_sheet(self.sheet(), self.dir / "frames", cell_width=16)


if __name__ == "__main__":
    unittest.main()

"""Seamless tiling and the PBR map set derived from a colour map."""

import json
import math
import random
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageFilter
    PIL_OK = True
except ImportError:  # pragma: no cover
    PIL_OK = False

from assetforge import texture
from assetforge.images import ImageError


def cloudy(path: Path, size=(96, 64), seed=7) -> Path:
    """A soft, non-repeating picture with a strong left-right and top-bottom
    drift, so its edges do not match."""
    rng = random.Random(seed)
    noise = Image.new("L", size)
    noise.putdata([rng.randrange(256) for _ in range(size[0] * size[1])])
    noise = noise.filter(ImageFilter.GaussianBlur(3))
    ramp = Image.linear_gradient("L").resize(size)
    side = Image.linear_gradient("L").rotate(90).resize(size)
    mix = ImageChops.add(ImageChops.add(noise, ramp, scale=2), side, scale=2)
    Image.merge("RGB", (mix, ImageChops.invert(mix), noise)).save(path)
    return path


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class SeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_drifting_picture_fails_the_seam_check(self):
        report = texture.seam_report(cloudy(self.dir / "c.png"))
        self.assertEqual(report["status"], "FAIL")
        self.assertGreater(report["worst_ratio"], texture.SEAM_WARN)

    def test_a_flat_picture_passes(self):
        Image.new("RGB", (32, 32), (90, 120, 40)).save(self.dir / "flat.png")
        self.assertEqual(texture.seam_report(self.dir / "flat.png")["status"], "PASS")

    def test_a_picture_that_repeats_passes(self):
        # A pattern whose period divides the size wraps exactly.
        tile = Image.new("L", (64, 64))
        tile.putdata([int(127 + 120 * math.sin(x * math.tau / 16) * math.cos(y * math.tau / 32))
                      for y in range(64) for x in range(64)])
        tile.save(self.dir / "wave.png")
        self.assertEqual(texture.seam_report(self.dir / "wave.png")["status"], "PASS")

    def test_make_tileable_removes_the_seam_and_keeps_the_size(self):
        source = cloudy(self.dir / "c.png")
        info = texture.make_tileable(source, self.dir / "t.png")
        self.assertEqual((info["width"], info["height"]), (96, 64))
        self.assertEqual(info["seam_before"]["status"], "FAIL")
        self.assertEqual(info["seam_after"]["status"], "PASS", info["seam_after"])
        # The file on disk is what was measured.
        self.assertEqual(texture.seam_report(self.dir / "t.png")["status"], "PASS")
        # The source is untouched.
        self.assertEqual(texture.seam_report(source)["status"], "FAIL")

    def test_make_tileable_keeps_alpha(self):
        image = Image.open(cloudy(self.dir / "c.png")).convert("RGBA")
        image.putalpha(200)
        image.save(self.dir / "a.png")
        info = texture.make_tileable(self.dir / "a.png", self.dir / "t.png")
        self.assertTrue(info["has_alpha"])

    def test_blend_out_of_range_is_refused(self):
        source = cloudy(self.dir / "c.png")
        for blend in (0.0, 0.9):
            with self.assertRaises(ImageError):
                texture.make_tileable(source, self.dir / "t.png", blend=blend)
        self.assertFalse((self.dir / "t.png").exists())

    def test_tiny_pictures_are_refused(self):
        Image.new("RGB", (2, 2)).save(self.dir / "tiny.png")
        with self.assertRaises(ImageError):
            texture.make_tileable(self.dir / "tiny.png", self.dir / "t.png")

    def test_tile_preview_repeats_the_texture(self):
        source = cloudy(self.dir / "c.png")
        info = texture.tile_preview(source, self.dir / "p.png", repeat=2)
        self.assertEqual((info["width"], info["height"]), (192, 128))


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class NormalTests(unittest.TestCase):
    def ramp(self, direction: str):
        """Height rising toward `direction` of the picture."""
        base = Image.linear_gradient("L")  # black at the top, white at the bottom
        turn = {"down": 0, "right": 90, "up": 180, "left": 270}[direction]
        return base.rotate(turn).resize((32, 32))

    def centre(self, image):
        return image.getpixel((16, 16))

    def test_flat_height_points_straight_up(self):
        normal = texture.normal_from_height(Image.new("L", (16, 16), 100))
        self.assertEqual(normal.getpixel((8, 8)), (128, 128, 255))

    def test_a_rise_to_the_right_leans_the_normal_left(self):
        red, green, blue = self.centre(texture.normal_from_height(self.ramp("right"), wrap=False))
        self.assertLess(red, 120)
        self.assertAlmostEqual(green, 128, delta=2)
        self.assertGreater(blue, 128)

    def test_green_follows_the_convention(self):
        up = self.ramp("up")
        opengl = self.centre(texture.normal_from_height(up, convention="opengl", wrap=False))
        directx = self.centre(texture.normal_from_height(up, convention="directx", wrap=False))
        # Rising toward the top of the picture: the surface normal leans down.
        self.assertLess(opengl[1], 120)
        self.assertGreater(directx[1], 136)
        self.assertAlmostEqual(opengl[0], 128, delta=2)

    def test_strength_steepens_the_slope(self):
        soft = self.centre(texture.normal_from_height(self.ramp("right"), strength=1, wrap=False))
        hard = self.centre(texture.normal_from_height(self.ramp("right"), strength=8, wrap=False))
        self.assertLess(hard[0], soft[0])

    def test_unwrapped_edges_do_not_read_the_far_side(self):
        normal = texture.normal_from_height(self.ramp("right"), wrap=False)
        left, mid = normal.getpixel((0, 16)), normal.getpixel((16, 16))
        self.assertAlmostEqual(left[0], mid[0], delta=30)
        wrapped = texture.normal_from_height(self.ramp("right"), wrap=True).getpixel((0, 16))
        self.assertGreater(wrapped[0], 200)  # the wrap sees a cliff there

    def test_unknown_convention_is_refused(self):
        with self.assertRaises(ImageError):
            texture.normal_from_height(Image.new("L", (8, 8)), convention="unity")


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class PbrSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.source = cloudy(self.dir / "stone.png", size=(64, 64))

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_every_map_and_the_material_record(self):
        result = texture.make_pbr_set(self.source, self.dir / "out")
        self.assertEqual(sorted(result["files"]), ["height", "metallic", "normal", "occlusion", "orm", "roughness"])
        for kind, path in result["files"].items():
            with Image.open(path) as image:
                self.assertEqual(image.size, (64, 64), kind)
                self.assertEqual(image.mode, "RGB" if kind in ("normal", "orm") else "L", kind)
        material = json.loads(result["material"].read_text(encoding="utf-8"))
        self.assertEqual(material["maps"]["base_color"], "stone.png")
        self.assertEqual(material["maps"]["normal"], "stone-normal.png")
        self.assertEqual(material["normal_convention"], "opengl")
        self.assertEqual(material["orm_channels"], {"r": "occlusion", "g": "roughness", "b": "metallic"})
        self.assertEqual(result["normal_check"]["status"], "PASS")

    def test_orm_channels_are_the_single_maps(self):
        result = texture.make_pbr_set(self.source, self.dir / "out", metallic=1.0)
        orm = Image.open(result["files"]["orm"]).split()
        for channel, kind in zip(orm, ("occlusion", "roughness", "metallic")):
            self.assertEqual(channel.tobytes(), Image.open(result["files"][kind]).tobytes(), kind)
        self.assertEqual(Image.open(result["files"]["metallic"]).getextrema(), (255, 255))

    def test_roughness_sits_at_the_base_without_variation(self):
        low = texture.make_pbr_set(self.source, self.dir / "low", roughness=0.2, roughness_variation=0.0)
        self.assertEqual(Image.open(low["files"]["roughness"]).getextrema(), (51, 51))

    def test_tileable_maps_wrap(self):
        tiled = self.dir / "tiled.png"
        texture.make_tileable(self.source, tiled)
        result = texture.make_pbr_set(tiled, self.dir / "out", tileable=True)
        for kind in ("height", "normal", "occlusion"):
            self.assertNotEqual(texture.seam_report(result["files"][kind])["status"], "FAIL", kind)

    def test_is_deterministic(self):
        one = texture.make_pbr_set(self.source, self.dir / "a")
        two = texture.make_pbr_set(self.source, self.dir / "b")
        for kind in one["files"]:
            self.assertEqual(one["files"][kind].read_bytes(), two["files"][kind].read_bytes(), kind)

    def test_out_of_range_values_are_refused(self):
        for bad in ({"strength": 0}, {"roughness": 1.5}, {"metallic": -0.1}, {"ao_strength": 9}, {"convention": "x"}):
            with self.assertRaises(ImageError, msg=str(bad)):
                texture.make_pbr_set(self.source, self.dir / "bad", **bad)

    def test_a_leaning_normal_map_is_flagged(self):
        harsh = Image.new("RGB", (8, 8), (20, 128, 90))
        self.assertEqual(texture.normal_check(harsh)["status"], "WARNING")


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, make_png

sys.path.insert(0, str(ROOT / "src"))

from assetforge import images  # noqa: E402


@unittest.skipUnless(images.available(), "Pillow is required")
class ImageTests(unittest.TestCase):
    def test_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_png(Path(tmp) / "source.png")
            info = images.inspect_image(path)
            self.assertEqual((info["width"], info["height"]), (128, 96))
            self.assertTrue(info["has_alpha"])

    def test_convert_resize_and_thumbnail(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_png(Path(tmp) / "source.png")
            target = Path(tmp) / "out.webp"
            result = images.convert_image(source, target, "webp", width=64)
            self.assertTrue(target.exists())
            self.assertEqual(result["width"], 64)
            self.assertTrue(result["has_alpha"])
            thumb = Path(tmp) / "thumb.png"
            result = images.thumbnail(target, thumb, size=32)
            self.assertLessEqual(max(result["width"], result["height"]), 32)

    def test_jpeg_flattens_alpha_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_png(Path(tmp) / "source.png")
            target = Path(tmp) / "out.jpg"
            result = images.convert_image(source, target, "jpeg")
            self.assertTrue(any("alpha" in warning for warning in result["warnings"]))

    def test_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = make_png(Path(tmp) / "a.png")
            second = make_png(Path(tmp) / "b.png", size=(128, 96))
            self.assertTrue(images.compare_images(first, second)["identical"])
            third = make_png(Path(tmp) / "c.png", size=(128, 96), alpha=False)
            self.assertFalse(images.compare_images(first, third)["identical"])

    def test_bad_input_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.png"
            bad.write_text("not an image")
            with self.assertRaises(images.ImageError):
                images.inspect_image(bad)


if __name__ == "__main__":
    unittest.main()

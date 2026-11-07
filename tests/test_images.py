import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_pack_orm_and_atlas(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {}
            for name, value in (("occlusion", 64), ("roughness", 128), ("metallic", 255)):
                path = root / f"{name}.png"
                Image.new("L", (32, 32), value).save(path)
                paths[name] = path
            target = root / "orm.png"
            info = images.pack_orm(paths["occlusion"], paths["roughness"], paths["metallic"], target)
            self.assertEqual((info["width"], info["height"]), (32, 32))
            with Image.open(target) as packed:
                self.assertEqual(packed.convert("RGB").getpixel((0, 0)), (64, 128, 255))
            self.assertEqual(info["channels"], {"r": "occlusion", "g": "roughness", "b": "metallic"})

            sources = []
            for index, color in enumerate([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]):
                path = root / f"frame-{index}.png"
                Image.new("RGBA", (16, 16), color).save(path)
                sources.append(path)
            atlas = root / "atlas.png"
            metadata = root / "atlas.json"
            info = images.make_atlas(sources, atlas, metadata, columns=2, padding=1)
            self.assertEqual((info["width"], info["height"]), (35, 35))
            data = json.loads(metadata.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["columns"], 2)
            self.assertEqual(len(data["frames"]), 4)
            self.assertEqual(data["frames"][3]["x"], 18)
            self.assertEqual(data["frames"][3]["y"], 18)

    def test_pack_orm_rejects_mismatched_sizes_without_opt_in(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            occlusion = root / "ao.png"
            roughness = root / "rough.png"
            metallic = root / "metal.png"
            Image.new("L", (32, 32), 64).save(occlusion)
            Image.new("L", (16, 16), 128).save(roughness)
            Image.new("L", (32, 32), 255).save(metallic)
            with self.assertRaises(images.ImageError) as caught:
                images.pack_orm(occlusion, roughness, metallic, root / "orm.png")
            self.assertIn("resize=true", str(caught.exception))
            result = images.pack_orm(occlusion, roughness, metallic, root / "orm.png", resize=True)
            self.assertTrue(result["warnings"])

    def test_atlas_rejects_excess_and_invalid_limits(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = []
            for index in range(65):
                path = root / f"{index:03d}.png"
                Image.new("RGBA", (4, 4), (index, 0, 0, 255)).save(path)
                sources.append(path)
            with self.assertRaises(images.ImageError) as caught:
                images.make_atlas(sources, root / "atlas.png", root / "atlas.json")
            self.assertIn("at most 64", str(caught.exception))
            with self.assertRaises(images.ImageError):
                images.make_atlas(sources[:1], root / "atlas.png", root / "atlas.json", columns=0)
            with self.assertRaises(images.ImageError):
                images.make_atlas(sources[:1], root / "atlas.png", root / "atlas.json", padding=-1)
            with mock.patch.object(images, "ATLAS_MAX_SIDE", 7):
                with self.assertRaises(images.ImageError):
                    images.make_atlas(sources[:1], root / "atlas.png", root / "atlas.json")
            with mock.patch.object(images, "ATLAS_MAX_PIXELS", 20):
                with self.assertRaises(images.ImageError):
                    images.make_atlas(sources[:2], root / "atlas.png", root / "atlas.json", padding=0)

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

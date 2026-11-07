"""Image operations on top of Pillow.

Pillow is optional: inspection and conversion raise a clear error when it is
missing, and `doctor` reports the provider as unavailable. No custom codec is
implemented here.
"""

from __future__ import annotations

from pathlib import Path

from .util import sha256_file, write_json

FORMATS = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}


class ImageError(RuntimeError):
    pass


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def _pillow():
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImageError("Pillow is not installed; run `pip install Pillow` or the installer with -WithImages") from exc
    return Image


def open_image(path: Path):
    Image = _pillow()
    try:
        image = Image.open(path)
        image.load()
        return image
    except Exception as exc:  # Pillow raises several unrelated exception types
        raise ImageError(f"cannot read image {path}: {exc}") from exc


def inspect_image(path: Path) -> dict:
    path = Path(path)
    image = open_image(path)
    alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "format": image.format,
        "mode": image.mode,
        "width": image.width,
        "height": image.height,
        "aspect_ratio": round(image.width / image.height, 4) if image.height else None,
        "has_alpha": bool(alpha),
        "frames": int(getattr(image, "n_frames", 1)),
        "dpi": list(image.info.get("dpi", [])) if image.info.get("dpi") else None,
        "icc_profile": bool(image.info.get("icc_profile")),
    }


def convert_image(
    source: Path,
    target: Path,
    fmt: str | None = None,
    width: int = 0,
    height: int = 0,
    quality: int = 90,
) -> dict:
    """Resize and re-encode into `target`. Writes via a sibling temp file and
    replaces the target only after a successful save."""
    source, target = Path(source), Path(target)
    fmt = (fmt or target.suffix.lstrip(".") or "png").lower()
    if fmt not in FORMATS:
        raise ImageError(f"unsupported output format {fmt!r}")
    image = open_image(source)
    warnings = []
    if width or height:
        from PIL import Image

        new_size = (int(width) if width else round(image.width * (int(height) / image.height)), int(height) if height else round(image.height * (int(width) / image.width)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    if FORMATS[fmt] == "JPEG":
        if image.mode in ("RGBA", "LA", "P"):
            from PIL import Image

            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
            warnings.append("alpha flattened onto white for JPEG")
        elif image.mode != "RGB":
            image = image.convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".part")
    save_kwargs = {}
    if FORMATS[fmt] in ("JPEG", "WEBP"):
        save_kwargs["quality"] = int(quality)
    if FORMATS[fmt] == "PNG":
        save_kwargs["optimize"] = True
    try:
        image.save(temp, format=FORMATS[fmt], **save_kwargs)
        temp.replace(target)
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        raise ImageError(f"cannot write {target}: {exc}") from exc
    result = inspect_image(target)
    result["warnings"] = warnings
    result["source"] = str(source)
    return result


def thumbnail(source: Path, target: Path, size: int = 256) -> dict:
    source, target = Path(source), Path(target)
    image = open_image(source)
    from PIL import Image

    image = image.convert("RGBA") if image.mode in ("RGBA", "LA", "P") else image.convert("RGB")
    image.thumbnail((int(size), int(size)), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".part")
    try:
        image.save(temp, format="PNG", optimize=True)
        temp.replace(target)
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        raise ImageError(f"cannot write thumbnail {target}: {exc}") from exc
    return inspect_image(target)


def pack_orm(occlusion: Path, roughness: Path, metallic: Path, target: Path) -> dict:
    """Pack three grayscale maps into an RGB occlusion/roughness/metallic
    texture. R=occlusion, G=roughness, B=metallic."""
    from PIL import Image

    base = open_image(occlusion)
    size = base.size
    channels = []
    sources = []
    warnings = []
    for role, path in (("occlusion", occlusion), ("roughness", roughness), ("metallic", metallic)):
        image = open_image(path)
        if image.size != size:
            warnings.append(f"{role} was {image.width}x{image.height}, resized to {size[0]}x{size[1]}")
            image = image.resize(size, Image.Resampling.LANCZOS)
        channels.append(image.convert("L"))
        sources.append({"role": role, "name": Path(path).name})
    merged = Image.merge("RGB", tuple(channels))
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".part")
    try:
        merged.save(temp, format="PNG", optimize=True)
        temp.replace(target)
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        raise ImageError(f"cannot write ORM texture {target}: {exc}") from exc
    result = inspect_image(target)
    result.update({
        "channels": {"r": "occlusion", "g": "roughness", "b": "metallic"},
        "sources": sources,
        "warnings": warnings,
    })
    return result


def make_atlas(sources: list[Path], target: Path, metadata: Path, columns: int = 4, padding: int = 2) -> dict:
    """Pack images into a fixed grid and write frame metadata. Cell size is the
    largest source image; frames record their original dimensions."""
    from PIL import Image

    paths = [Path(item) for item in sources]
    if not paths:
        raise ImageError("atlas needs at least one image")
    if len(paths) > 64:
        raise ImageError("atlas is limited to 64 images")
    images = [open_image(path) for path in paths]
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    cols = max(1, min(int(columns), len(paths)))
    rows = (len(paths) + cols - 1) // cols
    width = padding + cols * (cell_w + padding)
    height = padding + rows * (cell_h + padding)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    frames = []
    for index, (path, image) in enumerate(zip(paths, images)):
        x = padding + (index % cols) * (cell_w + padding)
        y = padding + (index // cols) * (cell_h + padding)
        canvas.alpha_composite(image.convert("RGBA"), (x, y))
        frames.append({"name": path.name, "x": x, "y": y, "w": image.width, "h": image.height})
    target, metadata = Path(target), Path(metadata)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".part")
    try:
        canvas.save(temp, format="PNG", optimize=True)
        temp.replace(target)
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        raise ImageError(f"cannot write atlas {target}: {exc}") from exc
    write_json(metadata, {
        "schema": 1,
        "image": target.name,
        "width": width,
        "height": height,
        "cell": [cell_w, cell_h],
        "columns": cols,
        "rows": rows,
        "padding": padding,
        "frames": frames,
    })
    result = inspect_image(target)
    result["frame_count"] = len(frames)
    result["metadata"] = metadata.name
    return result


def compare_images(first: Path, second: Path) -> dict:
    first_path, second_path = Path(first), Path(second)
    a = open_image(first_path).convert("RGBA")
    b = open_image(second_path).convert("RGBA")
    if a.size != b.size:
        from PIL import Image

        b = b.resize(a.size, Image.Resampling.LANCZOS)
    from PIL import ImageChops, ImageStat

    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    mean_abs = sum(stat.mean) / len(stat.mean)
    extrema = diff.getextrema()
    changed = 0
    pixels = a.width * a.height
    if pixels:
        gray = diff.convert("L")
        histogram = gray.histogram()
        changed = sum(histogram[1:])
    return {
        "first": str(first_path),
        "second": str(second_path),
        "width": a.width,
        "height": a.height,
        "mean_abs_diff": round(mean_abs, 4),
        "max_abs_diff": max(item[1] for item in extrema),
        "changed_pixel_fraction": round(changed / pixels, 6) if pixels else None,
        "identical": mean_abs == 0,
    }


def write_report(path: Path, data: dict) -> None:
    write_json(path, data)

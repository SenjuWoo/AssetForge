"""Texture work on top of Pillow: seamless tiling and a PBR map set from one
colour map.

Everything here is deterministic image arithmetic. `ImageChops.offset` wraps
around the edges, so a derivative or a blur taken through it is already
correct for a texture that tiles. The maps a colour picture yields (height,
normal, roughness, occlusion) are estimates, not measurements, and the
callers record them as such.
"""

from __future__ import annotations

import math
from pathlib import Path

from .images import ImageError, flat_pixels, inspect_image, open_image, save_image
from .util import write_json

# Seam ratio: how much the wrap-around edge differs from one pixel to the
# next, against the busiest ordinary columns or rows of the same picture.
SEAM_PASS = 1.3
SEAM_WARN = 2.0
# Below this mean step (of 255) a picture is flat; the floor keeps a flat
# picture from dividing by nothing.
SEAM_FLOOR = 0.5
MAX_SIDE = 8192


def _math():
    from PIL import ImageMath

    if not hasattr(ImageMath, "lambda_eval"):
        raise ImageError("Pillow 10.3 or later is needed for texture maps; run `pip install -U Pillow`")
    return ImageMath


def _check_size(image, what: str = "texture") -> None:
    if image.width < 4 or image.height < 4:
        raise ImageError(f"{what} is {image.width}x{image.height}; at least 4x4 is needed")
    if image.width > MAX_SIDE or image.height > MAX_SIDE:
        raise ImageError(f"{what} is {image.width}x{image.height}; the limit is {MAX_SIDE}px a side")


def _line_means(image, axis: str) -> list[float]:
    """Mean of every column (axis 'x') or row (axis 'y') of an L image."""
    from PIL import Image

    size = (image.width, 1) if axis == "x" else (1, image.height)
    return flat_pixels(image.convert("F").resize(size, Image.Resampling.BOX))


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, int(fraction * (len(ordered) - 1) + 0.5))]


def seam_report(source) -> dict:
    """Measure both wrap-around seams of an image (a path or an open image).

    A ratio near 1 means the edge that meets itself when the texture repeats
    is no rougher than the inside of the picture."""
    from PIL import ImageChops

    image = source if hasattr(source, "convert") else open_image(Path(source))
    _check_size(image)
    gray = image.convert("L")
    result = {}
    for axis, shift in (("x", (1, 0)), ("y", (0, 1))):
        # After a one-pixel wrap shift, line 0 of the difference is the seam.
        steps = _line_means(ImageChops.difference(gray, ImageChops.offset(gray, *shift)), axis)
        seam, inside = steps[0], steps[1:]
        usual = max(_percentile(inside, 0.95), SEAM_FLOOR)
        result[axis] = {"seam": round(seam, 3), "inside_p95": round(usual, 3), "ratio": round(seam / usual, 3)}
    worst = max(result["x"]["ratio"], result["y"]["ratio"])
    status = "PASS" if worst <= SEAM_PASS else "WARNING" if worst <= SEAM_WARN else "FAIL"
    return {"x": result["x"], "y": result["y"], "worst_ratio": worst, "status": status,
            "detail": f"seam/inside step ratio x {result['x']['ratio']}, y {result['y']['ratio']} (pass <= {SEAM_PASS})"}


def _ramp(band: int, length: int):
    """An upright mask running 0 at its left edge to 255 at its right, with
    a smooth start and end."""
    from PIL import Image

    values = []
    for index in range(band):
        t = index / max(1, band - 1)
        values.append(int(round(255 * t * t * (3 - 2 * t))))
    strip = Image.new("L", (band, 1))
    strip.putdata(values)
    return strip.resize((band, length), Image.Resampling.NEAREST)


def _cut_mask(head, tail):
    """Where an upright band switches from `tail` (0, its left edge) to
    `head` (255, its right edge): along the top-to-bottom path where the two
    differ least, so the switch runs through places that look alike in both.
    The path is found on a reduced copy of the band; that keeps the search
    fast on a large texture and costs nothing visible."""
    from array import array
    from operator import add

    from PIL import Image, ImageChops, ImageFilter

    band, length = head.size
    difference = ImageChops.difference(head.convert("RGB"), tail.convert("RGB")).convert("L")
    factor = max(1, -(-length // 1024))
    small_w, small_h = max(4, band // factor), max(4, length // factor)
    small = difference if factor == 1 else difference.resize((small_w, small_h), Image.Resampling.BOX)
    small_w, small_h = small.size
    data = small.tobytes()
    margin = max(1, small_w // 8)
    wall = 1 << 40
    blocked = [wall] * margin
    open_cells = small_w - 2 * margin
    rows = []
    previous: list = []
    for y in range(small_h):
        cost = list(data[y * small_w + margin:y * small_w + margin + open_cells])
        if y:
            inner = previous[margin:margin + open_cells]
            best = map(min, [wall] + inner[:-1], inner, inner[1:] + [wall])
            cost = list(map(add, cost, best))
        previous = blocked + cost + blocked
        rows.append(array("q", previous))
    x = min(range(small_w), key=previous.__getitem__)
    path = [0] * small_h
    for y in range(small_h - 1, -1, -1):
        path[y] = x
        if y:
            above = rows[y - 1]
            x = min((c for c in (x - 1, x, x + 1) if 0 <= c < small_w), key=above.__getitem__)
    mask = Image.frombytes("L", (small_w, small_h), b"".join(bytes(at) + b"\xff" * (small_w - at) for at in path))
    if mask.size != (band, length):
        mask = mask.resize((band, length), Image.Resampling.BILINEAR)
    mask = mask.filter(ImageFilter.GaussianBlur(max(1.0, band * 0.02)))
    # The band's outer lines must be purely one layer, or the wrap would not match.
    mask.paste(0, (0, 0, 1, length))
    mask.paste(255, (band - 1, 0, band, length))
    return mask


def _fold(image, band: int, vertical: bool):
    """Lay the last `band` lines over the first ones and drop them, so the
    picture's two ends become neighbours that already matched in the source.

    The two layers are joined in two parts. Their broad tones (lighting,
    colour drift) fade into each other across the whole band. Their detail
    switches from one layer to the other along the path where they differ
    least: a plain cross-fade would show both details at once, which reads as
    a ghost on bricks, planks or tiles."""
    from PIL import Image, ImageChops, ImageFilter

    if vertical:
        # Work on the transposed picture so the band is always upright.
        turned = _fold(image.transpose(Image.Transpose.TRANSPOSE), band, vertical=False)
        return turned.transpose(Image.Transpose.TRANSPOSE)
    w, h = image.size
    broad = image.filter(ImageFilter.GaussianBlur(max(2.0, band / 6)))

    def parts(box):
        tones = broad.crop(box)
        return tones, ImageChops.subtract(image.crop(box), tones, 1, 128)

    core = image.crop((0, 0, w - band, h))
    tail_tones, tail_detail = parts((w - band, 0, w, h))
    head_tones, head_detail = parts((0, 0, band, h))
    tones = Image.composite(head_tones, tail_tones, _ramp(band, h))
    detail = Image.composite(head_detail, tail_detail, _cut_mask(head_detail, tail_detail))
    core.paste(ImageChops.add(tones, detail, 1, -128), (0, 0))
    return core


def _wrap_pad(image, pad: int):
    """The image with `pad` pixels of itself repeated around every side."""
    from PIL import Image

    w, h = image.size
    canvas = Image.new(image.mode, (w + 2 * pad, h + 2 * pad))
    for dx in (-w, 0, w):
        for dy in (-h, 0, h):
            canvas.paste(image, (pad + dx, pad + dy))
    return canvas


def _resize_wrap(image, size: tuple[int, int]):
    """Resize a tiling image so the result still tiles: the filter reads the
    repeated neighbours instead of clamping at the edge."""
    from PIL import Image

    if image.size == size:
        return image
    pad = min(16, image.width, image.height)
    w, h = image.size
    return _wrap_pad(image, pad).resize(size, Image.Resampling.LANCZOS, box=(pad, pad, pad + w, pad + h))


def make_tileable(source: Path, target: Path, blend: float = 0.15, keep_size: bool = True) -> dict:
    """Write a copy of `source` that repeats without a visible seam.

    Each axis is folded: the last `blend` of the picture is laid over the
    first and removed (broad tones fade, detail is joined along the line where
    the two differ least); then the result is scaled back to the source size.
    A picture that already tiles is still folded, so check with `seam_report`
    first when that matters."""
    source, target = Path(source), Path(target)
    if not 0.02 <= blend <= 0.5:
        raise ImageError("blend must be between 0.02 and 0.5 of the side")
    image = open_image(source)
    _check_size(image)
    image = image.convert("RGBA" if _has_alpha(image) else "RGB")
    before = seam_report(image)
    w, h = image.size
    band_x = max(2, min(w // 2, round(w * blend)))
    band_y = max(2, min(h // 2, round(h * blend)))
    folded = _fold(_fold(image, band_x, vertical=False), band_y, vertical=True)
    result = _resize_wrap(folded, (w, h)) if keep_size else folded
    save_image(result, target)
    after = seam_report(result)
    info = inspect_image(target)
    info.update({"source": str(source), "blend": blend, "band": [band_x, band_y], "seam_before": before, "seam_after": after})
    return info


def tile_preview(source: Path, target: Path, repeat: int = 2, max_side: int = 1024) -> dict:
    """The texture repeated `repeat` times each way, so a seam shows."""
    from PIL import Image

    image = open_image(Path(source)).convert("RGBA")
    cell = max(1, min(max(image.size), max_side // repeat))
    scale = cell / max(image.size)
    tile = image if scale >= 1 else image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    sheet = Image.new("RGBA", (tile.width * repeat, tile.height * repeat))
    for x in range(repeat):
        for y in range(repeat):
            sheet.paste(tile, (x * tile.width, y * tile.height))
    save_image(sheet, Path(target))
    return inspect_image(Path(target))


def _has_alpha(image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)


def _edge_pad(image):
    """One pixel of the nearest edge repeated around the image, for maps of
    a picture that does not tile."""
    from PIL import Image

    w, h = image.size
    canvas = Image.new(image.mode, (w + 2, h + 2))
    canvas.paste(image, (1, 1))
    canvas.paste(image.crop((0, 0, 1, h)), (0, 1))
    canvas.paste(image.crop((w - 1, 0, w, h)), (w + 1, 1))
    canvas.paste(canvas.crop((0, 1, w + 2, 2)), (0, 0))
    canvas.paste(canvas.crop((0, h, w + 2, h + 1)), (0, h + 1))
    return canvas


def _blur(image, radius: float, wrap: bool):
    from PIL import ImageFilter

    if radius <= 0:
        return image
    if not wrap:
        return image.filter(ImageFilter.GaussianBlur(radius))
    pad = min(int(math.ceil(radius * 3)), image.width, image.height)
    w, h = image.size
    return _wrap_pad(image, pad).filter(ImageFilter.GaussianBlur(radius)).crop((pad, pad, pad + w, pad + h))


def height_from_color(image, invert: bool = False, blur: float = 1.0, wrap: bool = True):
    """A height estimate: the picture's brightness, stretched to the full
    range. Bright reads as raised unless `invert` is set."""
    from PIL import ImageOps

    gray = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    if invert:
        gray = ImageOps.invert(gray)
    return _blur(gray, blur, wrap)


def normal_from_height(height, strength: float = 2.0, convention: str = "opengl", wrap: bool = True):
    """A tangent-space normal map from a height map (Sobel slopes).

    `opengl` puts +Y up in green, which glTF, Godot, Blender and Unity read;
    `directx` flips green for Unreal and the Bethesda engines."""
    from PIL import Image, ImageChops

    if convention not in ("opengl", "directx"):
        raise ImageError("normal convention must be opengl or directx")
    math_lib = _math()
    base = height.convert("L")
    work = base if wrap else _edge_pad(base)
    field = math_lib.lambda_eval(lambda a: a["float"](a["h"]) / 255.0, h=work)

    def at(dx: int, dy: int):
        # The value of the neighbour (dx, dy) seen from each pixel.
        return ImageChops.offset(field, -dx, -dy)

    slope = float(strength) * 4.0
    green = 1.0 if convention == "opengl" else -1.0
    names = {"r0": at(1, -1), "r1": at(1, 0), "r2": at(1, 1), "l0": at(-1, -1), "l1": at(-1, 0), "l2": at(-1, 1),
             "d0": at(-1, 1), "d1": at(0, 1), "d2": at(1, 1), "u0": at(-1, -1), "u1": at(0, -1), "u2": at(1, -1)}

    def channel(which: str):
        def build(a):
            gx = ((a["r0"] + a["r1"] * 2 + a["r2"]) - (a["l0"] + a["l1"] * 2 + a["l2"])) / 8.0
            gy = ((a["d0"] + a["d1"] * 2 + a["d2"]) - (a["u0"] + a["u1"] * 2 + a["u2"])) / 8.0
            nx, ny = gx * -slope, gy * (slope * green)
            length = (nx * nx + ny * ny + 1.0) ** 0.5
            value = {"x": nx / length, "y": ny / length, "z": 1.0 / length}[which]
            return a["convert"](value * 127.5 + 128.0, "L")
        return math_lib.lambda_eval(build, **names)

    merged = Image.merge("RGB", (channel("x"), channel("y"), channel("z")))
    return merged if wrap else merged.crop((1, 1, 1 + base.width, 1 + base.height))


def occlusion_from_height(height, strength: float = 1.0, wrap: bool = True):
    """Cavity shading: a pixel lower than its surroundings is darkened."""
    math_lib = _math()
    base = height.convert("L")
    around = _blur(base, max(2.0, max(base.size) / 64.0), wrap)
    amount = float(strength) * 4.0
    return math_lib.lambda_eval(
        lambda a: a["convert"](a["max"](255.0 - a["max"](a["float"](a["around"]) - a["float"](a["h"]), 0.0) * amount, 51.0), "L"),
        around=around, h=base)


def roughness_from_height(height, base: float = 0.7, variation: float = 0.3):
    """Roughness around `base`: hollows read rougher, raised parts smoother."""
    math_lib = _math()
    level, spread = float(base) * 255.0, float(variation)
    return math_lib.lambda_eval(
        lambda a: a["convert"](a["min"](a["max"](level + (127.5 - a["float"](a["h"])) * spread, 0.0), 255.0), "L"),
        h=height.convert("L"))


def _unit(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ImageError(f"{name} must be between 0 and 1")
    return value


def make_pbr_set(source: Path, out_dir: Path, name: str = "", strength: float = 2.0, convention: str = "opengl",
                 roughness: float = 0.7, roughness_variation: float = 0.3, metallic: float = 0.0,
                 ao_strength: float = 1.0, height_invert: bool = False, height_blur: float = 1.0,
                 tileable: bool = True) -> dict:
    """Write a PBR map set beside a colour map: height, normal, roughness,
    occlusion, metallic, the packed ORM texture and `material.json`.

    `tileable` makes the maps wrap at the edges; leave it off for a picture
    that does not repeat."""
    from PIL import Image

    source, out_dir = Path(source), Path(out_dir)
    if not 0.0 < strength <= 20.0:
        raise ImageError("strength must be more than 0 and at most 20")
    if not 0.0 <= height_blur <= 16.0:
        raise ImageError("height_blur must be between 0 and 16")
    if not 0.0 <= ao_strength <= 4.0:
        raise ImageError("ao_strength must be between 0 and 4")
    _unit(roughness, "roughness")
    _unit(roughness_variation, "roughness_variation")
    _unit(metallic, "metallic")
    color = open_image(source)
    _check_size(color, "colour map")
    stem = name or source.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    height = height_from_color(color, invert=height_invert, blur=height_blur, wrap=tileable)
    maps = {
        "height": height,
        "normal": normal_from_height(height, strength=strength, convention=convention, wrap=tileable),
        "roughness": roughness_from_height(height, base=roughness, variation=roughness_variation),
        "occlusion": occlusion_from_height(height, strength=ao_strength, wrap=tileable),
        "metallic": Image.new("L", color.size, int(round(metallic * 255))),
    }
    maps["orm"] = Image.merge("RGB", (maps["occlusion"], maps["roughness"], maps["metallic"]))
    files = {}
    for kind, image in maps.items():
        path = out_dir / f"{stem}-{kind}.png"
        save_image(image, path)
        files[kind] = path
    material = {
        "schema": 1,
        "name": stem,
        "size": [color.width, color.height],
        "tileable": bool(tileable),
        "derived_from": "base_color",
        "maps": {"base_color": source.name, **{kind: path.name for kind, path in files.items()}},
        "color_space": {"base_color": "sRGB", "normal": "linear", "height": "linear", "roughness": "linear",
                        "occlusion": "linear", "metallic": "linear", "orm": "linear"},
        "normal_convention": convention,
        "orm_channels": {"r": "occlusion", "g": "roughness", "b": "metallic"},
        "parameters": {"strength": strength, "roughness": roughness, "roughness_variation": roughness_variation,
                       "metallic": metallic, "ao_strength": ao_strength, "height_invert": bool(height_invert),
                       "height_blur": height_blur},
    }
    material_path = out_dir / f"{stem}-material.json"
    write_json(material_path, material)
    return {"files": files, "material": material_path, "width": color.width, "height": color.height,
            "normal_check": normal_check(maps["normal"])}


def normal_check(image) -> dict:
    """A tangent-space normal map points out of the surface: blue well above
    the middle, and the average close to straight up."""
    from PIL import ImageStat

    stat = ImageStat.Stat(image.convert("RGB"))
    red, green, blue = stat.mean
    low_blue = image.convert("RGB").split()[2].getextrema()[0]
    tilt = max(abs(red - 127.5), abs(green - 127.5))
    ok = low_blue >= 128 and tilt <= 40
    return {"status": "PASS" if ok else "WARNING",
            "detail": f"mean RGB {red:.0f},{green:.0f},{blue:.0f}; lowest blue {low_blue}"
                      + ("" if ok else "; the map leans or dips below the surface, lower the strength")}

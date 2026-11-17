"""Sprite work on top of Pillow: cut a subject out of a flat background, turn
a picture into pixel art on a fixed palette, and cut a sheet into frames.

No model runs here. A generated picture on a plain background becomes a
sprite with real transparency by keying that background from the border
inwards, so a patch of the same colour inside the subject is kept.
"""

from __future__ import annotations

import re
from pathlib import Path

from .images import ImageError, flat_pixels, inspect_image, open_image, save_image

MAX_SIDE = 8192
MAX_FRAMES = 1024

# Fixed palettes as published by their authors (lospec.com/palette-list).
PALETTES = {
    "pico8": "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa",
    "db16": "140c1c 442434 30346d 4e4a4e 854c30 346524 d04648 757161 597dce d27d2c 8595a1 6daa2c d2aa99 6dc2ca dad45e deeed6",
    "sweetie16": "1a1c2c 5d275d b13e53 ef7d57 ffcd75 a7f070 38b764 257179 29366f 3b5dc9 41a6f6 73eff7 f4f4f4 94b0c2 566c86 333c57",
    "cga": "000000 555555 aaaaaa ffffff 0000aa 5555ff 00aa00 55ff55 00aaaa 55ffff aa0000 ff5555 aa00aa ff55ff aa5500 ffff55",
    "gameboy": "0f380f 306230 8bac0f 9bbc0f",
    "1bit": "000000 ffffff",
}
HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _color(text: str) -> tuple[int, int, int]:
    match = HEX.match(text.strip())
    if not match:
        raise ImageError(f"{text!r} is not a colour; write it as #rrggbb")
    value = match.group(1)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def load_palette(spec) -> list[tuple[int, int, int]]:
    """Colours of a built-in palette name, or of a file: a `.hex` list (one
    colour a line), a GIMP `.gpl`, or an image whose colours are the palette."""
    name = str(spec).strip()
    if name.lower() in PALETTES:
        return [_color(item) for item in PALETTES[name.lower()].split()]
    path = Path(name)
    if not path.is_file():
        raise ImageError(f"no palette named {name!r}; built in: {', '.join(sorted(PALETTES))}, or pass a .hex, .gpl or image file")
    colors: list[tuple[int, int, int]] = []
    if path.suffix.lower() in (".png", ".gif", ".bmp", ".webp"):
        found = open_image(path).convert("RGB").getcolors(maxcolors=257)
        if found is None:
            raise ImageError(f"{path.name} has more than 256 colours; a palette image holds one pixel per colour")
        colors = [color for _, color in found]
    else:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if HEX.match(line):
                colors.append(_color(line))
                continue
            parts = line.split()
            if len(parts) >= 3 and all(part.isdigit() and int(part) < 256 for part in parts[:3]):
                colors.append((int(parts[0]), int(parts[1]), int(parts[2])))
    colors = list(dict.fromkeys(colors))
    if not 2 <= len(colors) <= 256:
        raise ImageError(f"{path.name} holds {len(colors)} colour(s); a palette needs 2 to 256")
    return colors


def flood(mask: bytearray, width: int, height: int, seeds, filled: bytearray | None = None):
    """Fill the 4-connected region of 1-cells reached from `seeds`.

    `mask` holds 1 where filling may go and is cleared as it goes; `filled`
    receives 1 for every cell reached. Works a row span at a time, so the
    cost follows the number of spans, not pixels. Returns the filled bounding
    box (left, top, right, bottom, inclusive) and the area, or None."""
    filled = filled if filled is not None else bytearray(len(mask))
    stack = list(seeds)
    box = None
    area = 0
    while stack:
        x, y = stack.pop()
        row = y * width
        if not mask[row + x]:
            continue
        left = mask.rfind(0, row, row + x)
        left = row if left < 0 else left + 1
        right = mask.find(0, row + x, row + width)
        right = row + width if right < 0 else right
        count = right - left
        mask[left:right] = bytes(count)
        filled[left:right] = b"\x01" * count
        area += count
        first, last = left - row, right - row - 1
        box = (first, y, last, y) if box is None else (min(box[0], first), min(box[1], y), max(box[2], last), max(box[3], y))
        for near in (y - 1, y + 1):
            if not 0 <= near < height:
                continue
            base = near * width
            start, end = base + first, base + last + 1
            position = mask.find(1, start, end)
            while position >= 0:
                stack.append((position - base, near))
                stop = mask.find(0, position, end)
                if stop < 0:
                    break
                position = mask.find(1, stop, end)
    return (box, area) if box else None


def _border_color(image) -> tuple[tuple[int, int, int], float]:
    """The colour most of the border has, and the share of the border it
    covers. Colours are grouped in steps of 8 so noise does not split them."""
    w, h = image.size
    rgb = image.convert("RGB")
    pixels = []
    for box in ((0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h)):
        pixels.extend(flat_pixels(rgb.crop(box)))
    groups: dict[tuple, list] = {}
    for red, green, blue in pixels:
        groups.setdefault((red >> 3, green >> 3, blue >> 3), []).append((red, green, blue))
    members = max(groups.values(), key=len)
    mean = tuple(round(sum(color[i] for color in members) / len(members)) for i in range(3))
    return mean, len(members) / len(pixels)


def _already_cut(image) -> bool:
    """True when the border is mostly transparent already."""
    if image.mode != "RGBA":
        return False
    w, h = image.size
    alpha = image.getchannel("A")
    border = []
    for box in ((0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h)):
        border.extend(flat_pixels(alpha.crop(box)))
    return sum(1 for value in border if value < 8) > len(border) / 2


def cutout(source: Path, target: Path, key: str = "auto", tolerance: int = 24, feather: int = 1,
           mode: str = "flood", trim: bool = True, padding: int = 2) -> dict:
    """Make the flat background of `source` transparent and write a PNG.

    `key` is the background colour (`auto` reads it off the border). `flood`
    removes only background connected to the border; `key` removes that
    colour everywhere. Edge pixels within `feather` get partial alpha and
    lose the background's tint. `trim` crops to the subject plus `padding`."""
    from PIL import Image, ImageChops, ImageFilter, ImageMath

    source, target = Path(source), Path(target)
    if not hasattr(ImageMath, "lambda_eval"):
        raise ImageError("Pillow 10.3 or later is needed for cut-outs; run `pip install -U Pillow`")
    if mode not in ("flood", "key"):
        raise ImageError("mode must be flood or key")
    if not 0 <= tolerance <= 200:
        raise ImageError("tolerance must be between 0 and 200")
    if not 0 <= feather <= 8:
        raise ImageError("feather must be between 0 and 8 pixels")
    if not 0 <= padding <= 256:
        raise ImageError("padding must be between 0 and 256 pixels")
    image = open_image(source)
    if image.width > MAX_SIDE or image.height > MAX_SIDE:
        raise ImageError(f"{source.name} is {image.width}x{image.height}; the limit is {MAX_SIDE}px a side")
    image = image.convert("RGBA")
    w, h = image.size
    warnings: list[str] = []
    keyed = True
    background, share = None, None
    if key == "auto" and _already_cut(image):
        keyed = False
        alpha = image.getchannel("A")
        rgb = image.convert("RGB")
    else:
        if key == "auto":
            background, share = _border_color(image)
            if share < 0.5:
                warnings.append(f"only {share:.0%} of the border is one colour; the background may not be flat")
        else:
            background = _color(key)
        rgb = image.convert("RGB")
        bands = ImageChops.difference(rgb, Image.new("RGB", (w, h), background)).split()
        distance = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), bands[2])
        mask = bytearray(distance.point(lambda value: 1 if value <= tolerance else 0).tobytes())
        if mode == "flood":
            seeds = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
            reached = bytearray(len(mask))
            flood(mask, w, h, seeds, reached)
        else:
            reached = mask
        gone = Image.frombytes("L", (w, h), bytes(reached)).point(lambda value: 255 if value else 0)
        if feather:
            # An edge pixel is part subject, part background. How far it sits
            # from the background colour, against the strongest subject pixel
            # beside it, is its coverage.
            reference = distance.filter(ImageFilter.MaxFilter(2 * feather + 3))
            soft = ImageMath.lambda_eval(
                lambda a: a["convert"](a["min"](a["max"](
                    (a["float"](a["d"]) - tolerance) * 255.0 / a["max"](a["float"](a["ref"]) - tolerance, 1.0), 0.0), 255.0), "L"),
                d=distance, ref=reference)
            near = gone.filter(ImageFilter.MaxFilter(2 * feather + 1))
            alpha = Image.composite(soft, Image.new("L", (w, h), 255), near)
            alpha.paste(0, mask=gone)
        else:
            alpha = ImageChops.invert(gone)
        alpha = ImageChops.darker(alpha, image.getchannel("A"))
        rgb = _decontaminate(rgb, alpha, background)
    box = alpha.getbbox()
    if box is None:
        raise ImageError(f"nothing is left of {source.name} after removing the background; lower the tolerance or set key=#rrggbb")
    removed = 1.0 - _coverage(alpha)
    if keyed and removed < 0.005:
        warnings.append("almost nothing was removed; the background was not found at this tolerance")
    result = Image.merge("RGBA", (*_bleed(rgb, alpha).split(), alpha))
    offset = [0, 0]
    if trim:
        left, top, right, bottom = box
        canvas = Image.new("RGBA", (right - left + 2 * padding, bottom - top + 2 * padding), (0, 0, 0, 0))
        canvas.paste(result.crop(box), (padding, padding))
        result = canvas
        offset = [left - padding, top - padding]
        box = (padding, padding, padding + right - left, padding + bottom - top)
    save_image(result, target)
    info = inspect_image(target)
    info.update({
        "source": str(source),
        "background": "#%02x%02x%02x" % background if background else None,
        "border_share": round(share, 3) if share is not None else None,
        "keyed": keyed,
        "removed_fraction": round(removed, 4),
        "source_size": [w, h],
        "offset": offset,
        "content_box": list(box),
        # Where the subject stands: the middle of its bottom edge.
        "anchor": [round((box[0] + box[2]) / 2), box[3]],
        "warnings": warnings,
    })
    return info


def _coverage(alpha) -> float:
    """Share of pixels that are not fully transparent."""
    histogram = alpha.histogram()
    total = sum(histogram)
    return (total - histogram[0]) / total if total else 0.0


def _decontaminate(rgb, alpha, background):
    """Take the background's share out of half-transparent edge pixels, so a
    sprite cut from white does not carry a white rim."""
    from PIL import Image, ImageMath

    out = []
    for band, level in zip(rgb.split(), background):
        out.append(ImageMath.lambda_eval(
            lambda a, level=level: a["convert"](a["min"](a["max"](
                (a["float"](a["c"]) - level * (1.0 - a["float"](a["al"]) / 255.0)) / a["max"](a["float"](a["al"]) / 255.0, 1.0 / 255.0),
                0.0), 255.0), "L"),
            c=band, al=alpha))
    cleaned = Image.merge("RGB", out)
    # Only edge pixels change; opaque ones keep their exact colour.
    return Image.composite(rgb, cleaned, alpha.point(lambda value: 255 if value == 255 else 0))


def _bleed(rgb, alpha, radius: float = 2.0):
    """Give fully transparent pixels the colour of the nearest subject edge.
    An engine that filters the texture then blends toward the subject's own
    colour, not toward the old background."""
    from PIL import Image, ImageFilter, ImageMath

    if alpha.getextrema()[0] == 255:
        return rgb
    weight = alpha.filter(ImageFilter.GaussianBlur(radius))
    out = []
    for band in rgb.split():
        weighted = ImageMath.lambda_eval(lambda a: a["convert"](a["float"](a["c"]) * a["float"](a["al"]) / 255.0, "L"), c=band, al=alpha)
        spread = weighted.filter(ImageFilter.GaussianBlur(radius))
        out.append(ImageMath.lambda_eval(
            lambda a: a["convert"](a["min"](a["float"](a["s"]) * 255.0 / a["max"](a["float"](a["w"]), 1.0), 255.0), "L"), s=spread, w=weight))
    return Image.composite(rgb, Image.merge("RGB", out), alpha.point(lambda value: 255 if value else 0))


def pixelate(source: Path, target: Path, size: int = 64, palette: str = "", colors: int = 16,
             dither: bool = False, preview: Path | None = None, preview_scale: int = 8) -> dict:
    """Write `source` as pixel art: scaled down so its longer side is `size`
    pixels, alpha made on-or-off, and colours limited to a palette (a
    built-in name or a file) or to `colors` colours picked from the picture."""
    from PIL import Image

    source, target = Path(source), Path(target)
    if not 4 <= size <= 1024:
        raise ImageError("size must be between 4 and 1024 pixels")
    if not 2 <= colors <= 256:
        raise ImageError("colors must be between 2 and 256")
    if not 1 <= preview_scale <= 32:
        raise ImageError("preview_scale must be between 1 and 32")
    fixed = load_palette(palette) if palette else None
    image = open_image(source)
    if image.width > MAX_SIDE or image.height > MAX_SIDE:
        raise ImageError(f"{source.name} is {image.width}x{image.height}; the limit is {MAX_SIDE}px a side")
    image = image.convert("RGBA")
    scale = min(1.0, size / max(image.size))
    small_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    # Premultiplied, so transparent pixels do not tint the averaged edges.
    small = image.convert("RGBa").resize(small_size, Image.Resampling.BOX).convert("RGBA")
    alpha = small.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    if alpha.getbbox() is None:
        raise ImageError(f"{source.name} is fully transparent at {small_size[0]}x{small_size[1]}")
    rgb = small.convert("RGB")
    if alpha.getextrema()[0] == 0:
        # Fill the empty area with the subject's average so it claims no palette entry.
        mean = image.convert("RGBa").resize((1, 1), Image.Resampling.BOX).convert("RGBA").getpixel((0, 0))[:3]
        rgb = Image.composite(rgb, Image.new("RGB", small_size, mean), alpha)
    if fixed:
        holder = Image.new("P", (1, 1))
        flat = [value for color in fixed for value in color]
        holder.putpalette(flat + list(fixed[-1]) * (256 - len(fixed)))
        indexed = rgb.quantize(palette=holder, dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
    else:
        indexed = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    result = indexed.convert("RGB").convert("RGBA")
    result.putalpha(alpha)
    save_image(result, target)
    used = {color for color, visible in zip(flat_pixels(result.convert("RGB")), flat_pixels(alpha)) if visible}
    info = inspect_image(target)
    info.update({"source": str(source), "palette": palette or f"{colors} picked", "colors_used": len(used),
                 "palette_size": len(fixed) if fixed else colors, "dither": bool(dither and fixed), "scale": round(scale, 4)})
    if preview is not None:
        big = result.resize((result.width * preview_scale, result.height * preview_scale), Image.Resampling.NEAREST)
        save_image(big, Path(preview))
        info["preview"] = str(preview)
    return info


def _rows(boxes: list[tuple]) -> list[tuple]:
    """Reading order: top row first, left to right within a row."""
    ordered: list[tuple] = []
    row: list[tuple] = []
    bottom = None
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        middle = (box[1] + box[3]) / 2
        if bottom is not None and middle > bottom:
            ordered.extend(sorted(row, key=lambda item: item[0]))
            row, bottom = [], None
        row.append(box)
        bottom = box[3] if bottom is None else max(bottom, box[3])
    ordered.extend(sorted(row, key=lambda item: item[0]))
    return ordered


def slice_sheet(source: Path, out_dir: Path, mode: str = "grid", columns: int = 0, rows: int = 0,
                cell_width: int = 0, cell_height: int = 0, min_area: int = 16, keep_empty: bool = False) -> dict:
    """Cut a sprite sheet into frame files.

    `grid` cuts equal cells, from `columns` and `rows` or from a cell size;
    empty cells are skipped unless `keep_empty`. `auto` finds each separate
    island of pixels on a transparent sheet. Frames are numbered in reading
    order. Returns the frame rectangles."""
    source, out_dir = Path(source), Path(out_dir)
    if mode not in ("grid", "auto"):
        raise ImageError("mode must be grid or auto")
    image = open_image(source)
    if image.width > MAX_SIDE or image.height > MAX_SIDE:
        raise ImageError(f"{source.name} is {image.width}x{image.height}; the limit is {MAX_SIDE}px a side")
    image = image.convert("RGBA")
    w, h = image.size
    alpha = image.getchannel("A")
    boxes: list[tuple] = []
    if mode == "grid":
        if cell_width or cell_height:
            if cell_width < 1 or cell_height < 1:
                raise ImageError("give both cell_width and cell_height")
            columns, rows = w // cell_width, h // cell_height
        elif columns >= 1 and rows >= 1:
            cell_width, cell_height = w // columns, h // rows
        else:
            raise ImageError("grid needs columns and rows, or cell_width and cell_height")
        if columns < 1 or rows < 1 or cell_width < 1 or cell_height < 1:
            raise ImageError(f"a {w}x{h} sheet cannot be cut into those cells")
        if columns * rows > MAX_FRAMES:
            raise ImageError(f"that is {columns * rows} frames; the limit is {MAX_FRAMES}")
        for row in range(rows):
            for column in range(columns):
                box = (column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height)
                if keep_empty or alpha.crop(box).getbbox() is not None:
                    boxes.append(box)
    else:
        if alpha.getextrema()[0] != 0:
            raise ImageError("auto needs a transparent background; run image-cutout first, or use mode=grid")
        mask = bytearray(alpha.point(lambda value: 1 if value else 0).tobytes())
        position = mask.find(1)
        while position >= 0:
            found = flood(mask, w, h, [(position % w, position // w)])
            if found and found[1] >= min_area:
                left, top, right, bottom = found[0]
                boxes.append((left, top, right + 1, bottom + 1))
                if len(boxes) > MAX_FRAMES:
                    raise ImageError(f"more than {MAX_FRAMES} separate pieces; raise min_area or use mode=grid")
            position = mask.find(1, position)
        boxes = _rows(boxes)
    if not boxes:
        raise ImageError(f"no frames found in {source.name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, box in enumerate(boxes):
        name = f"{source.stem}_{index:03d}.png"
        save_image(image.crop(box), out_dir / name)
        frames.append({"name": name, "x": box[0], "y": box[1], "w": box[2] - box[0], "h": box[3] - box[1]})
    return {"source": str(source), "mode": mode, "sheet": [w, h], "frames": frames,
            "columns": columns if mode == "grid" else None, "rows": rows if mode == "grid" else None}

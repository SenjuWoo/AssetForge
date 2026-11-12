"""GLB inspection and structural validation using only the standard library.

The GLB container is simple: a 12-byte header and JSON/BIN chunks. Reading it
directly keeps the core dependency-free; official Khronos validation remains a
separate optional provider because this module checks structure, not conformance.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .util import human_bytes

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
INDEX_TYPES = {5121: ("<B", 1), 5123: ("<H", 2), 5125: ("<I", 4)}
DEGENERATE_LIMIT = 300_000


class GlbError(RuntimeError):
    pass


def _parse(path: Path):
    data = Path(path).read_bytes()
    if len(data) < 12:
        raise GlbError("file is shorter than a GLB header")
    magic, version, declared = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise GlbError("not a GLB file (bad magic)")
    if version != 2:
        raise GlbError(f"unsupported GLB container version {version}")
    problems = []
    if declared != len(data):
        problems.append(f"header declares {declared} bytes, file has {len(data)}")
    chunks = []
    offset = 12
    while offset + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        payload = data[offset : offset + length]
        if len(payload) != length:
            problems.append(f"chunk at {offset - 8} is truncated")
        chunks.append((kind, payload))
        offset += length
    json_chunk = next((payload for kind, payload in chunks if kind == CHUNK_JSON), None)
    if json_chunk is None:
        raise GlbError("GLB has no JSON chunk")
    try:
        text = json_chunk.decode("utf-8").rstrip("\x00 \t\r\n")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlbError(f"JSON chunk does not parse: {exc}") from exc
    bin_chunk = next((payload for kind, payload in chunks if kind == CHUNK_BIN), b"")
    return doc, bin_chunk, {"bytes": len(data), "declared": declared, "problems": problems}


def _accessor_count(doc: dict, index) -> int:
    try:
        return int(doc["accessors"][int(index)].get("count", 0))
    except (KeyError, TypeError, ValueError, IndexError):
        return 0


def _primitive_triangles(doc: dict, primitive: dict) -> int:
    mode = primitive.get("mode", 4)
    if mode != 4:
        return 0
    if primitive.get("indices") is not None:
        return _accessor_count(doc, primitive["indices"]) // 3
    position = (primitive.get("attributes") or {}).get("POSITION")
    return _accessor_count(doc, position) // 3 if position is not None else 0


def _bbox(doc: dict):
    low = [float("inf")] * 3
    high = [float("-inf")] * 3
    found = False
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            index = (primitive.get("attributes") or {}).get("POSITION")
            if index is None:
                continue
            try:
                accessor = doc["accessors"][int(index)]
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            minimum, maximum = accessor.get("min"), accessor.get("max")
            if not (isinstance(minimum, list) and isinstance(maximum, list) and len(minimum) >= 3 and len(maximum) >= 3):
                continue
            found = True
            for axis in range(3):
                low[axis] = min(low[axis], float(minimum[axis]))
                high[axis] = max(high[axis], float(maximum[axis]))
    if not found:
        return None
    return {"min": low, "max": high, "size": [round(high[i] - low[i], 6) for i in range(3)]}


def _read_indices(doc: dict, binary: bytes, accessor_index: int):
    """Return index values, or None when the accessor layout is unsupported."""
    try:
        accessor = doc["accessors"][int(accessor_index)]
        buffer_view = doc["bufferViews"][accessor["bufferView"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if accessor.get("type") != "SCALAR" or accessor.get("componentType") not in INDEX_TYPES:
        return None
    if accessor.get("sparse") or buffer_view.get("buffer", 0) != 0:
        return None
    fmt, width = INDEX_TYPES[accessor["componentType"]]
    start = int(buffer_view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    stride = int(buffer_view.get("byteStride") or width)
    count = int(accessor.get("count", 0))
    if start < 0 or count < 0 or start + stride * max(count - 1, 0) + width > len(binary):
        return None
    return [struct.unpack_from(fmt, binary, start + i * stride)[0] for i in range(count)]


def _degenerate_triangles(doc: dict, binary: bytes):
    total = 0
    bad = 0
    capped = False
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", 4) != 4 or primitive.get("indices") is None:
                continue
            if total >= DEGENERATE_LIMIT:
                capped = True
                break
            values = _read_indices(doc, binary, primitive["indices"])
            if values is None:
                capped = True
                continue
            for i in range(0, len(values) - 2, 3):
                total += 1
                a, b, c = values[i], values[i + 1], values[i + 2]
                if a == b or b == c or a == c:
                    bad += 1
                if total >= DEGENERATE_LIMIT:
                    capped = True
                    break
    return bad, total, capped


FLOAT = 5126
SAMPLE_LIMIT = 200_000
ANIMATION_PATHS = {"translation", "rotation", "scale", "weights"}
TEXTURE_SLOTS = ("baseColorTexture", "metallicRoughnessTexture")
MATERIAL_SLOTS = ("normalTexture", "occlusionTexture", "emissiveTexture")
COMPONENT_FORMAT = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}


def image_size(data: bytes):
    """Width, height and format of an encoded image, from its header only.

    Covers the formats a glTF image may carry: PNG, JPEG, WebP and KTX2. Returns
    None when the header is not one of them or is cut short.
    """
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            width, height = struct.unpack_from(">II", data, 16)
            return width, height, "png"
        if data[:2] == b"\xff\xd8":
            offset = 2
            while offset + 9 < len(data):
                if data[offset] != 0xFF:
                    offset += 1
                    continue
                marker = data[offset + 1]
                if marker in (0xD8, 0x01, 0xFF) or 0xD0 <= marker <= 0xD7:
                    offset += 1 if marker == 0xFF else 2
                    continue
                length = struct.unpack_from(">H", data, offset + 2)[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    height, width = struct.unpack_from(">HH", data, offset + 5)
                    return width, height, "jpeg"
                offset += 2 + length
            return None
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            kind = data[12:16]
            if kind == b"VP8X":
                width = int.from_bytes(data[24:27], "little") + 1
                height = int.from_bytes(data[27:30], "little") + 1
                return width, height, "webp"
            if kind == b"VP8L":
                bits = struct.unpack_from("<I", data, 21)[0]
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, "webp"
            if kind == b"VP8 ":
                width, height = struct.unpack_from("<HH", data, 26)
                return width & 0x3FFF, height & 0x3FFF, "webp"
            return None
        if data[:12] == b"\xabKTX 20\xbb\r\n\x1a\n":
            width, height = struct.unpack_from("<II", data, 20)
            return width, height, "ktx2"
    except (struct.error, IndexError):
        return None
    return None


def _view_bytes(doc: dict, binary: bytes, view_index):
    try:
        view = doc["bufferViews"][int(view_index)]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if view.get("buffer", 0) != 0:
        return None
    start = int(view.get("byteOffset", 0))
    end = start + int(view.get("byteLength", 0))
    if start < 0 or end > len(binary):
        return None
    return binary[start:end]


def _image_details(doc: dict, binary: bytes, folder: Path) -> list[dict]:
    """Decoded size of every image, embedded or beside the file."""
    details = []
    for index, image in enumerate(doc.get("images", [])):
        item = {"index": index, "name": image.get("name"), "source": None, "bytes": None,
                "format": None, "width": None, "height": None}
        data = None
        if image.get("bufferView") is not None:
            item["source"] = "embedded"
            data = _view_bytes(doc, binary, image["bufferView"])
        elif str(image.get("uri") or "").startswith("data:"):
            item["source"] = "data-uri"
            try:
                import base64

                data = base64.b64decode(str(image["uri"]).split(",", 1)[1])
            except (IndexError, ValueError):
                data = None
        elif image.get("uri"):
            item["source"] = "external"
            from urllib.parse import unquote

            target = folder / unquote(str(image["uri"]))
            try:
                with open(target, "rb") as handle:
                    data = handle.read(1 << 16)
                item["bytes"] = target.stat().st_size
            except OSError:
                data = None
        if data is not None:
            if item["bytes"] is None:
                item["bytes"] = len(data)
            size = image_size(data)
            if size:
                item["width"], item["height"], item["format"] = size
        details.append(item)
    return details


def _read_accessor(doc: dict, binary: bytes, accessor_index, limit: int = SAMPLE_LIMIT):
    """Rows of an accessor as tuples, at most `limit` rows. None when the layout
    is sparse, external or out of bounds; the bounds check reports those."""
    try:
        accessor = doc["accessors"][int(accessor_index)]
        view = doc["bufferViews"][accessor["bufferView"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    code = COMPONENT_FORMAT.get(accessor.get("componentType"))
    width = TYPE_COUNT.get(accessor.get("type"))
    if code is None or width is None or accessor.get("sparse") or view.get("buffer", 0) != 0:
        return None
    element = COMPONENT_SIZE[accessor["componentType"]] * width
    stride = int(view.get("byteStride") or element)
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    count = min(int(accessor.get("count", 0)), limit)
    if start < 0 or count < 0 or start + stride * max(count - 1, 0) + element > len(binary):
        return None
    fmt = "<" + code * width
    return [struct.unpack_from(fmt, binary, start + row * stride) for row in range(count)]


def _normalized(accessor: dict, value) -> float:
    if accessor.get("componentType") == FLOAT or not accessor.get("normalized"):
        return float(value)
    scale = {5121: 255.0, 5123: 65535.0, 5120: 127.0, 5122: 32767.0}.get(accessor.get("componentType"), 1.0)
    return float(value) / scale


def _material_textures(material: dict):
    """Yield (slot, texture info) for every texture a material names."""
    pbr = material.get("pbrMetallicRoughness") or {}
    for slot in TEXTURE_SLOTS:
        if isinstance(pbr.get(slot), dict):
            yield slot, pbr[slot]
    for slot in MATERIAL_SLOTS:
        if isinstance(material.get(slot), dict):
            yield slot, material[slot]
    for extension in (material.get("extensions") or {}).values():
        if isinstance(extension, dict):
            for key, value in extension.items():
                if key.endswith("Texture") and isinstance(value, dict) and "index" in value:
                    yield key, value


def _material_checks(doc: dict) -> list[dict]:
    """Dangling material, texture and image references, and textured surfaces
    that carry no UV set to map them with."""
    materials = doc.get("materials", [])
    textures = doc.get("textures", [])
    images = doc.get("images", [])
    dangling = []
    no_uv = 0
    unassigned = 0
    for index, texture in enumerate(textures):
        source = texture.get("source")
        if source is None:
            for extension in (texture.get("extensions") or {}).values():
                if isinstance(extension, dict) and extension.get("source") is not None:
                    source = extension["source"]
        if source is not None and not (isinstance(source, int) and 0 <= source < len(images)):
            dangling.append(f"texture {index} names missing image {source}")
    for index, material in enumerate(materials):
        for slot, info in _material_textures(material):
            ref = info.get("index")
            if not (isinstance(ref, int) and 0 <= ref < len(textures)):
                dangling.append(f"material {index} {slot} names missing texture {ref}")
    for mesh_index, mesh in enumerate(doc.get("meshes", [])):
        for primitive in mesh.get("primitives", []):
            ref = primitive.get("material")
            if ref is None:
                unassigned += 1
                continue
            if not (isinstance(ref, int) and 0 <= ref < len(materials)):
                dangling.append(f"mesh {mesh_index} names missing material {ref}")
                continue
            attributes = primitive.get("attributes") or {}
            for _, info in _material_textures(materials[ref]):
                if f"TEXCOORD_{int(info.get('texCoord', 0) or 0)}" not in attributes:
                    no_uv += 1
                    break
    if dangling:
        more = f" (+{len(dangling) - 4} more)" if len(dangling) > 4 else ""
        return [_check("GLB-015", "FAIL", "; ".join(dangling[:4]) + more)]
    if no_uv:
        return [_check("GLB-015", "WARNING", f"{no_uv} textured primitive(s) have no matching TEXCOORD set")]
    if not materials:
        return [_check("GLB-015", "NOT_TESTED", "document has no materials")]
    detail = f"{len(materials)} material(s), {len(textures)} texture(s) resolve"
    if unassigned:
        detail += f"; {unassigned} primitive(s) use the default material"
    return [_check("GLB-015", "PASS", detail)]


def _transform_checks(doc: dict) -> list[dict]:
    """Node transforms an engine importer commonly trips on."""
    import math

    zero = mirrored = broken = 0
    for node in doc.get("nodes", []):
        values = []
        for key in ("scale", "translation", "rotation", "matrix"):
            if isinstance(node.get(key), list):
                values.extend(node[key])
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            broken += 1
            continue
        scale = node.get("scale")
        if isinstance(scale, list) and len(scale) == 3:
            if any(abs(v) < 1e-9 for v in scale):
                zero += 1
            elif scale[0] * scale[1] * scale[2] < 0:
                mirrored += 1
    if broken:
        return [_check("GLB-016", "FAIL", f"{broken} node(s) carry a non-finite transform")]
    if zero or mirrored:
        parts = []
        if zero:
            parts.append(f"{zero} node(s) scaled to zero on an axis")
        if mirrored:
            parts.append(f"{mirrored} node(s) mirrored by a negative scale (flips triangle winding)")
        return [_check("GLB-016", "WARNING", "; ".join(parts))]
    return [_check("GLB-016", "PASS", f"{len(doc.get('nodes', []))} node transform(s) are finite and non-degenerate")]


def rig_stats(doc: dict) -> dict:
    skins = doc.get("skins", [])
    animations = doc.get("animations", [])
    duration = 0.0
    for animation in animations:
        for sampler in animation.get("samplers", []):
            try:
                top = doc["accessors"][int(sampler["input"])].get("max")
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            if isinstance(top, list) and top and isinstance(top[0], (int, float)):
                duration = max(duration, float(top[0]))
    return {
        "joints": [len(skin.get("joints") or []) for skin in skins],
        "max_joints": max((len(skin.get("joints") or []) for skin in skins), default=0),
        "animation_names": [animation.get("name") for animation in animations],
        "animation_channels": sum(len(animation.get("channels") or []) for animation in animations),
        "animation_seconds": round(duration, 4),
    }


def _summarize(items: list[str]) -> str:
    unique = list(dict.fromkeys(items))
    return "; ".join(unique[:4]) + (f" (+{len(unique) - 4} more)" if len(unique) > 4 else "")


def _rig_checks(doc: dict, binary: bytes) -> list[dict]:
    """Structural skin and animation checks. They prove the data is consistent,
    not that the deformation looks right: that needs an engine or a viewer."""
    skins = doc.get("skins", [])
    animations = doc.get("animations", [])
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    accessors = doc.get("accessors", [])
    if not skins and not animations:
        return [_check("GLB-013", "NOT_TESTED", "no skins or animations in this asset")]
    fails: list[str] = []
    warns: list[str] = []

    for index, skin in enumerate(skins):
        joints = skin.get("joints") or []
        if not joints:
            fails.append(f"skin {index} has no joints")
            continue
        if any(not (isinstance(j, int) and 0 <= j < len(nodes)) for j in joints):
            fails.append(f"skin {index} names a joint node that does not exist")
        if len(set(joints)) != len(joints):
            fails.append(f"skin {index} lists a joint twice")
        ibm = skin.get("inverseBindMatrices")
        if ibm is None:
            warns.append(f"skin {index} has no inverse bind matrices (identity assumed)")
        elif not (isinstance(ibm, int) and 0 <= ibm < len(accessors)):
            fails.append(f"skin {index} names a missing inverse bind accessor")
        else:
            accessor = accessors[ibm]
            if accessor.get("type") != "MAT4" or accessor.get("componentType") != FLOAT:
                fails.append(f"skin {index} inverse bind matrices are not float MAT4")
            elif int(accessor.get("count", 0)) < len(joints):
                fails.append(f"skin {index} has {len(joints)} joints but {accessor.get('count', 0)} inverse bind matrices")

    skinned = 0
    for node_index, node in enumerate(nodes):
        mesh_ref = node.get("mesh")
        if not (isinstance(mesh_ref, int) and 0 <= mesh_ref < len(meshes)):
            continue
        skin_ref = node.get("skin")
        has_skin = isinstance(skin_ref, int) and 0 <= skin_ref < len(skins)
        if skin_ref is not None and not has_skin:
            fails.append(f"node {node_index} names missing skin {skin_ref}")
            continue
        joint_count = len(skins[skin_ref].get("joints") or []) if has_skin else 0
        for primitive in meshes[mesh_ref].get("primitives", []):
            attributes = primitive.get("attributes") or {}
            has_j, has_w = "JOINTS_0" in attributes, "WEIGHTS_0" in attributes
            if has_skin and not (has_j and has_w):
                fails.append(f"node {node_index} is skinned but a primitive lacks JOINTS_0/WEIGHTS_0")
                continue
            if not has_skin:
                if has_j or has_w:
                    warns.append(f"node {node_index} carries skin weights but no skin")
                continue
            skinned += 1
            rows = _read_accessor(doc, binary, attributes["JOINTS_0"])
            weights = _read_accessor(doc, binary, attributes["WEIGHTS_0"])
            if rows is None or weights is None:
                warns.append(f"node {node_index} skin attributes could not be decoded")
                continue
            weight_accessor = accessors[attributes["WEIGHTS_0"]]
            out_of_range = unnormalized = 0
            for joint_row, weight_row in zip(rows, weights):
                values = [_normalized(weight_accessor, v) for v in weight_row]
                if any(w > 0 and j >= joint_count for j, w in zip(joint_row, values)):
                    out_of_range += 1
                if abs(sum(values) - 1.0) > 0.01:
                    unnormalized += 1
            if out_of_range:
                fails.append(f"node {node_index}: {out_of_range} vertex/vertices weighted to a joint index past the skin's {joint_count} joints")
            if unnormalized:
                warns.append(f"node {node_index}: {unnormalized} of {len(rows)} sampled vertices have weights that do not sum to 1")

    for index, animation in enumerate(animations):
        samplers = animation.get("samplers") or []
        channels = animation.get("channels") or []
        if not channels:
            warns.append(f"animation {index} has no channels")
        for channel in channels:
            target = channel.get("target") or {}
            sampler_ref = channel.get("sampler")
            if not (isinstance(sampler_ref, int) and 0 <= sampler_ref < len(samplers)):
                fails.append(f"animation {index} channel names a missing sampler")
                continue
            node_ref = target.get("node")
            if node_ref is not None and not (isinstance(node_ref, int) and 0 <= node_ref < len(nodes)):
                fails.append(f"animation {index} targets missing node {node_ref}")
            if target.get("path") not in ANIMATION_PATHS:
                fails.append(f"animation {index} uses unknown path {target.get('path')!r}")
            sampler = samplers[sampler_ref]
            refs = (sampler.get("input"), sampler.get("output"))
            if any(not (isinstance(r, int) and 0 <= r < len(accessors)) for r in refs):
                fails.append(f"animation {index} sampler names a missing accessor")
                continue
            times, values = accessors[refs[0]], accessors[refs[1]]
            keys = int(times.get("count", 0))
            if keys == 0:
                fails.append(f"animation {index} has a sampler with no keyframes")
                continue
            if target.get("path") != "weights":
                per_key = 3 if sampler.get("interpolation") == "CUBICSPLINE" else 1
                if int(values.get("count", 0)) != keys * per_key:
                    fails.append(f"animation {index}: {keys} key time(s) but {values.get('count', 0)} value(s) for {target.get('path')}")

    stats = rig_stats(doc)
    summary = (f"{len(skins)} skin(s), up to {stats['max_joints']} joints, {skinned} skinned primitive(s), "
               f"{len(animations)} animation(s), {stats['animation_channels']} channel(s)")
    if fails:
        return [_check("GLB-013", "FAIL", _summarize(fails))]
    if warns:
        return [_check("GLB-013", "WARNING", summary + "; " + _summarize(warns))]
    return [_check("GLB-013", "PASS", summary + "; data is consistent, deformation not rendered")]


def inspect_glb(path: Path) -> dict:
    doc, binary, container = _parse(path)
    primitives = 0
    triangles = 0
    vertices = 0
    missing_normals = 0
    modes = set()
    uv_sets = 0
    vertex_colors = False
    morph_targets = 0
    details = _image_details(doc, binary, Path(path).parent)
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            primitives += 1
            names = primitive.get("attributes") or {}
            uv_sets = max(uv_sets, sum(1 for key in names if key.startswith("TEXCOORD_")))
            vertex_colors = vertex_colors or "COLOR_0" in names
            morph_targets = max(morph_targets, len(primitive.get("targets") or []))
            modes.add(primitive.get("mode", 4))
            triangles += _primitive_triangles(doc, primitive)
            position = (primitive.get("attributes") or {}).get("POSITION")
            vertices += _accessor_count(doc, position) if position is not None else 0
            if position is not None and "NORMAL" not in (primitive.get("attributes") or {}):
                missing_normals += 1
    return {
        "file": str(path),
        "bytes": container["bytes"],
        "human_bytes": human_bytes(container["bytes"]),
        "asset_version": (doc.get("asset") or {}).get("version"),
        "generator": (doc.get("asset") or {}).get("generator"),
        "scene_count": len(doc.get("scenes", [])),
        "nodes": len(doc.get("nodes", [])),
        "meshes": len(doc.get("meshes", [])),
        "primitives": primitives,
        "triangles": triangles,
        "vertices": vertices,
        "indices_present": all(
            primitive.get("indices") is not None
            for mesh in doc.get("meshes", [])
            for primitive in mesh.get("primitives", [])
        )
        if primitives
        else False,
        "materials": len(doc.get("materials", [])),
        "textures": len(doc.get("textures", [])),
        "images": len(doc.get("images", [])),
        "animations": len(doc.get("animations", [])),
        "skins": len(doc.get("skins", [])),
        "extensions_used": doc.get("extensionsUsed", []),
        "extensions_required": doc.get("extensionsRequired", []),
        "modes": sorted(modes),
        "missing_normals": missing_normals,
        "bbox": _bbox(doc),
        "bin_bytes": len(binary),
        "image_details": details,
        "max_texture_size": max((max(item["width"] or 0, item["height"] or 0) for item in details), default=0),
        "uv_sets": uv_sets,
        "vertex_colors": vertex_colors,
        "morph_targets": morph_targets,
        "rig": rig_stats(doc),
    }


def _check(check_id: str, status: str, detail: str) -> dict:
    return {"id": check_id, "status": status, "detail": detail}


def _bounds_checks(doc: dict, binary: bytes) -> list[dict]:
    checks = []
    buffers = doc.get("buffers", [])
    if not buffers:
        return [_check("GLB-005", "FAIL", "document declares no buffers")]
    for index, buffer in enumerate(buffers):
        length = int(buffer.get("byteLength", 0))
        if index == 0 and not buffer.get("uri") and length > len(binary):
            checks.append(_check("GLB-005", "FAIL", f"buffer {index} declares {length} bytes but BIN has {len(binary)}"))
    for index, view in enumerate(doc.get("bufferViews", [])):
        length = int(view.get("byteLength", 0))
        offset = int(view.get("byteOffset", 0))
        buffer_index = int(view.get("buffer", 0))
        buffer_length = int(buffers[buffer_index].get("byteLength", 0)) if buffer_index < len(buffers) else 0
        if offset < 0 or length <= 0 or offset + length > buffer_length:
            checks.append(_check("GLB-005", "FAIL", f"bufferView {index} is outside buffer {buffer_index}"))
            break
    for index, accessor in enumerate(doc.get("accessors", [])):
        view_index = accessor.get("bufferView")
        if view_index is None:
            continue
        if not isinstance(view_index, int) or view_index >= len(doc.get("bufferViews", [])):
            checks.append(_check("GLB-005", "FAIL", f"accessor {index} names missing bufferView {view_index}"))
            break
        view = doc["bufferViews"][view_index]
        component = COMPONENT_SIZE.get(accessor.get("componentType"))
        count = TYPE_COUNT.get(accessor.get("type"))
        if component is None or count is None:
            checks.append(_check("GLB-005", "WARNING", f"accessor {index} has an unusual component/type"))
            continue
        element = component * count
        stride = int(view.get("byteStride") or element)
        needed = int(accessor.get("byteOffset", 0)) + stride * max(int(accessor.get("count", 0)) - 1, 0) + element
        if needed > int(view.get("byteLength", 0)):
            checks.append(_check("GLB-005", "FAIL", f"accessor {index} reads past its bufferView"))
            break
    if not checks:
        checks.append(_check("GLB-005", "PASS", "buffers, bufferViews and accessors are in bounds"))
    return checks


def validate_glb(path: Path) -> dict:
    path = Path(path)
    checks: list[dict] = []
    try:
        doc, binary, container = _parse(path)
        stats = inspect_glb(path)
    except (GlbError, OSError) as exc:
        return {
            "schema": 1,
            "file": str(path),
            "stats": None,
            "checks": [_check("GLB-001", "FAIL", str(exc))],
            "summary": {"PASS": 0, "WARNING": 0, "FAIL": 1, "NOT_TESTED": 0},
            "status": "FAIL",
        }

    checks.append(_check("GLB-001", "PASS", "GLB header and version 2"))
    checks.append(
        _check(
            "GLB-002",
            "PASS" if not container["problems"] else "FAIL",
            "; ".join(container["problems"]) or "declared length and chunk sizes match the file",
        )
    )
    checks.append(_check("GLB-003", "PASS", "JSON chunk parses"))
    asset_version = str(stats.get("asset_version") or "")
    checks.append(
        _check(
            "GLB-004",
            "PASS" if asset_version.startswith("2.") else "FAIL",
            f"asset.version={asset_version or 'missing'}",
        )
    )
    checks.extend(_bounds_checks(doc, binary))

    if not stats["primitives"]:
        checks.append(_check("GLB-006", "FAIL", "document contains no mesh primitives"))
    elif any(item.get("attributes", {}).get("POSITION") is None for mesh in doc.get("meshes", []) for item in mesh.get("primitives", [])):
        checks.append(_check("GLB-006", "FAIL", "at least one primitive has no POSITION attribute"))
    else:
        checks.append(_check("GLB-006", "PASS", f"{stats['primitives']} primitive(s) with POSITION"))

    bad, total, capped = _degenerate_triangles(doc, binary)
    if total == 0:
        status = "NOT_TESTED"
        detail = "no indexed triangle primitives to inspect"
    elif bad == 0:
        status = "PASS"
        detail = f"0 degenerate triangles in {total} indexed triangles"
    else:
        status = "FAIL" if bad > max(100, total * 0.01) else "WARNING"
        detail = f"{bad} degenerate triangles in {total}"
    if capped:
        detail += " (inspection capped; not full coverage)"
    checks.append(_check("GLB-008", status, detail))

    if stats["primitives"] == 0:
        checks.append(_check("GLB-009", "NOT_TESTED", "no primitives"))
    elif stats["missing_normals"]:
        checks.append(_check("GLB-009", "WARNING", f"{stats['missing_normals']} primitive(s) without NORMAL"))
    else:
        checks.append(_check("GLB-009", "PASS", "every primitive has NORMAL"))

    box = stats["bbox"]
    if not box:
        checks.append(_check("GLB-010", "NOT_TESTED", "POSITION accessors carry no min/max bounds"))
    else:
        size = box["size"]
        largest = max(size) if size else 0
        smallest = min((value for value in size if value > 0), default=0)
        if largest > 1000:
            checks.append(_check("GLB-010", "WARNING", f"largest dimension is {largest:g}; check the export unit"))
        elif smallest and smallest < 0.001:
            checks.append(_check("GLB-010", "WARNING", f"smallest dimension is {smallest:g}; check the export unit"))
        else:
            checks.append(_check("GLB-010", "PASS", f"bounding box {size[0]:g} x {size[1]:g} x {size[2]:g}"))

    known_extensions = {
        "KHR_materials_unlit",
        "KHR_texture_transform",
        "KHR_materials_emissive_strength",
        "KHR_materials_clearcoat",
        "KHR_materials_transmission",
        "KHR_lights_punctual",
        "KHR_mesh_quantization",
        "EXT_texture_webp",
        "EXT_meshopt_compression",
        "KHR_materials_ior",
        "KHR_materials_sheen",
        "KHR_materials_specular",
    }
    unknown = [item for item in stats["extensions_required"] if item not in known_extensions]
    checks.append(
        _check(
            "GLB-011",
            "WARNING" if unknown else "PASS",
            "unknown required extension(s): " + ", ".join(unknown) if unknown else "no unknown required extensions",
        )
    )

    missing_images = 0
    for image in doc.get("images", []):
        if image.get("bufferView") is None and not image.get("uri"):
            missing_images += 1
        elif image.get("uri") and not str(image["uri"]).startswith("data:"):
            target = path.parent / str(image["uri"])
            if not target.exists():
                missing_images += 1
    checks.append(
        _check(
            "GLB-012",
            "FAIL" if missing_images else "PASS",
            f"{missing_images} image reference(s) cannot be resolved" if missing_images else "image references resolve",
        )
    )

    checks.extend(_rig_checks(doc, binary))
    checks.extend(_material_checks(doc))
    checks.extend(_transform_checks(doc))

    checks.append(_check("GLB-014", "NOT_TESTED", "official glTF validator not run (optional provider)"))

    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    return {"schema": 1, "file": str(path), "stats": stats, "checks": checks, "summary": summary, "status": overall}


def compare_glb(before: Path, after: Path) -> dict:
    first = inspect_glb(before)
    second = inspect_glb(after)
    return {
        "before": first,
        "after": second,
        "delta": {
            "bytes": second["bytes"] - first["bytes"],
            "triangles": second["triangles"] - first["triangles"],
            "vertices": second["vertices"] - first["vertices"],
            "materials": second["materials"] - first["materials"],
            "textures": second["textures"] - first["textures"],
            "max_texture_size": second["max_texture_size"] - first["max_texture_size"],
            "skins": second["skins"] - first["skins"],
            "animations": second["animations"] - first["animations"],
        },
    }

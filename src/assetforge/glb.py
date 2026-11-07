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


def inspect_glb(path: Path) -> dict:
    doc, binary, container = _parse(path)
    primitives = 0
    triangles = 0
    vertices = 0
    missing_normals = 0
    modes = set()
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            primitives += 1
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

    if stats["skins"] or stats["animations"]:
        checks.append(
            _check(
                "GLB-013",
                "WARNING",
                f"{stats['skins']} skin(s), {stats['animations']} animation(s): rig deformation was not exercised",
            )
        )
    else:
        checks.append(_check("GLB-013", "NOT_TESTED", "no skins or animations in this asset"))

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
        },
    }

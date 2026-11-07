"""Test helpers: a valid GLB fixture and a CLI runner."""

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pad(data: bytes, filler: bytes) -> bytes:
    while len(data) % 4:
        data += filler
    return data


def make_glb(path: Path, degenerate: bool = False, normals: bool = True, node_name: str = "Triangle") -> Path:
    positions = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    normal_data = struct.pack("<9f", 0, 0, 1, 0, 0, 1, 0, 0, 1)
    indices = struct.pack("<3I", 0, 0, 2) if degenerate else struct.pack("<3I", 0, 1, 2)
    binary = _pad(positions + normal_data + indices, b"\x00")
    attributes = {"POSITION": 0}
    if normals:
        attributes["NORMAL"] = 1
    doc = {
        "asset": {"version": "2.0", "generator": "AssetForge test fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": node_name}],
        "meshes": [{"name": "Triangle", "primitives": [{"attributes": attributes, "indices": 2, "material": 0, "mode": 4}]}],
        "materials": [{"name": "Mat", "pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.2, 0.2, 1], "metallicFactor": 0, "roughnessFactor": 0.7}}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5125, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},
            {"buffer": 0, "byteOffset": 36, "byteLength": 36, "target": 34962},
            {"buffer": 0, "byteOffset": 72, "byteLength": 12, "target": 34963},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    json_chunk = _pad(json.dumps(doc, separators=(",", ":")).encode("utf-8"), b" ")
    total = 12 + 8 + len(json_chunk) + 8 + len(binary)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(json_chunk), 0x4E4F534A))
        fh.write(json_chunk)
        fh.write(struct.pack("<II", len(binary), 0x004E4942))
        fh.write(binary)
    return path


def make_textured_glb(path: Path) -> Path:
    """Two nodes, two materials, one embedded texture and two indexed
    triangles. Used to prove structure survives optimization."""
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    pos0 = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    norm0 = struct.pack("<9f", 0, 0, 1, 0, 0, 1, 0, 0, 1)
    uv0 = struct.pack("<6f", 0, 0, 1, 0, 0, 1)
    idx0 = struct.pack("<3I", 0, 1, 2)
    pos1 = struct.pack("<9f", 2, 0, 0, 3, 0, 0, 2, 1, 0)
    norm1 = struct.pack("<9f", 0, 0, 1, 0, 0, 1, 0, 0, 1)
    uv1 = struct.pack("<6f", 0, 0, 1, 0, 0, 1)
    idx1 = struct.pack("<3I", 0, 1, 2)
    parts = [pos0, norm0, uv0, idx0, pos1, norm1, uv1, idx1]
    offsets = []
    cursor = 0
    for part in parts:
        offsets.append(cursor)
        cursor += len(part)
    image_offset = cursor
    binary = _pad(b"".join(parts) + png, b"\x00")
    doc = {
        "asset": {"version": "2.0", "generator": "AssetForge textured fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0, 1]}],
        "nodes": [{"mesh": 0, "name": "TexturedPanel"}, {"mesh": 1, "name": "PlainPanel"}],
        "meshes": [
            {"name": "TexturedPanel", "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0, "mode": 4}]},
            {"name": "PlainPanel", "primitives": [{"attributes": {"POSITION": 4, "NORMAL": 5, "TEXCOORD_0": 6}, "indices": 7, "material": 1, "mode": 4}]},
        ],
        "materials": [
            {"name": "Textured", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 0.6}},
            {"name": "Plain", "pbrMetallicRoughness": {"baseColorFactor": [0.2, 0.4, 0.8, 1], "metallicFactor": 0, "roughnessFactor": 0.8}},
        ],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"bufferView": 8, "mimeType": "image/png"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5125, "count": 3, "type": "SCALAR"},
            {"bufferView": 4, "componentType": 5126, "count": 3, "type": "VEC3", "min": [2, 0, 0], "max": [3, 1, 0]},
            {"bufferView": 5, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 6, "componentType": 5126, "count": 3, "type": "VEC2"},
            {"bufferView": 7, "componentType": 5125, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": offsets[0], "byteLength": len(pos0), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[1], "byteLength": len(norm0), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[2], "byteLength": len(uv0), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[3], "byteLength": len(idx0), "target": 34963},
            {"buffer": 0, "byteOffset": offsets[4], "byteLength": len(pos1), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[5], "byteLength": len(norm1), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[6], "byteLength": len(uv1), "target": 34962},
            {"buffer": 0, "byteOffset": offsets[7], "byteLength": len(idx1), "target": 34963},
            {"buffer": 0, "byteOffset": image_offset, "byteLength": len(png)},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    json_chunk = _pad(json.dumps(doc, separators=(",", ":")).encode("utf-8"), b" ")
    total = 12 + 8 + len(json_chunk) + 8 + len(binary)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(json_chunk), 0x4E4F534A))
        fh.write(json_chunk)
        fh.write(struct.pack("<II", len(binary), 0x004E4942))
        fh.write(binary)
    return path


def make_png(path: Path, size=(128, 96), alpha: bool = True) -> Path:
    from PIL import Image

    mode = "RGBA" if alpha else "RGB"
    color = (40, 120, 200, 180) if alpha else (40, 120, 200)
    Image.new(mode, size, color).save(path)
    return path


def run_cli(args, cwd: Path, env=None):
    merged = os.environ.copy()
    merged["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + merged.get("PYTHONPATH", "")
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "assetforge", *args],
        cwd=str(cwd),
        env=merged,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=180,
    )

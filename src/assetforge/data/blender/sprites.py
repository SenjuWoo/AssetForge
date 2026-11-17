"""Render a GLB as sprite frames: a fixed orthographic camera at the game's
pitch, one set of frames per facing and per animation, transparent background.

Runs inside Blender. Every frame of every facing shares one scale, so the
frames line up, and the ground point under the model is reported as the
anchor of each facing.

    blender -b --factory-startup -P sprites.py -- --input in.glb --out DIR
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector

NAMES_8 = ("south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west")
MAX_RENDERS = 1024


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--directions", type=int, default=8)
    parser.add_argument("--pitch", type=float, default=30.0)
    parser.add_argument("--yaw", type=float, default=0.0)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--animations", default="all")
    parser.add_argument("--engine", default="workbench")
    parser.add_argument("--antialias", type=int, default=1)
    parser.add_argument("--outline", type=int, default=0)
    parser.add_argument("--margin", type=float, default=0.06)
    parser.add_argument("--pivot", default="auto")
    return parser.parse_args(argv)


def _facing_name(angle: float) -> str:
    step = angle / 45.0
    if abs(step - round(step)) < 1e-6:
        return NAMES_8[int(round(step)) % 8]
    return f"yaw{int(round(angle)) % 360:03d}"


def _import(path: str) -> None:
    try:
        bpy.ops.import_scene.gltf(filepath=path, disable_bone_shape=True)
    except TypeError:
        bpy.ops.import_scene.gltf(filepath=path)


def _drawn(scene) -> list:
    """Meshes that are part of the model, not helper shapes of a rig."""
    shapes = set()
    for obj in scene.objects:
        if obj.type == "ARMATURE":
            for bone in obj.pose.bones:
                if bone.custom_shape is not None:
                    shapes.add(bone.custom_shape.name)
    drawn = []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name in shapes:
            obj.hide_render = True
            continue
        if not obj.hide_render:
            drawn.append(obj)
    return drawn


def _animated(scene) -> list:
    """Everything that carries animation: objects and their shape keys."""
    owners = []
    for obj in scene.objects:
        if obj.animation_data is not None:
            owners.append(obj)
        keys = getattr(getattr(obj, "data", None), "shape_keys", None)
        if keys is not None and keys.animation_data is not None:
            owners.append(keys)
    return owners


def _animations(owners) -> dict:
    """Animation name -> (first frame, last frame). The glTF importer puts
    each animation on NLA tracks of that name, on every object it moves."""
    found: dict = {}
    for owner in owners:
        for track in owner.animation_data.nla_tracks:
            for strip in track.strips:
                first, last = found.get(track.name, (strip.frame_start, strip.frame_end))
                found[track.name] = (min(first, strip.frame_start), max(last, strip.frame_end))
    if not found:
        # A file with one bare action and no tracks.
        for owner in owners:
            action = owner.animation_data.action
            if action is not None:
                first, last = action.frame_range
                found[action.name] = (first, last)
    return found


def _select(owners, name) -> None:
    """Play one animation: only its tracks are heard. None is the rest pose."""
    for owner in owners:
        data = owner.animation_data
        tracks = [track for track in data.nla_tracks]
        if tracks:
            data.action = None
            for track in tracks:
                track.is_solo = False
                track.mute = track.name != name
        elif name is None or (data.action is not None and data.action.name != name):
            data.action = None


def _bounds(scene, drawn, low, high) -> None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in drawn:
        evaluated = obj.evaluated_get(depsgraph)
        for corner in evaluated.bound_box:
            point = evaluated.matrix_world @ Vector(corner)
            for axis in range(3):
                low[axis] = min(low[axis], point[axis])
                high[axis] = max(high[axis], point[axis])


def _samples(first: float, last: float, count: int) -> list:
    """`count` moments of a loop: the last frame repeats the first, so it is
    left out."""
    if count <= 1 or last <= first:
        return [first]
    return [first + index * (last - first) / count for index in range(count)]


def _set_frame(scene, moment: float) -> None:
    whole = math.floor(moment)
    scene.frame_set(int(whole), subframe=float(moment - whole))


def _engine(scene, wanted: str, antialias: bool, outline: bool) -> str:
    if wanted == "eevee":
        for name in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try:
                scene.render.engine = name
                break
            except TypeError:
                continue
        else:
            raise RuntimeError("this Blender has no EEVEE engine")
        sun = bpy.data.objects.new("AF_Sun", bpy.data.lights.new("AF_Sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))
        scene.collection.objects.link(sun)
        world = bpy.data.worlds.new("AF_World")
        world.use_nodes = True
        background = world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            background.inputs[1].default_value = 0.6
        scene.world = world
    else:
        scene.render.engine = "BLENDER_WORKBENCH"
        shading = scene.display.shading
        # flat: the base colour as it is, no shading at all.
        shading.light = "FLAT" if wanted == "flat" else "STUDIO"
        shading.color_type = "TEXTURE"
        shading.show_shadows = False
        shading.show_object_outline = bool(outline)
        scene.display.render_aa = "8" if antialias else "OFF"
    if not antialias:
        scene.render.filter_size = 0.01
    scene.view_settings.view_transform = "Standard"
    return scene.render.engine


def main() -> int:
    args = _args()
    if args.engine not in ("workbench", "flat", "eevee"):
        raise ValueError("engine must be workbench, flat or eevee")
    if args.directions not in (1, 4, 8, 16):
        raise ValueError("directions must be 1, 4, 8 or 16")
    if not 16 <= args.size <= 2048:
        raise ValueError("size must be between 16 and 2048")
    if not 1 <= args.frames <= 64:
        raise ValueError("frames must be between 1 and 64")
    if not 0.0 <= args.pitch <= 90.0:
        raise ValueError("pitch must be between 0 and 90 degrees")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _import(args.input)
    scene = bpy.context.scene
    drawn = _drawn(scene)
    if not drawn:
        raise ValueError("the file has no mesh to render")
    owners = _animated(scene)
    available = _animations(owners)
    wanted = args.animations.strip()
    notes = []
    if wanted in ("", "none") or not available:
        chosen = []
        if wanted not in ("", "none", "all"):
            raise ValueError(f"the file has no animations; asked for {wanted}")
    elif wanted == "all":
        chosen = sorted(available)
    else:
        chosen = [name.strip() for name in wanted.split(",") if name.strip()]
        missing = [name for name in chosen if name not in available]
        if missing:
            raise ValueError(f"no animation named {', '.join(missing)}; the file has {', '.join(sorted(available))}")
    plan = [(name, _samples(*available[name], args.frames)) for name in chosen] or [("static", [float(scene.frame_current)])]
    total = args.directions * sum(len(moments) for _, moments in plan)
    if total > MAX_RENDERS:
        raise ValueError(f"that is {total} frames; the limit is {MAX_RENDERS}. Use fewer facings, frames or animations")

    # One box around every pose that will be drawn, so all frames share a scale.
    low, high = [math.inf] * 3, [-math.inf] * 3
    for name, moments in plan:
        _select(owners, name if chosen else None)
        for moment in moments:
            _set_frame(scene, moment)
            _bounds(scene, drawn, low, high)
    # The facings turn about one upright axis. A model standing on its own
    # origin (a character) turns about that origin, so it does not slide when
    # it turns; one that sits away from its origin turns about its middle.
    pivot = args.pivot
    if pivot not in ("auto", "origin", "bounds"):
        raise ValueError("pivot must be auto, origin or bounds")
    if pivot == "auto":
        pivot = "origin" if low[0] <= 0.0 <= high[0] and low[1] <= 0.0 <= high[1] else "bounds"
    centre = Vector([(low[axis] + high[axis]) / 2 for axis in range(3)])
    if pivot == "origin":
        centre = Vector((0.0, 0.0, centre.z))
    corners = [Vector((x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    ground = Vector((centre.x, centre.y, low[2]))
    reach = max((corner - centre).length for corner in corners) or 1.0

    camera = bpy.data.objects.new("AF_Camera", bpy.data.cameras.new("AF_Camera"))
    camera.data.type = "ORTHO"
    camera.data.clip_start = 0.01
    camera.data.clip_end = reach * 8 + 10
    scene.collection.objects.link(camera)
    scene.camera = camera
    pitch = math.radians(args.pitch)
    facings = []
    half = 0.0
    for index in range(args.directions):
        angle = (args.yaw + index * 360.0 / args.directions) % 360.0
        turn = math.radians(angle)
        # A glTF model faces -Y in Blender. Turn 0 looks at its front; 90
        # stands on its right-hand side, so it faces east on screen.
        away = Vector((-math.sin(turn) * math.cos(pitch), -math.cos(turn) * math.cos(pitch), math.sin(pitch)))
        rotation = (-away).to_track_quat("-Z", "Y")
        right, up = rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0))
        for corner in corners:
            offset = corner - centre
            half = max(half, abs(offset.dot(right)), abs(offset.dot(up)))
        facings.append({"name": _facing_name(angle), "yaw": round(angle, 3), "away": away, "rotation": rotation, "right": right, "up": up})
    scale = 2.0 * half * (1.0 + max(0.0, args.margin)) or 1.0
    camera.data.ortho_scale = scale
    for facing in facings:
        offset = ground - centre
        facing["anchor"] = [round((offset.dot(facing["right"]) / scale + 0.5) * args.size, 2),
                            round((0.5 - offset.dot(facing["up"]) / scale) * args.size, 2)]

    render = scene.render
    render.resolution_x = render.resolution_y = args.size
    render.resolution_percentage = 100
    render.film_transparent = True
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGBA"
    engine = _engine(scene, args.engine, bool(args.antialias), bool(args.outline))

    os.makedirs(args.out, exist_ok=True)
    files = []
    for name, moments in plan:
        _select(owners, name if chosen else None)
        for facing in facings:
            camera.location = centre + facing["away"] * (reach * 4 + 5)
            camera.rotation_mode = "QUATERNION"
            camera.rotation_quaternion = facing["rotation"]
            for index, moment in enumerate(moments):
                _set_frame(scene, moment)
                file_name = f"{name}__{facing['name']}__{index:02d}.png"
                render.filepath = os.path.join(args.out, file_name)
                bpy.ops.render.render(write_still=True)
                files.append({"file": file_name, "animation": name, "direction": facing["name"], "index": index, "frame": round(moment, 3)})
    fps = scene.render.fps / (scene.render.fps_base or 1.0)
    animations = []
    for name, moments in plan:
        first, last = available.get(name, (moments[0], moments[0]))
        seconds = (last - first) / fps if fps else 0.0
        animations.append({"name": name, "frames": len(moments), "source_frames": [round(first, 3), round(last, 3)],
                           "seconds": round(seconds, 4), "fps": round(len(moments) / seconds, 3) if seconds > 0 else 0})
    if available and not chosen:
        notes.append(f"animations were left out; the file has {', '.join(sorted(available))}")
    print("SPRITES " + json.dumps({
        "ok": True, "blender": bpy.app.version_string, "engine": engine, "size": args.size, "pitch": args.pitch,
        "ortho_scale": round(scale, 6), "pixels_per_unit": round(args.size / scale, 4), "pivot": pivot,
        "directions": [{"name": f["name"], "yaw": f["yaw"], "anchor": f["anchor"]} for f in facings],
        "animations": animations, "available_animations": sorted(available), "meshes": len(drawn),
        "files": files, "notes": notes,
    }))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:  # report the reason on one line and fail
        print("SPRITES " + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        code = 1
    sys.stdout.flush()
    os._exit(code)

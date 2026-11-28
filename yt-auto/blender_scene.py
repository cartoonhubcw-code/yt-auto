"""Runs INSIDE Blender (headless), never imported by the rest of the project:

    blender -b --factory-startup -P blender_scene.py -- spec.json

Builds one small 3D scene (cut / stack / gears), animates it and renders PNG frames
with the Cycles CPU renderer. Free, no GPU needed.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
N = int(spec["frames"])
FPS = int(spec["fps"])
TH = spec["theme"]
PORT = bool(spec["portrait"])
TEMPLATE = spec["template"]
RX, RY = int(spec["res"][0]), int(spec["res"][1])
ASPECT = RX / RY


def lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def rgba(c):
    return (lin(c[0]), lin(c[1]), lin(c[2]), 1.0)


def acc(i):
    return TH["accents"][i % len(TH["accents"])]


def F(p):
    """Progress 0..1 -> frame number."""
    return 1 + int(round(max(0.0, min(1.0, p)) * (N - 1)))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---------------------------------------------------------------- building blocks
def make_mat(name, color, rough=0.45, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def make_floor():
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    o = bpy.context.active_object
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    ch = nt.nodes.new("ShaderNodeTexChecker")
    top, bot = TH["top"], TH["bot"]
    mix = tuple((a + b) / 2 for a, b in zip(top, bot))
    ch.inputs["Color1"].default_value = rgba(top)
    ch.inputs["Color2"].default_value = rgba(mix)
    ch.inputs["Scale"].default_value = 60
    nt.links.new(ch.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    o.data.materials.append(m)
    return o


def make_block(name, loc, size, color, bevel=0.07, rough=0.4, metal=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    m = o.modifiers.new("bevel", "BEVEL")
    m.width = bevel
    m.segments = 3
    mat = make_mat(name + "_mat", color, rough, metal)
    o.data.materials.append(mat)
    return o, mat


def key_loc(o, frame, loc):
    o.location = loc
    o.keyframe_insert("location", frame=frame)


def key_scale(o, frame, s):
    o.scale = (s, s, s)
    o.keyframe_insert("scale", frame=frame)


def key_rot_z(o, frame, a):
    o.rotation_euler = (0, 0, a)
    o.keyframe_insert("rotation_euler", frame=frame)


def linear(o):
    """Constant-speed rotation (best effort: the animation API differs between Blender versions)."""
    try:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    except Exception:  # noqa: BLE001
        pass


def setup_world_light():
    w = bpy.data.worlds.new("world")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = rgba(TH["top"])
    bg.inputs[1].default_value = 1.1
    scene.world = w
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 3.2
    sun.angle = math.radians(8)
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(40), math.radians(5), math.radians(30))
    scene.collection.objects.link(so)


def setup_camera(width, depth, tilt_deg, target=(0, 0, 0), drift=0.09):
    """Place the camera so a width x depth area fits the frame, with a slow dolly-in."""
    cd = bpy.data.cameras.new("cam")
    cd.lens = 35
    cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    extent = max(width * 1.15, depth * 1.2 * ASPECT)
    d = extent * 1.26
    t = math.radians(tilt_deg)
    tgt = Vector(target)
    base = tgt + Vector((0, -d * math.sin(t), d * math.cos(t)))
    emp = bpy.data.objects.new("target", None)
    emp.location = target
    scene.collection.objects.link(emp)
    con = cam.constraints.new("TRACK_TO")
    con.target = emp
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    key_loc(cam, 1, base)
    key_loc(cam, N, base * (1 - drift) + tgt * drift)
    return cam


# ---------------------------------------------------------------- templates
def build_cut():
    """A bar of blocks is chopped by a knife, the halves slide apart and re-join shifted."""
    cols, rows = (4, 5) if PORT else (6, 4)
    cut = rows // 2
    setup_camera(cols + 2.2, rows + 1.6, 22, target=(0, -0.2, 0))
    ycut = (rows - 1) / 2 - cut + 0.5
    for r in range(rows):
        for k in range(cols):
            x = k - (cols - 1) / 2
            y = (rows - 1) / 2 - r
            top = r < cut
            o, mat = make_block(f"t{r}_{k}", (x, y, 0.2), (0.94, 0.94, 0.4), acc(0), bevel=0.08)
            a = 0.02 + (r + k) * 0.012
            key_scale(o, 1, 0.01)
            key_scale(o, F(a), 0.01)
            key_scale(o, F(a + 0.1), 1.0)
            sx = -0.9 if top else 0.9
            fx = -0.5 if top else 0.5
            sy = 0.35 if top else -0.35
            key_loc(o, 1, (x, y, 0.2))
            key_loc(o, F(0.42), (x, y, 0.2))
            key_loc(o, F(0.56), (x + sx, y + sy, 0.2))
            key_loc(o, F(0.66), (x + sx, y + sy, 0.2))
            key_loc(o, F(0.82), (x + fx, y, 0.2))
            key_loc(o, N, (x + fx, y, 0.2))
            if not top:
                try:  # colour flips when the knife lands
                    sock = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
                    sock.default_value = rgba(acc(0))
                    sock.keyframe_insert("default_value", frame=F(0.29))
                    sock.default_value = rgba(acc(1))
                    sock.keyframe_insert("default_value", frame=F(0.33))
                except Exception:  # noqa: BLE001
                    pass
    blade, _ = make_block("blade", (0, ycut, 5), (cols + 1.2, 0.06, 0.9), (205, 210, 222),
                          bevel=0.02, rough=0.2, metal=0.8)
    handle, _ = make_block("handle", (0, 0, 0), (1.3, 0.2, 0.22), (40, 42, 52), bevel=0.05)
    handle.parent = blade
    handle.location = ((cols + 1.2) / 2 + 0.6, 0, 0.25)
    for f, z in ((1, 5), (F(0.20), 5), (F(0.30), 0.5), (F(0.36), 0.5), (F(0.48), 5), (N, 5)):
        key_loc(blade, f, (0, ycut, z))


def build_stack():
    """Blocks drop one after another into a tower."""
    n = 5
    setup_camera(4.2, 5.5, 42, target=(0, 0, 1.6), drift=0.07)
    h = 0.7
    for i in range(n):
        w = 3.0 - 0.42 * i
        z = h / 2 + h * i
        o, _ = make_block(f"s{i}", (0, 0, 9), (w, w, h), acc(i), bevel=0.09, rough=0.35)
        a = 0.05 + i * 0.15
        key_loc(o, 1, (0, 0, 9))
        key_loc(o, F(a), (0, 0, 9))
        key_loc(o, F(a + 0.12), (0, 0, z))
        key_loc(o, F(a + 0.16), (0, 0, z + 0.2))
        key_loc(o, F(a + 0.2), (0, 0, z))
        key_loc(o, N, (0, 0, z))
        key_rot_z(o, 1, math.radians(-25))
        key_rot_z(o, F(a + 0.12), math.radians(8 * (i % 2 * 2 - 1)))
        key_rot_z(o, N, math.radians(8 * (i % 2 * 2 - 1)))


def make_gear(name, teeth, pitch, thick, color):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    n = teeth * 4
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = pitch + 0.11 if (i % 4) in (0, 1) else pitch - 0.11
        verts.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0.0)))
    face = bm.faces.new(verts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    vs = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, thick), verts=vs)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.data.materials.append(make_mat(name + "_mat", color, 0.35, 0.35))
    return o


def tooth_rot(teeth, direction, gap=False):
    """Rotation that puts a tooth (or a gap) exactly at `direction` radians."""
    r = direction - math.pi / (4 * teeth)
    return r - math.pi / teeth if gap else r


def build_gears():
    """Three meshing gears turning at the right speed ratios."""
    teeth = [10, 14, 10]
    pitch = [t * 0.12 for t in teeth]
    xs = [0.0]
    for i in range(1, 3):
        xs.append(xs[-1] + pitch[i - 1] + pitch[i])
    cx = sum(xs) / 3
    width = xs[-1] + pitch[0] + pitch[2] + 0.8
    setup_camera(width, pitch[1] * 2 + 0.8, 18, target=(0, 0, 0.2), drift=0.08)
    turns = 0.8
    rots = [tooth_rot(teeth[0], 0.0),
            tooth_rot(teeth[1], math.pi, gap=True),
            tooth_rot(teeth[2], math.pi)]
    for i in range(3):
        o = make_gear(f"g{i}", teeth[i], pitch[i], 0.5, acc(i))
        hub = make_block(f"hub{i}", (0, 0, 0.35), (0.34, 0.34, 0.8), (240, 240, 245),
                         bevel=0.05, rough=0.3, metal=0.5)[0]
        hub.parent = o
        hub.location = (0, 0, 0.1)
        o.location = (xs[i] - cx, 0, 0.0)
        direction = 1 if i % 2 == 0 else -1
        ang = 2 * math.pi * turns * teeth[0] / teeth[i] * direction
        key_scale(o, 1, 0.01)
        key_scale(o, F(0.1 + i * 0.06), 0.01)
        key_scale(o, F(0.22 + i * 0.06), 1.0)
        key_rot_z(o, 1, rots[i])
        key_rot_z(o, F(0.25), rots[i])
        key_rot_z(o, N, rots[i] + ang)
        linear(o)


# ---------------------------------------------------------------- go
setup_world_light()
make_floor()
{"cut": build_cut, "stack": build_stack, "gears": build_gears}[TEMPLATE]()

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(spec.get("samples", 24))
for attr, val in (("use_denoising", True), ("use_adaptive_sampling", True), ("max_bounces", 4)):
    try:
        setattr(scene.cycles, attr, val)
    except Exception:  # noqa: BLE001
        pass
try:
    scene.view_settings.view_transform = "Standard"
except Exception:  # noqa: BLE001
    pass
scene.render.resolution_x = RX
scene.render.resolution_y = RY
scene.render.resolution_percentage = 100
scene.render.fps = FPS
scene.frame_start = 1
scene.frame_end = N
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.filepath = os.path.join(spec["out_dir"], "f_")
bpy.ops.render.render(animation=True)

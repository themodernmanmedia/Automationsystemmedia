"""Real-time-style 3D voxel renderer (OpenGL 3.3 via moderngl, headless EGL).

* Instanced textured blocks (pixel textures from ``blocky.texture``)
* Instanced boxes for block people / props (per-instance matrix + colour)
* Directional sun with PCF shadow map, hemisphere ambient, exponential fog
* Emissive lava / gold / gems, animated lava texture
* Output: RGBA numpy frame that the cairo pipeline composites overlays onto

All art is procedural and original.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import numpy as np

from .blocky import texture as _tex2d

# --------------------------------------------------------------------------
# math
# --------------------------------------------------------------------------


def perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def ortho(l, r, b, t, n, f):
    m = np.identity(4, dtype=np.float32)
    m[0, 0] = 2 / (r - l)
    m[1, 1] = 2 / (t - b)
    m[2, 2] = -2 / (f - n)
    m[0, 3] = -(r + l) / (r - l)
    m[1, 3] = -(t + b) / (t - b)
    m[2, 3] = -(f + n) / (f - n)
    return m


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = (np.asarray(v, dtype=np.float32) for v in (eye, target, up))
    fwd = target - eye
    fwd /= np.linalg.norm(fwd) + 1e-9
    side = np.cross(fwd, up)
    side /= np.linalg.norm(side) + 1e-9
    upv = np.cross(side, fwd)
    m = np.identity(4, dtype=np.float32)
    m[0, :3], m[1, :3], m[2, :3] = side, upv, -fwd
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def T(x, y, z):
    m = np.identity(4, dtype=np.float32)
    m[:3, 3] = (x, y, z)
    return m


def S(x, y, z):
    return np.diag(np.array([x, y, z, 1], dtype=np.float32))


def RX(a):
    c, s = math.cos(a), math.sin(a)
    m = np.identity(4, dtype=np.float32)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def RY(a):
    c, s = math.cos(a), math.sin(a)
    m = np.identity(4, dtype=np.float32)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    return m


def RZ(a):
    c, s = math.cos(a), math.sin(a)
    m = np.identity(4, dtype=np.float32)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def hex3(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


# --------------------------------------------------------------------------
# block types -> (top, bottom, side) texture kinds, emissive
# --------------------------------------------------------------------------

BLOCKS = {
    "grass": ("grass_top", "dirt", "grass_side", 0.0),
    "dirt": ("dirt", "dirt", "dirt", 0.0),
    "stone": ("stone", "stone", "stone", 0.0),
    "lava": ("lava", "lava", "lava", 1.0),
    "gold": ("gold", "gold", "gold", 0.55),
    "gem": ("gem", "gem", "gem", 0.6),
    "wood": ("wood", "wood", "wood", 0.0),
    "leaves": ("leaves", "leaves", "leaves", 0.0),
    "plank": ("plank", "plank", "plank", 0.0),
    "sand": ("sand", "sand", "sand", 0.0),
    "water": ("water", "water", "water", 0.15),
    "cloud": ("cloud", "cloud", "cloud", 0.35),
}
BLOCK_IDS = {k: i for i, k in enumerate(BLOCKS)}


def _tex_rgba(kind, frame=0) -> np.ndarray:
    if kind == "cloud":
        return np.full((16, 16, 4), 255, dtype=np.uint8)
    surf = _tex2d(kind, frame)
    buf = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(16, surf.get_stride() // 4, 4)[:, :16]
    rgba = buf[:, :, [2, 1, 0, 3]].copy()  # BGRA -> RGBA
    return rgba[::-1]


# --------------------------------------------------------------------------
# shaders
# --------------------------------------------------------------------------

COMMON_FS = """
uniform vec3 sun_dir;
uniform vec3 sun_col;
uniform vec3 sky_col;
uniform vec3 ground_col;
uniform vec3 fog_col;
uniform float fog_density;
uniform vec3 cam_pos;
uniform sampler2D shadow_map;
uniform float shadow_on;

float shadow_at(vec4 lp, float ndl) {
    vec3 p = lp.xyz / lp.w * 0.5 + 0.5;
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0 || p.z > 1.0) return 1.0;
    float bias = max(0.0025 * (1.0 - ndl), 0.0008);
    float s = 0.0;
    vec2 ts = 1.0 / vec2(textureSize(shadow_map, 0));
    for (int x = -1; x <= 1; x++)
      for (int y = -1; y <= 1; y++) {
        float d = texture(shadow_map, p.xy + vec2(x, y) * ts * 1.2).r;
        s += (p.z - bias > d) ? 0.0 : 1.0;
      }
    return mix(1.0, s / 9.0, shadow_on);
}

vec3 shade(vec3 albedo, vec3 n, vec3 wpos, vec4 lpos, float emissive) {
    float ndl = max(dot(n, -sun_dir), 0.0);
    float sh = shadow_at(lpos, ndl);
    vec3 amb = mix(ground_col, sky_col, n.y * 0.5 + 0.5) * 0.55;
    // simple face-based AO feel: sides a bit darker than tops
    float face = 0.86 + 0.14 * abs(n.y);
    vec3 col = albedo * (amb + sun_col * ndl * sh) * face;
    col = mix(col, albedo * 1.25, emissive);
    float dist = length(wpos - cam_pos);
    float fog = 1.0 - exp(-pow(dist * fog_density, 1.6));
    return mix(col, fog_col, clamp(fog, 0.0, 1.0));
}
"""

BLOCK_VS = """
#version 330
in vec3 in_pos; in vec3 in_norm; in vec2 in_uv; in float in_face;
in vec3 in_off; in vec3 in_scl; in float in_type;
uniform mat4 vp; uniform mat4 light_vp;
out vec3 v_norm; out vec2 v_uv; out vec3 v_wpos; out vec4 v_lpos; flat out float v_layer; flat out float v_type;
void main() {
    vec3 w = in_off + in_pos * in_scl;
    v_wpos = w; v_norm = in_norm;
    vec2 uv = in_uv;
    if (in_face > 1.5) uv.y = uv.y * in_scl.y + (1.0 - in_scl.y);  // keep texel size on short sides
    v_uv = uv;
    v_layer = in_type * 3.0 + in_face;
    v_type = in_type;
    v_lpos = light_vp * vec4(w, 1.0);
    gl_Position = vp * vec4(w, 1.0);
}
"""

BLOCK_FS = """
#version 330
in vec3 v_norm; in vec2 v_uv; in vec3 v_wpos; in vec4 v_lpos; flat in float v_layer; flat in float v_type;
uniform sampler2DArray tex;
uniform float time;
uniform float emissive_by_type[16];
uniform float lava_type;
out vec4 frag;
""" + COMMON_FS + """
void main() {
    vec2 uv = v_uv;
    if (abs(v_type - lava_type) < 0.5) uv += vec2(time * 0.03, time * 0.05);
    vec3 albedo = texture(tex, vec3(fract(uv), v_layer)).rgb;
    float e = emissive_by_type[int(v_type + 0.5)];
    if (abs(v_type - lava_type) < 0.5) albedo *= 1.15 + 0.15 * sin(time * 2.0 + v_wpos.x * 0.7 + v_wpos.z * 0.5);
    frag = vec4(shade(albedo, normalize(v_norm), v_wpos, v_lpos, e), 1.0);
}
"""

BOX_VS = """
#version 330
in vec3 in_pos; in vec3 in_norm; in vec2 in_uv; in float in_face;
in mat4 in_m; in vec4 in_col;
uniform mat4 vp; uniform mat4 light_vp;
out vec3 v_norm; out vec3 v_wpos; out vec4 v_lpos; out vec4 v_col; out vec2 v_uv; out vec3 v_lp;
void main() {
    vec4 w = in_m * vec4(in_pos, 1.0);
    v_wpos = w.xyz;
    v_norm = normalize(mat3(in_m) * in_norm);
    v_col = in_col; v_uv = in_uv; v_lp = in_pos;
    v_lpos = light_vp * w;
    gl_Position = vp * w;
}
"""

BOX_FS = """
#version 330
in vec3 v_norm; in vec3 v_wpos; in vec4 v_lpos; in vec4 v_col; in vec2 v_uv; in vec3 v_lp;
out vec4 frag;
""" + COMMON_FS + """
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
    // pixel-noise texture: 8 texels per box face
    vec2 cell = floor(v_uv * 8.0) + floor((v_lp.xz + v_lp.yy) * 3.0);
    float n = 0.93 + 0.07 * hash(cell);
    vec3 albedo = v_col.rgb * n;
    float e = v_col.a > 1.5 ? (v_col.a - 2.0) : 0.0;
    frag = vec4(shade(albedo, normalize(v_norm), v_wpos, v_lpos, e), 1.0);
}
"""

DEPTH_BLOCK_VS = """
#version 330
in vec3 in_pos; in vec3 in_off; in vec3 in_scl;
uniform mat4 light_vp;
void main() { gl_Position = light_vp * vec4(in_off + in_pos * in_scl, 1.0); }
"""
DEPTH_BOX_VS = """
#version 330
in vec3 in_pos; in mat4 in_m;
uniform mat4 light_vp;
void main() { gl_Position = light_vp * in_m * vec4(in_pos, 1.0); }
"""
DEPTH_FS = """
#version 330
void main() {}
"""

SKY_VS = """
#version 330
in vec2 in_xy; out vec2 v_xy;
void main() { v_xy = in_xy; gl_Position = vec4(in_xy, 0.9999, 1.0); }
"""
SKY_FS = """
#version 330
in vec2 v_xy; uniform vec3 top; uniform vec3 bottom; uniform vec3 sun_screen; uniform vec3 sun_glow;
uniform float stars; uniform float time;
out vec4 frag;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
    float t = clamp(v_xy.y * 0.5 + 0.5, 0.0, 1.0);
    vec3 c = mix(bottom, top, pow(t, 0.8));
    float d = length((v_xy - sun_screen.xy) * vec2(1.78, 1.0));
    c += sun_glow * (exp(-d * 6.0) * 0.8 + exp(-d * 1.6) * 0.25) * sun_screen.z;
    vec2 g = floor(gl_FragCoord.xy / 3.0);
    float st = step(0.9985, hash(g)) * stars * (0.6 + 0.4 * sin(time * 3.0 + g.x));
    c += vec3(st) * t;
    frag = vec4(c, 1.0);
}
"""


def _cube(centered: bool) -> np.ndarray:
    o = -0.5 if centered else 0.0
    faces = [
        # normal, face id, 4 corners (CCW from outside), uvs
        ((0, 1, 0), 0, [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)]),
        ((0, -1, 0), 1, [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
        ((0, 0, 1), 2, [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
        ((0, 0, -1), 2, [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)]),
        ((1, 0, 0), 2, [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)]),
        ((-1, 0, 0), 2, [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    out = []
    for n, fid, cs in faces:
        for i in (0, 1, 2, 0, 2, 3):
            p = cs[i]
            out += [p[0] + o, p[1] + o, p[2] + o, *n, *uvs[i], fid]
    return np.array(out, dtype=np.float32)


# --------------------------------------------------------------------------
# Scene description (filled by shot code every frame)
# --------------------------------------------------------------------------


@dataclass
class Env:
    sky_top: tuple = (0.29, 0.62, 1.0)
    sky_bottom: tuple = (0.78, 0.9, 1.0)
    sun_dir: tuple = (-0.45, -0.8, -0.35)
    sun_col: tuple = (1.05, 0.98, 0.88)
    amb_sky: tuple = (0.62, 0.72, 0.95)
    amb_ground: tuple = (0.45, 0.4, 0.33)
    fog_col: tuple = (0.75, 0.86, 1.0)
    fog_density: float = 0.012
    stars: float = 0.0
    sun_glow: tuple = (1.0, 0.9, 0.6)

    @staticmethod
    def blend(a: "Env", b: "Env", t: float) -> "Env":
        t = max(0.0, min(1.0, t))
        kw = {}
        for k in a.__dataclass_fields__:
            va, vb = getattr(a, k), getattr(b, k)
            if isinstance(va, tuple):
                kw[k] = tuple(x + (y - x) * t for x, y in zip(va, vb))
            else:
                kw[k] = va + (vb - va) * t
        return Env(**kw)


DAY = Env()
SUNSET = Env(sky_top=(0.25, 0.32, 0.65), sky_bottom=(1.0, 0.6, 0.35), sun_dir=(-0.8, -0.25, -0.2),
             sun_col=(1.1, 0.65, 0.4), amb_sky=(0.55, 0.45, 0.6), amb_ground=(0.45, 0.3, 0.25),
             fog_col=(0.95, 0.62, 0.45), fog_density=0.014, sun_glow=(1.0, 0.55, 0.25))
NIGHT = Env(sky_top=(0.02, 0.03, 0.1), sky_bottom=(0.08, 0.1, 0.24), sun_dir=(0.3, -0.9, 0.25),
            sun_col=(0.4, 0.46, 0.75), amb_sky=(0.38, 0.44, 0.7), amb_ground=(0.3, 0.2, 0.16),
            fog_col=(0.05, 0.06, 0.15), fog_density=0.016, stars=1.0, sun_glow=(0.6, 0.7, 1.0))


class Scene:
    def __init__(self):
        self.blocks: list[tuple] = []        # (x, y, z, sx, sy, sz, type_id)
        self.block_arrays: list[np.ndarray] = []
        self.boxes: list[np.ndarray] = []    # 20 floats: mat4 (column-major) + rgba
        self.boxes_ns: list[np.ndarray] = []  # boxes that cast no shadow (clouds, glows)

    def block(self, x, y, z, kind, sx=1.0, sy=1.0, sz=1.0):
        self.blocks.append((x, y, z, sx, sy, sz, BLOCK_IDS[kind]))

    def add_blocks(self, arr: np.ndarray):
        if len(arr):
            self.block_arrays.append(arr.astype(np.float32))

    def box(self, m: np.ndarray, color, emissive: float = 0.0):
        c = hex3(color) if isinstance(color, str) else list(color)[:3]
        a = 2.0 + emissive if emissive > 0 else 1.0
        self.boxes.append(np.concatenate([m.T.reshape(-1), np.array([*c, a], dtype=np.float32)]))

    def cube(self, cx, cy, cz, sx, sy, sz, color, emissive=0.0, rot_y=0.0, shadow=True):
        self.box(T(cx, cy, cz) @ RY(rot_y) @ S(sx, sy, sz), color, emissive)
        if not shadow:
            self.boxes_ns.append(self.boxes.pop())


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------


class Renderer:
    def __init__(self, width=1920, height=1080, samples=4, shadow_size=2048):
        import moderngl

        self.w, self.h = width, height
        self.gl = moderngl.create_standalone_context(backend="egl")
        gl = self.gl
        self.prog_block = gl.program(vertex_shader=BLOCK_VS, fragment_shader=BLOCK_FS)
        self.prog_box = gl.program(vertex_shader=BOX_VS, fragment_shader=BOX_FS)
        self.prog_dblock = gl.program(vertex_shader=DEPTH_BLOCK_VS, fragment_shader=DEPTH_FS)
        self.prog_dbox = gl.program(vertex_shader=DEPTH_BOX_VS, fragment_shader=DEPTH_FS)
        self.prog_sky = gl.program(vertex_shader=SKY_VS, fragment_shader=SKY_FS)
        self.cube0 = gl.buffer(_cube(False).tobytes())
        self.cubec = gl.buffer(_cube(True).tobytes())
        self.sky_vbo = gl.buffer(np.array([-1, -1, 3, -1, -1, 3], dtype=np.float32).tobytes())
        self.sky_vao = gl.vertex_array(self.prog_sky, [(self.sky_vbo, "2f", "in_xy")])
        # textures
        layers = []
        for kind in BLOCKS:
            top, bot, side, _ = BLOCKS[kind]
            for k in (top, bot, side):
                layers.append(_tex_rgba(k))
        self.n_layers = len(layers)
        self.tex = gl.texture_array((16, 16, self.n_layers), 4, np.stack(layers).tobytes())
        import moderngl as mgl
        self.tex.filter = (mgl.NEAREST, mgl.NEAREST)
        self.lava_frames = [_tex_rgba("lava", f) for f in range(8)]
        # shadow
        self.shadow_tex = gl.depth_texture((shadow_size, shadow_size))
        self.shadow_tex.compare_func = ""
        self.shadow_tex.filter = (mgl.LINEAR, mgl.LINEAR)
        self.shadow_fbo = gl.framebuffer(depth_attachment=self.shadow_tex)
        # main fbo (MSAA) + resolve target
        self.samples = samples
        if samples > 1:
            self.ms_color = gl.renderbuffer((width, height), 4, samples=samples)
            self.ms_depth = gl.depth_renderbuffer((width, height), samples=samples)
            self.ms_fbo = gl.framebuffer([self.ms_color], self.ms_depth)
        self.out_color = gl.renderbuffer((width, height), 4)
        self.out_depth = gl.depth_renderbuffer((width, height))
        self.out_fbo = gl.framebuffer([self.out_color], self.out_depth)
        em = [BLOCKS[k][3] for k in BLOCKS] + [0.0] * (16 - len(BLOCKS))
        self.prog_block["emissive_by_type"].value = em
        self.prog_block["lava_type"].value = float(BLOCK_IDS["lava"])
        self._buffers = []

    def _set_common(self, prog, env: Env, cam_pos, light_vp, vp=None):
        def setu(name, val):
            if name in prog:
                prog[name].value = val
        sd = np.array(env.sun_dir, dtype=np.float32)
        sd /= np.linalg.norm(sd)
        setu("sun_dir", tuple(sd))
        setu("sun_col", env.sun_col)
        setu("sky_col", env.amb_sky)
        setu("ground_col", env.amb_ground)
        setu("fog_col", env.fog_col)
        setu("fog_density", env.fog_density)
        setu("cam_pos", tuple(cam_pos))
        setu("shadow_on", 1.0)
        if "light_vp" in prog:
            prog["light_vp"].write(light_vp.T.astype(np.float32).tobytes())
        if vp is not None and "vp" in prog:
            prog["vp"].write(vp.T.astype(np.float32).tobytes())

    def render(self, scene: Scene, eye, target, env: Env, t: float, fov=55.0, shadow_center=(0, 0, 0),
               shadow_extent=34.0) -> np.ndarray:
        gl = self.gl
        import moderngl as mgl
        for b in self._buffers:
            b.release()
        self._buffers = []
        # instance data
        arrs = list(scene.block_arrays)
        if scene.blocks:
            arrs.append(np.array(scene.blocks, dtype=np.float32))
        blocks = np.concatenate(arrs) if arrs else np.zeros((0, 7), np.float32)
        boxes = np.stack(scene.boxes).astype(np.float32) if scene.boxes else np.zeros((0, 20), np.float32)
        vaos = []
        if len(blocks):
            ib = gl.buffer(blocks.tobytes())
            self._buffers.append(ib)
            v_main = gl.vertex_array(self.prog_block, [(self.cube0, "3f 3f 2f 1f", "in_pos", "in_norm", "in_uv", "in_face"),
                                                       (ib, "3f 3f 1f/i", "in_off", "in_scl", "in_type")])
            v_depth = gl.vertex_array(self.prog_dblock, [(self.cube0, "3f 12x 8x 4x", "in_pos"),
                                                         (ib, "3f 3f 4x/i", "in_off", "in_scl")])
            vaos.append((v_main, v_depth, len(blocks)))
        if len(boxes):
            bb = gl.buffer(boxes.tobytes())
            self._buffers.append(bb)
            b_main = gl.vertex_array(self.prog_box, [(self.cubec, "3f 3f 2f 4x", "in_pos", "in_norm", "in_uv"),
                                                     (bb, "16f 4f/i", "in_m", "in_col")])
            b_depth = gl.vertex_array(self.prog_dbox, [(self.cubec, "3f 12x 8x 4x", "in_pos"), (bb, "16f 16x/i", "in_m")])
            vaos.append((b_main, b_depth, len(boxes)))
        if scene.boxes_ns:
            nb = np.stack(scene.boxes_ns).astype(np.float32)
            nbb = gl.buffer(nb.tobytes())
            self._buffers.append(nbb)
            n_main = gl.vertex_array(self.prog_box, [(self.cubec, "3f 3f 2f 4x", "in_pos", "in_norm", "in_uv"),
                                                     (nbb, "16f 4f/i", "in_m", "in_col")])
            vaos.append((n_main, None, len(nb)))
        # light matrices
        sd = np.array(env.sun_dir, dtype=np.float32)
        sd /= np.linalg.norm(sd)
        c = np.array(shadow_center, dtype=np.float32)
        lview = look_at(c - sd * 60, c, up=(0, 1, 0) if abs(sd[1]) < 0.99 else (1, 0, 0))
        lproj = ortho(-shadow_extent, shadow_extent, -shadow_extent, shadow_extent, 1, 140)
        light_vp = lproj @ lview
        # shadow pass
        self.shadow_fbo.use()
        self.shadow_fbo.clear(depth=1.0)
        gl.enable(mgl.DEPTH_TEST)
        gl.disable(mgl.CULL_FACE)
        for main, depth, n in vaos:
            if depth is None:
                continue
            depth.program["light_vp"].write(light_vp.T.astype(np.float32).tobytes())
            depth.render(instances=n)
        # main pass
        fbo = self.ms_fbo if self.samples > 1 else self.out_fbo
        fbo.use()
        fbo.clear(0, 0, 0, 1, depth=1.0)
        view = look_at(eye, target)
        proj = perspective(fov, self.w / self.h, 0.1, 400)
        vp = proj @ view
        # sky
        gl.disable(mgl.DEPTH_TEST)
        sp = self.prog_sky
        sp["top"].value = env.sky_top
        sp["bottom"].value = env.sky_bottom
        sun_world = np.array([*(-sd * 300 + np.array(eye)), 1.0], dtype=np.float32)
        clip = vp @ sun_world
        if clip[3] > 0:
            ss = (clip[0] / clip[3], clip[1] / clip[3], 1.0)
        else:
            ss = (0.0, 2.0, 0.0)
        sp["sun_screen"].value = ss
        sp["sun_glow"].value = env.sun_glow
        sp["stars"].value = env.stars
        sp["time"].value = t
        self.sky_vao.render()
        gl.enable(mgl.DEPTH_TEST)
        gl.enable(mgl.CULL_FACE)
        self.shadow_tex.use(location=1)
        self.tex.use(location=0)
        for prog in (self.prog_block, self.prog_box):
            self._set_common(prog, env, eye, light_vp, vp)
            prog["shadow_map"].value = 1
        self.prog_block["tex"].value = 0
        self.prog_block["time"].value = t
        for main, depth, n in vaos:
            main.render(instances=n)
        for main, depth, n in vaos:
            main.release()
            if depth is not None:
                depth.release()
        if self.samples > 1:
            gl.copy_framebuffer(self.out_fbo, self.ms_fbo)
        data = self.out_fbo.read(components=4, alignment=1)
        img = np.frombuffer(data, dtype=np.uint8).reshape(self.h, self.w, 4)[::-1]
        return img


_RENDERER: Optional[Renderer] = None
_RENDERER_PID = None


def renderer(width=1920, height=1080) -> Renderer:
    """One GL context per process (safe with the multiprocessing fork pool)."""
    global _RENDERER, _RENDERER_PID
    if _RENDERER is None or _RENDERER_PID != os.getpid() or (_RENDERER.w, _RENDERER.h) != (width, height):
        _RENDERER = Renderer(width, height, samples=int(os.environ.get("EVERYDAY_MSAA", "4")))
        _RENDERER_PID = os.getpid()
    return _RENDERER


def blit(ctx, img: np.ndarray):
    """Paint an RGBA frame into a cairo context at logical 1920x1080 size."""
    import cairo

    h, w = img.shape[:2]
    bgra = np.ascontiguousarray(img[:, :, [2, 1, 0, 3]])
    bgra[:, :, 3] = 255
    surf = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_ARGB32, w, h, w * 4)
    ctx.save()
    ctx.scale(1920 / w, 1080 / h)
    ctx.set_source_surface(surf, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
    ctx.paint()
    ctx.restore()
    surf.finish()

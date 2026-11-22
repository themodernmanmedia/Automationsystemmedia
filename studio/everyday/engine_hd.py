"""Cinematic 3D renderer (OpenGL 3.3 core via moderngl, headless EGL).

Rendering features
  * Smooth meshes: spheres (2 LODs), cylinders, octahedra, boxes, terrain, rings
  * Instanced drawing: per-instance matrix, colour and material
  * Physically-inspired shading: linear-space lighting, GGX-style specular,
    Fresnel rim, wrap/subsurface lighting for skin, hemisphere ambient
  * Procedural materials: lava (animated fbm, emissive HDR), grass, stone,
    wood, gold, gems
  * Sun shadow map with 16-tap Poisson PCF soft shadows
  * HDR (RGBA16F, 4x MSAA) -> bloom (bright-pass + gaussian) -> depth of
    field (circle of confusion from depth) -> ACES filmic tonemap ->
    colour grade, vignette, film grain
  * Procedural sky with sun disc and drifting fbm clouds, height fog
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .engine3d import RX, RY, RZ, S, T, look_at, ortho, perspective  # matrix helpers


def srgb(c):
    if isinstance(c, str):
        h = c.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [float(v) for v in list(c)[:3]]


# material kinds
PLAIN, LAVA, GRASS, SKIN, STONE, WOOD, GOLD, GEM, CLOTH, HAIR, EYE, WATER = range(12)

# --------------------------------------------------------------------------
# Meshes
# --------------------------------------------------------------------------


def mesh_sphere(lat=16, lon=24):
    v = []
    for i in range(lat):
        t0, t1 = math.pi * i / lat, math.pi * (i + 1) / lat
        for j in range(lon):
            p0, p1 = 2 * math.pi * j / lon, 2 * math.pi * (j + 1) / lon

            def P(t, p):
                return (math.sin(t) * math.cos(p), math.cos(t), math.sin(t) * math.sin(p))
            a, b, c, d = P(t0, p0), P(t1, p0), P(t1, p1), P(t0, p1)
            for q in (a, c, b, a, d, c):
                v += [*q, *q]
    return np.array(v, dtype=np.float32)


def mesh_cylinder(seg=20, caps=True):
    v = []
    for j in range(seg):
        p0, p1 = 2 * math.pi * j / seg, 2 * math.pi * (j + 1) / seg
        c0, s0, c1, s1 = math.cos(p0), math.sin(p0), math.cos(p1), math.sin(p1)
        quad = [(c0, 0, s0), (c1, 0, s1), (c1, 1, s1), (c0, 0, s0), (c1, 1, s1), (c0, 1, s0)]
        for x, y, z in quad:
            v += [x, y, z, x, 0, z]
        if caps:
            for y, ny, order in ((1, 1, ((0, 1, 0), (c1, 1, s1), (c0, 1, s0))), (0, -1, ((0, 0, 0), (c0, 0, s0), (c1, 0, s1)))):
                for p in order:
                    v += [*p, 0, ny, 0]
    return np.array(v, dtype=np.float32)


def mesh_box():
    v = []
    faces = [((0, 1, 0), [(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)]),
             ((0, -1, 0), [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)]),
             ((0, 0, 1), [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]),
             ((0, 0, -1), [(1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)]),
             ((1, 0, 0), [(1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)]),
             ((-1, 0, 0), [(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)])]
    for n, cs in faces:
        for i in (0, 1, 2, 0, 2, 3):
            x, y, z = cs[i]
            v += [x * 0.5, y * 0.5, z * 0.5, *n]
    return np.array(v, dtype=np.float32)


def mesh_octa():
    pts = [(1, 0, 0), (-1, 0, 0), (0, 1.3, 0), (0, -1.3, 0), (0, 0, 1), (0, 0, -1)]
    tris = [(0, 2, 4), (4, 2, 1), (1, 2, 5), (5, 2, 0), (4, 3, 0), (1, 3, 4), (5, 3, 1), (0, 3, 5)]
    v = []
    for a, b, c in tris:
        A, B, C = (np.array(pts[k], dtype=np.float32) for k in (a, b, c))
        n = np.cross(B - A, C - A)
        n /= np.linalg.norm(n)
        for P in (A, B, C):
            v += [*P, *n]
    return np.array(v, dtype=np.float32)


def mesh_annulus(r0, r1, y=0.0, seg=96):
    v = []
    for j in range(seg):
        p0, p1 = 2 * math.pi * j / seg, 2 * math.pi * (j + 1) / seg
        a = (r0 * math.cos(p0), y, r0 * math.sin(p0))
        b = (r1 * math.cos(p0), y, r1 * math.sin(p0))
        c = (r1 * math.cos(p1), y, r1 * math.sin(p1))
        d = (r0 * math.cos(p1), y, r0 * math.sin(p1))
        for p in (a, c, b, a, d, c):
            v += [*p, 0, 1, 0]
    return np.array(v, dtype=np.float32)


def mesh_torus(R, r, seg=128, tube=10):
    v = []
    for i in range(seg):
        u0, u1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        for j in range(tube):
            w0, w1 = 2 * math.pi * j / tube, 2 * math.pi * (j + 1) / tube

            def P(u, w):
                cx, cz = math.cos(u), math.sin(u)
                n = (math.cos(w) * cx, math.sin(w), math.cos(w) * cz)
                return ((R + r * math.cos(w)) * cx, r * math.sin(w), (R + r * math.cos(w)) * cz), n
            quad = [P(u0, w0), P(u1, w0), P(u1, w1), P(u0, w0), P(u1, w1), P(u0, w1)]
            for p, n in (quad[0], quad[2], quad[1], quad[3], quad[5], quad[4]):
                v += [*p, *n]
    return np.array(v, dtype=np.float32)


def mesh_terrain(r_in, r_out, height_fn, n=160):
    """Square grid clipped to an annulus, smooth normals."""
    xs = np.linspace(-r_out, r_out, n)
    X, Z = np.meshgrid(xs, xs)
    Y = height_fn(X, Z)
    dx = xs[1] - xs[0]
    gy, gx = np.gradient(Y, dx)
    N = np.dstack([-gx, np.ones_like(Y), -gy])
    N /= np.linalg.norm(N, axis=2, keepdims=True)
    D = np.hypot(X, Z)
    v = []
    for i in range(n - 1):
        for j in range(n - 1):
            if max(D[i, j], D[i + 1, j + 1], D[i, j + 1], D[i + 1, j]) < r_in - dx:
                continue
            if min(D[i, j], D[i + 1, j + 1]) > r_out:
                continue
            for (a, b) in ((i, j), (i + 1, j + 1), (i, j + 1), (i, j), (i + 1, j), (i + 1, j + 1)):
                v += [X[a, b], Y[a, b], Z[a, b], *N[a, b]]
    return np.array(v, dtype=np.float32)


# --------------------------------------------------------------------------
# Shaders
# --------------------------------------------------------------------------

NOISE = """
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float a = 0.5, s = 0.0; for (int k = 0; k < 5; k++) { s += a * vnoise(p); p = p * 2.03 + 17.1; a *= 0.5; } return s; }
"""

MAIN_VS = """
#version 330
in vec3 in_pos; in vec3 in_norm;
in mat4 in_m; in vec3 in_col; in vec4 in_mat;
uniform mat4 vp; uniform mat4 light_vp; uniform mat4 view;
out vec3 v_w; out vec3 v_n; out vec3 v_col; out vec4 v_mat; out vec4 v_lp; out float v_vz; out vec3 v_obj;
void main() {
    vec4 w = in_m * vec4(in_pos, 1.0);
    mat3 nm = transpose(inverse(mat3(in_m)));
    v_w = w.xyz; v_n = normalize(nm * in_norm); v_col = in_col; v_mat = in_mat; v_obj = in_pos;
    v_lp = light_vp * w;
    v_vz = -(view * w).z;
    gl_Position = vp * w;
}
"""

MAIN_FS = """
#version 330
in vec3 v_w; in vec3 v_n; in vec3 v_col; in vec4 v_mat; in vec4 v_lp; in float v_vz; in vec3 v_obj;
uniform vec3 sun_dir; uniform vec3 sun_col; uniform vec3 amb_sky; uniform vec3 amb_ground;
uniform vec3 fog_col; uniform float fog_density; uniform vec3 cam_pos; uniform float time;
uniform sampler2D shadow_map;
out vec4 frag;
""" + NOISE + """
const vec2 poisson[16] = vec2[](vec2(-0.94201624, -0.39906216), vec2(0.94558609, -0.76890725), vec2(-0.094184101, -0.92938870),
  vec2(0.34495938, 0.29387760), vec2(-0.91588581, 0.45771432), vec2(-0.81544232, -0.87912464), vec2(-0.38277543, 0.27676845),
  vec2(0.97484398, 0.75648379), vec2(0.44323325, -0.97511554), vec2(0.53742981, -0.47373420), vec2(-0.26496911, -0.41893023),
  vec2(0.79197514, 0.19090188), vec2(-0.24188840, 0.99706507), vec2(-0.81409955, 0.91437590), vec2(0.19984126, 0.78641367),
  vec2(0.14383161, -0.14100790));

float shadow(vec4 lp, float ndl) {
    vec3 p = lp.xyz / lp.w * 0.5 + 0.5;
    if (p.x <= 0.0 || p.x >= 1.0 || p.y <= 0.0 || p.y >= 1.0 || p.z >= 1.0) return 1.0;
    float bias = mix(0.0016, 0.0004, ndl);
    vec2 ts = 1.6 / vec2(textureSize(shadow_map, 0));
    float a = hash12(gl_FragCoord.xy) * 6.2831;
    mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
    float s = 0.0;
    for (int i = 0; i < 16; i++) {
        float d = texture(shadow_map, p.xy + rot * poisson[i] * ts).r;
        s += (p.z - bias > d) ? 0.0 : 1.0;
    }
    return s / 16.0;
}

vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }

void main() {
    vec3 albedo = lin(v_col);
    float rough = v_mat.x, emis = v_mat.y; int kind = int(v_mat.z + 0.5); float extra = v_mat.w;
    vec3 N = normalize(v_n);
    vec3 V = normalize(cam_pos - v_w);
    vec3 L = -normalize(sun_dir);
    vec3 emissive = vec3(0.0);
    float wrap = 0.0; float spec_k = 0.5;

    if (kind == 1) { // lava
        vec2 q = v_w.xz * 0.35;
        float n1 = fbm(q + vec2(time * 0.05, time * 0.08));
        float n2 = fbm(q * 2.3 - vec2(time * 0.11, -time * 0.04) + n1 * 1.5);
        float h = smoothstep(0.35, 0.75, n2);
        vec3 crust = vec3(0.05, 0.012, 0.008);
        vec3 hot = mix(vec3(1.0, 0.18, 0.02), vec3(1.0, 0.65, 0.12), smoothstep(0.55, 0.95, n2));
        albedo = mix(crust, hot * 0.3, h);
        emissive = hot * (0.15 + 4.5 * h * h) * (0.85 + 0.15 * sin(time * 2.0 + n1 * 6.0));
        rough = 0.6;
    } else if (kind == 2) { // grass
        float n = fbm(v_w.xz * 0.35);
        float m = fbm(v_w.xz * 3.1);
        albedo *= 0.75 + 0.45 * n;
        albedo = mix(albedo, albedo * vec3(1.15, 1.05, 0.55), smoothstep(0.55, 0.8, m) * 0.35);
        float blade = hash12(floor(v_w.xz * 18.0));
        albedo *= 0.9 + 0.2 * blade;
        float slope = 1.0 - N.y;
        albedo = mix(albedo, lin(vec3(0.45, 0.42, 0.38)) * (0.8 + 0.4 * n), smoothstep(0.35, 0.6, slope));
        rough = 0.95; spec_k = 0.1;
    } else if (kind == 3) { // skin
        wrap = 0.45; rough = 0.55; spec_k = 0.25;
    } else if (kind == 4) { // stone
        float n = fbm(v_w.xz * 0.9 + v_w.y * 1.3);
        albedo *= 0.65 + 0.6 * n; rough = 0.85; spec_k = 0.15;
    } else if (kind == 5) { // wood
        float g = sin((v_w.x + v_w.z) * 18.0 + fbm(v_w.xz * 4.0 + v_w.y) * 6.0);
        albedo *= 0.8 + 0.2 * g; rough = 0.7; spec_k = 0.2;
    } else if (kind == 6) { // gold
        rough = 0.28; spec_k = 1.6;
        emissive = albedo * emis * (0.8 + 0.2 * sin(time * 4.0 + v_w.x));
    } else if (kind == 7) { // gem
        rough = 0.08; spec_k = 2.5;
        emissive = albedo * emis * 1.5;
    } else if (kind == 8) { // cloth
        float n = hash12(floor(v_obj.xy * 120.0 + v_obj.z * 77.0));
        albedo *= 0.94 + 0.08 * n; rough = 0.9; spec_k = 0.12; wrap = 0.15;
    } else if (kind == 9) { // hair
        rough = 0.4; spec_k = 0.6; wrap = 0.2;
        albedo *= 0.9 + 0.12 * sin(v_obj.x * 90.0 + v_obj.y * 30.0);
    } else if (kind == 10) { // eye
        rough = 0.05; spec_k = 2.0;
    } else {
        emissive = albedo * emis;
    }

    float ndl_raw = dot(N, L);
    float ndl = max((ndl_raw + wrap) / (1.0 + wrap), 0.0);
    float sh = shadow(v_lp, max(ndl_raw, 0.0));
    vec3 H = normalize(L + V);
    float a = max(rough * rough, 0.02);
    float ndh = max(dot(N, H), 0.0);
    float d = ndh * ndh * (a * a - 1.0) + 1.0;
    float D = a * a / (3.14159 * d * d);
    float F = 0.04 + 0.96 * pow(1.0 - max(dot(H, V), 0.0), 5.0);
    vec3 spec = vec3(D * F * spec_k * 0.25) * max(ndl_raw, 0.0);
    vec3 amb = mix(amb_ground, amb_sky, N.y * 0.5 + 0.5);
    float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0);
    vec3 col = albedo * (amb * 0.9 + sun_col * ndl * sh) + spec * sun_col * sh;
    // contact darkening near the ground plane
    col *= mix(0.72, 1.0, smoothstep(0.0, 0.35, v_w.y - (kind == 2 || kind == 1 ? -10.0 : 0.0)));
    col += amb_sky * rim * 0.18 * (kind == 3 ? 1.5 : 1.0);
    if (kind == 3) {  // subsurface-ish warm scatter
        col += albedo * vec3(0.9, 0.35, 0.25) * 0.05 * max(0.0, 1.0 - ndl_raw) * (0.4 + 0.6 * sh);
    }
    col += emissive;
    // fog
    float dist = length(v_w - cam_pos);
    float fog = 1.0 - exp(-pow(dist * fog_density, 1.5));
    fog *= exp(-max(v_w.y, 0.0) * 0.02);
    col = mix(col, fog_col, clamp(fog, 0.0, 1.0));
    if (any(isnan(col)) || any(isinf(col))) col = fog_col;
    col = min(col, vec3(48.0));
    frag = vec4(col, v_vz);
}
"""

DEPTH_VS = """
#version 330
in vec3 in_pos; in mat4 in_m;
uniform mat4 light_vp;
void main() { gl_Position = light_vp * in_m * vec4(in_pos, 1.0); }
"""
DEPTH_FS = "#version 330\nvoid main() {}\n"

FS_QUAD_VS = """
#version 330
in vec2 in_xy; out vec2 uv;
void main() { uv = in_xy * 0.5 + 0.5; gl_Position = vec4(in_xy, 0.0, 1.0); }
"""

SKY_FS = """
#version 330
in vec2 uv; out vec4 frag;
uniform mat4 inv_vp; uniform vec3 cam_pos; uniform vec3 sun_dir; uniform vec3 top; uniform vec3 horizon;
uniform vec3 sun_col; uniform float time; uniform float stars; uniform float clouds;
""" + NOISE + """
vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }
void main() {
    vec4 p = inv_vp * vec4(uv * 2.0 - 1.0, 1.0, 1.0);
    vec3 dir = normalize(p.xyz / p.w - cam_pos);
    float h = clamp(dir.y, -0.1, 1.0);
    vec3 col = mix(lin(horizon), lin(top), pow(max(h, 0.0), 0.55));
    vec3 L = -normalize(sun_dir);
    float sd = max(dot(dir, L), 0.0);
    col += sun_col * (pow(sd, 900.0) * 30.0 + pow(sd, 12.0) * 0.35 + pow(sd, 3.0) * 0.08);
    if (dir.y > 0.0) {
        vec2 cp = dir.xz / (dir.y + 0.08) * 1.4 + vec2(time * 0.01, time * 0.004);
        float c = smoothstep(0.5, 0.85, fbm(cp));
        vec3 ccol = mix(vec3(1.0), lin(horizon), 0.25) * (0.75 + 0.5 * sd) * mix(1.0, 0.18, stars);
        col = mix(col, ccol, c * clouds * smoothstep(0.0, 0.12, dir.y));
        float st = step(0.9975, hash12(floor(dir.xz / (dir.y + 0.2) * 300.0))) * stars;
        col += vec3(st) * smoothstep(0.05, 0.3, dir.y);
    }
    frag = vec4(col, 1000.0);
}
"""

BRIGHT_FS = """
#version 330
in vec2 uv; out vec4 frag; uniform sampler2D src; uniform float threshold;
void main() {
    vec3 c = texture(src, uv).rgb;
    float l = max(c.r, max(c.g, c.b));
    vec3 b = c * smoothstep(threshold, threshold * 2.0, l);
    frag = vec4(b, texture(src, uv).a);
}
"""

DOWN_FS = """
#version 330
in vec2 uv; out vec4 frag; uniform sampler2D src;
void main() {
    vec2 t = 1.0 / vec2(textureSize(src, 0));
    vec4 c = texture(src, uv + t * vec2(-1, -1)) + texture(src, uv + t * vec2(1, -1)) +
             texture(src, uv + t * vec2(-1, 1)) + texture(src, uv + t * vec2(1, 1));
    frag = c * 0.25;
}
"""

BLUR_FS = """
#version 330
in vec2 uv; out vec4 frag; uniform sampler2D src; uniform vec2 dir;
void main() {
    vec2 t = dir / vec2(textureSize(src, 0));
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    vec4 c = texture(src, uv) * w[0];
    for (int i = 1; i < 5; i++) { c += texture(src, uv + t * float(i) * 1.6) * w[i]; c += texture(src, uv - t * float(i) * 1.6) * w[i]; }
    frag = c;
}
"""

COMPOSE_FS = """
#version 330
in vec2 uv; out vec4 frag;
uniform sampler2D scene; uniform sampler2D blurred; uniform sampler2D bloom;
uniform float exposure; uniform float bloom_k; uniform float focus; uniform float dof; uniform float time;
uniform float saturation; uniform vec3 lift; uniform vec3 gain; uniform float vignette;
vec3 aces(vec3 x) { float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14; return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main() {
    vec4 s = texture(scene, uv);
    vec4 bl = texture(blurred, uv);
    if (any(isnan(bl))) bl = s;
    float z = s.a;
    float coc = clamp(abs(z - focus) / max(focus, 0.01) * dof, 0.0, 1.0);
    vec3 c = mix(s.rgb, bl.rgb, coc);
    vec3 bm = texture(bloom, uv).rgb;
    if (any(isnan(bm))) bm = vec3(0.0);
    c += bm * bloom_k;
    c *= exposure;
    c = aces(c);
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(l), c, saturation);
    c = c * gain + lift * (1.0 - c);
    vec2 d = uv - 0.5;
    c *= 1.0 - vignette * dot(d, d) * 1.6;
    c = pow(c, vec3(1.0 / 2.2));
    c += (hash12(uv * 1920.0 + time * 61.0) - 0.5) * 0.018;
    frag = vec4(c, 1.0);
}
"""


# --------------------------------------------------------------------------
# Environment presets
# --------------------------------------------------------------------------


@dataclass
class Env:
    sky_top: tuple = (0.24, 0.5, 0.92)
    sky_horizon: tuple = (0.75, 0.86, 0.98)
    sun_dir: tuple = (-0.5, -0.5, -0.55)
    sun_col: tuple = (2.5, 2.3, 2.05)
    amb_sky: tuple = (0.27, 0.36, 0.55)
    amb_ground: tuple = (0.16, 0.14, 0.1)
    fog_col: tuple = (0.55, 0.68, 0.88)
    fog_density: float = 0.006
    stars: float = 0.0
    clouds: float = 0.85
    exposure: float = 0.92
    bloom: float = 0.6
    saturation: float = 1.06
    lift: tuple = (0.0, 0.0, 0.01)
    gain: tuple = (1.0, 1.0, 1.0)

    @staticmethod
    def blend(a: "Env", b: "Env", t: float) -> "Env":
        t = max(0.0, min(1.0, t))
        kw = {}
        for k in a.__dataclass_fields__:
            va, vb = getattr(a, k), getattr(b, k)
            kw[k] = tuple(x + (y - x) * t for x, y in zip(va, vb)) if isinstance(va, tuple) else va + (vb - va) * t
        return Env(**kw)


DAY = Env()
SUNSET = Env(sky_top=(0.2, 0.25, 0.55), sky_horizon=(1.0, 0.55, 0.3), sun_dir=(-0.85, -0.18, -0.25),
             sun_col=(3.0, 1.6, 0.8), amb_sky=(0.38, 0.32, 0.45), amb_ground=(0.25, 0.14, 0.1),
             fog_col=(0.75, 0.45, 0.32), fog_density=0.011, exposure=1.05, bloom=0.7, gain=(1.05, 0.98, 0.92))
NIGHT = Env(sky_top=(0.01, 0.02, 0.06), sky_horizon=(0.05, 0.08, 0.18), sun_dir=(0.35, -0.8, 0.3),
            sun_col=(0.16, 0.2, 0.4), amb_sky=(0.07, 0.09, 0.18), amb_ground=(0.12, 0.05, 0.03),
            fog_col=(0.02, 0.025, 0.07), fog_density=0.008, stars=1.0, clouds=0.4, exposure=1.25, bloom=0.95,
            gain=(0.95, 1.0, 1.1))


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------


class Scene:
    def __init__(self):
        self.inst: dict[str, list] = {}      # mesh -> rows (23 floats)
        self.dynamic: list[tuple] = []       # (key, builder, color, mat)
        self.static: list[tuple] = []        # (key, builder, color, mat)
        self.noshadow: set[str] = set()

    def add(self, mesh: str, m: np.ndarray, color, rough=0.6, emissive=0.0, kind=PLAIN, extra=0.0, shadow=True):
        key = mesh if shadow else mesh + "#ns"
        row = np.empty(23, dtype=np.float32)
        row[:16] = m.T.reshape(-1)
        row[16:19] = srgb(color)
        row[19:23] = (rough, emissive, kind, extra)
        self.inst.setdefault(key, []).append(row)

    # compatibility with the voxel helpers (chest, target, beds, golden house)
    def box(self, m, color, emissive=0.0):
        self.add("box", m, color, rough=0.65, emissive=emissive, kind=GOLD if emissive > 0 else PLAIN)

    def cube(self, cx, cy, cz, sx, sy, sz, color, emissive=0.0, rot_y=0.0, shadow=True):
        self.add("box", T(cx, cy, cz) @ RY(rot_y) @ S(sx, sy, sz), color, emissive=emissive,
                 kind=GOLD if emissive > 0 else PLAIN, shadow=shadow)

    def block(self, x, y, z, kind, *a):
        kinds = {"plank": ("#b08a5a", WOOD), "stone": ("#8a8f98", STONE), "dirt": ("#7a5533", STONE),
                 "grass": ("#5aa83a", GRASS), "gold": ("#f2c230", GOLD)}
        col, k = kinds.get(kind, ("#999999", PLAIN))
        self.add("box", T(x + 0.5, y + 0.5, z + 0.5), col, kind=k, emissive=0.3 if k == GOLD else 0.0)

    def mesh(self, key, builder, color, rough=0.7, emissive=0.0, kind=PLAIN, static=False):
        (self.static if static else self.dynamic).append((key, builder, srgb(color), (rough, emissive, kind, 0.0)))

    def sphere(self, m, color, **kw):
        self.add("sphere", m, color, **kw)


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------


class Renderer:
    def __init__(self, width=1920, height=1080, samples=4, shadow_size=3072):
        import moderngl as mgl

        self.mgl = mgl
        self.w, self.h = width, height
        gl = self.gl = mgl.create_standalone_context(backend="egl")
        self.prog = gl.program(vertex_shader=MAIN_VS, fragment_shader=MAIN_FS)
        self.dprog = gl.program(vertex_shader=DEPTH_VS, fragment_shader=DEPTH_FS)
        self.sky = gl.program(vertex_shader=FS_QUAD_VS, fragment_shader=SKY_FS)
        self.bright = gl.program(vertex_shader=FS_QUAD_VS, fragment_shader=BRIGHT_FS)
        self.down = gl.program(vertex_shader=FS_QUAD_VS, fragment_shader=DOWN_FS)
        self.blur = gl.program(vertex_shader=FS_QUAD_VS, fragment_shader=BLUR_FS)
        self.compose = gl.program(vertex_shader=FS_QUAD_VS, fragment_shader=COMPOSE_FS)
        quad = gl.buffer(np.array([-1, -1, 3, -1, -1, 3], dtype=np.float32).tobytes())
        self.quads = {p: gl.vertex_array(p, [(quad, "2f", "in_xy")]) for p in
                      (self.sky, self.bright, self.down, self.blur, self.compose)}
        self.meshes = {
            "sphere": gl.buffer(mesh_sphere(18, 28).tobytes()),
            "sphere_lo": gl.buffer(mesh_sphere(8, 12).tobytes()),
            "cyl": gl.buffer(mesh_cylinder(22).tobytes()),
            "box": gl.buffer(mesh_box().tobytes()),
            "octa": gl.buffer(mesh_octa().tobytes()),
        }
        self.counts = {k: len(np.frombuffer(b.read(), dtype=np.float32)) // 6 for k, b in self.meshes.items()}
        self.ident = gl.buffer(np.concatenate([np.identity(4, dtype=np.float32).reshape(-1), np.zeros(7, np.float32)]).tobytes())
        self.mesh_cache: dict = {}
        # shadow
        self.shadow_tex = gl.depth_texture((shadow_size, shadow_size))
        self.shadow_tex.compare_func = ""
        self.shadow_tex.filter = (mgl.LINEAR, mgl.LINEAR)
        self.shadow_fbo = gl.framebuffer(depth_attachment=self.shadow_tex)
        # HDR targets
        self.samples = samples
        self.ms_col = gl.renderbuffer((width, height), 4, samples=samples, dtype="f2")
        self.ms_dep = gl.depth_renderbuffer((width, height), samples=samples)
        self.ms_fbo = gl.framebuffer([self.ms_col], self.ms_dep)
        self.hdr = gl.texture((width, height), 4, dtype="f2")
        self.hdr.filter = (mgl.LINEAR, mgl.LINEAR)
        self.hdr_fbo = gl.framebuffer([self.hdr])
        qw, qh = width // 4, height // 4
        self.q = [gl.texture((qw, qh), 4, dtype="f2") for _ in range(4)]
        for tx in self.q:
            tx.filter = (mgl.LINEAR, mgl.LINEAR)
            tx.repeat_x = tx.repeat_y = False
        self.q_fbo = [gl.framebuffer([tx]) for tx in self.q]
        self.half = gl.texture((width // 2, height // 2), 4, dtype="f2")
        self.half.filter = (mgl.LINEAR, mgl.LINEAR)
        self.half_fbo = gl.framebuffer([self.half])
        self.out = gl.renderbuffer((width, height), 4)
        self.out_fbo = gl.framebuffer([self.out])
        self._tmp = []

    def _mesh_buf(self, key, builder):
        if key not in self.mesh_cache:
            if len(self.mesh_cache) > 400:
                for k, b in list(self.mesh_cache.items())[:200]:
                    b[0].release()
                    del self.mesh_cache[k]
            data = builder()
            self.mesh_cache[key] = (self.gl.buffer(data.tobytes()), len(data) // 6)
        return self.mesh_cache[key]

    def render(self, scene: Scene, eye, target, env: Env, t: float, fov=50.0, shadow_center=(0, 0, 0),
               shadow_extent=30.0, focus=None, dof=0.0) -> np.ndarray:
        gl, mgl = self.gl, self.mgl
        for b in self._tmp:
            b.release()
        self._tmp = []
        draws = []   # (vao_main, vao_depth|None, count, instances)
        for key, rows in scene.inst.items():
            mesh = key.split("#")[0]
            ib = gl.buffer(np.stack(rows).tobytes())
            self._tmp.append(ib)
            vb = self.meshes[mesh]
            main = gl.vertex_array(self.prog, [(vb, "3f 3f", "in_pos", "in_norm"),
                                               (ib, "16f 3f 4f/i", "in_m", "in_col", "in_mat")])
            dep = None if key.endswith("#ns") else gl.vertex_array(self.dprog, [(vb, "3f 12x", "in_pos"), (ib, "16f 28x/i", "in_m")])
            draws.append((main, dep, self.counts[mesh], len(rows)))
        for lst, cast in ((scene.static, True), (scene.dynamic, True)):
            for key, builder, col, mat in lst:
                vb, n = self._mesh_buf(key, builder)
                inst = np.concatenate([np.identity(4, dtype=np.float32).reshape(-1), np.array(col, np.float32),
                                       np.array(mat, np.float32)])
                ib = gl.buffer(inst.tobytes())
                self._tmp.append(ib)
                main = gl.vertex_array(self.prog, [(vb, "3f 3f", "in_pos", "in_norm"),
                                                   (ib, "16f 3f 4f/i", "in_m", "in_col", "in_mat")])
                dep = gl.vertex_array(self.dprog, [(vb, "3f 12x", "in_pos"), (ib, "16f 28x/i", "in_m")]) if mat[2] not in (LAVA,) else None
                draws.append((main, dep, n, 1))
        # light
        sd = np.array(env.sun_dir, dtype=np.float32)
        sd /= np.linalg.norm(sd)
        c = np.array(shadow_center, dtype=np.float32)
        lview = look_at(c - sd * 80, c)
        light_vp = ortho(-shadow_extent, shadow_extent, -shadow_extent, shadow_extent, 1, 200) @ lview
        lvp_b = light_vp.T.astype(np.float32).tobytes()
        self.shadow_fbo.use()
        self.shadow_fbo.clear(depth=1.0)
        gl.enable(mgl.DEPTH_TEST)
        gl.disable(mgl.CULL_FACE)
        self.dprog["light_vp"].write(lvp_b)
        for main, dep, n, k in draws:
            if dep is not None:
                dep.render(vertices=n, instances=k)
        # main HDR pass
        view = look_at(eye, target)
        proj = perspective(fov, self.w / self.h, 0.08, 500)
        vp = proj @ view
        self.ms_fbo.use()
        self.ms_fbo.clear(0, 0, 0, 1000, depth=1.0)
        gl.disable(mgl.DEPTH_TEST)
        sk = self.sky
        sk["inv_vp"].write(np.linalg.inv(vp).T.astype(np.float32).tobytes())
        sk["cam_pos"].value = tuple(map(float, eye))
        sk["sun_dir"].value = tuple(map(float, sd))
        sk["top"].value = env.sky_top
        sk["horizon"].value = env.sky_horizon
        sk["sun_col"].value = env.sun_col
        sk["time"].value = t
        sk["stars"].value = env.stars
        sk["clouds"].value = env.clouds
        self.quads[sk].render()
        gl.enable(mgl.DEPTH_TEST)
        p = self.prog
        p["vp"].write(vp.T.astype(np.float32).tobytes())
        p["view"].write(view.T.astype(np.float32).tobytes())
        p["light_vp"].write(lvp_b)
        for name, val in (("sun_dir", tuple(map(float, sd))), ("sun_col", env.sun_col), ("amb_sky", env.amb_sky),
                          ("amb_ground", env.amb_ground), ("fog_col", env.fog_col), ("fog_density", env.fog_density),
                          ("cam_pos", tuple(map(float, eye))), ("time", t)):
            p[name].value = val
        self.shadow_tex.use(location=0)
        p["shadow_map"].value = 0
        for main, dep, n, k in draws:
            main.render(vertices=n, instances=k)
        for main, dep, n, k in draws:
            main.release()
            if dep is not None:
                dep.release()
        gl.copy_framebuffer(self.hdr_fbo, self.ms_fbo)
        # post: downsample chain
        gl.disable(mgl.DEPTH_TEST)
        self.half_fbo.use()
        self.hdr.use(0)
        self.down["src"].value = 0
        self.quads[self.down].render()
        self.q_fbo[0].use()
        self.half.use(0)
        self.quads[self.down].render()                      # q0 = quarter-res scene
        # blurred scene for DOF: q0 -> q1 -> q0b(q2)
        for src, dst, d in ((0, 1, (1, 0)), (1, 2, (0, 1))):
            self.q_fbo[dst].use()
            self.q[src].use(0)
            self.blur["src"].value = 0
            self.blur["dir"].value = d
            self.quads[self.blur].render()
        # bloom: bright(q0) -> q3 -> blur -> q1 -> blur -> q3
        self.q_fbo[3].use()
        self.q[0].use(0)
        self.bright["src"].value = 0
        self.bright["threshold"].value = 2.2
        self.quads[self.bright].render()
        for src, dst, d in ((3, 1, (1, 0)), (1, 3, (0, 1)), (3, 1, (2, 0)), (1, 3, (0, 2))):
            self.q_fbo[dst].use()
            self.q[src].use(0)
            self.blur["dir"].value = d
            self.quads[self.blur].render()
        # compose
        self.out_fbo.use()
        self.hdr.use(0)
        self.q[2].use(1)
        self.q[3].use(2)
        cp = self.compose
        cp["scene"].value = 0
        cp["blurred"].value = 1
        cp["bloom"].value = 2
        cp["exposure"].value = env.exposure
        cp["bloom_k"].value = env.bloom
        cp["focus"].value = float(focus if focus is not None else np.linalg.norm(np.array(target) - np.array(eye)))
        cp["dof"].value = float(dof)
        cp["time"].value = t
        cp["saturation"].value = env.saturation
        cp["lift"].value = env.lift
        cp["gain"].value = env.gain
        cp["vignette"].value = 0.55
        self.quads[cp].render()
        data = self.out_fbo.read(components=4, alignment=1)
        return np.frombuffer(data, dtype=np.uint8).reshape(self.h, self.w, 4)[::-1]


_R: Optional[Renderer] = None
_PID = None


def renderer(width=1920, height=1080) -> Renderer:
    global _R, _PID
    if _R is None or _PID != os.getpid():
        _R = Renderer(width, height, samples=int(os.environ.get("EVERYDAY_MSAA", "4")))
        _PID = os.getpid()
    return _R


from .engine3d import blit  # noqa: E402,F401  (same compositing into cairo)

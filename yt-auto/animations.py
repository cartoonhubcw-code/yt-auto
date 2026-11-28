"""Animated explainer visuals, drawn in code. 100% free: only Pillow + FFmpeg.

Look: bright grid background and chunky bevelled 3D-style tiles (like the reference Short).
Gemini picks one template per scene (see TEMPLATES) and fills in a few short labels.
"""
import math
import os
import subprocess
import zlib
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

S = 2  # supersampling factor (draw at 2x, shrink = smooth edges)

THEMES = [
    dict(top=(98, 170, 242), bot=(44, 106, 206),
         accents=[(60, 42, 38), (236, 168, 48), (30, 40, 80), (240, 244, 252)]),
    dict(top=(124, 84, 214), bot=(48, 28, 118),
         accents=[(250, 200, 60), (40, 200, 200), (250, 110, 150), (240, 240, 255)]),
    dict(top=(40, 190, 180), bot=(10, 90, 120),
         accents=[(255, 120, 70), (250, 230, 120), (25, 45, 80), (240, 250, 250)]),
    dict(top=(255, 150, 90), bot=(190, 60, 110),
         accents=[(40, 35, 80), (255, 230, 140), (90, 200, 200), (255, 255, 255)]),
]

_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_DEVA = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Bold.ttf",
]


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(p, a, b):
    return clamp((p - a) / (b - a)) if b > a else float(p >= a)


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_io(t):
    return 3 * t * t - 2 * t * t * t


def ease_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2 if 0 < t < 1 else clamp(t)


def lerp(a, b, t):
    return a + (b - a) * t


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def ink_for(c):
    return (25, 30, 55) if lum(c) > 150 else (255, 255, 255)


@lru_cache(maxsize=None)
def _font(path, size):
    return ImageFont.truetype(path, size)


def font(size, text=""):
    paths = _FONTS
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        paths = _DEVA + _FONTS
    for p in paths:
        if os.path.exists(p):
            return _font(p, max(8, int(size)))
    return ImageFont.load_default()


# ---------------------------------------------------------------- canvas
class Ctx:
    """Drawing surface. All coordinates are in normal (1x) pixels; scaling is handled here."""

    def __init__(self, W, H, theme, bg):
        self.W, self.H, self.th = W, H, theme
        self.u = min(W, H)
        self.portrait = H > W
        self.img = bg
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def A(self, i):
        return self.th["accents"][i % len(self.th["accents"])]

    def rect(self, x0, y0, x1, y1, fill):
        self.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill)

    def rrect(self, x0, y0, x1, y1, r, fill, outline=None, width=1):
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=r * S, fill=fill,
                                 outline=outline, width=int(width * S))

    def circle(self, x, y, r, fill=None, outline=None, width=1):
        self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill,
                       outline=outline, width=int(width * S))

    def line(self, pts, fill, width):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=max(1, int(width * S)),
                    joint="curve")

    def poly(self, pts, fill):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def glow(self, x, y, r, color):
        for k, a in ((2.4, 22), (1.7, 40), (1.2, 70)):
            self.circle(x, y, r * k, fill=color[:3] + (a,))
        self.circle(x, y, r, fill=color[:3] + (255,))

    def tile(self, cx, cy, w, h, color, scale=1.0, shadow=True):
        """Chunky bevelled block (the 'chocolate bar' look)."""
        w, h = w * scale, h * scale
        if w < 2 or h < 2:
            return
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        b = min(w, h) * 0.15
        if shadow:
            o = self.u * 0.012
            self.rect(x0 + o, y0 + o, x1 + o * 1.6, y1 + o * 1.6, (0, 0, 20, 60))
        self.rect(x0, y0, x1, y1, shade(color, 0.9))
        self.poly([(x0, y0), (x1, y0), (x1 - b, y0 + b), (x0 + b, y0 + b)], shade(color, 1.28))
        self.poly([(x0, y0), (x0 + b, y0 + b), (x0 + b, y1 - b), (x0, y1)], shade(color, 1.1))
        self.poly([(x1, y0), (x1, y1), (x1 - b, y1 - b), (x1 - b, y0 + b)], shade(color, 0.78))
        self.poly([(x0, y1), (x0 + b, y1 - b), (x1 - b, y1 - b), (x1, y1)], shade(color, 0.62))
        self.rect(x0 + b, y0 + b, x1 - b, y1 - b, color)

    def text(self, x, y, txt, size, fill=(255, 255, 255), maxw=None, maxlines=2, stroke=True):
        txt = str(txt)
        sz = size * S
        words = txt.split()
        while True:
            f = font(sz, txt)
            lines, cur = [], ""
            for w in words:
                trial = (cur + " " + w).strip()
                if not cur or self.d.textlength(trial, font=f) <= (maxw or 1e9) * S:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            widest = max(self.d.textlength(l, font=f) for l in lines)
            if (len(lines) <= maxlines and (not maxw or widest <= maxw * S)) or sz < 12 * S:
                break
            sz *= 0.92
        sw = max(1, int(sz * 0.07)) if stroke else 0
        sf = (0, 0, 30, 200) if lum(fill) > 140 else (255, 255, 255, 200)
        self.d.multiline_text((x * S, y * S), "\n".join(lines), font=f, fill=fill, anchor="mm",
                              align="center", spacing=sz * 0.18, stroke_width=sw, stroke_fill=sf)

    def result(self):
        return self.img.reduce(S).convert("RGB")


def make_bg(W, H, theme):
    """Gradient + grid, bigger than the frame by one cell so it can drift."""
    cell = int(min(W, H) / 12) * S
    BW, BH = W * S + cell, H * S + cell
    g = Image.linear_gradient("L").resize((BW, BH))
    top = Image.new("RGB", (BW, BH), theme["top"])
    bot = Image.new("RGB", (BW, BH), theme["bot"])
    img = Image.composite(bot, top, g)
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(0, BW, cell):
        d.line([(x, 0), (x, BH)], fill=(255, 255, 255, 34), width=S)
    for y in range(0, BH, cell):
        d.line([(0, y), (BW, y)], fill=(255, 255, 255, 34), width=S)
    return img, cell


# ---------------------------------------------------------------- templates
# Every template: fn(ctx, spec, p)  with p = progress 0..1 through the scene.
def t_blocks(c, sp, p):
    """A bar of tiles is cut with a knife, the halves slide and re-join shifted (the reference trick)."""
    W, H, u = c.W, c.H, c.u
    cols, rows = (4, 5) if c.portrait else (6, 4)
    cx, cy = W / 2, H * 0.43
    tw = min(W * 0.84 / (cols + 1), H * 0.50 / rows)
    cut = rows // 2
    gx0, gx1 = cx - cols * tw / 2, cx + cols * tw / 2
    ycut = cy - rows * tw / 2 + cut * tw
    kx = lerp(gx0 - tw, gx1 + tw * 1.4, ease_io(prog(p, 0.20, 0.42)))
    s1 = ease_io(prog(p, 0.44, 0.58))
    s2 = ease_io(prog(p, 0.66, 0.84))
    dxA = -0.9 * tw * s1 + 0.4 * tw * s2
    dy = 0.35 * tw * s1 * (1 - s2)
    order = [(r, k) for r in range(rows) for k in range(cols)]
    order.sort(key=lambda rk: -rk[0] if rk[0] >= cut else rk[0])
    for r, k in order:
        bx = gx0 + (k + 0.5) * tw
        by = cy - rows * tw / 2 + (r + 0.5) * tw
        a = 0.02 + (r + k) * 0.012
        pop = ease_back(prog(p, a, a + 0.12))
        top = r < cut
        swept = bx < kx and p > 0.2
        col = c.A(1) if (not top and swept) else c.A(0)
        x = bx + (dxA if top else -dxA)
        y = by + (-dy if top else dy)
        c.tile(x, y, tw * 0.96, tw * 0.96, col, scale=pop)
    if 0.2 < p < 0.46:
        L, bh = u * 0.55, u * 0.06
        c.poly([(kx + 4, ycut + 10), (kx - L * 0.9, ycut - bh + 14), (kx - L, ycut - bh + 14),
                (kx - L, ycut + 14)], (0, 0, 20, 60))
        c.poly([(kx, ycut), (kx - L * 0.9, ycut - bh), (kx - L, ycut - bh), (kx - L, ycut)],
               (214, 220, 230, 255))
        c.poly([(kx, ycut), (kx - L * 0.9, ycut - bh * 0.35), (kx - L, ycut - bh * 0.35),
                (kx - L, ycut)], (160, 168, 184, 255))
        c.rrect(kx - L - u * 0.22, ycut - bh * 0.9, kx - L, ycut + bh * 0.1, u * 0.015,
                (45, 48, 60, 255))
    if sp.get("text"):
        c.text(W / 2, H * 0.80, sp["text"], u * 0.055, maxw=W * 0.86)


def t_flow(c, sp, p):
    """Labelled steps joined by arrows; a glowing packet travels through them."""
    W, H, u = c.W, c.H, c.u
    steps = sp["steps"][:5]
    n = len(steps)
    if c.portrait:
        pts = [(W / 2, lerp(H * 0.27, H * 0.73, i / max(n - 1, 1))) for i in range(n)]
        nw, nh = W * 0.62, min(H * 0.105, (H * 0.46) / n)
    else:
        pts = [(lerp(W * 0.15, W * 0.85, i / max(n - 1, 1)), H * 0.5) for i in range(n)]
        nw, nh = min(W * 0.72 / n, W * 0.2), H * 0.26
    s = prog(p, 0.10, 0.95) * (n - 1)
    for i in range(n - 1):
        g = ease_out(prog(p, 0.10 + i * 0.85 / n, 0.10 + (i + 0.8) * 0.85 / n))
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        if c.portrait:
            a, b = (x0, y0 + nh / 2), (x1, y1 - nh / 2)
        else:
            a, b = (x0 + nw / 2, y0), (x1 - nw / 2, y1)
        e = (lerp(a[0], b[0], g), lerp(a[1], b[1], g))
        c.line([a, e], (255, 255, 255, 235), u * 0.012)
        if g > 0.97:
            ax, ay = (0, 1) if c.portrait else (1, 0)
            q = u * 0.03
            c.poly([(b[0], b[1]), (b[0] - ax * q + ay * q * 0.8, b[1] - ay * q + ax * q * 0.8),
                    (b[0] - ax * q - ay * q * 0.8, b[1] - ay * q - ax * q * 0.8)], (255, 255, 255, 235))
    for i, (x, y) in enumerate(pts):
        appear = ease_back(prog(p, 0.04 + i * 0.85 / n - 0.06 * (i > 0), 0.04 + i * 0.85 / n + 0.1))
        pulse = max(0.0, 1 - abs(s - i)) if p > 0.1 else 0
        col = c.A(0) if i % 2 == 0 else c.A(1)
        c.tile(x, y, nw, nh, col, scale=appear * (1 + 0.07 * pulse))
        if appear > 0.6:
            c.text(x, y, steps[i], nh * (0.2 if not c.portrait else 0.32), fill=ink_for(col),
                   maxw=nw * 0.86, maxlines=3)
            r = u * 0.032
            bx, by = x - nw / 2, y - nh / 2
            c.circle(bx, by, r, fill=(255, 255, 255, 255), outline=(20, 30, 60, 255), width=u * 0.004)
            c.text(bx, by, str(i + 1), r * 1.3, fill=(20, 30, 60), stroke=False)
    if p > 0.1 and s < n - 1 + 0.01:
        i = min(int(s), n - 2)
        f = s - i
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        c.glow(lerp(x0, x1, f), lerp(y0, y1, f), u * 0.022, (255, 235, 120))


def t_bars(c, sp, p):
    """Bars that grow with counting numbers (comparisons)."""
    W, H, u = c.W, c.H, c.u
    items = sp["items"][:5]
    n = len(items)
    vmax = max(i["value"] for i in items) or 1
    base_y = H * 0.66
    maxh = H * (0.40 if c.portrait else 0.42)
    areaw = W * 0.8
    bw = areaw / (n * 1.5)
    unit = sp.get("unit", "")
    c.line([(W * 0.08, base_y), (W * 0.92, base_y)], (255, 255, 255, 230), u * 0.008)
    for i, it in enumerate(items):
        x = W * 0.1 + areaw * (i + 0.5) / n
        g = ease_out(prog(p, 0.08 + i * 0.09, 0.55 + i * 0.09))
        h = maxh * it["value"] / vmax * g
        c.tile(x, base_y - h / 2, bw, h, c.A(i), shadow=h > 4)
        if g > 0.02:
            v = it["value"] * g
            txt = f"{v:,.0f}" if abs(it["value"]) >= 100 or float(it["value"]).is_integer() else f"{v:.1f}"
            c.text(x, base_y - h - u * 0.045, txt + unit, u * 0.05, maxw=bw * 1.6, maxlines=1)
        c.text(x, base_y + u * 0.07, it["label"], u * 0.045, maxw=areaw / n * 0.95)
    if sp.get("text"):
        c.text(W / 2, H * 0.80, sp["text"], u * 0.05, maxw=W * 0.86)


def t_orbit(c, sp, p):
    """Things orbiting a centre (space, atoms, satellites...)."""
    W, H, u = c.W, c.H, c.u
    cx, cy = W / 2, H * 0.50
    items = sp["items"][:5]
    n = len(items)
    rx0 = (W * 0.40) if c.portrait else (W * 0.40)
    ry_k = 0.55 if c.portrait else 0.36
    bodies = []
    for i, name in enumerate(items):
        rx = rx0 * (0.55 + 0.45 * (i + 1) / n)
        ry = rx * ry_k
        c.d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S],
                    outline=(255, 255, 255, 110), width=S * 2)
        sp_ = 1.0 + 0.35 * (n - i)
        ang = 2 * math.pi * (p * sp_ * 0.9) + i * 2.1
        bodies.append((math.sin(ang), i, name, rx, ry, ang))
    appear = ease_back(prog(p, 0.0, 0.18))

    def draw_body(b):
        depth, i, name, rx, ry, ang = b
        d01 = (depth + 1) / 2
        r = u * (0.03 + 0.022 * d01)
        for k in range(1, 7):
            a2 = ang - k * 0.07 * (1.0 + 0.0)
            c.circle(cx + rx * math.cos(a2), cy + ry * math.sin(a2), r * (1 - k * 0.1),
                     fill=c.A(i + 1)[:3] + (int(90 - k * 12),))
        x, y = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        c.circle(x + r * 0.2, y + r * 0.25, r, fill=(0, 0, 20, 60))
        c.circle(x, y, r, fill=shade(c.A(i + 1), 0.9) + (255,))
        c.circle(x - r * 0.3, y - r * 0.3, r * 0.45, fill=(255, 255, 255, 120))
        c.text(x, y + r + u * 0.032, name, u * 0.036, maxw=u * 0.28, maxlines=1)

    for b in sorted(bodies):
        if b[0] < 0:
            draw_body(b)
    R = u * 0.115 * appear
    c.circle(cx, cy, R * 1.0, fill=shade(c.A(1), 0.75) + (255,))
    c.circle(cx - R * 0.08, cy - R * 0.1, R * 0.82, fill=c.A(1) + (255,))
    c.circle(cx - R * 0.28, cy - R * 0.3, R * 0.38, fill=(255, 255, 255, 110))
    if appear > 0.7:
        c.text(cx, cy + R + u * 0.05, sp.get("center", ""), u * 0.05, maxw=W * 0.5, maxlines=1)
    for b in sorted(bodies):
        if b[0] >= 0:
            draw_body(b)


def t_wave(c, sp, p):
    """Moving waves (sound, light, signals, radio)."""
    W, H, u = c.W, c.H, c.u
    ys = [H * 0.38, H * 0.52, H * 0.66] if not c.portrait else [H * 0.34, H * 0.5, H * 0.66]
    ks = [2.0, 3.0, 4.5]
    front = ease_io(prog(p, 0.04, 0.45))
    x0, x1 = W * 0.08, W * 0.92
    ph = p * 14
    for i, (y0, k) in enumerate(zip(ys, ks)):
        amp = u * (0.075 - 0.012 * i)
        pts = []
        N = 120
        for j in range(N + 1):
            f = j / N
            if f > front:
                break
            pts.append((lerp(x0, x1, f), y0 + amp * math.sin(2 * math.pi * k * f - ph * (1 + i * 0.3))))
        c.line([(x0, y0), (x1, y0)], (255, 255, 255, 70), u * 0.004)
        if len(pts) > 1:
            c.line([(x + 0, y + u * 0.01) for x, y in pts], (0, 0, 30, 60), u * 0.02)
            c.line(pts, c.A(i) if i != 0 else c.A(1), u * 0.02)
            c.glow(pts[-1][0], pts[-1][1], u * 0.017, (255, 255, 255))
    if sp.get("text"):
        c.text(W / 2, H * 0.78, sp["text"], u * 0.055, maxw=W * 0.86)


def t_counter(c, sp, p):
    """Big number counting up inside a progress ring."""
    W, H, u = c.W, c.H, c.u
    cx, cy, R = W / 2, H * 0.42, u * 0.27
    e = ease_out(prog(p, 0.08, 0.7))
    val = sp["value"] * e
    box = [(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S]
    appear = ease_back(prog(p, 0.0, 0.15))
    c.circle(cx, cy, R * 1.06 * appear, fill=(0, 0, 30, 70))
    c.d.arc(box, 0, 360, fill=(255, 255, 255, 80), width=int(u * 0.045 * S))
    c.d.arc(box, -90, -90 + 360 * e, fill=c.A(1) + (255,), width=int(u * 0.045 * S))
    big = abs(sp["value"]) >= 1000 or float(sp["value"]).is_integer()
    txt = f"{val:,.0f}" if big else f"{val:.1f}"
    c.text(cx, cy - (u * 0.02 if sp.get("unit") else 0), txt, u * 0.14 * appear, maxw=R * 1.6, maxlines=1)
    if sp.get("unit"):
        c.text(cx, cy + u * 0.1, sp["unit"], u * 0.05, maxw=R * 1.5, maxlines=1)
    if sp.get("label"):
        c.text(W / 2, cy + R + u * 0.09, sp["label"], u * 0.055, maxw=W * 0.86)


def t_cycle(c, sp, p):
    """Steps arranged in a loop (water cycle, feedback loops, routines)."""
    W, H, u = c.W, c.H, c.u
    steps = sp["steps"][:6]
    n = len(steps)
    cx, cy = W / 2, H * 0.46
    R = W * 0.27 if c.portrait else u * 0.27
    nw = W * 0.30 if c.portrait else u * 0.27
    nh = nw * 0.46
    step = 360 / n
    gap = 17
    for i in range(n):
        g = prog(p, 0.1 + i * 0.1, 0.1 + i * 0.1 + 0.12)
        a0, a1 = -90 + i * step + gap, -90 + (i + 1) * step - gap
        if g > 0:
            c.d.arc([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], a0, lerp(a0, a1, g),
                    fill=(255, 255, 255, 235), width=int(u * 0.012 * S))
        if g >= 0.99:
            t = math.radians(a1)
            px, py = cx + R * math.cos(t), cy + R * math.sin(t)
            tx, ty = -math.sin(t), math.cos(t)
            nx, ny = math.cos(t), math.sin(t)
            q = u * 0.028
            c.poly([(px + tx * q, py + ty * q), (px - nx * q * 0.8, py - ny * q * 0.8),
                    (px + nx * q * 0.8, py + ny * q * 0.8)], (255, 255, 255, 240))
    active = (p * n * 1.5) % n
    for i in range(n):
        t = math.radians(-90 + i * step)
        x, y = cx + R * math.cos(t), cy + R * math.sin(t)
        ap = ease_back(prog(p, 0.05 + i * 0.1, 0.2 + i * 0.1))
        near = max(0.0, 1 - min(abs(active - i), n - abs(active - i)))
        col = c.A(i)
        c.tile(x, y, nw, nh, col, scale=ap * (1 + 0.1 * near))
        if ap > 0.6:
            c.text(x, y, steps[i], nh * 0.27, fill=ink_for(col), maxw=nw * 0.86, maxlines=2)
    if sp.get("text"):
        c.text(cx, cy, sp["text"], u * 0.045, maxw=R * 0.62, maxlines=3)


TEMPLATES = {"blocks": t_blocks, "flow": t_flow, "bars": t_bars, "orbit": t_orbit,
             "wave": t_wave, "counter": t_counter, "cycle": t_cycle}
TYPES_HELP = "blocks, flow, bars, orbit, wave, counter, cycle"


# ---------------------------------------------------------------- spec cleanup
def _strs(v, limit=22):
    return [str(x).strip()[:limit] for x in (v or []) if str(x).strip()]


def normalize(vis, scene):
    """Make whatever the LLM returned safe to draw (never raises)."""
    vis = vis if isinstance(vis, dict) else {}
    t = str(vis.get("type", "")).lower()
    if t not in TEMPLATES:
        t = "flow"
    sp = {"type": t, "text": str(vis.get("text") or "")[:60],
          "unit": str(vis.get("unit") or "")[:12], "label": str(vis.get("label") or "")[:60],
          "center": str(vis.get("center") or "")[:20]}
    fallback = _strs((scene.get("on_screen_text") or scene.get("visual_keyword") or "").split(), 14)
    if t in ("flow", "cycle"):
        steps = _strs(vis.get("steps") or vis.get("items"))
        if len(steps) < 3:
            steps = (steps + fallback + ["Start", "Process", "Result"])[:3]
        sp["steps"] = steps
    if t == "orbit":
        items = _strs(vis.get("items") or vis.get("steps"), 14)
        sp["items"] = items if items else ["A", "B", "C"]
        sp["center"] = sp["center"] or (fallback[0] if fallback else "")
    if t == "bars":
        items = []
        for it in vis.get("items") or []:
            try:
                items.append({"label": str(it["label"])[:16], "value": abs(float(it["value"]))})
            except Exception:  # noqa: BLE001
                continue
        if len(items) < 2:
            sp["type"] = "flow"
            sp["steps"] = (fallback + ["Start", "Process", "Result"])[:3]
        else:
            sp["items"] = items
    if t == "counter":
        try:
            sp["value"] = float(vis.get("value"))
        except Exception:  # noqa: BLE001
            sp["type"] = "flow"
            sp["steps"] = (fallback + ["Start", "Process", "Result"])[:3]
    return sp


def theme_for(title: str):
    return THEMES[zlib.crc32(title.encode("utf-8")) % len(THEMES)]


# ---------------------------------------------------------------- renderer
def headline(c, text, t):
    if not text:
        return
    a = ease_back(prog(t, 0.1, 0.65))
    if a <= 0.02:
        return
    size = c.u * 0.058 * a
    f = font(size * S, text)
    tw = min(c.d.textlength(text, font=f) / S, c.W * 0.9)
    pad = c.u * 0.035
    y = c.H * (0.13 if c.portrait else 0.11)
    c.rrect(c.W / 2 - tw / 2 - pad, y - size * 0.95, c.W / 2 + tw / 2 + pad, y + size * 0.95,
            size * 0.5, (255, 255, 255, 235))
    c.text(c.W / 2, y, text, size, fill=(22, 28, 60), maxw=c.W * 0.9, maxlines=1, stroke=False)


def render_scene(vis, scene, duration, audio_path, out_path, W, H, fps, pad, theme, ffmpeg="ffmpeg"):
    """Draw frames and pipe them straight into FFmpeg together with the narration audio."""
    sp = normalize(vis, scene)
    fn = TEMPLATES[sp["type"]]
    bg, cell = make_bg(W, H, theme)
    n = int(round(duration * fps))
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", str(audio_path),
           "-map", "0:v:0", "-map", "1:a:0", "-af", f"apad=pad_dur={pad}",
           "-vf", "fade=t=in:st=0:d=0.2,format=yuv420p", "-t", f"{duration:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in range(n):
            t = f / fps
            p = f / max(n - 1, 1)
            ox = int((t * cell * 0.25) % cell)
            oy = int((t * cell * 0.12) % cell)
            frame = bg.crop((ox, oy, ox + W * S, oy + H * S))
            c = Ctx(W, H, theme, frame)
            fn(c, sp, p)
            headline(c, scene.get("on_screen_text", ""), t)
            proc.stdin.write(c.result().tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + err[-800:])
    except BrokenPipeError:
        raise RuntimeError("ffmpeg closed early: " + proc.stderr.read().decode(errors="replace")[-800:])
    return out_path

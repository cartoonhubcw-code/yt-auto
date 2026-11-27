"""Free motion-graphics engine: draws animated explainer scenes frame by frame (Pillow)
and pipes them into FFmpeg. No stock footage, no extra keys.

Scene types: title, bullets, flow, stat.
"""
import hashlib
import math
import os
import re
import subprocess
import tempfile
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import config

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
WHITE = (255, 255, 255)

THEMES = [
    dict(top=(14, 22, 56), bot=(44, 16, 84), accent=(255, 196, 61), accent2=(72, 202, 228)),
    dict(top=(8, 48, 66), bot=(10, 18, 44), accent=(255, 127, 80), accent2=(120, 230, 170)),
    dict(top=(40, 14, 40), bot=(14, 20, 58), accent=(255, 99, 146), accent2=(130, 200, 255)),
    dict(top=(10, 52, 44), bot=(8, 24, 52), accent=(250, 204, 21), accent2=(94, 234, 212)),
]
BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf"]
REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
       "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/Library/Fonts/Arial.ttf",
       "C:/Windows/Fonts/arial.ttf"]


def theme_for(title: str) -> int:
    return int(hashlib.md5(title.encode()).hexdigest(), 16) % len(THEMES)


# ---------------- helpers ----------------
def clamp(x):
    return max(0.0, min(1.0, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


@lru_cache(maxsize=64)
def _font(bold, size):
    for p in (BOLD if bold else REG):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


@lru_cache(maxsize=1024)
def text_layer(text, size, color, max_w, bold=True, align="center"):
    f = _font(bold, size)
    lines = _wrap(text, f, max_w)
    lh = int(size * 1.25)
    w = int(max(f.getlength(l) for l in lines)) + 16
    h = lh * len(lines) + 16
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = (w - f.getlength(l)) / 2 if align == "center" else 8
        y = 8 + i * lh
        d.text((x + 3, y + 3), l, font=f, fill=(0, 0, 0, 110))
        d.text((x, y), l, font=f, fill=color + (255,))
    return img


def blit(canvas, layer, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    w, h = layer.size
    if abs(scale - 1.0) > 0.001:
        layer = layer.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        w, h = layer.size
    if alpha < 0.99:
        r, g, b, a = layer.split()
        a = a.point([int(i * alpha) for i in range(256)])
        layer = Image.merge("RGBA", (r, g, b, a))
    canvas.paste(layer, (int(cx - w / 2), int(cy - h / 2)), layer)


@lru_cache(maxsize=8)
def _gradient(ti):
    th = THEMES[ti]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(th["top"][i] + (th["bot"][i] - th["top"][i]) * t) for i in range(3)))
    return img


def background(ti, gt):
    th = THEMES[ti]
    img = _gradient(ti).copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for k in range(7):
        r = 70 + (k * 37) % 110
        cx = W * ((k * 0.173 + 0.08) % 1) + 70 * math.sin(gt * 0.35 + k * 1.7)
        cy = H * ((k * 0.291 + 0.15) % 1) + 55 * math.cos(gt * 0.28 + k * 2.1)
        col = th["accent"] if k % 2 == 0 else th["accent2"]
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (24,))
    img.paste(ov, (0, 0), ov)
    return img


# ---------------- cached card layers ----------------
@lru_cache(maxsize=256)
def bullet_card(text, num, ti):
    th = THEMES[ti]
    w, h = 1000, 104
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 22, fill=(255, 255, 255, 34), outline=th["accent"] + (150,), width=2)
    d.ellipse([22, 22, 82, 82], fill=th["accent"] + (255,))
    n = text_layer(str(num), 38, (20, 20, 40), 80)
    img.paste(n, (52 - n.width // 2, 52 - n.height // 2), n)
    t = text_layer(text, 34, WHITE, 830, True, "left")
    img.paste(t, (110, (h - t.height) // 2), t)
    return img


@lru_cache(maxsize=256)
def flow_box(text, num, bw, bh, ti):
    th = THEMES[ti]
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], 24, fill=(255, 255, 255, 34), outline=th["accent2"] + (200,), width=3)
    d.ellipse([bw // 2 - 20, 14, bw // 2 + 20, 54], fill=th["accent2"] + (255,))
    n = text_layer(str(num), 26, (10, 20, 40), 60)
    img.paste(n, (bw // 2 - n.width // 2, 34 - n.height // 2), n)
    t = text_layer(text, 30, WHITE, bw - 30)
    img.paste(t, ((bw - t.width) // 2, 62 + (bh - 62 - t.height) // 2), t)
    return img


# ---------------- scene types ----------------
def _heading(img, v, t, y=95):
    if not v["heading"]:
        return
    p = ease_out(prog(t, 0.0, 0.6))
    layer = text_layer(v["heading"], 58, WHITE, 1120)
    blit(img, layer, W / 2, y - (1 - p) * 30, alpha=p)


def f_title(img, v, ti, t, T):
    th = THEMES[ti]
    p = ease_out(prog(t, 0.1, 0.8))
    layer = text_layer(v["heading"], 86, WHITE, 1050)
    cy = H / 2 - 30 + (1 - p) * 50
    blit(img, layer, W / 2, cy, alpha=p, scale=1 + 0.03 * (t / max(T, 0.1)))
    bw = int(300 * ease_out(prog(t, 0.6, 0.7)))
    y = H / 2 - 30 + layer.height / 2 + 28
    ImageDraw.Draw(img).rounded_rectangle([W / 2 - bw / 2, y, W / 2 + bw / 2, y + 8], 4, fill=th["accent"])
    if v["items"]:
        sub = text_layer(v["items"][0], 40, th["accent2"], 1000, False)
        blit(img, sub, W / 2, y + 62, alpha=ease_out(prog(t, 1.1, 0.6)))


def f_bullets(img, v, ti, t, T):
    _heading(img, v, t)
    items = v["items"]
    n = len(items)
    start = 0.7
    step = max(0.5, (T * 0.7 - start) / n)
    gap = 112 if n <= 4 else 100
    top = 210
    for k, txt in enumerate(items):
        p = prog(t, start + k * step, 0.5)
        if p <= 0:
            continue
        card = bullet_card(txt, k + 1, ti)
        blit(img, card, W / 2 - (1 - ease_out(p)) * 140, top + k * gap + card.height / 2,
             alpha=ease_out(p), scale=0.88 + 0.12 * ease_back(p))


def f_flow(img, v, ti, t, T):
    th = THEMES[ti]
    _heading(img, v, t)
    items = v["items"]
    n = len(items)
    gapx = 100
    bw = min(270, int((W - 140 - (n - 1) * gapx) / n))
    bh = 170
    total = n * bw + (n - 1) * gapx
    x0 = (W - total) / 2
    cy = H / 2 + 30
    step = max(0.8, (T * 0.7 - 0.7) / n)
    d = ImageDraw.Draw(img)
    for k, txt in enumerate(items):
        s = 0.7 + k * step
        if k > 0:
            ap = prog(t, s - 0.45, 0.4)
            if ap > 0:
                xa = x0 + (k - 1) * (bw + gapx) + bw + 12
                xb = x0 + k * (bw + gapx) - 12
                xe = xa + (xb - xa) * ease_out(ap)
                d.line([xa, cy, xe, cy], fill=th["accent"], width=6)
                if ap > 0.95:
                    d.polygon([(xb + 4, cy), (xb - 16, cy - 13), (xb - 16, cy + 13)], fill=th["accent"])
        p = prog(t, s, 0.5)
        if p > 0:
            blit(img, flow_box(txt, k + 1, bw, bh, ti), x0 + k * (bw + gapx) + bw / 2, cy,
                 alpha=ease_out(p), scale=0.7 + 0.3 * ease_back(p))
    last = 0.7 + (n - 1) * step + 0.7
    if t > last and n > 1:
        ty = cy + bh / 2 + 45
        xs, xe_ = x0 + bw / 2, x0 + (n - 1) * (bw + gapx) + bw / 2
        d.line([xs, ty, xe_, ty], fill=(255, 255, 255, 60), width=3)
        u = ((t - last) % 2.2) / 2.2
        px = xs + (xe_ - xs) * u
        d.ellipse([px - 11, ty - 11, px + 11, ty + 11], fill=th["accent"])


_NUM = re.compile(r"^(\D*?)(\d[\d,]*\.?\d*)(.*)$")


def _stat_text(val, t):
    m = _NUM.match(val)
    if not m:
        return val
    pre, num, suf = m.groups()
    target = float(num.replace(",", ""))
    dec = len(num.split(".")[1]) if "." in num else 0
    if "," not in num and dec == 0 and 1800 <= target <= 2100:  # looks like a year: don't count up
        return val
    cur = target * ease_out(prog(t, 0.3, 1.6))
    s = f"{cur:,.{dec}f}" if "," in num else f"{cur:.{dec}f}"
    return pre + s + suf


def f_stat(img, v, ti, t, T):
    th = THEMES[ti]
    p = prog(t, 0.1, 0.6)
    big = text_layer(_stat_text(v["value"], t), 170, th["accent"], 1150)
    blit(img, big, W / 2, H / 2 - 40, alpha=ease_out(p), scale=0.8 + 0.2 * ease_back(p))
    if v["heading"]:
        lab = text_layer(v["heading"], 50, WHITE, 1000)
        blit(img, lab, W / 2, H / 2 + 100 + (1 - ease_out(prog(t, 0.6, 0.6))) * 30,
             alpha=ease_out(prog(t, 0.6, 0.6)))
    if v["items"]:
        sub = text_layer(v["items"][0], 34, th["accent2"], 1000, False)
        blit(img, sub, W / 2, H / 2 + 185, alpha=ease_out(prog(t, 1.2, 0.6)))


RENDERERS = {"title": f_title, "bullets": f_bullets, "flow": f_flow, "stat": f_stat}


def norm_visual(scene):
    v = scene.get("visual") or {}
    typ = str(v.get("type", "title")).lower()
    heading = (v.get("heading") or scene.get("on_screen_text") or scene.get("visual_keyword") or "").strip()
    items = [str(x).strip() for x in (v.get("items") or []) if str(x).strip()][:5]
    value = str(v.get("value", "")).strip()
    if typ not in RENDERERS:
        typ = "title"
    if typ == "flow":
        items = items[:4]
        if len(items) < 2:
            typ = "bullets" if items else "title"
    if typ == "bullets" and not items:
        typ = "title"
    if typ == "stat" and not value:
        typ = "title"
    if not heading and typ in ("title", "stat"):
        heading = " ".join(scene["narration"].split()[:6])
    return {"type": typ, "heading": heading, "items": items, "value": value}


# ---------------- render a scene to an mp4 segment ----------------
def render_segment(scene, audio, seg_dur, pad, out_path, ti=0, t_offset=0.0):
    v = norm_visual(scene)
    fn = RENDERERS[v["type"]]
    nframes = int(round(seg_dur * FPS))
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0", "-af", f"apad=pad_dur={pad}", "-t", f"{seg_dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out_path)],
        stdin=subprocess.PIPE, stderr=err)
    try:
        for f in range(nframes):
            t = f / FPS
            img = background(ti, t_offset + t)
            fn(img, v, ti, t, seg_dur)
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    proc.wait()
    if proc.returncode != 0:
        err.seek(0)
        raise RuntimeError("ffmpeg failed while rendering animation:\n" + err.read().decode(errors="ignore")[-1500:])
    return out_path

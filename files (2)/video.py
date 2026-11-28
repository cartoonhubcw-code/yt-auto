"""Visuals + FFmpeg assembly: Pexels stock clips (or generated slides), voiceover, captions, thumbnail."""
import os
import random
import subprocess
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

import animations
import blender_render
import config

FPS = config.FPS
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
PALETTES = [((20, 30, 70), (60, 20, 90)), ((10, 60, 80), (10, 20, 50)),
            ((70, 20, 40), (20, 20, 60)), ((15, 70, 50), (10, 30, 60))]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr[-1500:]}")
    return r.stdout


def duration(path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


# ---------------- visuals ----------------
def make_slide(text: str, idx: int, out_path: str, fmt: dict):
    W, H = fmt["width"], fmt["height"]
    top, bot = PALETTES[idx % len(PALETTES)]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    wrapped = "\n".join(textwrap.wrap(text, fmt["slide_wrap"]))
    d.multiline_text((W / 2, H / 2), wrapped, font=font(fmt["slide_font"]), fill="white",
                     anchor="mm", align="center", spacing=14)
    img.save(out_path)


def fetch_pexels_clip(keyword: str, out_path: str, used_ids: set, fmt: dict):
    """Return (path, credit) or (None, None). Needs PEXELS_API_KEY (free)."""
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None, None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": keyword, "orientation": fmt["orientation"], "size": "medium", "per_page": 10},
            timeout=30,
        )
        r.raise_for_status()
        videos = [v for v in r.json().get("videos", []) if v["id"] not in used_ids]
        if not videos:
            return None, None
        v = random.choice(videos[:6])
        files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
        if not files:
            return None, None
        f = min(files, key=lambda x: abs(x["width"] - fmt["width"]))
        with requests.get(f["link"], stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in dl.iter_content(1 << 20):
                    fh.write(chunk)
        used_ids.add(v["id"])
        return out_path, v.get("user", {}).get("name")
    except Exception as e:  # noqa: BLE001
        print(f"[pexels] '{keyword}' failed: {e}")
        return None, None


# ---------------- assembly ----------------
_STATE = {"n3d": 0}


def build_scene(i, scene, audio, work: Path, used_ids, fmt: dict, script_title=""):
    W, H, PAD = fmt["width"], fmt["height"], fmt["pad"]
    audio_dur = duration(audio)
    seg_dur = audio_dur + PAD
    seg = work / f"seg{i}.mp4"

    # Free animated visual (drawn in code). Falls back to stock footage / slide if anything goes wrong.
    vis = scene.get("visual")
    if isinstance(vis, dict) and str(vis.get("type")) in blender_render.TEMPLATES:
        # Real 3D (Blender) only where Gemini asked for it, max N per video, otherwise 2D version
        if blender_render.available() and _STATE["n3d"] < fmt["max_3d"]:
            _STATE["n3d"] += 1
            try:
                blender_render.render_scene(vis, scene, seg_dur, audio, seg, W, H, FPS, PAD,
                                            animations.theme_for(script_title), work, i)
                return seg, audio_dur, None
            except Exception as e:  # noqa: BLE001
                print(f"[blender] scene {i} failed, using 2D fallback: {e}")
        vis = dict(vis, type=blender_render.FALLBACK_2D[str(vis["type"])])
    # Vertical (Short): the subtitles live in the lower area, so drop the animation's own bottom
    # caption (blocks / bars / wave) - it would overlap, and it just repeats the narration.
    if H > W and isinstance(vis, dict) and vis.get("type") in ("blocks", "bars", "wave"):
        vis = dict(vis, text="")
    if config.ANIMATED_VISUALS and not (isinstance(vis, dict) and vis.get("type") == "stock"):
        try:
            animations.render_scene(vis, scene, seg_dur, audio, seg, W, H, FPS, PAD,
                                    animations.theme_for(script_title))
            return seg, audio_dur, None
        except Exception as e:  # noqa: BLE001
            print(f"[animation] scene {i} failed, using fallback: {e}")
    clip, credit = fetch_pexels_clip(scene["visual_keyword"], str(work / f"clip{i}.mp4"), used_ids, fmt)

    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},format=yuv420p")
    if clip:
        vin = ["-stream_loop", "-1", "-i", clip]
    else:
        slide = str(work / f"slide{i}.png")
        make_slide(scene.get("on_screen_text") or scene["visual_keyword"], i, slide, fmt)
        vin = ["-loop", "1", "-framerate", str(FPS), "-i", slide]

    run(["ffmpeg", "-y", "-loglevel", "error", *vin, "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-af", f"apad=pad_dur={PAD}",
         "-t", f"{seg_dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", str(seg)])
    return seg, audio_dur, credit


def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def build_srt(timings, path, words_per_line=7):
    lines, n = [], 1
    for start, dur, text in timings:
        words = text.split()
        chunks = [" ".join(words[k:k + words_per_line]) for k in range(0, len(words), words_per_line)]
        total = max(len(words), 1)
        t = start
        for c in chunks:
            span = dur * len(c.split()) / total
            lines.append(f"{n}\n{_ts(t)} --> {_ts(t + span)}\n{c}\n")
            t += span
            n += 1
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def assemble(script, audios, work: Path, fmt: dict):
    """Returns (final_video_path, credits list)."""
    _STATE["n3d"] = 0
    used_ids, segs, timings, credits, cursor = set(), [], [], [], 0.0
    for i, (scene, audio) in enumerate(zip(script["scenes"], audios)):
        seg, adur, credit = build_scene(i, scene, audio, work, used_ids, fmt, script["title"])
        segs.append(seg)
        timings.append((cursor, adur, scene["narration"]))
        cursor += adur + fmt["pad"]
        if credit:
            credits.append(credit)

    (work / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", "nocap.mp4"], cwd=work)

    if config.CAPTIONS:
        build_srt(timings, work / "captions.srt", fmt["words_per_caption"])
        style = fmt["caption_style"]
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", "nocap.mp4",
             "-vf", f"subtitles=captions.srt:force_style='{style}'",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy",
             "-movflags", "+faststart", "final.mp4"], cwd=work)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", "nocap.mp4", "-c", "copy",
             "-movflags", "+faststart", "final.mp4"], cwd=work)
    return work / "final.mp4", sorted(set(credits))


def make_thumbnail(video: Path, title: str, out_path: Path, fmt: dict):
    W, H = fmt["width"], fmt["height"]
    frame = out_path.with_suffix(".frame.jpg")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(video),
         "-frames:v", "1", str(frame)])
    img = Image.open(frame).convert("RGB").resize((W, H))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H // 3, H):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, int(210 * (y - H // 3) / (H - H // 3))))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    d = ImageDraw.Draw(img)
    text = "\n".join(textwrap.wrap(title.upper(), 22)[:3])
    d.multiline_text((50, H - 40), text, font=font(76), fill="white", anchor="ld",
                     stroke_width=5, stroke_fill="black", spacing=10)
    img.save(out_path, quality=88)
    return out_path

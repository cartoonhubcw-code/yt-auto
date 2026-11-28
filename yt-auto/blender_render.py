"""Optional real-3D scenes rendered with Blender (free) in the GitHub Actions runner.

Used only when Gemini asks for a "3d_*" visual AND Blender is installed. Any problem (Blender missing,
crash, timeout) raises, and video.py falls back to the 2D animation for that scene.
"""
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image

import animations
import config

HERE = Path(__file__).parent
RENDER_FPS = 24
TEMPLATES = {"3d_cut": "cut", "3d_stack": "stack", "3d_gears": "gears"}
FALLBACK_2D = {"3d_cut": "blocks", "3d_stack": "flow", "3d_gears": "cycle"}


def available() -> bool:
    return bool(config.BLENDER_3D) and shutil.which(config.BLENDER_BIN) is not None


def render_scene(vis, scene, duration, audio, out_path, W, H, fps, pad, theme, work, idx):
    name = TEMPLATES[str(vis.get("type"))]
    work = Path(work)
    frames_dir = work / f"blender{idx}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    n = int(math.ceil(duration * RENDER_FPS))
    k = min(1.0, 960 / max(W, H))
    rx, ry = int(W * k) // 2 * 2, int(H * k) // 2 * 2
    spec = {"template": name, "frames": n, "fps": RENDER_FPS, "res": [rx, ry],
            "portrait": H > W, "theme": theme, "out_dir": str(frames_dir),
            "samples": config.BLENDER_SAMPLES}
    spec_path = work / f"blender{idx}.json"
    spec_path.write_text(json.dumps(spec))
    cmd = [config.BLENDER_BIN, "-b", "--factory-startup", "-noaudio",
           "-P", str(HERE / "blender_scene.py"), "--", str(spec_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=config.BLENDER_TIMEOUT)
    got = len(list(frames_dir.glob("f_*.png")))
    if r.returncode != 0 or got < n:
        raise RuntimeError(f"blender rc={r.returncode} frames={got}/{n}\n"
                           f"{(r.stderr or r.stdout)[-1200:]}")

    # headline + optional caption as a fading overlay
    ov = Image.new("RGBA", (W * animations.S, H * animations.S), (0, 0, 0, 0))
    c = animations.Ctx(W, H, theme, ov)
    animations.headline(c, scene.get("on_screen_text", ""), 5.0)
    caption = str(vis.get("text") or "")[:60]
    if caption:
        c.text(W / 2, H * 0.80, caption, c.u * 0.055, maxw=W * 0.86)
    pill = work / f"overlay{idx}.png"
    ov.reduce(animations.S).save(pill)

    fc = (f"[0:v]scale={W}:{H}:flags=lanczos,fps={fps}[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.2:d=0.3:alpha=1[p];"
          f"[v][p]overlay=0:0:format=auto,fade=t=in:st=0:d=0.2,format=yuv420p[o]")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(RENDER_FPS),
         "-i", str(frames_dir / "f_%04d.png"), "-loop", "1", "-framerate", str(fps), "-i", str(pill),
         "-i", str(audio), "-filter_complex", fc, "-map", "[o]", "-map", "2:a:0",
         "-af", f"apad=pad_dur={pad}", "-t", f"{duration:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out_path)],
        check=True, capture_output=True, text=True)
    shutil.rmtree(frames_dir, ignore_errors=True)
    return out_path

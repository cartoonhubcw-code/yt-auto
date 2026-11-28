import asyncio
import subprocess
import time

import config


def synth(text: str, out_path: str, dry_run: bool = False, rate: str | None = None) -> str:
    if dry_run:  # silent placeholder audio, length based on word count
        secs = max(2.0, len(text.split()) / 2.6)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", f"{secs:.2f}", out_path],
            check=True,
        )
        return out_path

    import edge_tts

    async def _go():
        await edge_tts.Communicate(text, config.VOICE, rate=rate or config.VOICE_RATE).save(out_path)

    last = None
    for _ in range(4):
        try:
            asyncio.run(_go())
            return out_path
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4)
    raise RuntimeError(f"edge-tts failed: {last}")

"""Daily pipeline: topic -> script -> voice -> video (+ Short) -> scheduled YouTube upload.

Usage:
    python main.py              # full run
    python main.py --dry-run    # no API keys needed; builds a test video, skips upload
"""
import csv
import json
import shutil
import sys
import traceback
from pathlib import Path

import config
import llm
import notify
import script_gen
import tts
import video

ROOT = Path(__file__).parent
TOPICS = ROOT / "topics.csv"
HISTORY = ROOT / "history.json"
WORK = ROOT / "work"


def load_topics():
    with open(TOPICS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_topics(rows):
    with open(TOPICS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["topic", "used"])
        w.writeheader()
        w.writerows(rows)


def pick_topic(dry_run):
    rows = load_topics()
    for r in rows:
        if r["used"].strip() != "1":
            return r["topic"], r
    if dry_run:
        return "Sample topic", None
    past = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    d = llm.generate_json(
        f'Suggest ONE new YouTube explainer topic about {config.NICHE} for {config.AUDIENCE}. '
        f'Avoid these past topics: {past[-60:]}. Return JSON: {{"topic": "..."}}',
        validate=lambda x: x["topic"])
    return d["topic"], None


def build(kind, script, dry):
    """Voiceover + video for one format. kind = 'long' or 'short'.
    Returns (final_path, credits, thumb_or_None)."""
    fmt = config.LONG_FORMAT if kind == "long" else config.SHORT_FORMAT
    rate = config.SHORT_VOICE_RATE if kind == "short" else config.VOICE_RATE
    work = WORK / kind
    work.mkdir(parents=True)
    audios = [tts.synth(s["narration"], str(work / f"voice{i}.mp3"), dry_run=dry, rate=rate)
              for i, s in enumerate(script["scenes"])]
    final, credits = video.assemble(script, audios, work, fmt)
    thumb = video.make_thumbnail(final, script["title"], work / "thumb.jpg", fmt) if kind == "long" else None
    print(f"[{kind}] {final} ({video.duration(final):.0f} sec)")
    return final, credits, thumb


def credits_text(credits):
    return "\n\nStock footage: Pexels (" + ", ".join(credits) + ")" if credits else ""


def main():
    dry = "--dry-run" in sys.argv
    if not (config.MAKE_LONG or config.MAKE_SHORT):
        raise SystemExit("config.py: enable MAKE_LONG and/or MAKE_SHORT")
    topic, row = pick_topic(dry)
    print(f"[topic] {topic}")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    # ---- 1. scripts (the Short reuses the long script's facts) ----
    long_script = None
    if config.MAKE_LONG:
        long_script = script_gen.sample_script(topic) if dry else script_gen.write_script(topic)
        print(f"[script:long] {long_script['title']} ({len(long_script['scenes'])} scenes)")
    short_script = None
    if config.MAKE_SHORT:
        short_script = (script_gen.sample_short_script(topic) if dry
                        else script_gen.write_short_script(topic, long_script))
        print(f"[script:short] {short_script['title']} ({len(short_script['scenes'])} scenes)")

    # ---- 2. render ----
    long_out = build("long", long_script, dry) if long_script else None
    short_out = build("short", short_script, dry) if short_script else None

    if dry:
        if long_out:
            shutil.copy(long_out[0], ROOT / "dry_run_long.mp4")
            shutil.copy(long_out[2], ROOT / "dry_run_thumb.jpg")
        if short_out:
            shutil.copy(short_out[0], ROOT / "dry_run_short.mp4")
        print("[dry-run] done -> dry_run_long.mp4 / dry_run_short.mp4")
        return

    # ---- 3. upload: long first (so the Short can link to it), then the Short ----
    import uploader
    messages, long_id = [], None

    if long_out:
        final, credits, thumb = long_out
        desc = long_script.get("description", "") + credits_text(credits)
        if config.AI_DISCLOSURE:
            desc += "\n\nNarration generated with AI text-to-speech."
        long_id, at = uploader.upload(final, thumb, long_script["title"], desc, long_script.get("tags", []))
        messages.append(f"Long: {long_script['title']}\nhttps://youtu.be/{long_id}\nPublishes {at} (UTC)")
        mark_done(topic, row, long_script["title"])   # progress is saved even if the Short fails below

    if short_out:
        try:
            final, credits, _ = short_out
            desc = short_script.get("description", "")
            if long_id:
                desc += f"\n\nFull video: https://youtu.be/{long_id}"
            desc += credits_text(credits)
            if config.AI_DISCLOSURE:
                desc += "\n\nNarration generated with AI text-to-speech."
            desc += "\n\n#Shorts"
            sid, at = uploader.upload(final, None, short_script["title"], desc,
                                      short_script.get("tags", []), short=True)
            messages.append(f"Short: {short_script['title']}\nhttps://youtube.com/shorts/{sid}\nPublishes {at} (UTC)")
            if not long_out:
                mark_done(topic, row, short_script["title"])
        except Exception:  # noqa: BLE001  (don't lose the already-uploaded long video's notification)
            err = traceback.format_exc()
            print(err)
            messages.append("Short FAILED:\n" + err[-800:])

    notify.telegram("\n\n".join(messages))


def mark_done(topic, row, title):
    if row is not None:
        rows = load_topics()
        for r in rows:
            if r["topic"] == topic:
                r["used"] = "1"
        save_topics(rows)
    past = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    past.append(title)
    HISTORY.write_text(json.dumps(past[-300:], indent=1))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        print(err)
        notify.telegram("Daily video FAILED:\n" + err[-1500:])
        sys.exit(1)

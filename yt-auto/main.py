"""Daily pipeline: topic -> script -> voice -> video -> thumbnail -> scheduled YouTube upload.

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


def main():
    dry = "--dry-run" in sys.argv
    topic, row = pick_topic(dry)
    print(f"[topic] {topic}")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    script = script_gen.sample_script(topic) if dry else script_gen.write_script(topic)
    print(f"[script] {script['title']} ({len(script['scenes'])} scenes)")

    audios = [tts.synth(s["narration"], str(WORK / f"voice{i}.mp3"), dry_run=dry)
              for i, s in enumerate(script["scenes"])]

    final, credits = video.assemble(script, audios, WORK)
    thumb = video.make_thumbnail(final, script["title"], WORK / "thumb.jpg")
    mins = video.duration(final) / 60
    print(f"[video] {final} ({mins:.1f} min)")

    if dry:
        out = ROOT / "dry_run_output.mp4"
        shutil.copy(final, out)
        shutil.copy(thumb, ROOT / "dry_run_thumb.jpg")
        print(f"[dry-run] done -> {out}")
        return

    import uploader
    desc = script.get("description", "")
    if credits:
        desc += "\n\nStock footage: Pexels (" + ", ".join(credits) + ")"
    if config.AI_DISCLOSURE:
        desc += "\n\nNarration generated with AI text-to-speech."
    vid, publish_at = uploader.upload(final, thumb, script["title"], desc, script.get("tags", []))

    if row is not None:
        rows = load_topics()
        for r in rows:
            if r["topic"] == topic:
                r["used"] = "1"
        save_topics(rows)
    past = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    past.append(script["title"])
    HISTORY.write_text(json.dumps(past[-300:], indent=1))

    notify.telegram(f"Uploaded: {script['title']}\nhttps://youtu.be/{vid}\nPublishes at {publish_at} (UTC)")



if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        print(err)
        notify.telegram("Daily video FAILED:\n" + err[-1500:])
        sys.exit(1)

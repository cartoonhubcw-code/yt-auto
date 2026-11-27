import json
from pathlib import Path

import config
import llm


def _validate(d):
    assert d.get("title") and d.get("scenes"), "missing title/scenes"
    for s in d["scenes"]:
        assert s.get("narration"), "scene missing narration"


def write_script(topic: str) -> dict:
    prompt = f"""You write scripts for a faceless YouTube explainer channel about {config.NICHE}, for {config.AUDIENCE}.
Topic: "{topic}"
Language: {config.LANGUAGE}

Rules:
- About {config.TARGET_WORDS} words of narration in total, split into exactly {config.SCENES} scenes.
- Scene 1 is a strong hook (a surprising question or fact). Middle scenes explain step by step, with ONE concrete analogy or example. Last scene is a short recap and a friendly call to subscribe.
- Plain spoken sentences, no stage directions, no emojis, no markdown.
- Only state facts you are confident are true. Do NOT invent statistics, quotes or studies.
- Each scene has an animated "visual" that appears on screen while it is spoken. Choose its "type":
  * "title": big heading (scene 1 and the last scene). Optional items[0] = a short subtitle.
  * "bullets": heading + 2 to 4 short items (max 7 words each) that pop up one by one. For lists, key points, causes, features.
  * "flow": heading + 2 to 4 very short steps (max 4 words each) shown as connected boxes. For processes and sequences.
  * "stat": "value" = one big number or short figure (e.g. "24 satellites", "1969", "99.9%") + heading = what it means. Use ONLY for numbers you are certain are correct.
- Headings max 6 words. Mix the types so consecutive scenes do not look the same. The on-screen text should support the narration, not repeat it word for word.
- "visual_keyword": 1-3 English words for stock footage (only used if the channel is set to stock mode).

Return ONLY JSON in this shape:
{{
  "title": "catchy title under 70 characters",
  "description": "2-3 sentence description for YouTube",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "scenes": [
    {{"narration": "...", "visual_keyword": "...",
      "visual": {{"type": "title|bullets|flow|stat", "heading": "...", "items": ["..."], "value": ""}}}}
  ]
}}"""
    return llm.generate_json(prompt, validate=_validate)


def sample_script(topic: str) -> dict:
    """Used for --dry-run so you can test without any API keys."""
    scenes = [
        ("Have you ever wondered about this: " + topic, {"type": "title", "heading": topic, "items": ["Explained in 60 seconds"]}),
        ("Let us break it down into three simple ideas that build on each other.", {"type": "bullets", "heading": "Three simple ideas", "items": ["Start with the basic principle", "Add one everyday example", "See the big picture"]}),
        ("It works as a chain: one step feeds the next until the result appears.", {"type": "flow", "heading": "How it works", "items": ["Input", "Process", "Signal", "Result"]}),
        ("Here is a number that shows the scale of it all.", {"type": "stat", "heading": "satellites in orbit", "items": ["Always working together"], "value": "24"}),
        ("Put those pieces together and the answer becomes clear to anyone.", {"type": "bullets", "heading": "Putting it together", "items": ["Principle plus example", "Plus the big picture"]}),
        ("That is why this matters in daily life more than you might think.", {"type": "stat", "heading": "of daily life affected", "items": [], "value": "99.9%"}),
        ("If you enjoyed this, subscribe for a new explainer every day.", {"type": "title", "heading": "Subscribe for more", "items": ["New explainer daily"]}),
    ]
    return {
        "title": topic[:70],
        "description": "Dry-run sample video.",
        "tags": ["test"],
        "scenes": [{"narration": n, "visual_keyword": "nature", "visual": v} for n, v in scenes],
    }

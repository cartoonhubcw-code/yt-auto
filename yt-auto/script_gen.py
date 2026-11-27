import json
from pathlib import Path

import config
import llm


def _validate(d):
    assert d.get("title") and d.get("scenes"), "missing title/scenes"
    for s in d["scenes"]:
        assert s.get("narration") and s.get("visual_keyword"), "scene missing fields"


def write_script(topic: str) -> dict:
    prompt = f"""You write scripts for a faceless YouTube explainer channel about {config.NICHE}, for {config.AUDIENCE}.
Topic: "{topic}"
Language: {config.LANGUAGE}

Rules:
- About {config.TARGET_WORDS} words of narration in total, split into exactly {config.SCENES} scenes.
- Scene 1 is a strong hook (a surprising question or fact). Middle scenes explain step by step, with ONE concrete analogy or example. Last scene is a short recap and a friendly call to subscribe.
- Plain spoken sentences, no stage directions, no emojis, no markdown.
- Only state facts you are confident are true. Do NOT invent statistics, quotes or studies.
- "visual_keyword": 1-3 English words for generic, filmable stock footage (e.g. "city traffic", "satellite orbit"). Concrete, not abstract.
- "on_screen_text": max 6 words, shown only if no footage is found.

Return ONLY JSON in this shape:
{{
  "title": "catchy title under 70 characters",
  "description": "2-3 sentence description for YouTube",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "scenes": [
    {{"narration": "...", "visual_keyword": "...", "on_screen_text": "..."}}
  ]
}}"""
    return llm.generate_json(prompt, validate=_validate)


def sample_script(topic: str) -> dict:
    """Used for --dry-run so you can test without any API keys."""
    narr = [
        f"Have you ever wondered about this: {topic}",
        "Let us break it down into a few simple ideas.",
        "First, everything starts with a basic principle that is easy to picture.",
        "Now imagine a simple everyday example that makes it click.",
        "Put those two pieces together and the answer becomes clear.",
        "That is why this matters in daily life more than you might think.",
        "If you enjoyed this, subscribe for a new explainer every day.",
    ]
    return {
        "title": topic[:70],
        "description": "Dry-run sample video.",
        "tags": ["test"],
        "scenes": [
            {"narration": n, "visual_keyword": "nature", "on_screen_text": f"Idea {i + 1}"}
            for i, n in enumerate(narr)
        ],
    }

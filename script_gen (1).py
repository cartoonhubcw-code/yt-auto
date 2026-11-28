import json
from pathlib import Path

import config
import llm


def _validate(d):
    assert d.get("title") and d.get("scenes"), "missing title/scenes"
    for s in d["scenes"]:
        assert s.get("narration") and s.get("visual_keyword"), "scene missing fields"


# Plain strings (not f-strings) so the JSON examples reach the model exactly as written.
_VISUALS_2D = """- "visual": an animation for the scene. "type" must be one of:
    "flow"    -> {"type":"flow","steps":["3-5 short steps, max 4 words each"]}  (processes, how-it-works)
    "cycle"   -> {"type":"cycle","steps":["3-6 short steps"],"text":"centre label"}  (loops, repeating systems)
    "bars"    -> {"type":"bars","unit":" km","items":[{"label":"x","value":10},{"label":"y","value":50}],"text":"caption"}  (comparisons; ONLY real numbers you are sure of, otherwise use flow)
    "counter" -> {"type":"counter","value":31000,"unit":"km/h","label":"caption"}  (one big real number you are sure of)
    "orbit"   -> {"type":"orbit","center":"Earth","items":["Moon","Satellite"]}  (things moving around a centre)
    "wave"    -> {"type":"wave","text":"caption"}  (sound, light, radio, signals)
    "blocks"  -> {"type":"blocks","text":"caption"}  (splitting, dividing, rearranging, fractions, puzzles)
    "stock"   -> {"type":"stock"}  (use for at most 1 scene; real-world footage)"""

_VISUALS_3D = """    "3d_cut"   -> {"type":"3d_cut","text":"caption"}   REAL 3D render: a block cut by a knife, halves slid and rejoined (division, fractions, paradoxes, splitting)
    "3d_stack" -> {"type":"3d_stack","text":"caption"}  REAL 3D render: blocks dropping into a tower (layers, stages, building up)
    "3d_gears" -> {"type":"3d_gears","text":"caption"}  REAL 3D render: meshing gears (machines, mechanisms, cause and effect)
  The three 3d_ types are slow to render: use AT MOST ONE 3d_ scene per video, and only if a physical object demo genuinely fits the topic; otherwise use none."""

# long video: 2D types + the optional 3D ones
_LONG_VISUALS = _VISUALS_2D.replace('    "stock"', _VISUALS_3D.split("\n  The three")[0] + '\n    "stock"') \
    + "\n  " + _VISUALS_3D.split("\n  ")[-1] + "\n  Use at least 4 different types across the video. Keep every label very short."
# short video: 2D only, fewer scenes
_SHORT_VISUALS = _VISUALS_2D.replace('    "stock"', _VISUALS_3D.split("\n  The three")[0] + '\n    "stock"') \
    + "\n  The 3d_ types are real 3D renders (the most eye-catching look). For a Short: if the topic has ANY physical, mechanical, splitting or building angle, make scene 1 (the hook) a 3d_ scene, and use at most 2 3d_ scenes in total; otherwise use none." \
    + "\n  Use at least 3 different types. Keep every label very short."


def write_script(topic: str) -> dict:
    prompt = f"""You write scripts for a faceless YouTube explainer channel about {config.NICHE}, for {config.AUDIENCE}.
Topic: "{topic}"
Language: {config.LANGUAGE}

Rules:
- About {config.TARGET_WORDS} words of narration in total, split into exactly {config.SCENES} scenes (roughly equal length).
- Scene 1 is a strong hook (a surprising question or fact). Middle scenes explain step by step, with ONE concrete analogy or example per major idea. Last scene is a short recap and a friendly call to subscribe.
- Plain spoken sentences, no stage directions, no emojis, no markdown.
- Only state facts you are confident are true. Do NOT invent statistics, quotes or studies.
- "visual_keyword": 1-3 English words for generic, filmable stock footage (e.g. "city traffic", "satellite orbit"). Concrete, not abstract. Use a different keyword for each scene.
- "on_screen_text": max 5 words, shown as a headline on the animation.
{_LONG_VISUALS}

Return ONLY JSON in this shape:
{{
  "title": "catchy title under 70 characters",
  "description": "2-3 sentence description for YouTube",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "scenes": [
    {{"narration": "...", "visual_keyword": "...", "on_screen_text": "...", "visual": {{"type": "flow", "steps": ["..", "..", ".."]}}}}
  ]
}}"""
    return llm.generate_json(prompt, validate=_validate)


def write_short_script(topic: str, long_script: dict | None = None) -> dict:
    """A separate, standalone vertical Short about the same topic.
    If the long script exists it is used as the fact base, so both videos agree."""
    base = ""
    if long_script:
        facts = " ".join(s["narration"] for s in long_script["scenes"])
        base = f'\nUse ONLY facts from this full script (do not add new claims):\n"""{facts}"""\n'
    prompt = f"""You write scripts for YouTube SHORTS (vertical, under 60 seconds) for a faceless explainer channel about {config.NICHE}, for {config.AUDIENCE}.
Topic: "{topic}"
Language: {config.LANGUAGE}
{base}
Rules:
- About {config.SHORT_WORDS} words of narration in total, split into exactly {config.SHORT_SCENES} scenes.
- Scene 1 is a hook that makes people stop scrolling: a surprising fact or a bold question, 12 words or fewer. Do NOT start with "Hi", "Welcome" or the channel name.
- Pick the single most interesting idea and explain only that. Short punchy sentences. One concrete analogy.
- The last scene must end with a call to action: tell viewers the full explanation is on the channel / in the full video.
- Must make sense on its own without having seen the long video.
- Plain spoken sentences, no stage directions, no emojis, no markdown. Do NOT invent statistics, quotes or studies.
- "visual_keyword": 1-3 English words for generic, filmable VERTICAL stock footage. Concrete, not abstract.
- "on_screen_text": max 4 words, shown as a headline on the animation.
{_SHORT_VISUALS}

Return ONLY JSON in this shape:
{{
  "title": "curiosity-driven title under 60 characters",
  "description": "1-2 sentence description",
  "tags": ["tag1", "tag2", "tag3"],
  "scenes": [
    {{"narration": "...", "visual_keyword": "...", "on_screen_text": "...", "visual": {{"type": "flow", "steps": ["..", "..", ".."]}}}}
  ]
}}"""
    return llm.generate_json(prompt, validate=_validate)


_SAMPLE_VISUALS = [
    {"type": "blocks", "text": "Sample"},
    {"type": "flow", "steps": ["Input", "Process", "Output"]},
    {"type": "orbit", "center": "Sun", "items": ["A", "B", "C"]},
    {"type": "bars", "items": [{"label": "A", "value": 10}, {"label": "B", "value": 40}]},
    {"type": "wave", "text": "Waves"},
    {"type": "counter", "value": 1200, "unit": "units", "label": "Counter"},
    {"type": "cycle", "steps": ["One", "Two", "Three", "Four"], "text": "Loop"},
]


def _sample(narr, title):
    return {
        "title": title[:70],
        "description": "Dry-run sample video.",
        "tags": ["test"],
        "scenes": [
            {"narration": n, "visual_keyword": "nature", "on_screen_text": f"Idea {i + 1}",
             "visual": _SAMPLE_VISUALS[i % len(_SAMPLE_VISUALS)]}
            for i, n in enumerate(narr)
        ],
    }


def sample_script(topic: str) -> dict:
    """Used for --dry-run so you can test without any API keys."""
    base = [
        f"Have you ever wondered about this: {topic}",
        "Let us break it down into a few simple ideas.",
        "First, everything starts with a basic principle that is easy to picture.",
        "Now imagine a simple everyday example that makes it click.",
        "Put those two pieces together and the answer becomes clear.",
        "That is why this matters in daily life more than you might think.",
        "If you enjoyed this, subscribe for a new explainer every day.",
    ]
    return _sample(base * 2, topic)


def sample_short_script(topic: str) -> dict:
    narr = [
        f"Here is something strange about this: {topic}",
        "Most people get the first part wrong.",
        "Picture an everyday example and it suddenly makes sense.",
        "Put the pieces together and the answer is surprisingly simple.",
        "Watch the full video on the channel for the whole story.",
    ]
    return _sample(narr, topic)

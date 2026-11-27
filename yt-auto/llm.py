"""Free LLM access: tries Gemini first, then Groq. Both have free tiers (no card).

Gemini models are auto-discovered from the API, so retired model names
(or a stale GEMINI_MODELS setting) can no longer cause 404 errors.
"""
import json
import os
import re
import time

import requests

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODELS = "gemini-3.5-flash,gemini-3.5-flash-lite"


def _clean_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    return json.loads(text)


def _gemini_available_models():
    """Return the model IDs this API key can call with generateContent."""
    key = os.environ["GEMINI_API_KEY"]
    names = []
    token = None
    for _ in range(5):  # a few pages is plenty
        params = {"pageSize": 200}
        if token:
            params["pageToken"] = token
        r = requests.get(
            f"{GEMINI_BASE}/models",
            headers={"x-goog-api-key": key},
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                names.append(m["name"].removeprefix("models/"))
        token = data.get("nextPageToken")
        if not token:
            break
    return names


def _auto_pick(available):
    """Newest stable text models: gemini-<ver>-flash and -flash-lite only
    (skips preview, image, tts, live, etc.). Newest version first, flash before lite."""
    found = []
    for name in available:
        m = re.match(r"^gemini-(\d+(?:\.\d+)*)-flash(-lite)?$", name)
        if m:
            ver = tuple(int(x) for x in m.group(1).split("."))
            found.append((ver, m.group(2) is None, name))
    found.sort(reverse=True)
    return [name for _, _, name in found[:4]]


def _gemini_models():
    configured = [
        m.strip()
        for m in os.getenv("GEMINI_MODELS", DEFAULT_GEMINI_MODELS).split(",")
        if m.strip()
    ]
    try:
        available = set(_gemini_available_models())
    except Exception as e:  # noqa: BLE001
        print(f"[llm] could not list Gemini models ({e}); using configured names")
        return configured
    ordered = [m for m in configured if m in available]
    for m in _auto_pick(available):
        if m not in ordered:
            ordered.append(m)
    skipped = [m for m in configured if m not in available]
    if skipped:
        print(f"[llm] configured models not available for this key, skipped: {skipped}")
    if not ordered:
        print("[llm] no suitable Gemini models found for this key")
    return ordered


def _gemini(prompt: str, model: str):
    key = os.environ["GEMINI_API_KEY"]
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }
    r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str, model: str):
    key = os.environ["GROQ_API_KEY"]
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _providers():
    """Ordered list of (label, callable)."""
    out = []
    if os.getenv("GEMINI_API_KEY"):
        for m in _gemini_models():
            out.append((f"gemini:{m}", lambda p, m=m: _gemini(p, m)))
    if os.getenv("GROQ_API_KEY"):
        for m in os.getenv("GROQ_MODELS", "llama-3.3-70b-versatile").split(","):
            m = m.strip()
            if m:
                out.append((f"groq:{m}", lambda p, m=m: _groq(p, m)))
    return out


def generate_json(prompt: str, validate=None):
    providers = _providers()
    if not providers:
        raise RuntimeError("No LLM key found. Set GEMINI_API_KEY and/or GROQ_API_KEY.")
    errors = []
    for label, fn in providers:
        for attempt in range(2):
            try:
                data = _clean_json(fn(prompt))
                if validate:
                    validate(data)
                print(f"[llm] ok via {label}")
                return data
            except Exception as e:  # noqa: BLE001
                errors.append(f"{label} attempt {attempt + 1}: {e}")
                time.sleep(3)
    raise RuntimeError("All LLM providers failed:\n" + "\n".join(errors))

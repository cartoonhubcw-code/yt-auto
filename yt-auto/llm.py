"""Free LLM access: tries Gemini first, then Groq. Both have free tiers (no card)."""
import json
import os
import re
import time

import requests


def _clean_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    return json.loads(text)


def _gemini(prompt: str, model: str):
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
    """Ordered list of (label, callable). Models are configurable via env vars
    because free-tier model availability changes over time."""
    out = []
    if os.getenv("GEMINI_API_KEY"):
        for m in os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(","):
            m = m.strip()
            if m:
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

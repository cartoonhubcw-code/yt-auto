import os

import requests


def telegram(msg: str):
    tok, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT")
    if not (tok and chat):
        print(f"[notify] {msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": msg[:3500]}, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"[notify] telegram failed: {e}")

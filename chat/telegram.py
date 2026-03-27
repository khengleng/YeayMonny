from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings


def send_telegram_message(chat_id: int | str, text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.TELEGRAM_TIMEOUT_SECONDS):
            pass
    except (urllib.error.URLError, TimeoutError):
        # Do not fail webhook processing if Telegram send has transient network errors.
        return

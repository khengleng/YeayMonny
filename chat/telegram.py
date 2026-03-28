from __future__ import annotations

import json
import mimetypes
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


def _telegram_api_get(path: str) -> dict | None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=settings.TELEGRAM_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not payload.get("ok"):
        return None
    return payload.get("result") or None


def fetch_telegram_file(file_id: str, *, max_bytes: int | None = None) -> tuple[bytes, str, str] | None:
    file_meta = _telegram_api_get(f"getFile?file_id={file_id}")
    if not file_meta:
        return None

    file_path = file_meta.get("file_path")
    if not file_path:
        return None
    file_size = int(file_meta.get("file_size") or 0)
    if max_bytes and file_size and file_size > max_bytes:
        return None

    download_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
    try:
        with urllib.request.urlopen(download_url, timeout=settings.TELEGRAM_TIMEOUT_SECONDS) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError):
        return None

    if max_bytes and len(content) > max_bytes:
        return None

    filename = file_path.split("/")[-1] or "telegram_file"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return content, content_type, filename

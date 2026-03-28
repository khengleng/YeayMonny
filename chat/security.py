from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time


def generate_totp_secret(length: int = 32) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _totp_code(secret: str, for_ts: int, *, period: int = 30, digits: int = 6) -> str:
    normalized = (secret or "").strip().replace(" ", "").upper()
    if not normalized:
        return ""
    counter = int(for_ts // period)
    key = base64.b32decode(normalized, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    otp = binary % (10**digits)
    return str(otp).zfill(digits)


def verify_totp_code(secret: str, code: str, *, drift_steps: int = 1, period: int = 30) -> bool:
    value = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(value) != 6:
        return False
    now = int(time.time())
    for step in range(-drift_steps, drift_steps + 1):
        if hmac.compare_digest(_totp_code(secret, now + step * period, period=period), value):
            return True
    return False


def current_totp_code(secret: str) -> str:
    return _totp_code(secret, int(time.time()))

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Header, HTTPException

ROLES = (
    "Salesman",
    "Admin",
    "Production Supervisor",
    "Accountant/Auditor",
    "Owner",
)
_DEMO_SECRET = os.getenv("APP_SECRET", "local-only-demo-secret-change-before-deployment").encode()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 180_000)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_token(user: dict[str, Any]) -> str:
    payload = {**user, "exp": int(time.time()) + 60 * 60 * 12}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_DEMO_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


async def current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    try:
        encoded, signature = authorization[7:].split(".", 1)
        expected = hmac.new(_DEMO_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload["exp"] < time.time() or payload["role"] not in ROLES:
            raise ValueError("Expired or invalid token")
        return {key: payload[key] for key in ("id", "username", "display_name", "role")}
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Your session is invalid or has expired.") from None

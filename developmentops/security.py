from __future__ import annotations

import hashlib
import hmac


def verify_github_signature(
    secret: str,
    body: bytes,
    signature: str | None,
) -> bool:
    if not secret or not signature:
        return False
    if not signature.startswith("sha256="):
        return False
    supplied = signature.removeprefix("sha256=")
    if len(supplied) != 64:
        return False
    try:
        bytes.fromhex(supplied)
    except ValueError:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)

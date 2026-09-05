import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional
from app.core.config import settings

# Secret key for token signatures
JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against PBKDF2 hash."""
    try:
        salt, key_hex = hashed_password.split(":")
        test_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(test_key.hex(), key_hex)
    except Exception:
        return False


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_access_token(data: Dict[str, Any], expires_delta_seconds: Optional[int] = None) -> str:
    """Creates a signed HMAC-SHA256 JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()
    now = int(time.time())
    expire = now + (expires_delta_seconds or ACCESS_TOKEN_EXPIRE_SECONDS)
    payload.update({"iat": now, "exp": expire})

    h_str = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_str = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h_str}.{p_str}"

    sig = hmac.new(JWT_SECRET.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    sig_str = _b64_encode(sig)

    return f"{msg}.{sig_str}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Validates and decodes a signed JWT access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_str, p_str, sig_str = parts
        msg = f"{h_str}.{p_str}"

        expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64_encode(expected_sig), sig_str):
            return None

        payload = json.loads(_b64_decode(p_str).decode("utf-8"))
        if payload.get("exp") and payload["exp"] < int(time.time()):
            return None  # Expired

        return payload
    except Exception:
        return None

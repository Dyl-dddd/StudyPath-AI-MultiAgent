import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import DATA_DIR, get_settings
from app.core.db import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    configured = get_settings().jwt_secret
    if configured:
        return configured.encode()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "auth.secret"
    if not path.exists():
        try:
            with path.open("xb") as file:
                file.write(secrets.token_bytes(48).hex().encode())
        except FileExistsError:
            pass
    return path.read_bytes().strip()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1], digest_hex)
    except (ValueError, TypeError):
        return False


def sign_captcha_answer(challenge_id: str, answer: str) -> str:
    message = f"register-captcha:{challenge_id}:{answer.strip().upper()}".encode("utf-8")
    return hmac.new(_secret(), message, hashlib.sha256).hexdigest()


def issue_token(user_id: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "exp": int(time.time()) + 60 * 60 * 24 * 14}, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return payload.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "请先登录")
    try:
        encoded, signature_text = credentials.credentials.split(".", 1)
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not hmac.compare_digest(signature, expected) or payload["exp"] < time.time():
            raise ValueError
        user = db.get(User, payload["sub"])
        if user is None:
            raise ValueError
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "登录凭证无效或已过期") from None

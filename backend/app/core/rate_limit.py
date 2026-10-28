import hashlib
import time
from fastapi import HTTPException, Request
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.core.config import get_settings
from app.models import AuthRateLimit


def _client_ip(request: Request) -> str:
    # Use the socket peer. Forwarded headers are untrusted unless a trusted proxy
    # layer is configured explicitly in front of the application.
    return request.client.host if request.client else "unknown"


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _consume(db, key: str, limit: int, now: int, window: int) -> bool:
    bucket = now // window * window
    dialect = db.get_bind().dialect.name
    insert = sqlite_insert if dialect == "sqlite" else pg_insert if dialect == "postgresql" else None
    if insert is None:
        raise HTTPException(503, "当前数据库不支持分布式认证限流")
    table = AuthRateLimit.__table__
    stmt = insert(table).values(key=key, window_start=bucket, hits=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.key],
        set_={
            "window_start": bucket,
            "hits": case((table.c.window_start == bucket, table.c.hits + 1), else_=1),
        },
    )
    db.execute(stmt)
    db.execute(delete(table).where(table.c.window_start < bucket - window * 2))
    row = db.get(AuthRateLimit, key)
    allowed = bool(row and row.window_start == bucket and row.hits <= limit)
    db.commit()
    return allowed


def enforce_auth_rate_limit(request: Request, db, action: str, username: str = "") -> None:
    settings = get_settings()
    now = int(time.time())
    window = max(60, settings.auth_rate_window_seconds)
    ip = _client_ip(request)
    if action == "register":
        checks = [(_key(f"register:{ip}"), settings.register_ip_limit)]
    elif action == "captcha":
        checks = [(_key(f"captcha:{ip}"), settings.captcha_ip_limit)]
    else:
        normalized = username.strip().casefold()
        checks = [
            (_key(f"login-ip:{ip}"), settings.login_ip_limit),
            (_key(f"login-user-ip:{ip}:{normalized}"), settings.login_user_ip_limit),
        ]
    for key, limit in checks:
        if not _consume(db, key, max(1, limit), now, window):
            retry = window - now % window
            raise HTTPException(429, "尝试次数过多，请稍后再试", headers={"Retry-After": str(retry)})

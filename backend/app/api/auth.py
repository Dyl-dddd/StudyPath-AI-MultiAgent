import base64
import html
import secrets
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.config import get_settings
from app.core.security import current_user, hash_password, issue_token, sign_captcha_answer, verify_password
from app.core.rate_limit import enforce_auth_rate_limit
from app.models import CaptchaChallenge, User, UserProfile
from app.schemas import AuthInput, RegisterInput

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/captcha")
def registration_captcha(request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_auth_rate_limit(request, db, "captcha")
    now = int(time.time())
    db.execute(delete(CaptchaChallenge).where(CaptchaChallenge.expires_at < now))
    challenge_id = str(uuid.uuid4())
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    answer = "".join(secrets.choice(alphabet) for _ in range(5))
    db.add(CaptchaChallenge(
        id=challenge_id,
        answer_hash=sign_captcha_answer(challenge_id, answer),
        expires_at=now + 300,
        attempts=0,
        created_at=now,
    ))
    db.commit()

    colors = ["#5436a8", "#704bd0", "#42366c", "#8a69db"]
    glyphs = []
    for index, char in enumerate(answer):
        x = 25 + index * 29
        y = secrets.randbelow(9) + 31
        angle = secrets.randbelow(31) - 15
        color = secrets.choice(colors)
        glyphs.append(f'<text x="{x}" y="{y}" fill="{color}" transform="rotate({angle} {x} {y})">{html.escape(char)}</text>')
    noise = []
    for _ in range(7):
        x1, x2 = secrets.randbelow(160), secrets.randbelow(160)
        y1, y2 = secrets.randbelow(52), secrets.randbelow(52)
        noise.append(f'<path d="M{x1} {y1} Q{(x1+x2)//2} {secrets.randbelow(52)} {x2} {y2}"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="52" viewBox="0 0 160 52">'
        '<rect width="160" height="52" rx="11" fill="#f5f0ff"/>'
        '<g fill="none" stroke="#baa6ec" stroke-width="1" opacity=".55">' + "".join(noise) + "</g>"
        '<g font-family="Arial,sans-serif" font-size="25" font-weight="700" letter-spacing="2">' + "".join(glyphs) + "</g></svg>"
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return {"captcha_id": challenge_id, "image_data": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(), "expires_in": 300}


def _consume_registration_captcha(db: Session, challenge_id: str, answer: str) -> None:
    now = int(time.time())
    challenge = db.scalar(select(CaptchaChallenge).where(CaptchaChallenge.id == challenge_id).with_for_update())
    invalid = HTTPException(400, "验证码错误或已失效，请刷新后重试")
    if challenge is None:
        raise invalid
    if challenge.expires_at <= now:
        db.delete(challenge)
        db.commit()
        raise invalid
    expected = sign_captcha_answer(challenge_id, answer)
    if not secrets.compare_digest(challenge.answer_hash, expected):
        challenge.attempts += 1
        if challenge.attempts >= 5:
            db.delete(challenge)
        db.commit()
        raise invalid
    db.delete(challenge)
    db.commit()


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, db: Session = Depends(get_db)):
    enforce_auth_rate_limit(request, db, "register", payload.username)
    if payload.password != payload.password_confirm:
        raise HTTPException(400, "两次输入的密码不一致")
    _consume_registration_captcha(db, payload.captcha_id, payload.captcha_code)
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "用户名已被使用")
    user = User(id=str(uuid.uuid4()), username=payload.username, password_hash=hash_password(payload.password))
    db.add_all([user, UserProfile(user_id=user.id)])
    db.commit()
    return {"access_token": issue_token(user.id), "token_type": "bearer", "username": user.username, "user_id": user.id}


@router.post("/login")
def login(payload: AuthInput, request: Request, db: Session = Depends(get_db)):
    enforce_auth_rate_limit(request, db, "login", payload.username)
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码不正确")
    return {"access_token": issue_token(user.id), "token_type": "bearer", "username": user.username, "user_id": user.id}


@router.get("/me")
def me(user: User = Depends(current_user)):
    admin_usernames = {
        username.strip()
        for username in get_settings().content_admin_usernames.split(",")
        if username.strip()
    }
    return {"user_id": user.id, "username": user.username, "role": "admin" if user.username in admin_usernames else "learner"}

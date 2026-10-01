import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession

SESSION_COOKIE = "session_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def register_user(db: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Пользователь с таким email уже зарегистрирован")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return user


def start_session(db: Session, response: Response, user: User) -> None:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    ttl = timedelta(days=settings.session_ttl_days)
    db.add(
        UserSession(
            token=token, user_id=user.id, expires_at=datetime.now(timezone.utc) + ttl
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def end_session(db: Session, response: Response, token: str | None) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token == token))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User | None:
    if not session_token:
        return None
    session = db.get(UserSession, session_token)
    if not session or session.expires_at < datetime.now(timezone.utc):
        return None
    return db.get(User, session.user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(401, "Требуется вход в систему")
    return user

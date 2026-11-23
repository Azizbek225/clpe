import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import audit, get_current_user, user_permissions, user_role_names
from app.core.security import create_access_token, hash_password, new_refresh_token, sha256, verify_password
from app.db import get_db
from app.models import Organization, RefreshToken, User
from app.services.seed import assign_role

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    preferred_language: str = Field("uz", pattern="^(uz|ru|en)$")


class LoginIn(BaseModel):
    login: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    preferred_language: str | None = Field(None, pattern="^(uz|ru|en)$")


def user_out(u: User) -> dict:
    return {"id": str(u.id), "username": u.username, "email": u.email, "full_name": u.full_name,
            "preferred_language": u.preferred_language, "status": u.status, "xp": u.xp, "level": u.level,
            "organization_id": str(u.organization_id) if u.organization_id else None,
            "roles": user_role_names(u), "permissions": sorted(user_permissions(u))}


def issue_tokens(db: Session, user: User, family: uuid.UUID | None = None) -> TokenOut:
    raw, digest = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=digest, family_id=family or uuid.uuid4(),
                        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_days)))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), refresh_token=raw)


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(or_(User.email == body.email.lower(), User.username == body.username))):
        raise HTTPException(409, "Bu foydalanuvchi nomi yoki email band")
    org = db.scalar(select(Organization).where(Organization.name == "CLPE"))
    user = User(username=body.username, email=body.email.lower(), password_hash=hash_password(body.password),
                full_name=body.full_name, preferred_language=body.preferred_language,
                organization_id=org.id if org else None)
    db.add(user)
    db.flush()
    assign_role(db, user, "student")
    audit(db, user, "auth.register", "user", str(user.id), request)
    db.commit()
    return user_out(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    ident = body.login.strip().lower()
    user = db.scalar(select(User).where(or_(User.email == ident, User.username == body.login.strip())))
    if not user or not verify_password(body.password, user.password_hash) or user.status != "active":
        audit(db, user, "auth.login_failed", "user", str(user.id) if user else ident, request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login yoki parol noto'g'ri")
    audit(db, user, "auth.login", "user", str(user.id), request)
    return issue_tokens(db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> TokenOut:
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    if not tok:
        raise HTTPException(401, "Refresh token yaroqsiz")
    exp = tok.expires_at if tok.expires_at.tzinfo else tok.expires_at.replace(tzinfo=timezone.utc)
    if tok.revoked:
        # Qayta ishlatish aniqlandi — butun oilani bekor qilamiz (token o'g'irlanishidan himoya)
        for t in db.scalars(select(RefreshToken).where(RefreshToken.family_id == tok.family_id)):
            t.revoked = True
        db.commit()
        raise HTTPException(401, "Refresh token qayta ishlatildi — sessiya bekor qilindi")
    if exp < datetime.now(timezone.utc):
        raise HTTPException(401, "Refresh token muddati tugagan")
    tok.revoked = True
    user = db.get(User, tok.user_id)
    return issue_tokens(db, user, tok.family_id)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)) -> None:
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    if tok:
        for t in db.scalars(select(RefreshToken).where(RefreshToken.family_id == tok.family_id)):
            t.revoked = True
        db.commit()


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return user_out(user)


@router.put("/me")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    u = db.get(User, user.id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    db.commit()
    return user_out(u)


@router.post("/password/reset", status_code=202)
def password_reset(body: dict) -> dict:
    # Email yuborish servisi keyingi bosqichda ulanadi; foydalanuvchi mavjudligini oshkor qilmaymiz.
    return {"detail": "Agar email ro'yxatdan o'tgan bo'lsa, tiklash havolasi yuboriladi"}

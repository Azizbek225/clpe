from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import AuditLog, User

bearer = HTTPBearer(auto_error=False)


def user_permissions(user: User) -> set[str]:
    perms: set[str] = set()
    for ur in user.roles:
        perms.update(rp.permission.permission_key for rp in ur.role.permissions)
    return perms


def user_role_names(user: User) -> list[str]:
    return sorted({ur.role.name for ur in user.roles})


def get_user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    uid = decode_access_token(token)
    if not uid:
        return None
    user = db.get(User, uid)
    if not user or user.status != "active" or user.deleted_at is not None:
        return None
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    user = get_user_from_token(db, creds.credentials if creds else None)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Avtorizatsiya talab qilinadi")
    return user


def require(*perms: str) -> Callable[..., User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        have = user_permissions(user)
        if not set(perms).issubset(have):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Ruxsat yetarli emas")
        return user

    return checker


def audit(db: Session, user: User | None, action: str, resource_type: str,
          resource_id: str | None = None, request: Request | None = None, details: str | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        organization_id=user.organization_id if user else None,
        action=action, resource_type=resource_type, resource_id=resource_id,
        ip_address=request.client.host if request and request.client else None,
        details=details,
    ))

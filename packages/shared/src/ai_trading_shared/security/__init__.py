"""Security: JWT, password hashing, RBAC, secret helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from ai_trading_shared.domain.enums import Role

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_HIERARCHY = {
    Role.VIEWER: 1,
    Role.ANALYST: 2,
    Role.TRADER: 3,
    Role.ADMIN: 4,
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    *,
    subject: str,
    role: Role,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 30,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_days: int = 7,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expires_days),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> Dict[str, Any]:
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def role_at_least(user_role: Role, required: Role) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required]


class TokenPayload:
    """Parsed access token claims."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.subject: str = str(data["sub"])
        self.role: Role = Role(data["role"])
        self.token_type: str = str(data.get("type", "access"))
        self.raw = data

    @property
    def user_id(self) -> UUID:
        return UUID(self.subject)

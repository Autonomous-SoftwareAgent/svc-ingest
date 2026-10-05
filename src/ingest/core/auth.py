"""Xác thực đối tác bằng tên đăng nhập và mật khẩu. Mật khẩu chỉ lưu dạng băm scrypt."""
from __future__ import annotations

import hashlib
import hmac
import os

from sqlalchemy import select
from sqlalchemy.engine import Engine

from ingest.contract import PartnerInfo
from ingest.core.schema import partner

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), digest)


_DUMMY = hash_password("khong-ai-biet-mat-khau-nay")


def authenticate(engine: Engine, username: str, password: str) -> PartnerInfo | None:
    """Trả đối tác nếu đúng. Tên lạ vẫn tốn thời gian băm như tên thật, để không dò được tên đăng nhập."""
    with engine.connect() as conn:
        row = conn.execute(
            select(partner.c.id, partner.c.name, partner.c.format, partner.c.password_hash).where(
                partner.c.username == username, partner.c.active.is_(True)
            )
        ).first()
    if row is None:
        verify_password(password, _DUMMY)
        return None
    if not verify_password(password, row.password_hash):
        return None
    return PartnerInfo(row.id, row.name, row.format)

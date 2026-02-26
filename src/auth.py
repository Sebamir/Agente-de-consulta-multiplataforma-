"""
Autenticación JWT para la interfaz web.

Usuarios definidos en la variable de entorno:
  WEB_USERS=usuario1:contraseña1,usuario2:contraseña2

Clave de firma del token:
  JWT_SECRET=clave-secreta-larga
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

JWT_SECRET       = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM    = "HS256"
JWT_EXPIRE_HOURS = 12


def _load_users() -> dict[str, str]:
    """Carga los usuarios desde WEB_USERS=user1:pass1,user2:pass2."""
    raw = os.environ.get("WEB_USERS", "")
    users: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            user, pwd = pair.split(":", 1)
            users[user.strip()] = pwd.strip()
    return users


def authenticate_user(username: str, password: str) -> bool:
    """Valida usuario y contraseña. Usa compare_digest para prevenir timing attacks."""
    stored = _load_users().get(username)
    if stored is None:
        return False
    return secrets.compare_digest(password, stored)


def create_token(username: str) -> str:
    """Genera un JWT firmado con expiración de JWT_EXPIRE_HOURS horas."""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str | None:
    """Valida el JWT y devuelve el username. Devuelve None si es inválido o expirado."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

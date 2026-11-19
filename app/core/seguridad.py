"""Autenticación (JWT + contraseñas con hash) y el ACTOR de cada solicitud.

Tipos de actor:
  - admin    : cuenta de la empresa (tabla usuarios, rol admin).
  - usuario  : comprador (tabla usuarios, rol usuario).
  - invitado : sin cuenta; sesión temporal ligada a UNA unidad de exhibición.

El rol del token NUNCA basta: cada solicitud vuelve a validar en RDS que la
cuenta siga activa y que el token no haya sido invalidado (version_token), y
la autorización sobre cada unidad se decide en services/autorizacion.py.
"""
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings

ADMIN = "admin"
USUARIO = "usuario"
INVITADO = "invitado"

_ITERACIONES = 390_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 con sal aleatoria (biblioteca estándar de Python)."""
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, _ITERACIONES)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERACIONES, base64.b64encode(sal).decode(), base64.b64encode(derivada).decode()
    )


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = almacenado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(sal), int(iteraciones)
        )
        return hmac.compare_digest(derivada, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False


# Hash de referencia para comparar en tiempo constante aunque el usuario no exista
HASH_FALSO = hash_password(secrets.token_hex(16))


@dataclass(frozen=True)
class Actor:
    tipo: str                       # admin | usuario | invitado
    id: int                         # id_usuario o id_sesion
    nombre: str
    usuario: str | None = None      # login (admin/usuario)
    codigo_sesion: str | None = None
    id_vehiculo_invitado: int | None = None

    @property
    def clave(self) -> str:
        """Identifica a la sesión/cuenta para el control exclusivo y los WebSocket."""
        return f"inv:{self.codigo_sesion}" if self.tipo == INVITADO else f"usr:{self.id}"

    @property
    def es_admin(self) -> bool:
        return self.tipo == ADMIN

    @property
    def es_usuario(self) -> bool:
        return self.tipo == USUARIO

    @property
    def es_invitado(self) -> bool:
        return self.tipo == INVITADO


class ServicioAutenticacion:
    ALGORITMO = "HS256"

    def __init__(self, settings: Settings):
        self._s = settings

    def token_usuario(self, fila: dict) -> tuple[str, int]:
        segundos = self._s.jwt_minutos * 60
        ahora = datetime.now(timezone.utc)
        payload = {
            "sub": str(fila["id_usuario"]), "tipo": fila["rol"], "rol": fila["rol"],
            "usr": fila["usuario"], "ver": int(fila["version_token"]),
            "iat": ahora, "exp": ahora + timedelta(seconds=segundos),
        }
        return jwt.encode(payload, self._s.jwt_secret, algorithm=self.ALGORITMO), segundos

    def token_invitado(self, codigo: str, id_vehiculo: int, expira: datetime) -> tuple[str, int]:
        ahora = datetime.now(timezone.utc)
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)
        payload = {"sub": codigo, "tipo": INVITADO, "rol": INVITADO, "veh": id_vehiculo,
                   "iat": ahora, "exp": expira}
        segundos = max(int((expira - ahora).total_seconds()), 0)
        return jwt.encode(payload, self._s.jwt_secret, algorithm=self.ALGORITMO), segundos

    def decodificar(self, token: str) -> dict:
        return jwt.decode(token, self._s.jwt_secret, algorithms=[self.ALGORITMO])

    def token_dispositivo_valido(self, token: str | None, id_vehiculo: int) -> bool:
        return (bool(token) and id_vehiculo == self._s.dispositivo_id_vehiculo
                and hmac.compare_digest(token.encode("utf-8"), self._s.dispositivo_token.encode("utf-8")))

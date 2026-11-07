"""Autenticación (JWT) y autorización por roles.

Roles:
  - operador: ejecutar movimientos, iniciar y cancelar DEMO.
  - admin: todo lo anterior + crear, actualizar y eliminar (vehículos, comandos, DEMO).
Las consultas GET son públicas y de solo lectura.
"""
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings, obtener_settings

ROL_OPERADOR = "operador"
ROL_ADMIN = "admin"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


class ServicioAutenticacion:
    ALGORITMO = "HS256"

    def __init__(self, settings: Settings):
        self._s = settings

    @staticmethod
    def _iguales(a: str, b: str) -> bool:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    def validar_credenciales(self, usuario: str, password: str) -> str | None:
        """Devuelve el rol si las credenciales son correctas; None en otro caso."""
        if self._iguales(usuario, self._s.admin_usuario) and self._iguales(password, self._s.admin_password):
            return ROL_ADMIN
        if self._iguales(usuario, self._s.operador_usuario) and self._iguales(password, self._s.operador_password):
            return ROL_OPERADOR
        return None

    def crear_token(self, usuario: str, rol: str) -> tuple[str, int]:
        segundos = self._s.jwt_minutos * 60
        ahora = datetime.now(timezone.utc)
        payload = {"sub": usuario, "rol": rol, "iat": ahora, "exp": ahora + timedelta(seconds=segundos)}
        return jwt.encode(payload, self._s.jwt_secret, algorithm=self.ALGORITMO), segundos

    def decodificar(self, token: str) -> dict:
        return jwt.decode(token, self._s.jwt_secret, algorithms=[self.ALGORITMO])

    def token_dispositivo_valido(self, token: str | None) -> bool:
        return bool(token) and self._iguales(token, self._s.dispositivo_token)


def obtener_servicio_auth() -> ServicioAutenticacion:
    return ServicioAutenticacion(obtener_settings())


def requerir_rol(*roles_permitidos: str):
    """Dependencia FastAPI: exige token válido con alguno de los roles indicados."""

    def _dependencia(
        token: str | None = Depends(oauth2_scheme),
        auth: ServicioAutenticacion = Depends(obtener_servicio_auth),
    ) -> dict:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se requiere autenticación (Bearer token)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = auth.decodificar(token)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.get("rol") not in roles_permitidos:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return payload

    return _dependencia


solo_admin = requerir_rol(ROL_ADMIN)
operador_o_admin = requerir_rol(ROL_OPERADOR, ROL_ADMIN)

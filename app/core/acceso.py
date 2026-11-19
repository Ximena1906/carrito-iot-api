"""Dependencias FastAPI de autenticación y autorización por rol.

El rol solo decide QUÉ operaciones puede intentar un actor. Sobre QUÉ unidad
puede hacerlo lo decide ServicioAutorizacion en cada ruta.
"""
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer

from app import dependencias as dep
from app.core.errores import NoAutenticado, Prohibido
from app.core.seguridad import ADMIN, INVITADO, USUARIO, Actor

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def actor_opcional(token: str | None = Depends(oauth2_scheme)) -> Actor | None:
    if not token:
        return None
    return await run_in_threadpool(dep.identidad.actor, token)


async def actor_requerido(actor: Actor | None = Depends(actor_opcional)) -> Actor:
    if actor is None:
        raise NoAutenticado("Se requiere iniciar sesión (token Bearer)")
    return actor


def solo(*tipos: str):
    async def _dependencia(actor: Actor = Depends(actor_requerido)) -> Actor:
        if actor.tipo not in tipos:
            raise Prohibido("Tu rol no tiene acceso a esta operación")
        return actor
    return _dependencia


solo_admin = solo(ADMIN)
solo_usuario = solo(USUARIO)
solo_invitado = solo(INVITADO)
cuenta = solo(ADMIN, USUARIO)
cualquiera = solo(ADMIN, USUARIO, INVITADO)

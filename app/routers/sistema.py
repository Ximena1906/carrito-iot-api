"""Salud del servicio y autenticación (login, logout y «quién soy»)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import dependencias as dep
from app.core.acceso import actor_requerido, cuenta
from app.core.errores import BaseDatosNoDisponible
from app.core.seguridad import Actor
from app.models.esquemas import Mensaje, TokenSesion, Yo

router = APIRouter()
EAUTH = {401: {"model": Mensaje, "description": "Sin sesión, token inválido, expirado o cerrado"}}


@router.get("/health", tags=["Salud"], summary="Disponibilidad de la API",
            description="Comprueba que el servidor FastAPI en AWS responde. No consulta la base de datos.")
def salud_api():
    return {
        "estado": "disponible",
        "servicio": dep.settings.app_nombre,
        "version": dep.settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@router.get("/health/db", tags=["Salud"], summary="Disponibilidad de Amazon RDS",
            description="Diagnóstico seguro: ejecuta `SELECT 1` en RDS desde el backend. "
                        "Responde 200 si la base está disponible y 503 si no lo está. No expone credenciales.",
            responses={503: {"description": "Base de datos no disponible"}})
async def salud_bd():
    try:
        latencia = await run_in_threadpool(dep.db.verificar)
    except BaseDatosNoDisponible:
        return JSONResponse(status_code=503, content={"estado": "no_disponible", "base_datos": "Amazon RDS"})
    return {"estado": "disponible", "base_datos": "Amazon RDS", "latencia_ms": latencia}


@router.post("/auth/login", response_model=TokenSesion, tags=["Autenticación"], summary="Iniciar sesión",
             description=(
                 "Envía `username` y `password` (form-data). Cuentas de la tabla **usuarios** con rol "
                 "**admin** (empresa) o **usuario** (comprador). La contraseña se compara contra un hash "
                 "PBKDF2. Tras 5 intentos fallidos la cuenta se bloquea 5 minutos (429). El Invitado no inicia "
                 "sesión aquí: usa `POST /invitados/sesiones`.\n\nEn Swagger usa el botón *Authorize*."),
             responses={**EAUTH, 429: {"model": Mensaje, "description": "Demasiados intentos"}})
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    # Por IP + cuenta: frena la fuerza bruta sin bloquear a todo un salón que comparte la misma IP pública.
    ip = request.client.host if request.client else "-"
    dep.limite_login.verificar(f"login:{ip}:{form.username.strip().lower()[:40]}")
    return await run_in_threadpool(dep.usuarios.login, form.username.strip(), form.password)


@router.post("/auth/logout", response_model=Mensaje, tags=["Autenticación"], summary="Cerrar sesión",
             description="Invalida TODOS los tokens emitidos para la cuenta (version_token + 1) y corta sus "
                         "suscripciones WebSocket.", responses=EAUTH)
async def logout(actor: Actor = Depends(cuenta)):
    await run_in_threadpool(dep.usuarios.logout, actor)
    await dep.conexiones.revalidar(id_usuario=actor.id)
    return Mensaje(detail="Sesión cerrada")


@router.get("/auth/yo", response_model=Yo, tags=["Autenticación"], summary="Identidad de la sesión actual",
            description="Devuelve el actor del token después de revalidarlo contra RDS.", responses=EAUTH)
async def yo(actor: Actor = Depends(actor_requerido)):
    return Yo(tipo=actor.tipo, id=actor.id, nombre=actor.nombre, usuario=actor.usuario,
              id_vehiculo_invitado=actor.id_vehiculo_invitado)

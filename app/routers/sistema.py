"""Salud del servicio y autenticación."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import dependencias as dep
from app.core.errores import BaseDatosNoDisponible
from app.models.esquemas import Token

router = APIRouter()


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


@router.post("/auth/login", response_model=Token, tags=["Autenticación"], summary="Obtener token de acceso",
             description="Envía usuario y contraseña (form-data). Roles: **operador** (movimientos y DEMO) y "
                         "**admin** (además crear, actualizar y eliminar). En Swagger usa el botón *Authorize*.",
             responses={401: {"description": "Credenciales incorrectas"}})
def login(form: OAuth2PasswordRequestForm = Depends()):
    rol = dep.auth.validar_credenciales(form.username, form.password)
    if rol is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos",
                            headers={"WWW-Authenticate": "Bearer"})
    token, segundos = dep.auth.crear_token(form.username, rol)
    return Token(access_token=token, rol=rol, expira_en_segundos=segundos)

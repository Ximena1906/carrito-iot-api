"""Excepciones de dominio y su traducción a respuestas HTTP."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("carrito_iot")


class ErrorAplicacion(Exception):
    status_code = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class SolicitudInvalida(ErrorAplicacion):
    status_code = 400


class NoAutenticado(ErrorAplicacion):
    status_code = 401
class Prohibido(ErrorAplicacion):
    status_code = 403
class RecursoNoEncontrado(ErrorAplicacion):
    status_code = 404


class Conflicto(ErrorAplicacion):
    status_code = 409


class DemasiadasSolicitudes(ErrorAplicacion):
    status_code = 429
class BaseDatosNoDisponible(ErrorAplicacion):
    status_code = 503


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorAplicacion)
    async def _error_aplicacion(_: Request, exc: ErrorAplicacion):
        cabeceras = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensaje}, headers=cabeceras)

    @app.exception_handler(Exception)
    async def _error_inesperado(_: Request, exc: Exception):
        # Se registra el detalle en el servidor, nunca se expone al cliente.
        log.exception("Error no controlado: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

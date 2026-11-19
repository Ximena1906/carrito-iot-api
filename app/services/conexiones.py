"""Revalidación de suscripciones WebSocket.

Cuando cambian los permisos (asignación, liberación, cambio de estado,
revocación de soporte, logout o desactivación de una cuenta) se vuelve a
comprobar CADA suscripción afectada con el mismo criterio de la API REST.
Las que ya no estén autorizadas se cierran (código 4403) para que no sigan
recibiendo eventos de unidades ajenas.
"""
import logging

from fastapi.concurrency import run_in_threadpool

from app.core.errores import ErrorAplicacion
from app.services.autorizacion import ServicioAutorizacion
from app.services.identidad import ServicioIdentidad
from app.websocket.gestor import GestorWebSocket

log = logging.getLogger("carrito_iot.ws")


class ServicioConexiones:
    def __init__(self, identidad: ServicioIdentidad, autorizacion: ServicioAutorizacion, gestor: GestorWebSocket):
        self._identidad = identidad
        self._authz = autorizacion
        self._gestor = gestor

    async def revalidar(self, id_vehiculo: int | None = None, id_usuario: int | None = None) -> int:
        revocadas = 0
        for ws, meta in self._gestor.suscriptores(id_vehiculo):
            if id_usuario is not None and meta.get("id_usuario") != id_usuario:
                continue
            try:
                actor = await run_in_threadpool(self._identidad.actor, meta["token"])
                await run_in_threadpool(self._authz.para_lectura, actor, meta["id_vehiculo"])
            except ErrorAplicacion as exc:
                await self._gestor.revocar(ws, f"Acceso revocado: {exc.mensaje}")
                revocadas += 1
        if revocadas:
            log.info("Suscripciones WSS revocadas: %s", revocadas)
        return revocadas

    async def cerrar_clave(self, clave: str, motivo: str) -> None:
        for ws, _ in self._gestor.suscriptores(clave=clave):
            await self._gestor.revocar(ws, motivo, codigo=4401)

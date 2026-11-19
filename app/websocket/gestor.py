"""Gestión de clientes WebSocket agrupados por vehículo.

Cada vehículo tiene su propio conjunto de clientes; un evento solo se envía a
los clientes del vehículo correspondiente. Se distingue entre clientes
autenticados (navegador, cliente WSS externo) y el dispositivo físico (ESP32).
Desde 4.3 cada cliente guarda su identidad (meta) para poder revocar su
suscripción cuando pierde permisos sobre la unidad.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import WebSocket

log = logging.getLogger("carrito_iot.ws")


def crear_evento(tipo: str, id_vehiculo: int, **datos) -> dict:
    return {
        "tipo": tipo,
        "id_evento": uuid.uuid4().hex,
        "id_vehiculo": id_vehiculo,
        **datos,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }


class GestorWebSocket:
    TIEMPO_ENVIO_S = 5

    def __init__(self):
        self._clientes: dict[int, set[WebSocket]] = {}
        self._dispositivos: dict[int, set[WebSocket]] = {}
        self._meta: dict[WebSocket, dict] = {}
        self._lock = asyncio.Lock()

    async def conectar(self, id_vehiculo: int, ws: WebSocket, es_dispositivo: bool, meta: dict | None = None) -> None:
        async with self._lock:
            self._clientes.setdefault(id_vehiculo, set()).add(ws)
            if es_dispositivo:
                self._dispositivos.setdefault(id_vehiculo, set()).add(ws)
            elif meta:
                self._meta[ws] = {**meta, "id_vehiculo": id_vehiculo}

    async def desconectar(self, id_vehiculo: int, ws: WebSocket) -> bool:
        """Retira al cliente. Devuelve True si era el último dispositivo del vehículo."""
        async with self._lock:
            self._clientes.get(id_vehiculo, set()).discard(ws)
            self._meta.pop(ws, None)
            dispositivos = self._dispositivos.get(id_vehiculo, set())
            era_dispositivo = ws in dispositivos
            dispositivos.discard(ws)
            return era_dispositivo and not dispositivos

    def dispositivo_conectado(self, id_vehiculo: int) -> bool:
        return bool(self._dispositivos.get(id_vehiculo))

    def total_clientes(self, id_vehiculo: int) -> int:
        return len(self._clientes.get(id_vehiculo, ()))

    def total_conexiones(self) -> int:
        return sum(len(c) for c in self._clientes.values())

    def suscriptores(self, id_vehiculo: int | None = None, clave: str | None = None) -> list[tuple[WebSocket, dict]]:
        """Clientes autenticados (no dispositivos), filtrados por unidad y/o identidad."""
        return [(ws, m) for ws, m in list(self._meta.items())
                if (id_vehiculo is None or m["id_vehiculo"] == id_vehiculo)
                and (clave is None or m.get("clave") == clave)]

    async def revocar(self, ws: WebSocket, motivo: str, codigo: int = 4403) -> None:
        """Avisa al cliente y cierra su suscripción (deja de recibir eventos de la unidad)."""
        meta = self._meta.get(ws)
        if meta is None:
            return
        await self.desconectar(meta["id_vehiculo"], ws)
        try:
            await ws.send_json(crear_evento("acceso_revocado", meta["id_vehiculo"], motivo=motivo))
            await ws.close(code=codigo, reason=motivo[:120])
        except Exception:
            pass

    async def _enviar(self, ws: WebSocket, mensaje: dict) -> bool:
        try:
            await asyncio.wait_for(ws.send_json(mensaje), timeout=self.TIEMPO_ENVIO_S)
            return True
        except Exception:
            return False

    async def publicar(self, id_vehiculo: int, mensaje: dict) -> int:
        """Envía el evento a todos los clientes del vehículo. Devuelve cuántos lo recibieron."""
        destinatarios = list(self._clientes.get(id_vehiculo, ()))
        if not destinatarios:
            return 0
        resultados = await asyncio.gather(*(self._enviar(ws, mensaje) for ws in destinatarios))
        for ws, ok in zip(destinatarios, resultados):
            if not ok:  # cliente caído: se retira sin afectar a los demás
                await self.desconectar(id_vehiculo, ws)
        enviados = sum(resultados)
        log.info("Evento %s vehículo %s -> %s cliente(s)", mensaje.get("tipo"), id_vehiculo, enviados)
        return enviados

"""Pruebas comerciales de INVITADO sobre unidades de exhibición.

* Reserva EXCLUSIVA: la base de datos impide dos sesiones activas en la misma
  unidad (UNIQUE sesiones_invitado.reserva_vehiculo).
* Tiempo máximo (INVITADO_SEGUNDOS), comandos reducidos (capacidades con
  permitido_invitado) y duración por movimiento limitada.
* Cierre automático y SEGURO: al expirar, al cerrar la sesión o si se pierde la
  conexión WSS más de INVITADO_GRACIA_DESCONEXION_S, se cancela la DEMO, se
  envía DETENER (origen SISTEMA), se publica `sesion_invitado` y se cierran
  sus suscripciones.
* Nunca se ofrecen unidades vendidas: solo estado «exhibicion».
"""
import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errores import Conflicto, ErrorAplicacion, RecursoNoEncontrado
from app.core.seguridad import Actor, ServicioAutenticacion
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.auditoria import ServicioAuditoria
from app.services.conexiones import ServicioConexiones
from app.services.control import ServicioControl
from app.websocket.gestor import GestorWebSocket, crear_evento

log = logging.getLogger("carrito_iot.invitados")


class ServicioInvitados:
    def __init__(self, settings: Settings, sp: ProcedimientosAdmin, auth: ServicioAutenticacion,
                 control: ServicioControl, gestor: GestorWebSocket, conexiones: ServicioConexiones,
                 auditoria: ServicioAuditoria):
        self._s = settings
        self._sp = sp
        self._auth = auth
        self._control = control
        self._gestor = gestor
        self._conexiones = conexiones
        self._aud = auditoria
        self._activas: dict[str, tuple[int, float]] = {}
        self._gracia: dict[str, asyncio.Task] = {}

    def _comandos_permitidos(self, id_modelo: int) -> list[dict]:
        return [{"nombre": c["nombre"], "codigo": c["codigo"], "tipo": c["tipo"]}
                for c in self._sp.capacidades_listar(id_modelo)
                if c["activo"] and (c["permitido_invitado"] or c["nombre"] == "DETENER")]

    # ------------------------------------------------------------- inicio
    async def iniciar(self, id_vehiculo: int) -> dict:
        unidad = await run_in_threadpool(self._sp.unidad_obtener, id_vehiculo)
        if unidad is None or unidad["estado_comercial"] != "exhibicion" or not unidad["activo"]:
            await self._aud.aregistrar(None, "iniciar_prueba", "unidad", id_vehiculo, "rechazado", "no es de exhibición",
                                       actor_tipo="invitado")
            raise RecursoNoEncontrado("La unidad no está disponible para pruebas de Invitado")
        if self._control.ocupada_por_otro(id_vehiculo, None):
            raise Conflicto("La unidad está siendo usada por la empresa en este momento. Intenta en unos segundos.")
        codigo = secrets.token_hex(16)
        segundos = self._s.invitado_segundos
        try:
            fila = await run_in_threadpool(self._sp.invitado_iniciar, codigo, id_vehiculo, segundos)
        except Conflicto:
            activa = await run_in_threadpool(self._sp.invitado_activa_vehiculo, id_vehiculo)
            espera = activa["segundos_restantes"] if activa else 0
            await self._aud.aregistrar(None, "iniciar_prueba", "unidad", id_vehiculo, "rechazado",
                                       "unidad ocupada por otra sesión", actor_tipo="invitado")
            raise Conflicto(f"La unidad está ocupada por otra prueba. Se libera en {espera} s.")
        expira = datetime.now(timezone.utc) + timedelta(seconds=int(fila["segundos_restantes"]))
        token, restantes = self._auth.token_invitado(codigo, id_vehiculo, expira)
        self._activas[codigo] = (id_vehiculo, time.monotonic() + restantes)
        await self._aud.aregistrar(None, "iniciar_prueba", "sesion_invitado", fila["id_sesion"],
                                   detalle=f"unidad={id_vehiculo} segundos={restantes}", actor_tipo="invitado",
                                   actor_nombre="Invitado")
        await self._gestor.publicar(id_vehiculo, crear_evento("sesion_invitado", id_vehiculo, estado="iniciada",
                                                               segundos_restantes=restantes))
        return {"access_token": token, "token_type": "bearer", "rol": "invitado", "expira_en_segundos": restantes,
                "id_vehiculo": id_vehiculo, "unidad": unidad["nombre"], "modelo": unidad["modelo"],
                "comandos_permitidos": self._comandos_permitidos(unidad["id_modelo"]),
                "duracion_max_ms": self._s.invitado_duracion_max_ms}

    def info(self, actor: Actor) -> dict:
        fila = self._sp.invitado_obtener(actor.codigo_sesion)
        unidad = self._sp.unidad_obtener(actor.id_vehiculo_invitado)
        return {"id_vehiculo": actor.id_vehiculo_invitado, "unidad": unidad["nombre"], "modelo": unidad["modelo"],
                "segundos_restantes": int(fila["segundos_restantes"]), "vigente": fila["vigente"],
                "comandos_permitidos": self._comandos_permitidos(unidad["id_modelo"]),
                "duracion_max_ms": self._s.invitado_duracion_max_ms}

    def segundos_restantes(self, actor: Actor) -> int:
        fila = self._sp.invitado_obtener(actor.codigo_sesion)
        return int(fila["segundos_restantes"]) if fila else 0

    # -------------------------------------------------------------- final
    async def _efectos_fin(self, codigo: str, id_vehiculo: int, motivo: str) -> None:
        self._activas.pop(codigo, None)
        tarea = self._gracia.pop(codigo, None)
        if tarea and tarea is not asyncio.current_task():
            tarea.cancel()
        await self._control.detener_por_sistema(id_vehiculo, f"INVITADO_{motivo}")
        await self._gestor.publicar(id_vehiculo, crear_evento("sesion_invitado", id_vehiculo, estado="finalizada",
                                                               motivo=motivo))
        await self._conexiones.cerrar_clave(f"inv:{codigo}", f"Prueba finalizada ({motivo.lower()})")
        await self._aud.aregistrar(None, "finalizar_prueba", "sesion_invitado", codigo[:8],
                                   detalle=f"unidad={id_vehiculo} motivo={motivo}", actor_tipo="sistema"
                                   if motivo != "CERRADA" else "invitado", actor_nombre="Invitado")

    async def finalizar(self, codigo: str, id_vehiculo: int, motivo: str) -> bool:
        cerradas = await run_in_threadpool(self._sp.invitado_finalizar, codigo, motivo)
        if cerradas:
            await self._efectos_fin(codigo, id_vehiculo, motivo)
        else:
            self._activas.pop(codigo, None)
        return bool(cerradas)

    # --------------------------------------------- conexión / desconexión
    def al_conectar(self, actor: Actor) -> None:
        tarea = self._gracia.pop(actor.codigo_sesion, None)
        if tarea:
            tarea.cancel()
        if actor.codigo_sesion not in self._activas:
            restantes = self.segundos_restantes(actor)
            self._activas[actor.codigo_sesion] = (actor.id_vehiculo_invitado, time.monotonic() + restantes)

    def al_desconectar(self, actor: Actor) -> None:
        if self._gestor.suscriptores(clave=actor.clave) or actor.codigo_sesion not in self._activas:
            return
        self._gracia[actor.codigo_sesion] = asyncio.create_task(self._esperar_reconexion(actor))

    async def _esperar_reconexion(self, actor: Actor) -> None:
        try:
            await asyncio.sleep(self._s.invitado_gracia_desconexion_s)
        except asyncio.CancelledError:
            return
        if not self._gestor.suscriptores(clave=actor.clave) and actor.codigo_sesion in self._activas:
            log.info("Invitado sin conexión WSS: se cierra la prueba de la unidad %s", actor.id_vehiculo_invitado)
            await self.finalizar(actor.codigo_sesion, actor.id_vehiculo_invitado, "DESCONEXION")

    # --------------------------------------------------------- vigilancia
    async def vigilar(self) -> None:
        """Tarea de fondo: cierra sesiones vencidas (memoria cada 1 s; RDS cada 30 s)."""
        vueltas = 0
        while True:
            try:
                await asyncio.sleep(1)
                vueltas += 1
                ahora = time.monotonic()
                for codigo, (id_vehiculo, expira) in list(self._activas.items()):
                    if expira <= ahora:
                        await self.finalizar(codigo, id_vehiculo, "EXPIRADA")
                if vueltas % 30 == 1:  # también al arrancar: sesiones que vencieron con el servidor apagado
                    for fila in await run_in_threadpool(self._sp.invitado_expirar):
                        await self._efectos_fin(fila["codigo"], int(fila["id_vehiculo"]), "EXPIRADA")
            except asyncio.CancelledError:
                raise
            except ErrorAplicacion as exc:
                log.warning("Vigilancia de invitados: %s", exc.mensaje)
            except Exception as exc:
                log.exception("Vigilancia de invitados: %s", exc)

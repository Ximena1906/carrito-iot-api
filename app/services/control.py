"""Control del vehículo: movimientos individuales y ejecución de DEMO.

Reglas:
  * Movimiento individual: valida vehículo y comando -> sp_actualizar_estado +
    sp_registrar_historial en UNA transacción -> COMMIT -> evento WebSocket.
  * DEMO: lee sp_obtener_movimientos_demo -> evento de inicio, N eventos de paso
    temporizados (duracion_ms + pausa_ms) y evento de fin. Actualiza el estado
    pero NUNCA llama a sp_registrar_historial.
  * No se permiten dos DEMO simultáneas por vehículo. DETENER cancela la DEMO
    en curso y tiene prioridad.
  * 4.3: control EXCLUSIVO por sesión. Quien envía un comando «toma» la unidad
    durante CONTROL_EXCLUSIVO_S; otra sesión recibe 409 hasta que se libere.
    DETENER nunca se bloquea (seguridad física). El Invitado solo usa los
    comandos permitidos de su modelo y con duración limitada.
"""
import asyncio
import logging
import time

from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errores import Conflicto, Prohibido, SolicitudInvalida
from app.core.seguridad import Actor
from app.db.database import Database
from app.db.procedimientos import Fila, ProcedimientosAlmacenados
from app.services.catalogo import ServicioComandos, ServicioDemos, ServicioVehiculos
from app.websocket.gestor import GestorWebSocket, crear_evento

log = logging.getLogger("carrito_iot.control")

COMANDO_DETENER = "DETENER"


class EjecutorDemos:
    """Ejecuta las DEMO como tareas asíncronas independientes (no bloquean la API)."""

    def __init__(self, sp: ProcedimientosAlmacenados, gestor: GestorWebSocket):
        self._sp = sp
        self._gestor = gestor
        self._tareas: dict[int, asyncio.Task] = {}
        self._info: dict[int, dict] = {}
        self._lock = asyncio.Lock()

    def demo_en_curso(self, id_vehiculo: int) -> dict | None:
        tarea = self._tareas.get(id_vehiculo)
        if tarea and not tarea.done():
            return self._info.get(id_vehiculo)
        return None

    async def iniciar(self, id_vehiculo: int, demo: Fila, pasos: list[Fila], id_detener: int | None,
                      origen: str) -> None:
        async with self._lock:
            if self.demo_en_curso(id_vehiculo):
                raise Conflicto("Ya hay una DEMO en ejecución para este vehículo")
            self._info[id_vehiculo] = {
                "id_demo": demo["id_demo"], "nombre": demo["nombre"], "total_pasos": len(pasos),
                "motivo_cancelacion": None,
            }
            self._tareas[id_vehiculo] = asyncio.create_task(
                self._ejecutar(id_vehiculo, demo, pasos, id_detener, origen),
                name=f"demo-v{id_vehiculo}-d{demo['id_demo']}",
            )

    async def cancelar(self, id_vehiculo: int, motivo: str) -> dict | None:
        """Cancela la DEMO en curso y espera a que termine. Devuelve su info o None si no había."""
        tarea = self._tareas.get(id_vehiculo)
        if not tarea or tarea.done():
            return None
        info = self._info[id_vehiculo]
        info["motivo_cancelacion"] = motivo
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass
        return info

    async def cancelar_todas(self) -> None:
        for id_vehiculo in list(self._tareas):
            await self.cancelar(id_vehiculo, "APAGADO_SERVIDOR")

    async def _ejecutar(self, id_vehiculo: int, demo: Fila, pasos: list[Fila], id_detener: int | None,
                        origen: str) -> None:
        base = {"id_demo": demo["id_demo"], "nombre": demo["nombre"], "total_pasos": len(pasos)}
        try:
            await self._gestor.publicar(id_vehiculo, crear_evento("demo_inicio", id_vehiculo, **base, origen=origen))
            for indice, paso in enumerate(pasos, start=1):
                conectado = self._gestor.dispositivo_conectado(id_vehiculo)
                # Solo estado: los pasos de DEMO NO se registran en historial_comandos.
                await run_in_threadpool(self._sp.actualizar_estado, id_vehiculo, paso["id_comando"], conectado)
                await self._gestor.publicar(id_vehiculo, crear_evento(
                    "demo_paso", id_vehiculo,
                    id_demo=demo["id_demo"], paso=indice, total_pasos=len(pasos), orden=paso["orden"],
                    id_comando=paso["id_comando"], comando=paso["comando"], codigo=paso["codigo"],
                    duracion_ms=paso["duracion_ms"], pausa_ms=paso["pausa_ms"],
                ))
                await asyncio.sleep((paso["duracion_ms"] + paso["pausa_ms"]) / 1000)
            await self._gestor.publicar(id_vehiculo, crear_evento("demo_fin", id_vehiculo, **base))
        except asyncio.CancelledError:
            motivo = self._info.get(id_vehiculo, {}).get("motivo_cancelacion") or "CANCELADA"
            await self._finalizar_seguro(id_vehiculo, id_detener)
            await self._gestor.publicar(id_vehiculo, crear_evento("demo_cancelada", id_vehiculo, **base, motivo=motivo))
        except Exception as exc:  # fallo de RDS u otro: se termina de forma controlada
            log.exception("Error durante la DEMO: %s", exc)
            await self._finalizar_seguro(id_vehiculo, id_detener)
            await self._gestor.publicar(id_vehiculo, crear_evento(
                "error", id_vehiculo, contexto="demo", id_demo=demo["id_demo"],
                mensaje="La DEMO se detuvo por un error del servidor",
            ))
            await self._gestor.publicar(id_vehiculo, crear_evento("demo_cancelada", id_vehiculo, **base, motivo="ERROR"))

    async def _finalizar_seguro(self, id_vehiculo: int, id_detener: int | None) -> None:
        if id_detener is None:
            return
        try:
            await run_in_threadpool(
                self._sp.actualizar_estado, id_vehiculo, id_detener, self._gestor.dispositivo_conectado(id_vehiculo)
            )
        except Exception:
            log.warning("No se pudo registrar DETENER al finalizar la DEMO del vehículo %s", id_vehiculo)


class ServicioControl:
    def __init__(self, settings: Settings, db: Database, sp: ProcedimientosAlmacenados,
                 vehiculos: ServicioVehiculos, comandos: ServicioComandos, demos: ServicioDemos,
                 gestor: GestorWebSocket, ejecutor: EjecutorDemos):
        self._s = settings
        self._db = db
        self._sp = sp
        self._vehiculos = vehiculos
        self._comandos = comandos
        self._demos = demos
        self._gestor = gestor
        self._ejecutor = ejecutor
        self._exclusivo: dict[int, tuple[str, float]] = {}

    # --------------------------------------------------- control exclusivo
    def ocupada_por_otro(self, id_vehiculo: int, clave: str | None) -> bool:
        actual = self._exclusivo.get(id_vehiculo)
        return bool(actual and actual[0] != clave and actual[1] > time.monotonic())

    def _tomar(self, id_vehiculo: int, clave: str, es_detener: bool, extra_s: float = 0) -> None:
        if self.ocupada_por_otro(id_vehiculo, clave):
            if es_detener:
                return  # DETENER siempre pasa, pero no roba el control
            raise Conflicto("La unidad está siendo controlada por otra sesión. Intenta de nuevo en unos segundos.")
        self._exclusivo[id_vehiculo] = (clave, time.monotonic() + self._s.control_exclusivo_s + extra_s)

    def liberar(self, id_vehiculo: int, clave: str | None = None) -> None:
        actual = self._exclusivo.get(id_vehiculo)
        if actual and (clave is None or actual[0] == clave):
            self._exclusivo.pop(id_vehiculo, None)

    # ------------------------------------------------- movimiento individual
    def _persistir_movimiento(self, id_vehiculo: int, id_comando: int, conectado: bool, origen: str) -> None:
        with self._db.transaccion() as conn:
            self._sp.actualizar_estado(id_vehiculo, id_comando, conectado, conn=conn)
            self._sp.registrar_historial(id_vehiculo, id_comando, origen, conn=conn)

    async def ejecutar_movimiento(self, id_vehiculo: int, solicitud, actor: Actor | None = None,
                                  nivel: str | None = None, capacidades: dict | None = None) -> dict:
        await run_in_threadpool(self._vehiculos.obtener_activo, id_vehiculo)
        comando = await run_in_threadpool(
            self._comandos.resolver_activo, id_vehiculo, solicitud.comando, solicitud.codigo
        )
        es_detener = comando["nombre"] == COMANDO_DETENER
        tope = self._s.duracion_max_ms
        origen = solicitud.origen
        if capacidades is not None:  # capacidades reales del modelo de la unidad
            cap = capacidades.get(comando["codigo"])
            if cap is None or not cap["activo"]:
                raise Conflicto(f"El modelo de esta unidad no admite el comando {comando['nombre']}")
            tope = min(tope, int(cap["duracion_max_ms"]))
            if actor is not None and actor.es_invitado:
                if not cap["permitido_invitado"] and not es_detener:
                    raise Prohibido(f"El comando {comando['nombre']} no está disponible en la prueba de Invitado")
                tope = min(tope, self._s.invitado_duracion_max_ms)
        if actor is not None:
            self._tomar(id_vehiculo, actor.clave, es_detener)
            origen = "INVITADO" if actor.es_invitado else ("SOPORTE" if nivel == "soporte" else origen)

        demo_cancelada = False
        if self._ejecutor.demo_en_curso(id_vehiculo):
            if not es_detener:
                raise Conflicto("Hay una DEMO en ejecución: use DETENER o cancele la DEMO antes de mover")
            await self._ejecutor.cancelar(id_vehiculo, "DETENER")
            demo_cancelada = True

        duracion = min(solicitud.duracion_ms or self._s.duracion_default_ms, tope)
        conectado = self._gestor.dispositivo_conectado(id_vehiculo)

        # Transacción confirmada en RDS ANTES de notificar por WebSocket
        await run_in_threadpool(self._persistir_movimiento, id_vehiculo, comando["id_comando"], conectado, origen)

        evento = crear_evento(
            "movimiento", id_vehiculo,
            id_comando=comando["id_comando"], comando=comando["nombre"], codigo=comando["codigo"],
            duracion_ms=duracion, origen=origen,
        )
        enviados = await self._gestor.publicar(id_vehiculo, evento)
        return {
            "id_evento": evento["id_evento"], "id_vehiculo": id_vehiculo,
            "id_comando": comando["id_comando"], "comando": comando["nombre"], "codigo": comando["codigo"],
            "duracion_ms": duracion, "origen": origen, "timestamp": evento["timestamp"],
            "clientes_notificados": enviados, "dispositivo_conectado": conectado,
            "demo_cancelada": demo_cancelada,
        }

    # ------------------------------------------------------------------ DEMO
    async def iniciar_demo(self, id_vehiculo: int, id_demo: int, origen: str, actor: Actor | None = None,
                           segundos_disponibles: int | None = None) -> dict:
        await run_in_threadpool(self._vehiculos.obtener_activo, id_vehiculo)
        demo = await run_in_threadpool(self._demos.obtener, id_vehiculo, id_demo)
        if not demo["activo"]:
            raise Conflicto(f"La DEMO {id_demo} está inactiva")
        pasos = await run_in_threadpool(self._sp.obtener_movimientos_demo, id_demo)
        if not pasos:
            raise SolicitudInvalida(f"La DEMO {id_demo} no tiene movimientos registrados")
        total_s = sum(p["duracion_ms"] + p["pausa_ms"] for p in pasos) / 1000
        if segundos_disponibles is not None and total_s > segundos_disponibles:
            raise Conflicto(f"La DEMO dura {total_s:.0f} s y a tu sesión le quedan {segundos_disponibles} s")
        detener = await run_in_threadpool(self._comandos.buscar_por_nombre, id_vehiculo, COMANDO_DETENER)
        if actor is not None:
            self._tomar(id_vehiculo, actor.clave, False, extra_s=total_s)
            origen = "INVITADO" if actor.es_invitado else origen
        await self._ejecutor.iniciar(id_vehiculo, demo, pasos, detener["id_comando"] if detener else None, origen)
        return {"estado": "en_curso", "id_vehiculo": id_vehiculo, "id_demo": id_demo,
                "nombre": demo["nombre"], "total_pasos": len(pasos)}

    async def detener_por_sistema(self, id_vehiculo: int, motivo: str) -> None:
        """Detención segura al terminar una sesión (expiración, cierre o desconexión)."""
        try:
            await self._ejecutor.cancelar(id_vehiculo, motivo)
            detener = await run_in_threadpool(self._comandos.buscar_por_nombre, id_vehiculo, COMANDO_DETENER)
            if detener is None:
                return
            conectado = self._gestor.dispositivo_conectado(id_vehiculo)
            await run_in_threadpool(self._persistir_movimiento, id_vehiculo, detener["id_comando"], conectado,
                                    "SISTEMA")
            await self._gestor.publicar(id_vehiculo, crear_evento(
                "movimiento", id_vehiculo, id_comando=detener["id_comando"], comando=detener["nombre"],
                codigo=detener["codigo"], duracion_ms=0, origen="SISTEMA", motivo=motivo,
            ))
        except Exception as exc:
            log.warning("No se pudo detener la unidad %s (%s): %s", id_vehiculo, motivo, exc)
        finally:
            self.liberar(id_vehiculo)

    async def cancelar_demo(self, id_vehiculo: int) -> dict:
        await run_in_threadpool(self._vehiculos.obtener, id_vehiculo)
        info = await self._ejecutor.cancelar(id_vehiculo, "CANCELADA_POR_USUARIO")
        if info is None:
            return {"estado": "sin_demo", "id_vehiculo": id_vehiculo}
        return {"estado": "cancelada", "id_vehiculo": id_vehiculo, "id_demo": info["id_demo"],
                "nombre": info["nombre"], "total_pasos": info["total_pasos"]}

    async def demo_en_curso(self, id_vehiculo: int) -> dict:
        await run_in_threadpool(self._vehiculos.obtener, id_vehiculo)
        info = self._ejecutor.demo_en_curso(id_vehiculo)
        if info is None:
            return {"estado": "sin_demo", "id_vehiculo": id_vehiculo}
        return {"estado": "en_curso", "id_vehiculo": id_vehiculo, "id_demo": info["id_demo"],
                "nombre": info["nombre"], "total_pasos": info["total_pasos"]}

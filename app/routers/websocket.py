"""Canal WebSocket por unidad: /ws/vehiculos/{id_vehiculo}?token=...

* Navegador o cliente WSS externo: `token` = JWT de la sesión (Administrador,
  Usuario o Invitado). Se autoriza con las MISMAS reglas que la API REST: solo
  quien puede consultar la unidad recibe sus eventos.
* Dispositivo (ESP32): `token` = DISPOSITIVO_TOKEN, válido solo para la unidad
  DISPOSITIVO_ID_VEHICULO. Su presencia marca `conectado = 1`.
* Sin token o sin permiso: se envía un evento `error` y se cierra con código
  4401 (sin autenticación) o 4403/4404 (sin autorización).
* Si los permisos cambian (reasignación, soporte revocado, logout...), el
  servidor cierra la suscripción con `acceso_revocado` + código 4403.
CORS no aplica a WebSocket: por eso la autorización se hace aquí.
"""
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.errores import ErrorAplicacion
from app.websocket.gestor import crear_evento

router = APIRouter()
log = logging.getLogger("carrito_iot.ws")


async def _actualizar_conexion(id_vehiculo: int, conectado: bool) -> None:
    """Conserva el último comando y solo cambia el campo `conectado`."""
    try:
        actual = await run_in_threadpool(dep.sp.obtener_estado, id_vehiculo)
        id_comando = actual["id_comando"] if actual else None
        await run_in_threadpool(dep.sp.actualizar_estado, id_vehiculo, id_comando, conectado)
    except Exception:
        log.warning("No se pudo actualizar 'conectado' del vehículo %s", id_vehiculo)


async def _estado_inicial(id_vehiculo: int) -> dict:
    estado = await run_in_threadpool(dep.estado.obtener_estado, id_vehiculo)
    en_curso = dep.ejecutor_demos.demo_en_curso(id_vehiculo)
    return crear_evento(
        "estado_inicial", id_vehiculo,
        vehiculo=estado.get("vehiculo"), id_comando=estado.get("id_comando"), comando=estado.get("comando"),
        codigo=estado.get("codigo"),
        fecha_actualizacion=estado["fecha_actualizacion"].isoformat() if estado.get("fecha_actualizacion") else None,
        dispositivo_conectado=dep.gestor_ws.dispositivo_conectado(id_vehiculo),
        demo_en_curso=en_curso["id_demo"] if en_curso else None,
    )


async def _rechazar(websocket: WebSocket, id_vehiculo: int, codigo_http: int, mensaje: str) -> None:
    await websocket.accept()
    await websocket.send_json(crear_evento("error", id_vehiculo, codigo=codigo_http, mensaje=mensaje))
    await websocket.close(code=4000 + codigo_http, reason=mensaje[:120])


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int, token: str | None = Query(default=None)):
    es_dispositivo = dep.auth.token_dispositivo_valido(token, id_vehiculo)
    actor = None
    if not es_dispositivo:
        if not token:
            await _rechazar(websocket, id_vehiculo, 401, "Se requiere token: /ws/vehiculos/{id}?token=<JWT>")
            return
        try:
            actor = await run_in_threadpool(dep.identidad.actor, token)
            await run_in_threadpool(dep.autorizacion.para_lectura, actor, id_vehiculo)
        except ErrorAplicacion as exc:
            await _rechazar(websocket, id_vehiculo, exc.status_code, exc.mensaje)
            return
    else:
        try:
            await run_in_threadpool(dep.vehiculos.obtener, id_vehiculo)
        except ErrorAplicacion as exc:
            await _rechazar(websocket, id_vehiculo, exc.status_code, exc.mensaje)
            return

    await websocket.accept()
    meta = None if es_dispositivo else {
        "token": token, "clave": actor.clave, "tipo": actor.tipo,
        "id_usuario": None if actor.es_invitado else actor.id,
    }
    await dep.gestor_ws.conectar(id_vehiculo, websocket, es_dispositivo, meta)
    if actor is not None and actor.es_invitado:
        dep.invitados.al_conectar(actor)
    log.info("WS conectado vehículo=%s %s", id_vehiculo, "dispositivo" if es_dispositivo else actor.tipo)
    try:
        if es_dispositivo:
            await _actualizar_conexion(id_vehiculo, True)
            await dep.gestor_ws.publicar(id_vehiculo, crear_evento("dispositivo", id_vehiculo, conectado=True))
        await websocket.send_json(await _estado_inicial(id_vehiculo))
        while True:
            texto = await websocket.receive_text()
            try:
                mensaje = json.loads(texto)
            except ValueError:
                await websocket.send_json(crear_evento("error", id_vehiculo, mensaje="JSON inválido"))
                continue
            tipo = mensaje.get("tipo") if isinstance(mensaje, dict) else None
            if tipo == "ping":
                await websocket.send_json(crear_evento("pong", id_vehiculo))
            elif tipo == "ack" and es_dispositivo:
                # Confirmación del ESP32: indica recepción del evento, no movimiento físico comprobado.
                await dep.gestor_ws.publicar(id_vehiculo, crear_evento(
                    "ack_dispositivo", id_vehiculo,
                    id_evento_ref=str(mensaje.get("id_evento_ref", ""))[:64],
                    resultado=str(mensaje.get("resultado", ""))[:30],
                ))
            # Cualquier otro mensaje se ignora: las órdenes solo entran por POST autorizado.
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("WS vehículo %s cerrado por error: %s", id_vehiculo, exc)
    finally:
        await dep.gestor_ws.desconectar(id_vehiculo, websocket)
        if es_dispositivo and not dep.gestor_ws.dispositivo_conectado(id_vehiculo):
            await _actualizar_conexion(id_vehiculo, False)
            await dep.gestor_ws.publicar(id_vehiculo, crear_evento("dispositivo", id_vehiculo, conectado=False))
        if actor is not None and actor.es_invitado:
            dep.invitados.al_desconectar(actor)
        log.info("WS desconectado vehículo=%s", id_vehiculo)

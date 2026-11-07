"""Canal WebSocket por vehículo: /ws/vehiculos/{id_vehiculo}

* Cliente de monitoreo (navegador, Thunder Client): se conecta sin token.
* Dispositivo (ESP32): se conecta con ?token=<DISPOSITIVO_TOKEN>. Su presencia
  marca `conectado = 1` en estado_vehiculo; al desconectarse vuelve a 0.
"""
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
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


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int, token: str | None = Query(default=None)):
    es_dispositivo = token is not None
    if es_dispositivo and not dep.auth.token_dispositivo_valido(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token de dispositivo inválido")
        return
    try:
        await run_in_threadpool(dep.vehiculos.obtener, id_vehiculo)
    except ErrorAplicacion as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.mensaje[:120])
        return

    await websocket.accept()
    await dep.gestor_ws.conectar(id_vehiculo, websocket, es_dispositivo)
    log.info("WS conectado vehículo=%s dispositivo=%s", id_vehiculo, es_dispositivo)
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
            # Cualquier otro mensaje se ignora: las órdenes solo entran por POST.
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("WS vehículo %s cerrado por error: %s", id_vehiculo, exc)
    finally:
        await dep.gestor_ws.desconectar(id_vehiculo, websocket)
        if es_dispositivo and not dep.gestor_ws.dispositivo_conectado(id_vehiculo):
            await _actualizar_conexion(id_vehiculo, False)
            await dep.gestor_ws.publicar(id_vehiculo, crear_evento("dispositivo", id_vehiculo, conectado=False))
        log.info("WS desconectado vehículo=%s dispositivo=%s", id_vehiculo, es_dispositivo)

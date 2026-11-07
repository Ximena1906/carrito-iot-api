"""Control del vehículo: movimiento individual y ejecución/cancelación de DEMO."""
from fastapi import APIRouter, Body, Depends, Path, status

from app import dependencias as dep
from app.core.seguridad import operador_o_admin
from app.models.esquemas import Mensaje, RespuestaDemo, RespuestaMovimiento, SolicitudDemo, SolicitudMovimiento

router = APIRouter(prefix="/vehiculos/{id_vehiculo}", tags=["Control"])

ID_V = Path(ge=1, description="Identificador del vehículo")
EAUTH = {401: {"model": Mensaje, "description": "Sin token o token inválido"},
         403: {"model": Mensaje, "description": "Rol sin permiso"}}
E404 = {404: {"model": Mensaje, "description": "Vehículo, comando o DEMO inexistente"}}
E409 = {409: {"model": Mensaje, "description": "Vehículo/comando inactivo o DEMO en ejecución"}}
E503 = {503: {"model": Mensaje, "description": "Base de datos no disponible"}}


@router.post("/movimientos", response_model=RespuestaMovimiento, summary="Ejecutar movimiento individual",
             description=(
                 "Valida que el vehículo exista y esté activo y que el comando exista, esté activo y pertenezca "
                 "al vehículo. Después ejecuta **`sp_actualizar_estado` + `sp_registrar_historial` en una sola "
                 "transacción**, confirma en RDS y publica el evento `movimiento` por WebSocket.\n\n"
                 "Indica `comando` (nombre) **o** `codigo`. `duracion_ms` es el tiempo máximo que el ESP32 "
                 "mantiene la salida activa (por defecto 1000 ms, máximo 10000 ms).\n\n"
                 "Si hay una DEMO en curso solo se acepta `DETENER`, que la cancela."),
             dependencies=[Depends(operador_o_admin)], responses={**EAUTH, **E404, **E409, **E503})
async def ejecutar_movimiento(solicitud: SolicitudMovimiento, id_vehiculo: int = ID_V):
    return await dep.control.ejecutar_movimiento(id_vehiculo, solicitud)


@router.post("/demos/{id_demo}/iniciar", response_model=RespuestaDemo, status_code=status.HTTP_202_ACCEPTED,
             summary="Iniciar DEMO",
             description=(
                 "Inicia una DEMO existente, activa y del vehículo. Lee **`sp_obtener_movimientos_demo`** y publica "
                 "por WebSocket `demo_inicio`, un `demo_paso` por movimiento (respetando `duracion_ms` + `pausa_ms`) "
                 "y `demo_fin`. Actualiza el estado con **`sp_actualizar_estado`** pero **no registra historial**.\n\n"
                 "Responde 202 de inmediato; la secuencia continúa en segundo plano. 409 si ya hay una DEMO en curso."),
             dependencies=[Depends(operador_o_admin)], responses={**EAUTH, **E404, **E409, **E503})
async def iniciar_demo(id_vehiculo: int = ID_V, id_demo: int = Path(ge=1),
                       solicitud: SolicitudDemo = Body(default_factory=SolicitudDemo)):
    return await dep.control.iniciar_demo(id_vehiculo, id_demo, solicitud.origen)


@router.post("/demos/cancelar", response_model=RespuestaDemo, summary="Cancelar DEMO en curso",
             description="Detiene de inmediato los pasos pendientes y publica `demo_cancelada` por WebSocket. "
                         "Si no hay DEMO en curso responde `estado: sin_demo`.",
             dependencies=[Depends(operador_o_admin)], responses={**EAUTH, **E404})
async def cancelar_demo(id_vehiculo: int = ID_V):
    return await dep.control.cancelar_demo(id_vehiculo)


@router.get("/demos/en-curso", response_model=RespuestaDemo, summary="¿Hay una DEMO en ejecución?",
            description="Consulta en memoria del servidor; no modifica datos.", responses=E404)
async def demo_en_curso(id_vehiculo: int = ID_V):
    return await dep.control.demo_en_curso(id_vehiculo)

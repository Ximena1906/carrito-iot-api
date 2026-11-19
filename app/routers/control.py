"""Control de la unidad: movimiento individual y ejecución/cancelación de DEMO.

Desde 4.3 cada solicitud valida: sesión vigente, autorización sobre la unidad
(propietario, soporte autorizado, empresa o Invitado con reserva), capacidades
del modelo, límites del Invitado y control exclusivo por sesión. DETENER
conserva la prioridad: nunca se bloquea por el control exclusivo.
"""
from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import actor_requerido
from app.core.seguridad import Actor
from app.models.esquemas import Mensaje, RespuestaDemo, RespuestaMovimiento, SolicitudDemo, SolicitudMovimiento

router = APIRouter(prefix="/vehiculos/{id_vehiculo}", tags=["Control"])
ID_V = Path(ge=1, description="Identificador de la unidad")
ERR = {401: {"model": Mensaje, "description": "Sin sesión, token inválido o prueba de Invitado terminada"},
       403: {"model": Mensaje, "description": "Sin permiso sobre la unidad o comando no permitido al Invitado"},
       404: {"model": Mensaje, "description": "Unidad, comando o DEMO inexistente (o unidad ajena)"},
       409: {"model": Mensaje, "description": "Unidad ocupada por otra sesión, inactiva o DEMO en ejecución"},
       429: {"model": Mensaje, "description": "Demasiados comandos seguidos"},
       503: {"model": Mensaje, "description": "Base de datos no disponible"}}


async def _control(actor: Actor, id_vehiculo: int):
    return await run_in_threadpool(dep.autorizacion.para_control, actor, id_vehiculo)


@router.post("/movimientos", response_model=RespuestaMovimiento, summary="Ejecutar movimiento individual",
             description=(
                 "Autoriza al actor sobre la unidad y valida que el comando esté habilitado y exista como "
                 "capacidad de su modelo. Después ejecuta **`sp_actualizar_estado` + `sp_registrar_historial` en "
                 "una sola transacción**, confirma en RDS y publica el evento `movimiento` por WebSocket SOLO a los "
                 "suscriptores autorizados de esa unidad.\n\nIndica `comando` (nombre) **o** `codigo`. "
                 "Invitado: solo comandos permitidos y `duracion_ms` ≤ 2000. Si hay una DEMO en curso solo se "
                 "acepta `DETENER`, que la cancela."),
             responses=ERR)
async def ejecutar_movimiento(solicitud: SolicitudMovimiento, id_vehiculo: int = ID_V,
                              actor: Actor = Depends(actor_requerido)):
    dep.limite_comandos.verificar(actor.clave)
    unidad, nivel = await _control(actor, id_vehiculo)
    capacidades = await run_in_threadpool(dep.inventario.capacidades_por_codigo, unidad["id_modelo"])
    return await dep.control.ejecutar_movimiento(id_vehiculo, solicitud, actor, nivel, capacidades)


@router.post("/demos/{id_demo}/iniciar", response_model=RespuestaDemo, status_code=status.HTTP_202_ACCEPTED,
             summary="Iniciar DEMO",
             description=(
                 "Inicia una DEMO visible para el actor (fábrica o propia). Publica `demo_inicio`, un `demo_paso` por "
                 "movimiento y `demo_fin`; actualiza el estado pero **no registra historial individual**. El Invitado "
                 "solo puede ejecutar DEMO de fábrica que quepan en el tiempo restante de su prueba. 409 si ya hay "
                 "una DEMO en curso o si otra sesión controla la unidad."),
             responses=ERR)
async def iniciar_demo(id_vehiculo: int = ID_V, id_demo: int = Path(ge=1),
                       solicitud: SolicitudDemo = Body(default_factory=SolicitudDemo),
                       actor: Actor = Depends(actor_requerido)):
    dep.limite_comandos.verificar(actor.clave)
    unidad, nivel = await _control(actor, id_vehiculo)
    await run_in_threadpool(dep.editor_demos.verificar_ejecucion, actor, nivel, id_vehiculo, id_demo)
    restantes = await run_in_threadpool(dep.invitados.segundos_restantes, actor) if actor.es_invitado else None
    return await dep.control.iniciar_demo(id_vehiculo, id_demo, solicitud.origen, actor, restantes)


@router.post("/demos/cancelar", response_model=RespuestaDemo, summary="Cancelar DEMO en curso",
             description="Detiene de inmediato los pasos pendientes y publica `demo_cancelada` por WebSocket.",
             responses=ERR)
async def cancelar_demo(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    await run_in_threadpool(dep.autorizacion.para_lectura, actor, id_vehiculo)
    await _control(actor, id_vehiculo)
    return await dep.control.cancelar_demo(id_vehiculo)


@router.get("/demos/en-curso", response_model=RespuestaDemo, summary="¿Hay una DEMO en ejecución?",
            description="Consulta en memoria del servidor; no modifica datos.", responses=ERR)
async def demo_en_curso(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    await run_in_threadpool(dep.autorizacion.para_lectura, actor, id_vehiculo)
    return await dep.control.demo_en_curso(id_vehiculo)

"""DEMO de la unidad: consulta, editor (4.3) y rutas heredadas de 4.1.

* GET  /vehiculos/{id}/demos               DEMO visibles para el actor
* POST /vehiculos/{id}/demos               crear (Admin → fábrica, Usuario → privada)
* GET  /vehiculos/{id}/demos/{d}           detalle con pasos
* PUT  /vehiculos/{id}/demos/{d}           guardar encabezado + pasos (una transacción)
* DELETE /vehiculos/{id}/demos/{d}         baja lógica
Las rutas heredadas (/actualizar, /eliminar, /movimientos) se conservan y pasan
por las MISMAS validaciones del editor.
"""
from fastapi import APIRouter, Depends, Path, status
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import actor_requerido, cuenta
from app.core.errores import Conflicto, Prohibido, RecursoNoEncontrado
from app.core.seguridad import Actor
from app.models.esquemas import (Creado, DemoActualizar, DemoDetalle, DemoEditorCrear, DemoEditorGuardar,
                                 Mensaje, MovimientoDemo, MovimientoDemoCrear, PasoDemo)

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/demos")

ID_V = Path(ge=1, description="Identificador de la unidad")
ID_D = Path(ge=1, description="Identificador de la DEMO")
ID_M = Path(ge=1, description="Identificador del movimiento de la DEMO")
ERR = {401: {"model": Mensaje, "description": "Sin sesión"},
       403: {"model": Mensaje, "description": "Sin permiso sobre la unidad o la DEMO"},
       404: {"model": Mensaje, "description": "Unidad o DEMO inexistente / ajena"},
       409: {"model": Mensaje, "description": "DEMO en ejecución u orden duplicado"},
       400: {"model": Mensaje, "description": "Paso no válido para el modelo (comando o duración)"}}
TAG_D, TAG_M = "DEMO", "Movimientos de DEMO"


async def _acceso(actor: Actor, id_vehiculo: int):
    return await run_in_threadpool(dep.autorizacion.para_lectura, actor, id_vehiculo)


# ------------------------------------------------------------- consulta
@router.get("", response_model=list[DemoDetalle], tags=[TAG_D], summary="DEMO disponibles en la unidad",
            description="**SP:** `sp_demos_vehiculo`. Fábrica (empresa) y, para el comprador, sus DEMO privadas.",
            responses=ERR)
async def listar_demos(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    _, nivel = await _acceso(actor, id_vehiculo)
    return await run_in_threadpool(dep.editor_demos.listar, actor, nivel, id_vehiculo)


@router.get("/{id_demo}", response_model=DemoDetalle, tags=[TAG_D], summary="Detalle de DEMO con sus pasos",
            responses=ERR)
async def detalle_demo(id_vehiculo: int = ID_V, id_demo: int = ID_D, actor: Actor = Depends(actor_requerido)):
    _, nivel = await _acceso(actor, id_vehiculo)
    return await run_in_threadpool(dep.editor_demos.obtener, actor, nivel, id_vehiculo, id_demo)


# ---------------------------------------------------------------- editor
@router.post("", response_model=Creado, status_code=status.HTTP_201_CREATED, tags=[TAG_D],
             summary="Crear DEMO",
             description=("Administrador: DEMO de **fábrica** en una unidad no vendida. Usuario: DEMO **privada** en "
                          "su unidad. Cada paso se valida en el servidor contra los comandos de la unidad y las "
                          "capacidades del modelo (máximo por paso y total)."), responses=ERR)
async def crear_demo(datos: DemoEditorCrear, id_vehiculo: int = ID_V, actor: Actor = Depends(cuenta)):
    unidad, nivel = await _acceso(actor, id_vehiculo)
    return Creado(id=await run_in_threadpool(dep.editor_demos.crear, actor, unidad, nivel, datos),
                  mensaje="DEMO creada")


@router.put("/{id_demo}", response_model=DemoDetalle, tags=[TAG_D], summary="Guardar DEMO (encabezado y pasos)",
            description="Reemplaza la secuencia completa en UNA transacción: o se guarda todo o nada.", responses=ERR)
async def guardar_demo(datos: DemoEditorGuardar, id_vehiculo: int = ID_V, id_demo: int = ID_D,
                       actor: Actor = Depends(cuenta)):
    unidad, nivel = await _acceso(actor, id_vehiculo)
    return await run_in_threadpool(dep.editor_demos.guardar, actor, unidad, nivel, id_demo, datos)


@router.delete("/{id_demo}", response_model=Mensaje, tags=[TAG_D], summary="Dar de baja una DEMO",
               description="Baja lógica (`activo = false`); sus pasos se conservan.", responses=ERR)
async def baja_demo(id_vehiculo: int = ID_V, id_demo: int = ID_D, actor: Actor = Depends(cuenta)):
    unidad, nivel = await _acceso(actor, id_vehiculo)
    await run_in_threadpool(dep.editor_demos.dar_de_baja, actor, unidad, nivel, id_demo)
    return Mensaje(detail=f"DEMO {id_demo} dada de baja")


# ------------------------------------------------------ rutas heredadas
async def _editable(actor: Actor, id_vehiculo: int, id_demo: int):
    unidad, nivel = await _acceso(actor, id_vehiculo)
    demo = await run_in_threadpool(dep.editor_demos.obtener, actor, nivel, id_vehiculo, id_demo)
    if not demo["editable"]:
        raise Prohibido("No puedes modificar esta DEMO")
    return unidad, nivel, demo


def _a_pasos(movimientos: list[dict]) -> list[PasoDemo]:
    return [PasoDemo(comando=m["comando"], duracion_ms=m["duracion_ms"], pausa_ms=m["pausa_ms"])
            for m in sorted(movimientos, key=lambda m: m["orden"])]


async def _guardar(actor, unidad, nivel, demo, pasos) -> list[dict]:
    datos = DemoEditorGuardar(nombre=demo["nombre"], descripcion=demo["descripcion"], activo=demo["activo"], pasos=pasos)
    resultado = await run_in_threadpool(dep.editor_demos.guardar, actor, unidad, nivel, demo["id_demo"], datos)
    return resultado["pasos"]


@router.post("/{id_demo}/actualizar", response_model=DemoDetalle, tags=[TAG_D], summary="Actualizar encabezado (heredada)",
             description="**SP:** `sp_actualizar_demo`", responses=ERR)
async def actualizar_demo(datos: DemoActualizar, id_vehiculo: int = ID_V, id_demo: int = ID_D,
                          actor: Actor = Depends(cuenta)):
    unidad, nivel, demo = await _editable(actor, id_vehiculo, id_demo)
    guardar = DemoEditorGuardar(nombre=datos.nombre, descripcion=datos.descripcion, activo=datos.activo,
                                pasos=_a_pasos(demo["pasos"]))
    return await run_in_threadpool(dep.editor_demos.guardar, actor, unidad, nivel, id_demo, guardar)


@router.post("/{id_demo}/eliminar", response_model=Mensaje, tags=[TAG_D], summary="Eliminar DEMO (heredada → baja lógica)",
             responses=ERR)
async def eliminar_demo(id_vehiculo: int = ID_V, id_demo: int = ID_D, actor: Actor = Depends(cuenta)):
    return await baja_demo(id_vehiculo, id_demo, actor)


@router.get("/{id_demo}/movimientos", response_model=list[MovimientoDemo], tags=[TAG_M],
            summary="Movimientos ordenados de la DEMO", description="**SP:** `sp_obtener_movimientos_demo`",
            responses=ERR)
async def listar_movimientos(id_vehiculo: int = ID_V, id_demo: int = ID_D, actor: Actor = Depends(actor_requerido)):
    return (await detalle_demo(id_vehiculo, id_demo, actor))["pasos"]


@router.post("/{id_demo}/movimientos", response_model=list[MovimientoDemo], status_code=status.HTTP_201_CREATED,
             tags=[TAG_M], summary="Agregar movimiento (heredada)",
             description="Inserta el paso en la posición `orden` y vuelve a validar la DEMO completa.", responses=ERR)
async def agregar_movimiento(datos: MovimientoDemoCrear, id_vehiculo: int = ID_V, id_demo: int = ID_D,
                             actor: Actor = Depends(cuenta)):
    unidad, nivel, demo = await _editable(actor, id_vehiculo, id_demo)
    comando = next((c for c in await run_in_threadpool(dep.sp.obtener_comandos_vehiculo, id_vehiculo)
                    if c["id_comando"] == datos.id_comando), None)
    if comando is None:
        raise RecursoNoEncontrado("El comando no pertenece a esta unidad")
    pasos = _a_pasos(demo["pasos"])
    pasos.insert(min(datos.orden, len(pasos) + 1) - 1, PasoDemo(comando=comando["nombre"],
                                                                duracion_ms=min(datos.duracion_ms, 10000),
                                                                pausa_ms=min(datos.pausa_ms, 5000)))
    return await _guardar(actor, unidad, nivel, demo, pasos)


@router.post("/{id_demo}/movimientos/{id_movimiento}/actualizar", response_model=list[MovimientoDemo],
             tags=[TAG_M], summary="Actualizar movimiento (heredada)", responses=ERR)
async def actualizar_movimiento(datos: MovimientoDemoCrear, id_vehiculo: int = ID_V, id_demo: int = ID_D,
                                id_movimiento: int = ID_M, actor: Actor = Depends(cuenta)):
    unidad, nivel, demo = await _editable(actor, id_vehiculo, id_demo)
    movimientos = [m for m in demo["pasos"] if m["id_demo_movimiento"] != id_movimiento]
    if len(movimientos) == len(demo["pasos"]):
        raise RecursoNoEncontrado("El movimiento no pertenece a la DEMO")
    comando = next((c for c in await run_in_threadpool(dep.sp.obtener_comandos_vehiculo, id_vehiculo)
                    if c["id_comando"] == datos.id_comando), None)
    if comando is None:
        raise RecursoNoEncontrado("El comando no pertenece a esta unidad")
    pasos = _a_pasos(movimientos)
    pasos.insert(min(datos.orden, len(pasos) + 1) - 1, PasoDemo(comando=comando["nombre"],
                                                                duracion_ms=min(datos.duracion_ms, 10000),
                                                                pausa_ms=min(datos.pausa_ms, 5000)))
    return await _guardar(actor, unidad, nivel, demo, pasos)


@router.post("/{id_demo}/movimientos/{id_movimiento}/eliminar", response_model=Mensaje, tags=[TAG_M],
             summary="Eliminar movimiento (heredada)", responses=ERR)
async def eliminar_movimiento(id_vehiculo: int = ID_V, id_demo: int = ID_D, id_movimiento: int = ID_M,
                              actor: Actor = Depends(cuenta)):
    unidad, nivel, demo = await _editable(actor, id_vehiculo, id_demo)
    movimientos = [m for m in demo["pasos"] if m["id_demo_movimiento"] != id_movimiento]
    if len(movimientos) == len(demo["pasos"]):
        raise RecursoNoEncontrado("El movimiento no pertenece a la DEMO")
    if not movimientos:
        raise Conflicto("La DEMO debe conservar al menos un paso: si ya no la usas, dala de baja")
    await _guardar(actor, unidad, nivel, demo, _a_pasos(movimientos))
    return Mensaje(detail=f"Movimiento {id_movimiento} eliminado")

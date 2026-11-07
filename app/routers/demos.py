"""DEMO y sus movimientos (administración y consulta)."""
from fastapi import APIRouter, Depends, Path, status

from app import dependencias as dep
from app.core.errores import Conflicto
from app.core.seguridad import solo_admin
from app.models.esquemas import (Creado, Demo, DemoActualizar, DemoCrear, Mensaje, MovimientoDemo,
                                 MovimientoDemoCrear)

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/demos")

ID_V = Path(ge=1, description="Identificador del vehículo")
ID_D = Path(ge=1, description="Identificador de la DEMO")
ID_M = Path(ge=1, description="Identificador del movimiento de la DEMO")
E404 = {404: {"model": Mensaje, "description": "Recurso inexistente"}}
EAUTH = {401: {"model": Mensaje, "description": "Sin token o token inválido"},
         403: {"model": Mensaje, "description": "Rol sin permiso"}}
E409 = {409: {"model": Mensaje, "description": "Conflicto (orden duplicado, DEMO en uso)"}}
TAG_D, TAG_M = "DEMO", "Movimientos de DEMO"


@router.get("", response_model=list[Demo], tags=[TAG_D], summary="Listar DEMO del vehículo",
            description="**SP:** `sp_obtener_demos`", responses=E404)
def listar_demos(id_vehiculo: int = ID_V):
    return dep.demos.listar(id_vehiculo)


@router.post("", response_model=Creado, status_code=status.HTTP_201_CREATED, tags=[TAG_D],
             summary="Crear DEMO (admin)", description="**SP:** `sp_crear_demo`",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH})
def crear_demo(datos: DemoCrear, id_vehiculo: int = ID_V):
    return Creado(id=dep.demos.crear(id_vehiculo, datos), mensaje="DEMO creada")


@router.post("/{id_demo}/actualizar", response_model=Demo, tags=[TAG_D], summary="Actualizar DEMO (admin)",
             description="**SP:** `sp_actualizar_demo`", dependencies=[Depends(solo_admin)],
             responses={**E404, **EAUTH})
def actualizar_demo(datos: DemoActualizar, id_vehiculo: int = ID_V, id_demo: int = ID_D):
    return dep.demos.actualizar(id_vehiculo, id_demo, datos)


@router.post("/{id_demo}/eliminar", response_model=Mensaje, tags=[TAG_D], summary="Eliminar DEMO (admin)",
             description="**SP:** `sp_eliminar_demo` (elimina también sus movimientos).",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH, **E409})
def eliminar_demo(id_vehiculo: int = ID_V, id_demo: int = ID_D):
    en_curso = dep.ejecutor_demos.demo_en_curso(id_vehiculo)
    if en_curso and en_curso["id_demo"] == id_demo:
        raise Conflicto("No se puede eliminar una DEMO mientras se ejecuta")
    dep.demos.eliminar(id_vehiculo, id_demo)
    return Mensaje(detail=f"DEMO {id_demo} eliminada")


@router.get("/{id_demo}/movimientos", response_model=list[MovimientoDemo], tags=[TAG_M],
            summary="Movimientos ordenados de la DEMO", description="**SP:** `sp_obtener_movimientos_demo`",
            responses=E404)
def listar_movimientos(id_vehiculo: int = ID_V, id_demo: int = ID_D):
    return dep.demos.movimientos(id_vehiculo, id_demo)


@router.post("/{id_demo}/movimientos", response_model=list[MovimientoDemo], status_code=status.HTTP_201_CREATED,
             tags=[TAG_M], summary="Agregar movimiento a la DEMO (admin)",
             description="**SP:** `sp_agregar_movimiento_demo`. El comando debe pertenecer al mismo vehículo. "
                         "Devuelve la secuencia actualizada.",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH, **E409})
def agregar_movimiento(datos: MovimientoDemoCrear, id_vehiculo: int = ID_V, id_demo: int = ID_D):
    return dep.demos.agregar_movimiento(id_vehiculo, id_demo, datos)


@router.post("/{id_demo}/movimientos/{id_movimiento}/actualizar", response_model=list[MovimientoDemo],
             tags=[TAG_M], summary="Actualizar movimiento de la DEMO (admin)",
             description="**SP:** `sp_actualizar_movimiento_demo`", dependencies=[Depends(solo_admin)],
             responses={**E404, **EAUTH, **E409})
def actualizar_movimiento(datos: MovimientoDemoCrear, id_vehiculo: int = ID_V, id_demo: int = ID_D,
                          id_movimiento: int = ID_M):
    return dep.demos.actualizar_movimiento(id_vehiculo, id_demo, id_movimiento, datos)


@router.post("/{id_demo}/movimientos/{id_movimiento}/eliminar", response_model=Mensaje, tags=[TAG_M],
             summary="Eliminar movimiento de la DEMO (admin)", description="**SP:** `sp_eliminar_movimiento_demo`",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH})
def eliminar_movimiento(id_vehiculo: int = ID_V, id_demo: int = ID_D, id_movimiento: int = ID_M):
    dep.demos.eliminar_movimiento(id_vehiculo, id_demo, id_movimiento)
    return Mensaje(detail=f"Movimiento {id_movimiento} eliminado")

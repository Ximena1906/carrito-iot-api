"""«Mis vehículos» del comprador y autorización de soporte al Administrador."""
from fastapi import APIRouter, Depends, Path
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import solo_usuario
from app.core.seguridad import Actor
from app.models.esquemas import EstadoSoporte, Mensaje, Soporte, Unidad

router = APIRouter(prefix="/mis-vehiculos", tags=["Mis vehículos"])
ID_V = Path(ge=1, description="Unidad propia")
ERR = {401: {"model": Mensaje}, 403: {"model": Mensaje}, 404: {"model": Mensaje}}


@router.get("", response_model=list[Unidad], summary="Unidades asignadas a mi cuenta",
            description="Solo las unidades cuyo propietario es la cuenta del token (nunca se acepta un ID de "
                        "usuario enviado por el navegador).", responses=ERR)
async def mis_vehiculos(actor: Actor = Depends(solo_usuario)):
    return await run_in_threadpool(dep.inventario.mis_vehiculos, actor)


@router.put("/{id_vehiculo}/soporte", response_model=EstadoSoporte, summary="Autorizar soporte temporal",
            description="El comprador permite que el Administrador consulte y opere SU unidad durante N minutos.",
            responses=ERR)
async def otorgar_soporte(datos: Soporte, id_vehiculo: int = ID_V, actor: Actor = Depends(solo_usuario)):
    return await run_in_threadpool(dep.inventario.otorgar_soporte, actor, id_vehiculo, datos.minutos)


@router.delete("/{id_vehiculo}/soporte", response_model=EstadoSoporte, summary="Revocar soporte",
               description="Revoca el permiso de inmediato: si el Administrador estaba operando la unidad se "
                           "envía DETENER y se cierran sus suscripciones WSS.", responses=ERR)
async def revocar_soporte(id_vehiculo: int = ID_V, actor: Actor = Depends(solo_usuario)):
    return await dep.inventario.revocar_soporte(actor, id_vehiculo, dep.conexiones.revalidar)

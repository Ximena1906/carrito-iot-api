"""Catálogo público «Prueba nuestros vehículos IoT» y sesiones de Invitado."""
from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import solo_invitado
from app.core.seguridad import Actor
from app.models.esquemas import Mensaje, SesionInvitado, SolicitudPrueba

router = APIRouter(tags=["Catálogo e Invitados"])


@router.get("/catalogo", summary="Catálogo público de modelos y unidades de exhibición",
            description=(
                "Sin autenticación. Modelos activos con sus capacidades y las unidades en estado **exhibicion** "
                "(ocupada/libre). No expone inventario privado, propietarios ni datos de compradores."))
async def catalogo():
    return await run_in_threadpool(dep.inventario.catalogo)


@router.post("/invitados/sesiones", response_model=SesionInvitado, status_code=status.HTTP_201_CREATED,
             summary="Iniciar prueba temporal de Invitado",
             description=(
                 "Reserva EXCLUSIVA de una unidad de exhibición durante `INVITADO_SEGUNDOS` (180 s por defecto). "
                 "Devuelve un token de Invitado limitado a esa unidad y a sus comandos permitidos. "
                 "Una segunda sesión sobre la misma unidad recibe **409**. Unidades vendidas → **404**."),
             responses={404: {"model": Mensaje}, 409: {"model": Mensaje}, 429: {"model": Mensaje}})
async def iniciar_prueba(solicitud: SolicitudPrueba, request: Request):
    dep.limite_invitado.verificar(f"inv:{request.client.host if request.client else '-'}")
    return await dep.invitados.iniciar(solicitud.id_vehiculo)


@router.get("/invitados/sesion", response_model=SesionInvitado, summary="Estado de mi prueba (Invitado)",
            description="Tiempo restante, unidad reservada y comandos habilitados.",
            responses={401: {"model": Mensaje}, 403: {"model": Mensaje}})
async def mi_prueba(actor: Actor = Depends(solo_invitado)):
    return await run_in_threadpool(dep.invitados.info, actor)


@router.delete("/invitados/sesion", response_model=Mensaje, summary="Terminar mi prueba (Invitado)",
               description="Libera la reserva, detiene la unidad (DETENER) y cierra las suscripciones WSS.",
               responses={401: {"model": Mensaje}, 403: {"model": Mensaje}})
async def terminar_prueba(actor: Actor = Depends(solo_invitado)):
    await dep.invitados.finalizar(actor.codigo_sesion, actor.id_vehiculo_invitado, "CERRADA")
    return Mensaje(detail="Prueba finalizada")

"""Vehículos (unidades), comandos, estado e historial.

Mismas rutas y respuestas que en 4.1/4.2. Desde 4.3 TODAS exigen sesión y
autorización sobre la unidad concreta (ver services/autorizacion.py):
el Usuario solo ve sus unidades (404 si no es suya), el Administrador las no
vendidas (o vendidas con permiso de soporte) y el Invitado su unidad reservada.
"""
from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import actor_requerido, solo_admin
from app.core.errores import Conflicto
from app.core.seguridad import Actor
from app.models.esquemas import (Comando, ComandoActualizar, ComandoCrear, Creado, Estado, Mensaje,
                                 RegistroHistorial, Vehiculo, VehiculoActualizar, VehiculoCrear)
from app.services.autorizacion import EMPRESA

router = APIRouter(prefix="/vehiculos")

ID_V = Path(ge=1, description="Identificador de la unidad (id_vehiculo)")
ID_C = Path(ge=1, description="Identificador del comando")
E404 = {404: {"model": Mensaje, "description": "Recurso inexistente (o unidad ajena para un Usuario)"}}
EAUTH = {401: {"model": Mensaje, "description": "Sin sesión o token inválido"},
         403: {"model": Mensaje, "description": "Sin permiso sobre esta unidad"}}
E409 = {409: {"model": Mensaje, "description": "Conflicto (duplicado, registro en uso o baja lógica requerida)"}}


async def _lectura(actor: Actor, id_vehiculo: int):
    return await run_in_threadpool(dep.autorizacion.para_lectura, actor, id_vehiculo)


async def _empresa(actor: Actor, id_vehiculo: int):
    unidad, nivel = await _lectura(actor, id_vehiculo)
    if nivel != EMPRESA:
        raise Conflicto("La unidad está vendida: su catálogo se administra desde el modelo")
    return unidad


# ------------------------------------------------------------- Vehículos
@router.get("", response_model=list[Vehiculo], tags=["Vehículos"], summary="Listar vehículos (admin)",
            description="**SP:** `sp_obtener_vehiculos`. Solo Administrador; el comprador usa `/mis-vehiculos`.",
            responses=EAUTH)
async def listar_vehiculos(_: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.vehiculos.listar)


@router.get("/{id_vehiculo}", response_model=Vehiculo, tags=["Vehículos"], summary="Consultar una unidad",
            description="**SP:** `sp_obtener_vehiculo`", responses={**E404, **EAUTH})
async def obtener_vehiculo(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    await _lectura(actor, id_vehiculo)
    return await run_in_threadpool(dep.vehiculos.obtener, id_vehiculo)


@router.post("", response_model=Creado, status_code=status.HTTP_201_CREATED, tags=["Vehículos"], deprecated=True,
             summary="Crear vehículo (reemplazado por POST /admin/unidades)",
             description="Desde 4.3 una unidad debe tener modelo y número de serie: usa `POST /admin/unidades`.",
             responses={**EAUTH, **E409})
async def crear_vehiculo(_datos: VehiculoCrear, _: Actor = Depends(solo_admin)):
    raise Conflicto("Registra la unidad con POST /admin/unidades (modelo y número de serie obligatorios)")


@router.post("/{id_vehiculo}/actualizar", response_model=Vehiculo, tags=["Vehículos"],
             summary="Actualizar vehículo (admin)",
             description="**SP:** `sp_actualizar_vehiculo` (+ `sp_obtener_vehiculo`). Para el estado comercial usa "
                         "`PATCH /admin/unidades/{id}/estado`.", responses={**E404, **EAUTH})
async def actualizar_vehiculo(datos: VehiculoActualizar, id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    await _empresa(admin, id_vehiculo)
    resultado = await run_in_threadpool(dep.vehiculos.actualizar, id_vehiculo, datos)
    await dep.auditoria.aregistrar(admin, "actualizar_vehiculo", "unidad", id_vehiculo)
    return resultado


@router.post("/{id_vehiculo}/eliminar", response_model=Mensaje, tags=["Vehículos"],
             summary="Eliminar vehículo (admin, solo sin historial)",
             description="**SP:** `sp_eliminar_vehiculo`. Prohibido si la unidad tiene historial, asignaciones o "
                         "DEMO (409): en ese caso usa la baja lógica `PATCH /admin/unidades/{id}/estado`.",
             responses={**E404, **EAUTH, **E409})
async def eliminar_vehiculo(id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    unidad = await _empresa(admin, id_vehiculo)
    historial = await run_in_threadpool(dep.sp.obtener_historial, id_vehiculo)
    asignaciones = await run_in_threadpool(dep.sp.asignaciones_listar, id_vehiculo)
    demos = await run_in_threadpool(dep.sp.demos_vehiculo, id_vehiculo)
    if historial or asignaciones or demos:
        await dep.auditoria.aregistrar(admin, "eliminar_vehiculo", "unidad", id_vehiculo, "rechazado",
                                       "tiene historial/asignaciones/demos")
        raise Conflicto("La unidad tiene historial, asignaciones o DEMO: usa la baja lógica (estado «inactivo»)")
    await run_in_threadpool(dep.vehiculos.eliminar, id_vehiculo)
    await dep.auditoria.aregistrar(admin, "eliminar_vehiculo", "unidad", id_vehiculo,
                                   detalle=f"serie={unidad['numero_serie']} sin historial")
    return Mensaje(detail=f"Vehículo {id_vehiculo} eliminado")


# -------------------------------------------------------------- Comandos
@router.get("/{id_vehiculo}/comandos", response_model=list[Comando], tags=["Comandos"],
            summary="Comandos habilitados de la unidad", description="**SP:** `sp_obtener_comandos_vehiculo`",
            responses={**E404, **EAUTH})
async def listar_comandos(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    unidad, _ = await _lectura(actor, id_vehiculo)
    comandos = await run_in_threadpool(dep.comandos.listar, id_vehiculo)
    if actor.es_invitado:  # el Invitado solo recibe la lista reducida de su prueba
        caps = await run_in_threadpool(dep.inventario.capacidades_por_codigo, unidad["id_modelo"])
        comandos = [c for c in comandos if c["nombre"] == "DETENER"
                    or (caps.get(c["codigo"]) or {}).get("permitido_invitado")]
    return comandos


@router.post("/{id_vehiculo}/comandos", response_model=Creado, status_code=status.HTTP_201_CREATED,
             tags=["Comandos"], summary="Agregar comando a una unidad (admin)",
             description="**SP:** `sp_crear_comando`. Debe existir como capacidad del modelo (usa "
                         "`PUT /admin/modelos/{id}/capacidades` para agregarlo a todas las unidades).",
             responses={**E404, **EAUTH, **E409})
async def crear_comando(datos: ComandoCrear, id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    unidad = await _empresa(admin, id_vehiculo)
    caps = await run_in_threadpool(dep.inventario.capacidades_por_codigo, unidad["id_modelo"])
    if datos.codigo not in caps:
        raise Conflicto("El modelo de la unidad no tiene esa capacidad")
    nuevo = await run_in_threadpool(dep.comandos.crear, id_vehiculo, datos)
    await dep.auditoria.aregistrar(admin, "crear_comando", "unidad", id_vehiculo, detalle=datos.nombre)
    return Creado(id=nuevo, mensaje="Comando creado")


@router.post("/{id_vehiculo}/comandos/{id_comando}/actualizar", response_model=Comando, tags=["Comandos"],
             summary="Actualizar comando (admin)", description="**SP:** `sp_actualizar_comando`. Con `activo=false` "
             "se deshabilita (baja lógica).", responses={**E404, **EAUTH, **E409})
async def actualizar_comando(datos: ComandoActualizar, id_vehiculo: int = ID_V, id_comando: int = ID_C,
                             admin: Actor = Depends(solo_admin)):
    await _empresa(admin, id_vehiculo)
    resultado = await run_in_threadpool(dep.comandos.actualizar, id_vehiculo, id_comando, datos)
    await dep.auditoria.aregistrar(admin, "actualizar_comando", "unidad", id_vehiculo,
                                   detalle=f"{datos.nombre} activo={datos.activo}")
    return resultado


@router.post("/{id_vehiculo}/comandos/{id_comando}/eliminar", response_model=Mensaje, tags=["Comandos"],
             summary="Eliminar comando (admin)",
             description="Desde 4.3 se rechaza (409): borrar un comando dejaría el historial sin nombre. "
                         "Usa `activo=false` en `/actualizar`.", responses={**E404, **EAUTH, **E409})
async def eliminar_comando(id_vehiculo: int = ID_V, id_comando: int = ID_C, admin: Actor = Depends(solo_admin)):
    await _empresa(admin, id_vehiculo)
    raise Conflicto("Los comandos no se eliminan: desactívalo con activo=false para conservar el historial")


# ------------------------------------------------------ Estado / historial
@router.get("/{id_vehiculo}/estado", response_model=Estado, tags=["Estado e historial"],
            summary="Último estado de la unidad",
            description="**SP:** `sp_obtener_estado`. `conectado` indica si el ESP32 tiene una sesión WSS activa.",
            responses={**E404, **EAUTH})
async def obtener_estado(id_vehiculo: int = ID_V, actor: Actor = Depends(actor_requerido)):
    await _lectura(actor, id_vehiculo)
    datos = await run_in_threadpool(dep.estado.obtener_estado, id_vehiculo)
    en_curso = dep.ejecutor_demos.demo_en_curso(id_vehiculo)
    datos["demo_en_curso"] = en_curso["id_demo"] if en_curso else None
    return datos


@router.get("/{id_vehiculo}/historial", response_model=list[RegistroHistorial], tags=["Estado e historial"],
            summary="Últimos movimientos individuales (máximo 10)",
            description="**SP:** `sp_obtener_historial`. Como máximo los 10 movimientos individuales más recientes "
                        "de ESTA unidad, del más reciente al más antiguo. Los pasos de DEMO nunca aparecen aquí.",
            responses={**E404, **EAUTH})
async def obtener_historial(id_vehiculo: int = ID_V,
                            limite: int = Query(default=10, ge=1, le=10, description="Cantidad (1-10)"),
                            actor: Actor = Depends(actor_requerido)):
    await _lectura(actor, id_vehiculo)
    return await run_in_threadpool(dep.estado.historial, id_vehiculo, limite)

"""Vehículos, comandos, estado e historial."""
from fastapi import APIRouter, Depends, Path, Query, status

from app import dependencias as dep
from app.core.seguridad import solo_admin
from app.models.esquemas import (Comando, ComandoActualizar, ComandoCrear, Creado, Estado, Mensaje,
                                 RegistroHistorial, Vehiculo, VehiculoActualizar, VehiculoCrear)

router = APIRouter(prefix="/vehiculos")

ID_V = Path(ge=1, description="Identificador del vehículo")
ID_C = Path(ge=1, description="Identificador del comando")
E404 = {404: {"model": Mensaje, "description": "Recurso inexistente"}}
EAUTH = {401: {"model": Mensaje, "description": "Sin token o token inválido"},
         403: {"model": Mensaje, "description": "Rol sin permiso"}}
E409 = {409: {"model": Mensaje, "description": "Conflicto (duplicado o registro en uso)"}}


# ------------------------------------------------------------- Vehículos
@router.get("", response_model=list[Vehiculo], tags=["Vehículos"], summary="Listar vehículos",
            description="**SP:** `sp_obtener_vehiculos`")
def listar_vehiculos():
    return dep.vehiculos.listar()


@router.get("/{id_vehiculo}", response_model=Vehiculo, tags=["Vehículos"], summary="Consultar un vehículo",
            description="**SP:** `sp_obtener_vehiculo`", responses=E404)
def obtener_vehiculo(id_vehiculo: int = ID_V):
    return dep.vehiculos.obtener(id_vehiculo)


@router.post("", response_model=Creado, status_code=status.HTTP_201_CREATED, tags=["Vehículos"],
             summary="Crear vehículo (admin)", description="**SP:** `sp_crear_vehiculo`",
             dependencies=[Depends(solo_admin)], responses=EAUTH)
def crear_vehiculo(datos: VehiculoCrear):
    return Creado(id=dep.vehiculos.crear(datos), mensaje="Vehículo creado")


@router.post("/{id_vehiculo}/actualizar", response_model=Vehiculo, tags=["Vehículos"],
             summary="Actualizar vehículo (admin)",
             description="**SP:** `sp_actualizar_vehiculo` (+ `sp_obtener_vehiculo`)",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH})
def actualizar_vehiculo(datos: VehiculoActualizar, id_vehiculo: int = ID_V):
    return dep.vehiculos.actualizar(id_vehiculo, datos)


@router.post("/{id_vehiculo}/eliminar", response_model=Mensaje, tags=["Vehículos"],
             summary="Eliminar vehículo (admin)",
             description="**SP:** `sp_eliminar_vehiculo`. Elimina en cascada comandos, estado, historial y DEMO.",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH})
def eliminar_vehiculo(id_vehiculo: int = ID_V):
    dep.vehiculos.eliminar(id_vehiculo)
    return Mensaje(detail=f"Vehículo {id_vehiculo} eliminado")


# -------------------------------------------------------------- Comandos
@router.get("/{id_vehiculo}/comandos", response_model=list[Comando], tags=["Comandos"],
            summary="Catálogo de comandos del vehículo", description="**SP:** `sp_obtener_comandos_vehiculo`",
            responses=E404)
def listar_comandos(id_vehiculo: int = ID_V):
    return dep.comandos.listar(id_vehiculo)


@router.post("/{id_vehiculo}/comandos", response_model=Creado, status_code=status.HTTP_201_CREATED,
             tags=["Comandos"], summary="Agregar comando al catálogo (admin)",
             description="**SP:** `sp_crear_comando`. Crea un comando nuevo; NO lo ejecuta.",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH, **E409})
def crear_comando(datos: ComandoCrear, id_vehiculo: int = ID_V):
    return Creado(id=dep.comandos.crear(id_vehiculo, datos), mensaje="Comando creado")


@router.post("/{id_vehiculo}/comandos/{id_comando}/actualizar", response_model=Comando, tags=["Comandos"],
             summary="Actualizar comando (admin)", description="**SP:** `sp_actualizar_comando`",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH, **E409})
def actualizar_comando(datos: ComandoActualizar, id_vehiculo: int = ID_V, id_comando: int = ID_C):
    return dep.comandos.actualizar(id_vehiculo, id_comando, datos)


@router.post("/{id_vehiculo}/comandos/{id_comando}/eliminar", response_model=Mensaje, tags=["Comandos"],
             summary="Eliminar comando (admin)",
             description="**SP:** `sp_eliminar_comando`. Responde 409 si el comando está usado en una DEMO.",
             dependencies=[Depends(solo_admin)], responses={**E404, **EAUTH, **E409})
def eliminar_comando(id_vehiculo: int = ID_V, id_comando: int = ID_C):
    dep.comandos.eliminar(id_vehiculo, id_comando)
    return Mensaje(detail=f"Comando {id_comando} eliminado")


# ------------------------------------------------------ Estado / historial
@router.get("/{id_vehiculo}/estado", response_model=Estado, tags=["Estado e historial"],
            summary="Último estado del vehículo",
            description="**SP:** `sp_obtener_estado`. `conectado` indica si el ESP32 tiene una sesión WSS activa.",
            responses=E404)
def obtener_estado(id_vehiculo: int = ID_V):
    datos = dep.estado.obtener_estado(id_vehiculo)
    en_curso = dep.ejecutor_demos.demo_en_curso(id_vehiculo)
    datos["demo_en_curso"] = en_curso["id_demo"] if en_curso else None
    return datos


@router.get("/{id_vehiculo}/historial", response_model=list[RegistroHistorial], tags=["Estado e historial"],
            summary="Últimos movimientos individuales (máximo 10)",
            description="**SP:** `sp_obtener_historial`. Devuelve como máximo los 10 movimientos individuales "
                        "más recientes, del más reciente al más antiguo. Los pasos de DEMO nunca aparecen aquí. "
                        "No elimina registros de RDS.",
            responses=E404)
def obtener_historial(id_vehiculo: int = ID_V,
                      limite: int = Query(default=10, ge=1, le=10, description="Cantidad (1-10)")):
    return dep.estado.historial(id_vehiculo, limite)

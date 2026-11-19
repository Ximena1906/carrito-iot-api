"""ADMINISTRACIÓN (solo rol admin): Dashboard, modelos, unidades, clientes,
asignaciones y auditoría.

El Administrador gestiona el INVENTARIO; no obtiene control operativo de una
unidad vendida salvo con permiso de soporte del comprador (ver autorizacion.py).
"""
from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.concurrency import run_in_threadpool

from app import dependencias as dep
from app.core.acceso import solo_admin
from app.core.seguridad import Actor
from app.models.esquemas import (AsignarUnidad, CambioActivo, CambioEstadoUnidad, CapacidadGuardar, Capacidad,
                                 Creado, Dashboard, Mensaje, Modelo, ModeloActualizar, ModeloCrear,
                                 PaginaAuditoria, PaginaUnidades, PaginaUsuarios, Unidad, UnidadActualizar,
                                 UnidadCrear, UsuarioActualizar, UsuarioCrear, UsuarioPassword, UsuarioSalida)

router = APIRouter(prefix="/admin", tags=["Administración"])
ERR = {401: {"model": Mensaje, "description": "Sin sesión"},
       403: {"model": Mensaje, "description": "Rol distinto de Administrador"},
       404: {"model": Mensaje, "description": "Recurso inexistente"},
       409: {"model": Mensaje, "description": "Conflicto (duplicado, estado no válido, unidad en uso)"}}
ID_M = Path(ge=1, description="Modelo comercial")
ID_V = Path(ge=1, description="Unidad física (id_vehiculo)")
ID_U = Path(ge=1, description="Cuenta")
LIMITE = Query(default=20, ge=1, le=100)
DESDE = Query(default=0, ge=0)


# ------------------------------------------------------------ Dashboard
@router.get("/dashboard", response_model=Dashboard, summary="Métricas reales del inventario",
            description="Conteos leídos de RDS (`sp_dashboard_resumen`) y conexiones WSS activas del servidor.",
            responses=ERR)
async def dashboard(_: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.dashboard, dep.gestor_ws.total_conexiones())


# -------------------------------------------------------------- Modelos
@router.get("/modelos", response_model=list[Modelo], summary="Listar modelos comerciales", responses=ERR)
async def modelos(solo_activos: bool = False, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.modelos, solo_activos)


@router.post("/modelos", response_model=Creado, status_code=status.HTTP_201_CREATED, summary="Crear modelo",
             description="Crea el modelo y, opcionalmente, sus capacidades (comandos que soporta el hardware).",
             responses=ERR)
async def crear_modelo(datos: ModeloCrear, admin: Actor = Depends(solo_admin)):
    return Creado(id=await run_in_threadpool(dep.inventario.crear_modelo, admin, datos), mensaje="Modelo creado")


@router.get("/modelos/{id_modelo}", response_model=Modelo, summary="Consultar modelo y capacidades", responses=ERR)
async def modelo(id_modelo: int = ID_M, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.modelo, id_modelo)


@router.put("/modelos/{id_modelo}", response_model=Modelo, summary="Editar modelo", responses=ERR)
async def actualizar_modelo(datos: ModeloActualizar, id_modelo: int = ID_M, admin: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.actualizar_modelo, admin, id_modelo, datos)


@router.patch("/modelos/{id_modelo}/estado", response_model=Modelo, summary="Activar o desactivar modelo",
              description="Baja lógica: un modelo inactivo deja de aparecer en el catálogo público.", responses=ERR)
async def estado_modelo(datos: CambioActivo, id_modelo: int = ID_M, admin: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.cambiar_activo_modelo, admin, id_modelo, datos.activo)


@router.put("/modelos/{id_modelo}/capacidades", response_model=list[Capacidad],
            summary="Agregar o actualizar una capacidad del modelo",
            description="Upsert por `codigo`. Las unidades del modelo reciben el comando (o su nuevo estado) "
                        "sin cambiar su id_comando, para no romper historial ni DEMO.", responses=ERR)
async def guardar_capacidad(datos: CapacidadGuardar, id_modelo: int = ID_M, admin: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.guardar_capacidad, admin, id_modelo, datos)


# ------------------------------------------------------------- Unidades
@router.get("/unidades", response_model=PaginaUnidades, summary="Inventario de unidades físicas",
            description="Filtros por estado, modelo y texto (nombre, serie o propietario). Paginado.", responses=ERR)
async def unidades(estado: str | None = Query(default=None, pattern="^(disponible|asignado|exhibicion|inactivo)$"),
                   id_modelo: int | None = Query(default=None, ge=1), q: str | None = Query(default=None, max_length=80),
                   limite: int = LIMITE, desplazamiento: int = DESDE, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.unidades, estado, id_modelo, q, limite, desplazamiento)


@router.post("/unidades", response_model=Creado, status_code=status.HTTP_201_CREATED, summary="Registrar unidad",
             description="Crea la unidad física (fila en `vehiculos`) con número de serie ÚNICO y le habilita los "
                         "comandos de su modelo.", responses=ERR)
async def crear_unidad(datos: UnidadCrear, admin: Actor = Depends(solo_admin)):
    return Creado(id=await run_in_threadpool(dep.inventario.crear_unidad, admin, datos), mensaje="Unidad registrada")


@router.get("/unidades/{id_vehiculo}", response_model=Unidad, summary="Detalle de unidad con historia de propietarios",
            responses=ERR)
async def unidad(id_vehiculo: int = ID_V, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.unidad, id_vehiculo)


@router.put("/unidades/{id_vehiculo}", response_model=Unidad, summary="Editar unidad", responses=ERR)
async def actualizar_unidad(datos: UnidadActualizar, id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.inventario.actualizar_unidad, admin, id_vehiculo, datos)


@router.patch("/unidades/{id_vehiculo}/estado", response_model=Unidad,
              summary="Cambiar estado comercial (disponible, exhibición o baja lógica)",
              description="No borra la unidad ni su historial: «inactivo» es la baja lógica.", responses=ERR)
async def estado_unidad(datos: CambioEstadoUnidad, id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    return await dep.inventario.cambiar_estado(admin, id_vehiculo, datos.estado_comercial, dep.conexiones.revalidar)


@router.put("/unidades/{id_vehiculo}/propietario", response_model=Unidad, summary="Asignar o reasignar a un comprador",
            description="Cierra la asignación anterior (se conserva), revoca soporte y corta de inmediato las "
                        "suscripciones WSS del titular anterior.", responses=ERR)
async def asignar(datos: AsignarUnidad, id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    return await dep.inventario.asignar(admin, id_vehiculo, datos.id_usuario, dep.conexiones.revalidar)


@router.delete("/unidades/{id_vehiculo}/propietario", response_model=Unidad, summary="Liberar unidad del comprador",
               responses=ERR)
async def liberar(estado: str = Query(default="disponible", pattern="^(disponible|exhibicion)$"),
                  id_vehiculo: int = ID_V, admin: Actor = Depends(solo_admin)):
    return await dep.inventario.liberar(admin, id_vehiculo, estado, dep.conexiones.revalidar)


# ------------------------------------------------------ Clientes/cuentas
@router.get("/usuarios", response_model=PaginaUsuarios, summary="Clientes y administradores",
            description="Filtros por rol, texto y estado. Nunca devuelve hashes de contraseña.", responses=ERR)
async def usuarios(rol: str | None = Query(default=None, pattern="^(admin|usuario)$"),
                   q: str | None = Query(default=None, max_length=100), activo: bool | None = None,
                   limite: int = LIMITE, desplazamiento: int = DESDE, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.usuarios.listar, rol, q, activo, limite, desplazamiento)


@router.post("/usuarios", response_model=Creado, status_code=status.HTTP_201_CREATED, summary="Dar de alta una cuenta",
             description="Alta de comprador (rol usuario) o de otro administrador. La contraseña se guarda con hash.",
             responses=ERR)
async def crear_usuario(datos: UsuarioCrear, admin: Actor = Depends(solo_admin)):
    return Creado(id=await run_in_threadpool(dep.usuarios.crear, admin, datos), mensaje="Cuenta creada")


@router.get("/usuarios/{id_usuario}", response_model=UsuarioSalida, summary="Consultar cuenta", responses=ERR)
async def usuario(id_usuario: int = ID_U, _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.usuarios.obtener, id_usuario)


@router.put("/usuarios/{id_usuario}", response_model=UsuarioSalida, summary="Editar datos de contacto", responses=ERR)
async def actualizar_usuario(datos: UsuarioActualizar, id_usuario: int = ID_U, admin: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.usuarios.actualizar, admin, id_usuario, datos)


@router.patch("/usuarios/{id_usuario}/estado", response_model=UsuarioSalida, summary="Activar o desactivar cuenta",
              description="Desactivar invalida sus tokens y corta sus suscripciones WSS al instante.", responses=ERR)
async def estado_usuario(datos: CambioActivo, id_usuario: int = ID_U, admin: Actor = Depends(solo_admin)):
    resultado = await run_in_threadpool(dep.usuarios.cambiar_activo, admin, id_usuario, datos.activo)
    await dep.conexiones.revalidar(id_usuario=id_usuario)
    return resultado


@router.put("/usuarios/{id_usuario}/password", response_model=Mensaje, summary="Restablecer contraseña",
            description="Invalida las sesiones abiertas de esa cuenta.", responses=ERR)
async def password_usuario(datos: UsuarioPassword, id_usuario: int = ID_U, admin: Actor = Depends(solo_admin)):
    await run_in_threadpool(dep.usuarios.restablecer_password, admin, id_usuario, datos.password)
    await dep.conexiones.revalidar(id_usuario=id_usuario)
    return Mensaje(detail="Contraseña actualizada")


# ------------------------------------------------------------ Auditoría
@router.get("/auditoria", response_model=PaginaAuditoria, summary="Bitácora de auditoría",
            description="Altas, asignaciones, cambios de estado, DEMO, sesiones de Invitado e inicios de sesión. "
                        "Sin contraseñas ni tokens.", responses=ERR)
async def auditoria(accion: str | None = Query(default=None, max_length=50),
                    actor_tipo: str | None = Query(default=None, pattern="^(admin|usuario|invitado|sistema|anonimo)$"),
                    resultado: str | None = Query(default=None, pattern="^(ok|rechazado|error)$"),
                    limite: int = Query(default=50, ge=1, le=200), desplazamiento: int = DESDE,
                    _: Actor = Depends(solo_admin)):
    return await run_in_threadpool(dep.auditoria.listar, accion, actor_tipo, resultado, limite, desplazamiento)

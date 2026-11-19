"""Inventario comercial: modelos, capacidades, unidades físicas, asignaciones,
permisos de soporte, catálogo público y Dashboard.

Reglas:
  * MODELO comercial ≠ UNIDAD física. La unidad conserva id_vehiculo (el que
    usan CONTROL, MONITOREO, el historial y el ESP32).
  * No hay borrado destructivo de unidades: baja lógica (estado «inactivo»).
  * Asignar/reasignar cierra la asignación anterior (se conserva la historia),
    revoca permisos de soporte y corta de inmediato las suscripciones WSS de
    quien perdió el acceso.
"""
from app.core.config import Settings
from app.core.errores import Conflicto, Prohibido, RecursoNoEncontrado, SolicitudInvalida
from app.core.seguridad import Actor
from app.db.database import Database
from app.db.procedimientos import Fila
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.auditoria import ServicioAuditoria
from app.services.autorizacion import PROPIETARIO, ServicioAutorizacion
from app.services.control import EjecutorDemos, ServicioControl
from app.services.usuarios import ServicioUsuarios

ESTADOS_LIBRES = ("disponible", "exhibicion", "inactivo")


def _bools(fila: Fila, *campos) -> Fila:
    for c in campos:
        if c in fila and fila[c] is not None:
            fila[c] = bool(fila[c])
    fila.pop("total", None)
    return fila


class ServicioInventario:
    def __init__(self, settings: Settings, db: Database, sp: ProcedimientosAdmin, autorizacion: ServicioAutorizacion,
                 usuarios: ServicioUsuarios, control: ServicioControl, ejecutor: EjecutorDemos,
                 auditoria: ServicioAuditoria):
        self._s = settings
        self._db = db
        self._sp = sp
        self._authz = autorizacion
        self._usuarios = usuarios
        self._control = control
        self._ejecutor = ejecutor
        self._aud = auditoria

    # ============================================================ MODELOS
    def modelos(self, solo_activos: bool = False) -> list[Fila]:
        return [_bools(f, "activo") for f in self._sp.modelos_listar(solo_activos)]

    def modelo(self, id_modelo: int) -> Fila:
        fila = self._sp.modelo_obtener(id_modelo)
        if fila is None:
            raise RecursoNoEncontrado("El modelo no existe")
        fila = _bools(fila, "activo")
        fila["capacidades"] = self.capacidades(id_modelo)
        return fila

    def capacidades(self, id_modelo: int) -> list[Fila]:
        return [_bools(f, "permitido_invitado", "activo") for f in self._sp.capacidades_listar(id_modelo)]

    def capacidades_por_codigo(self, id_modelo: int | None) -> dict[int, Fila]:
        return {} if id_modelo is None else {c["codigo"]: c for c in self.capacidades(id_modelo)}

    def crear_modelo(self, admin: Actor, datos) -> int:
        try:
            id_modelo = self._sp.modelo_crear(datos.nombre, datos.descripcion, datos.imagen, datos.microcontrolador)
        except Conflicto:
            raise Conflicto("Ya existe un modelo con ese nombre")
        for cap in datos.capacidades or []:
            self._guardar_capacidad(id_modelo, cap)
        self._aud.registrar(admin, "crear_modelo", "modelo", id_modelo, detalle=datos.nombre)
        return id_modelo

    def actualizar_modelo(self, admin: Actor, id_modelo: int, datos) -> Fila:
        self.modelo(id_modelo)
        try:
            self._sp.modelo_actualizar(id_modelo, datos.nombre, datos.descripcion, datos.imagen, datos.microcontrolador)
        except Conflicto:
            raise Conflicto("Ya existe un modelo con ese nombre")
        self._aud.registrar(admin, "actualizar_modelo", "modelo", id_modelo)
        return self.modelo(id_modelo)

    def cambiar_activo_modelo(self, admin: Actor, id_modelo: int, activo: bool) -> Fila:
        self.modelo(id_modelo)
        self._sp.modelo_cambiar_activo(id_modelo, activo)
        self._aud.registrar(admin, "activar_modelo" if activo else "desactivar_modelo", "modelo", id_modelo)
        return self.modelo(id_modelo)

    def _guardar_capacidad(self, id_modelo: int, cap, conn=None) -> None:
        tipo = "detener" if cap.nombre == "DETENER" else cap.tipo
        self._sp.capacidad_guardar(id_modelo, cap.nombre, cap.codigo, cap.descripcion, tipo, cap.duracion_max_ms,
                                   cap.permitido_invitado, cap.activo, conn=conn)

    def guardar_capacidad(self, admin: Actor, id_modelo: int, cap) -> list[Fila]:
        self.modelo(id_modelo)
        with self._db.transaccion() as conn:
            self._guardar_capacidad(id_modelo, cap, conn)
        self._aud.registrar(admin, "guardar_capacidad", "modelo", id_modelo,
                            detalle=f"{cap.nombre} codigo={cap.codigo} activo={cap.activo} invitado={cap.permitido_invitado}")
        return self.capacidades(id_modelo)

    # =========================================================== UNIDADES
    def unidades(self, estado, id_modelo, texto, limite: int, desplazamiento: int) -> dict:
        filas = self._sp.unidades_listar(estado, id_modelo, texto, limite, desplazamiento)
        total = int(filas[0]["total"]) if filas else 0
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento,
                "elementos": [_bools(f, "activo", "conectado") for f in filas]}

    def unidad(self, id_vehiculo: int) -> Fila:
        fila = self._authz.unidad(id_vehiculo)
        fila["asignaciones"] = self._sp.asignaciones_listar(id_vehiculo)
        soporte = self._sp.soporte_activo(id_vehiculo)
        fila["soporte_hasta"] = soporte["fecha_expira"] if soporte else None
        return fila

    def crear_unidad(self, admin: Actor, datos) -> int:
        modelo = self.modelo(datos.id_modelo)
        if not modelo["activo"]:
            raise Conflicto("El modelo está inactivo")
        if not modelo["capacidades"]:
            raise Conflicto("El modelo no tiene capacidades (comandos) registradas")
        try:
            with self._db.transaccion() as conn:
                id_vehiculo = self._sp.unidad_crear(datos.id_modelo, datos.numero_serie, datos.nombre,
                                                    datos.descripcion, datos.estado_comercial, conn=conn)
        except Conflicto:
            self._aud.registrar(admin, "crear_unidad", "unidad", datos.numero_serie, "rechazado", "número de serie duplicado")
            raise Conflicto("Ya existe una unidad con ese número de serie")
        self._aud.registrar(admin, "crear_unidad", "unidad", id_vehiculo,
                            detalle=f"serie={datos.numero_serie} modelo={datos.id_modelo} estado={datos.estado_comercial}")
        return id_vehiculo

    def actualizar_unidad(self, admin: Actor, id_vehiculo: int, datos) -> Fila:
        self._authz.unidad(id_vehiculo)
        try:
            self._sp.unidad_actualizar(id_vehiculo, datos.numero_serie, datos.nombre, datos.descripcion)
        except Conflicto:
            raise Conflicto("Ya existe una unidad con ese número de serie")
        self._aud.registrar(admin, "actualizar_unidad", "unidad", id_vehiculo)
        return self.unidad(id_vehiculo)

    def _sin_actividad(self, id_vehiculo: int) -> None:
        if self._ejecutor.demo_en_curso(id_vehiculo):
            raise Conflicto("La unidad está ejecutando una DEMO: detenla antes de cambiarla")
        if self._sp.invitado_activa_vehiculo(id_vehiculo):
            raise Conflicto("Hay una prueba de Invitado en curso en esta unidad")

    async def cambiar_estado(self, admin: Actor, id_vehiculo: int, estado: str, revalidar) -> Fila:
        if estado not in ESTADOS_LIBRES:
            raise SolicitudInvalida("Para «asignado» usa la asignación a un comprador")
        unidad = self._authz.unidad(id_vehiculo)
        if unidad["estado_comercial"] == "asignado":
            raise Conflicto("La unidad está asignada a un comprador: primero libérala")
        self._sin_actividad(id_vehiculo)
        self._sp.unidad_cambiar_estado(id_vehiculo, estado)
        self._control.liberar(id_vehiculo)
        self._aud.registrar(admin, "cambiar_estado_unidad", "unidad", id_vehiculo,
                            detalle=f"{unidad['estado_comercial']} -> {estado}")
        await revalidar(id_vehiculo=id_vehiculo)
        return self.unidad(id_vehiculo)

    async def asignar(self, admin: Actor, id_vehiculo: int, id_usuario: int, revalidar) -> Fila:
        unidad = self._authz.unidad(id_vehiculo)
        if unidad["estado_comercial"] == "inactivo":
            raise Conflicto("No se puede asignar una unidad dada de baja")
        cliente = self._usuarios.validar_cliente_activo(id_usuario)
        if unidad["id_propietario"] == id_usuario:
            raise Conflicto("La unidad ya pertenece a ese comprador")
        self._sin_actividad(id_vehiculo)
        with self._db.transaccion() as conn:
            self._sp.unidad_asignar(id_vehiculo, id_usuario, admin.id, conn=conn)
        self._control.liberar(id_vehiculo)
        anterior = unidad["id_propietario"]
        self._aud.registrar(admin, "reasignar_unidad" if anterior else "asignar_unidad", "unidad", id_vehiculo,
                            detalle=f"propietario {anterior or '-'} -> {id_usuario} ({cliente['usuario']})")
        await revalidar(id_vehiculo=id_vehiculo)  # revoca al titular anterior y a cualquier otro acceso
        return self.unidad(id_vehiculo)

    async def liberar(self, admin: Actor, id_vehiculo: int, estado: str, revalidar) -> Fila:
        if estado not in ("disponible", "exhibicion"):
            raise SolicitudInvalida("Al liberar, la unidad queda «disponible» o «exhibicion»")
        unidad = self._authz.unidad(id_vehiculo)
        if unidad["estado_comercial"] != "asignado":
            raise Conflicto("La unidad no está asignada")
        self._sin_actividad(id_vehiculo)
        with self._db.transaccion() as conn:
            self._sp.unidad_liberar(id_vehiculo, estado, "LIBERADA", conn=conn)
        self._control.liberar(id_vehiculo)
        self._aud.registrar(admin, "liberar_unidad", "unidad", id_vehiculo,
                            detalle=f"propietario {unidad['id_propietario']} -> ninguno; estado {estado}")
        await revalidar(id_vehiculo=id_vehiculo)
        return self.unidad(id_vehiculo)

    # ===================================================== MIS VEHÍCULOS
    def mis_vehiculos(self, actor: Actor) -> list[Fila]:
        return [_bools(f, "activo", "conectado") for f in self._sp.mis_vehiculos(actor.id)]

    def otorgar_soporte(self, actor: Actor, id_vehiculo: int, minutos: int) -> Fila:
        unidad, nivel = self._authz.para_lectura(actor, id_vehiculo)
        if nivel != PROPIETARIO:
            raise Prohibido("Solo el comprador propietario puede autorizar soporte")
        minutos = min(minutos, self._s.soporte_minutos_max)
        self._sp.soporte_otorgar(id_vehiculo, actor.id, minutos)
        self._aud.registrar(actor, "otorgar_soporte", "unidad", id_vehiculo, detalle=f"{minutos} min")
        soporte = self._sp.soporte_activo(id_vehiculo)
        return {"id_vehiculo": id_vehiculo, "soporte_hasta": soporte["fecha_expira"] if soporte else None}

    async def revocar_soporte(self, actor: Actor, id_vehiculo: int, revalidar) -> Fila:
        unidad, nivel = self._authz.para_lectura(actor, id_vehiculo)
        if nivel != PROPIETARIO:
            raise Prohibido("Solo el comprador propietario puede revocar el soporte")
        self._sp.soporte_revocar(id_vehiculo)
        if self._control.ocupada_por_otro(id_vehiculo, actor.clave):
            await self._control.detener_por_sistema(id_vehiculo, "SOPORTE_REVOCADO")
        self._aud.registrar(actor, "revocar_soporte", "unidad", id_vehiculo)
        await revalidar(id_vehiculo=id_vehiculo)
        return {"id_vehiculo": id_vehiculo, "soporte_hasta": None}

    # ====================================================== CATÁLOGO
    def catalogo(self) -> dict:
        modelos = self._sp.catalogo_modelos()
        for m in modelos:
            m["capacidades"] = [
                {"nombre": c["nombre"], "codigo": c["codigo"], "descripcion": c["descripcion"], "tipo": c["tipo"],
                 "permitido_invitado": c["permitido_invitado"]}
                for c in self.capacidades(m["id_modelo"]) if c["activo"]
            ]
        return {"modelos": modelos, "unidades_exhibicion": self._sp.catalogo_exhibicion(),
                "prueba_segundos": self._s.invitado_segundos,
                "prueba_duracion_max_ms": self._s.invitado_duracion_max_ms}

    # ===================================================== DASHBOARD
    def dashboard(self, conexiones_wss: int) -> Fila:
        resumen = dict(self._sp.dashboard_resumen())
        resumen["conexiones_wss_navegador"] = conexiones_wss
        return resumen

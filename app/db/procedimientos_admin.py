"""Acceso a datos de ADMINISTRACIÓN (4.3): los 44 procedimientos de V006.

Igual que en 4.1/4.2, la API solo ejecuta procedimientos almacenados con
parámetros enlazados (%s). Los métodos que deben formar parte de una
transacción reciben `conn` (ver Database.transaccion()).
"""
from app.db.procedimientos import Fila, ProcedimientosAlmacenados


def _uno(filas: list[Fila]) -> Fila | None:
    return filas[0] if filas else None


def _bool(v) -> bool | None:
    return None if v is None else bool(v)


class ProcedimientosAdmin(ProcedimientosAlmacenados):
    # ------------------------------------------------------------ usuarios
    def usuario_crear(self, usuario, nombre, correo, telefono, rol, hash_pw, conn=None) -> int:
        return self._id(self._ejecutar("sp_usuario_crear", (usuario, nombre, correo, telefono, rol, hash_pw), conn),
                        "id_usuario")

    def usuario_por_login(self, usuario: str) -> Fila | None:
        return _uno(self._ejecutar("sp_usuario_por_login", (usuario,)))

    def usuario_por_id(self, id_usuario: int) -> Fila | None:
        return _uno(self._ejecutar("sp_usuario_por_id", (id_usuario,)))

    def usuarios_listar(self, rol, texto, activo, limite, desplazamiento) -> list[Fila]:
        return self._ejecutar("sp_usuarios_listar", (rol, texto, activo, limite, desplazamiento))

    def usuario_actualizar(self, id_usuario, nombre, correo, telefono) -> None:
        self._ejecutar("sp_usuario_actualizar", (id_usuario, nombre, correo, telefono))

    def usuario_cambiar_activo(self, id_usuario, activo: bool) -> None:
        self._ejecutar("sp_usuario_cambiar_activo", (id_usuario, activo))

    def usuario_cambiar_password(self, id_usuario, hash_pw) -> None:
        self._ejecutar("sp_usuario_cambiar_password", (id_usuario, hash_pw))

    def usuario_cerrar_sesiones(self, id_usuario) -> None:
        self._ejecutar("sp_usuario_cerrar_sesiones", (id_usuario,))

    def usuario_login_fallido(self, id_usuario) -> None:
        self._ejecutar("sp_usuario_login_fallido", (id_usuario,))

    def usuario_login_exitoso(self, id_usuario) -> None:
        self._ejecutar("sp_usuario_login_exitoso", (id_usuario,))

    def usuarios_contar_admin(self) -> int:
        return int(self._ejecutar("sp_usuarios_contar_admin")[0]["total"])

    # ------------------------------------------------------------- modelos
    def modelo_crear(self, nombre, descripcion, imagen, micro) -> int:
        return self._id(self._ejecutar("sp_modelo_crear", (nombre, descripcion, imagen, micro)), "id_modelo")

    def modelo_actualizar(self, id_modelo, nombre, descripcion, imagen, micro) -> None:
        self._ejecutar("sp_modelo_actualizar", (id_modelo, nombre, descripcion, imagen, micro))

    def modelo_cambiar_activo(self, id_modelo, activo: bool) -> None:
        self._ejecutar("sp_modelo_cambiar_activo", (id_modelo, activo))

    def modelos_listar(self, solo_activos: bool) -> list[Fila]:
        return self._ejecutar("sp_modelos_listar", (solo_activos,))

    def modelo_obtener(self, id_modelo: int) -> Fila | None:
        return _uno(self._ejecutar("sp_modelo_obtener", (id_modelo,)))

    def capacidades_listar(self, id_modelo: int) -> list[Fila]:
        return self._ejecutar("sp_capacidades_listar", (id_modelo,))

    def capacidad_guardar(self, id_modelo, nombre, codigo, descripcion, tipo, duracion_max, invitado, activo,
                          conn=None) -> None:
        self._ejecutar("sp_capacidad_guardar",
                       (id_modelo, nombre, codigo, descripcion, tipo, duracion_max, invitado, activo), conn)

    # ------------------------------------------------------------ unidades
    def unidad_crear(self, id_modelo, numero_serie, nombre, descripcion, estado, conn=None) -> int:
        return self._id(self._ejecutar("sp_unidad_crear", (id_modelo, numero_serie, nombre, descripcion, estado),
                                       conn), "id_vehiculo")

    def unidades_listar(self, estado, id_modelo, texto, limite, desplazamiento) -> list[Fila]:
        return self._ejecutar("sp_unidades_listar", (estado, id_modelo, texto, limite, desplazamiento))

    def unidad_obtener(self, id_vehiculo: int) -> Fila | None:
        return _uno(self._ejecutar("sp_unidad_obtener", (id_vehiculo,)))

    def unidad_actualizar(self, id_vehiculo, numero_serie, nombre, descripcion) -> None:
        self._ejecutar("sp_unidad_actualizar", (id_vehiculo, numero_serie, nombre, descripcion))

    def unidad_cambiar_estado(self, id_vehiculo, estado, conn=None) -> None:
        self._ejecutar("sp_unidad_cambiar_estado", (id_vehiculo, estado), conn)

    def unidad_asignar(self, id_vehiculo, id_usuario, id_admin, conn=None) -> None:
        self._ejecutar("sp_unidad_asignar", (id_vehiculo, id_usuario, id_admin), conn)

    def unidad_liberar(self, id_vehiculo, estado, motivo, conn=None) -> None:
        self._ejecutar("sp_unidad_liberar", (id_vehiculo, estado, motivo), conn)

    def asignaciones_listar(self, id_vehiculo: int) -> list[Fila]:
        return self._ejecutar("sp_asignaciones_listar", (id_vehiculo,))

    def mis_vehiculos(self, id_usuario: int) -> list[Fila]:
        return self._ejecutar("sp_mis_vehiculos", (id_usuario,))

    # ------------------------------------------------------------- soporte
    def soporte_otorgar(self, id_vehiculo, id_usuario, minutos) -> int:
        return self._id(self._ejecutar("sp_soporte_otorgar", (id_vehiculo, id_usuario, minutos)), "id_permiso")

    def soporte_revocar(self, id_vehiculo) -> int:
        return int(self._ejecutar("sp_soporte_revocar", (id_vehiculo,))[0]["revocados"])

    def soporte_activo(self, id_vehiculo) -> Fila | None:
        return _uno(self._ejecutar("sp_soporte_activo", (id_vehiculo,)))

    # --------------------------------------------------------------- demos
    def demos_vehiculo(self, id_vehiculo: int) -> list[Fila]:
        return self._ejecutar("sp_demos_vehiculo", (id_vehiculo,))

    def demo_obtener(self, id_demo: int) -> Fila | None:
        return _uno(self._ejecutar("sp_demo_obtener", (id_demo,)))

    def demo_crear_v2(self, id_vehiculo, nombre, descripcion, tipo, id_propietario, conn=None) -> int:
        return self._id(self._ejecutar("sp_demo_crear_v2", (id_vehiculo, nombre, descripcion, tipo, id_propietario),
                                       conn), "id_demo")

    def demo_actualizar(self, id_demo, nombre, descripcion, activo, conn=None) -> None:
        self._ejecutar("sp_actualizar_demo", (id_demo, nombre, descripcion, activo), conn)

    def demo_vaciar_pasos(self, id_demo, conn=None) -> None:
        self._ejecutar("sp_demo_vaciar_pasos", (id_demo,), conn)

    def demo_agregar_paso(self, id_demo, id_comando, orden, duracion_ms, pausa_ms, conn=None) -> None:
        self._ejecutar("sp_agregar_movimiento_demo", (id_demo, id_comando, orden, duracion_ms, pausa_ms), conn)

    # ----------------------------------------------------------- invitados
    def invitado_iniciar(self, codigo, id_vehiculo, segundos) -> Fila:
        return self._ejecutar("sp_invitado_iniciar", (codigo, id_vehiculo, segundos))[0]

    def invitado_obtener(self, codigo) -> Fila | None:
        fila = _uno(self._ejecutar("sp_invitado_obtener", (codigo,)))
        if fila:
            fila["vigente"] = bool(fila["vigente"])
        return fila

    def invitado_finalizar(self, codigo, motivo) -> int:
        return int(self._ejecutar("sp_invitado_finalizar", (codigo, motivo))[0]["finalizadas"])

    def invitado_expirar(self) -> list[Fila]:
        return self._ejecutar("sp_invitado_expirar")

    def invitado_activa_vehiculo(self, id_vehiculo) -> Fila | None:
        return _uno(self._ejecutar("sp_invitado_activa_vehiculo", (id_vehiculo,)))

    # ------------------------------------------------------------ catálogo
    def catalogo_modelos(self) -> list[Fila]:
        return self._ejecutar("sp_catalogo_modelos")

    def catalogo_exhibicion(self) -> list[Fila]:
        filas = self._ejecutar("sp_catalogo_exhibicion")
        for f in filas:
            f["conectado"] = bool(f["conectado"])
            f["ocupada"] = bool(f["ocupada"])
        return filas

    # ----------------------------------------------------------- auditoría
    def auditoria_registrar(self, actor_tipo, id_actor, actor, accion, recurso, id_recurso, resultado, detalle) -> None:
        self._ejecutar("sp_auditoria_registrar",
                       (actor_tipo, id_actor, actor, accion, recurso, id_recurso, resultado, detalle))

    def auditoria_listar(self, accion, actor_tipo, resultado, limite, desplazamiento) -> list[Fila]:
        return self._ejecutar("sp_auditoria_listar", (accion, actor_tipo, resultado, limite, desplazamiento))

    # ----------------------------------------------------------- dashboard
    def dashboard_resumen(self) -> Fila:
        return self._ejecutar("sp_dashboard_resumen")[0]

"""Capa de acceso a datos: los 21 Stored Procedures de carrito_iot.

Toda la persistencia pasa por aquí. Los parámetros siempre se envían enlazados
(%s), nunca concatenados en el SQL.
"""
from typing import Any

import pymysql

from app.core.errores import BaseDatosNoDisponible
from app.db.database import Database, traducir_error_mysql

Fila = dict[str, Any]


class ProcedimientosAlmacenados:
    def __init__(self, db: Database):
        self._db = db

    # ------------------------------------------------------------------ núcleo
    @staticmethod
    def _llamar(conn, nombre: str, params: tuple) -> list[Fila]:
        marcadores = ", ".join(["%s"] * len(params))
        try:
            with conn.cursor() as cur:
                cur.execute(f"CALL {nombre}({marcadores})", params)
                filas = list(cur.fetchall()) if cur.description else []
                while cur.nextset():  # consumir el resultado de estado del CALL
                    pass
            return filas
        except pymysql.MySQLError as exc:
            raise traducir_error_mysql(exc) from exc

    def _ejecutar(self, nombre: str, params: tuple = (), conn=None) -> list[Fila]:
        if conn is not None:
            return self._llamar(conn, nombre, params)
        with self._db.conexion() as nueva:
            return self._llamar(nueva, nombre, params)

    @staticmethod
    def _id(filas: list[Fila], campo: str) -> int:
        if not filas or filas[0].get(campo) is None:
            raise BaseDatosNoDisponible("La base de datos no devolvió el identificador creado")
        return int(filas[0][campo])

    # ------------------------------------------------------- VEHÍCULOS (5)
    def crear_vehiculo(self, nombre, modelo, descripcion, microcontrolador) -> int:
        filas = self._ejecutar("sp_crear_vehiculo", (nombre, modelo, descripcion, microcontrolador))
        return self._id(filas, "id_vehiculo")

    def obtener_vehiculos(self) -> list[Fila]:
        return self._ejecutar("sp_obtener_vehiculos")

    def obtener_vehiculo(self, id_vehiculo: int) -> Fila | None:
        filas = self._ejecutar("sp_obtener_vehiculo", (id_vehiculo,))
        return filas[0] if filas else None

    def actualizar_vehiculo(self, id_vehiculo, nombre, modelo, descripcion, microcontrolador, activo) -> None:
        self._ejecutar("sp_actualizar_vehiculo", (id_vehiculo, nombre, modelo, descripcion, microcontrolador, activo))

    def eliminar_vehiculo(self, id_vehiculo: int) -> None:
        self._ejecutar("sp_eliminar_vehiculo", (id_vehiculo,))

    # -------------------------------------------------------- COMANDOS (4)
    def crear_comando(self, id_vehiculo, nombre, codigo, descripcion) -> int:
        filas = self._ejecutar("sp_crear_comando", (id_vehiculo, nombre, codigo, descripcion))
        return self._id(filas, "id_comando")

    def obtener_comandos_vehiculo(self, id_vehiculo: int) -> list[Fila]:
        return self._ejecutar("sp_obtener_comandos_vehiculo", (id_vehiculo,))

    def actualizar_comando(self, id_comando, nombre, codigo, descripcion, activo) -> None:
        self._ejecutar("sp_actualizar_comando", (id_comando, nombre, codigo, descripcion, activo))

    def eliminar_comando(self, id_comando: int) -> None:
        self._ejecutar("sp_eliminar_comando", (id_comando,))

    # ---------------------------------------------------------- ESTADO (2)
    def actualizar_estado(self, id_vehiculo, id_comando, conectado: bool, conn=None) -> None:
        self._ejecutar("sp_actualizar_estado", (id_vehiculo, id_comando, conectado), conn)

    def obtener_estado(self, id_vehiculo: int) -> Fila | None:
        filas = self._ejecutar("sp_obtener_estado", (id_vehiculo,))
        return filas[0] if filas else None

    # ------------------------------------------------------- HISTORIAL (2)
    def registrar_historial(self, id_vehiculo, id_comando, origen: str, conn=None) -> None:
        self._ejecutar("sp_registrar_historial", (id_vehiculo, id_comando, origen), conn)

    def obtener_historial(self, id_vehiculo: int) -> list[Fila]:
        return self._ejecutar("sp_obtener_historial", (id_vehiculo,))

    # ------------------------------------------------------------ DEMO (4)
    def crear_demo(self, id_vehiculo, nombre, descripcion) -> int:
        filas = self._ejecutar("sp_crear_demo", (id_vehiculo, nombre, descripcion))
        return self._id(filas, "id_demo")

    def obtener_demos(self, id_vehiculo: int) -> list[Fila]:
        return self._ejecutar("sp_obtener_demos", (id_vehiculo,))

    def actualizar_demo(self, id_demo, nombre, descripcion, activo) -> None:
        self._ejecutar("sp_actualizar_demo", (id_demo, nombre, descripcion, activo))

    def eliminar_demo(self, id_demo: int) -> None:
        self._ejecutar("sp_eliminar_demo", (id_demo,))

    # ------------------------------------------------ MOVIMIENTOS DEMO (4)
    def agregar_movimiento_demo(self, id_demo, id_comando, orden, duracion_ms, pausa_ms) -> None:
        self._ejecutar("sp_agregar_movimiento_demo", (id_demo, id_comando, orden, duracion_ms, pausa_ms))

    def obtener_movimientos_demo(self, id_demo: int) -> list[Fila]:
        return self._ejecutar("sp_obtener_movimientos_demo", (id_demo,))

    def actualizar_movimiento_demo(self, id_demo_movimiento, id_comando, orden, duracion_ms, pausa_ms) -> None:
        self._ejecutar(
            "sp_actualizar_movimiento_demo", (id_demo_movimiento, id_comando, orden, duracion_ms, pausa_ms)
        )

    def eliminar_movimiento_demo(self, id_demo_movimiento: int) -> None:
        self._ejecutar("sp_eliminar_movimiento_demo", (id_demo_movimiento,))

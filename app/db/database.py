"""Conexión a Amazon RDS (MySQL) con PyMySQL.

Cada operación abre y cierra su propia conexión (sin estado compartido entre hilos)
y los errores de MySQL se traducen a excepciones de dominio.
"""
import time
from contextlib import contextmanager
from typing import Iterator

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import Settings
from app.core.errores import BaseDatosNoDisponible, Conflicto, SolicitudInvalida


def traducir_error_mysql(exc: Exception) -> Exception:
    if isinstance(exc, pymysql.err.IntegrityError):
        codigo = exc.args[0] if exc.args else None
        if codigo == 1062:
            return Conflicto("Registro duplicado: ya existe un registro con ese nombre, código u orden")
        if codigo == 1451:
            return Conflicto("No se puede eliminar o modificar: el registro está en uso (por ejemplo, en una DEMO)")
        if codigo == 1452:
            return SolicitudInvalida("Referencia inexistente: el registro relacionado no existe")
        return Conflicto("La operación viola una restricción de la base de datos")
    if isinstance(exc, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
        return BaseDatosNoDisponible("Base de datos no disponible")
    return exc


class Database:
    def __init__(self, settings: Settings):
        self._s = settings

    def _conectar(self, autocommit: bool) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._s.db_host,
            port=self._s.db_port,
            user=self._s.db_user,
            password=self._s.db_password,
            database=self._s.db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=autocommit,
            connect_timeout=self._s.db_connect_timeout,
            read_timeout=15,
            write_timeout=15,
        )

    @contextmanager
    def conexion(self) -> Iterator[pymysql.connections.Connection]:
        """Conexión en modo autocommit para consultas y escrituras simples."""
        try:
            conn = self._conectar(autocommit=True)
        except Exception as exc:
            raise traducir_error_mysql(exc) from exc
        try:
            yield conn
        except pymysql.MySQLError as exc:
            raise traducir_error_mysql(exc) from exc
        finally:
            conn.close()

    @contextmanager
    def transaccion(self) -> Iterator[pymysql.connections.Connection]:
        """Transacción atómica: COMMIT si todo sale bien, ROLLBACK ante cualquier error."""
        try:
            conn = self._conectar(autocommit=False)
        except Exception as exc:
            raise traducir_error_mysql(exc) from exc
        try:
            conn.begin()
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if isinstance(exc, pymysql.MySQLError):
                raise traducir_error_mysql(exc) from exc
            raise
        finally:
            conn.close()

    def verificar(self) -> float:
        """Ejecuta SELECT 1 y devuelve la latencia en ms. Lanza BaseDatosNoDisponible si falla."""
        inicio = time.perf_counter()
        with self.conexion() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return round((time.perf_counter() - inicio) * 1000, 1)

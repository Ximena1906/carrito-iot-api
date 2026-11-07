"""Servicios de catálogo: vehículos, comandos, estado/historial y DEMO.

Contienen las reglas de negocio de consulta y administración. No conocen HTTP;
lanzan excepciones de dominio que la capa de rutas convierte en códigos HTTP.
"""
from app.core.errores import Conflicto, RecursoNoEncontrado
from app.db.procedimientos import Fila, ProcedimientosAlmacenados


class ServicioVehiculos:
    def __init__(self, sp: ProcedimientosAlmacenados):
        self._sp = sp

    def listar(self) -> list[Fila]:
        return self._sp.obtener_vehiculos()

    def obtener(self, id_vehiculo: int) -> Fila:
        vehiculo = self._sp.obtener_vehiculo(id_vehiculo)
        if vehiculo is None:
            raise RecursoNoEncontrado(f"El vehículo {id_vehiculo} no existe")
        return vehiculo

    def obtener_activo(self, id_vehiculo: int) -> Fila:
        vehiculo = self.obtener(id_vehiculo)
        if not vehiculo["activo"]:
            raise Conflicto(f"El vehículo {id_vehiculo} está inactivo")
        return vehiculo

    def crear(self, datos) -> int:
        return self._sp.crear_vehiculo(datos.nombre, datos.modelo, datos.descripcion, datos.microcontrolador)

    def actualizar(self, id_vehiculo: int, datos) -> Fila:
        self.obtener(id_vehiculo)
        self._sp.actualizar_vehiculo(
            id_vehiculo, datos.nombre, datos.modelo, datos.descripcion, datos.microcontrolador, datos.activo
        )
        return self.obtener(id_vehiculo)

    def eliminar(self, id_vehiculo: int) -> None:
        self.obtener(id_vehiculo)
        self._sp.eliminar_vehiculo(id_vehiculo)


class ServicioComandos:
    def __init__(self, sp: ProcedimientosAlmacenados, vehiculos: ServicioVehiculos):
        self._sp = sp
        self._vehiculos = vehiculos

    def listar(self, id_vehiculo: int) -> list[Fila]:
        self._vehiculos.obtener(id_vehiculo)
        return self._sp.obtener_comandos_vehiculo(id_vehiculo)

    def obtener(self, id_vehiculo: int, id_comando: int) -> Fila:
        for c in self.listar(id_vehiculo):
            if c["id_comando"] == id_comando:
                return c
        raise RecursoNoEncontrado(f"El comando {id_comando} no pertenece al vehículo {id_vehiculo}")

    def resolver_activo(self, id_vehiculo: int, nombre: str | None = None, codigo: int | None = None) -> Fila:
        """Busca un comando del vehículo por nombre o código y verifica que esté activo."""
        for c in self._sp.obtener_comandos_vehiculo(id_vehiculo):
            if (nombre is not None and c["nombre"] == nombre) or (codigo is not None and c["codigo"] == codigo):
                if not c["activo"]:
                    raise Conflicto(f"El comando {c['nombre']} está inactivo")
                return c
        buscado = nombre if nombre is not None else f"código {codigo}"
        raise RecursoNoEncontrado(f"El comando '{buscado}' no existe para el vehículo {id_vehiculo}")

    def buscar_por_nombre(self, id_vehiculo: int, nombre: str) -> Fila | None:
        for c in self._sp.obtener_comandos_vehiculo(id_vehiculo):
            if c["nombre"] == nombre:
                return c
        return None

    def crear(self, id_vehiculo: int, datos) -> int:
        self._vehiculos.obtener(id_vehiculo)
        return self._sp.crear_comando(id_vehiculo, datos.nombre, datos.codigo, datos.descripcion)

    def actualizar(self, id_vehiculo: int, id_comando: int, datos) -> Fila:
        self.obtener(id_vehiculo, id_comando)
        self._sp.actualizar_comando(id_comando, datos.nombre, datos.codigo, datos.descripcion, datos.activo)
        return self.obtener(id_vehiculo, id_comando)

    def eliminar(self, id_vehiculo: int, id_comando: int) -> None:
        self.obtener(id_vehiculo, id_comando)
        self._sp.eliminar_comando(id_comando)


class ServicioEstado:
    def __init__(self, sp: ProcedimientosAlmacenados, vehiculos: ServicioVehiculos, limite_historial: int):
        self._sp = sp
        self._vehiculos = vehiculos
        self._limite = limite_historial

    def obtener_estado(self, id_vehiculo: int) -> dict:
        vehiculo = self._vehiculos.obtener(id_vehiculo)
        estado = self._sp.obtener_estado(id_vehiculo)
        if estado is None:  # vehículo válido sin estado registrado todavía
            return {"id_vehiculo": id_vehiculo, "vehiculo": vehiculo["nombre"], "conectado": False}
        return dict(estado)

    def historial(self, id_vehiculo: int, limite: int | None = None) -> list[Fila]:
        """Como máximo los N movimientos individuales más recientes (el SP ya ordena DESC)."""
        self._vehiculos.obtener(id_vehiculo)
        limite = min(limite or self._limite, self._limite)
        return self._sp.obtener_historial(id_vehiculo)[:limite]


class ServicioDemos:
    def __init__(self, sp: ProcedimientosAlmacenados, vehiculos: ServicioVehiculos, comandos: ServicioComandos):
        self._sp = sp
        self._vehiculos = vehiculos
        self._comandos = comandos

    def listar(self, id_vehiculo: int) -> list[Fila]:
        self._vehiculos.obtener(id_vehiculo)
        return self._sp.obtener_demos(id_vehiculo)

    def obtener(self, id_vehiculo: int, id_demo: int) -> Fila:
        for d in self.listar(id_vehiculo):
            if d["id_demo"] == id_demo:
                return d
        raise RecursoNoEncontrado(f"La DEMO {id_demo} no pertenece al vehículo {id_vehiculo}")

    def crear(self, id_vehiculo: int, datos) -> int:
        self._vehiculos.obtener(id_vehiculo)
        return self._sp.crear_demo(id_vehiculo, datos.nombre, datos.descripcion)

    def actualizar(self, id_vehiculo: int, id_demo: int, datos) -> Fila:
        self.obtener(id_vehiculo, id_demo)
        self._sp.actualizar_demo(id_demo, datos.nombre, datos.descripcion, datos.activo)
        return self.obtener(id_vehiculo, id_demo)

    def eliminar(self, id_vehiculo: int, id_demo: int) -> None:
        self.obtener(id_vehiculo, id_demo)
        self._sp.eliminar_demo(id_demo)

    # ----------------------------------------------- movimientos de la DEMO
    def movimientos(self, id_vehiculo: int, id_demo: int) -> list[Fila]:
        self.obtener(id_vehiculo, id_demo)
        return self._sp.obtener_movimientos_demo(id_demo)

    def _movimiento(self, id_vehiculo: int, id_demo: int, id_mov: int) -> Fila:
        for m in self.movimientos(id_vehiculo, id_demo):
            if m["id_demo_movimiento"] == id_mov:
                return m
        raise RecursoNoEncontrado(f"El movimiento {id_mov} no pertenece a la DEMO {id_demo}")

    def agregar_movimiento(self, id_vehiculo: int, id_demo: int, datos) -> list[Fila]:
        self.obtener(id_vehiculo, id_demo)
        self._comandos.obtener(id_vehiculo, datos.id_comando)  # el comando debe ser del mismo vehículo
        self._sp.agregar_movimiento_demo(id_demo, datos.id_comando, datos.orden, datos.duracion_ms, datos.pausa_ms)
        return self._sp.obtener_movimientos_demo(id_demo)

    def actualizar_movimiento(self, id_vehiculo: int, id_demo: int, id_mov: int, datos) -> list[Fila]:
        self._movimiento(id_vehiculo, id_demo, id_mov)
        self._comandos.obtener(id_vehiculo, datos.id_comando)
        self._sp.actualizar_movimiento_demo(id_mov, datos.id_comando, datos.orden, datos.duracion_ms, datos.pausa_ms)
        return self._sp.obtener_movimientos_demo(id_demo)

    def eliminar_movimiento(self, id_vehiculo: int, id_demo: int, id_mov: int) -> None:
        self._movimiento(id_vehiculo, id_demo, id_mov)
        self._sp.eliminar_movimiento_demo(id_mov)

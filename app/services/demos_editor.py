"""Editor de DEMO (4.3): demos de FÁBRICA (empresa) y PRIVADAS (comprador).

Visibilidad:
  * Administrador (nivel empresa/soporte): DEMO de fábrica de la unidad.
  * Usuario propietario: DEMO de fábrica activas + SUS DEMO privadas.
  * Invitado: solo DEMO de fábrica activas de su unidad de exhibición.
Edición:
  * Fábrica: solo el Administrador y sobre unidades NO vendidas.
  * Privada: solo su propietario, sobre su propia unidad.
Cada paso se valida EN EL SERVIDOR: el comando debe pertenecer a la unidad,
estar activo y existir como capacidad activa de su modelo; la duración no
supera el límite de esa capacidad, y la DEMO tiene un máximo de pasos y de
duración total. El encabezado y los pasos se guardan en UNA transacción.
"""
from app.core.config import Settings
from app.core.errores import Conflicto, Prohibido, RecursoNoEncontrado, SolicitudInvalida
from app.core.seguridad import Actor
from app.db.database import Database
from app.db.procedimientos import Fila
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.auditoria import ServicioAuditoria
from app.services.autorizacion import EMPRESA, PROPIETARIO
from app.services.control import EjecutorDemos

FABRICA, PRIVADA = "fabrica", "privada"


class ServicioEditorDemos:
    def __init__(self, settings: Settings, db: Database, sp: ProcedimientosAdmin, ejecutor: EjecutorDemos,
                 auditoria: ServicioAuditoria):
        self._s = settings
        self._db = db
        self._sp = sp
        self._ejecutor = ejecutor
        self._aud = auditoria

    @staticmethod
    def _normalizar(d: Fila) -> Fila:
        d["activo"] = bool(d["activo"])
        return d

    def visible(self, actor: Actor, nivel: str, demo: Fila) -> bool:
        if demo["tipo"] == FABRICA:
            return demo["activo"] or actor.es_admin
        return actor.es_usuario and nivel == PROPIETARIO and demo["id_propietario"] == actor.id

    def editable(self, actor: Actor, nivel: str, demo: Fila) -> bool:
        if demo["tipo"] == FABRICA:
            return actor.es_admin and nivel == EMPRESA
        return actor.es_usuario and nivel == PROPIETARIO and demo["id_propietario"] == actor.id

    def listar(self, actor: Actor, nivel: str, id_vehiculo: int) -> list[Fila]:
        demos = [self._normalizar(d) for d in self._sp.demos_vehiculo(id_vehiculo)]
        visibles = [d for d in demos if self.visible(actor, nivel, d)]
        for d in visibles:
            d["editable"] = self.editable(actor, nivel, d)
        return visibles

    def obtener(self, actor: Actor, nivel: str, id_vehiculo: int, id_demo: int) -> Fila:
        demo = self._sp.demo_obtener(id_demo)
        if demo is None or demo["id_vehiculo"] != id_vehiculo:
            raise RecursoNoEncontrado("La DEMO no existe en esta unidad")
        demo = self._normalizar(demo)
        if not self.visible(actor, nivel, demo):
            raise RecursoNoEncontrado("La DEMO no existe en esta unidad")
        demo["editable"] = self.editable(actor, nivel, demo)
        demo["pasos"] = self._sp.obtener_movimientos_demo(id_demo)
        return demo

    # ------------------------------------------------------- validación
    def _resolver_pasos(self, unidad: Fila, pasos, permitir_vacia: bool = False) -> list[tuple]:
        if not pasos and permitir_vacia:
            return []
        if not pasos:
            raise SolicitudInvalida("La DEMO necesita al menos un paso")
        if len(pasos) > self._s.demo_max_pasos:
            raise SolicitudInvalida(f"Máximo {self._s.demo_max_pasos} pasos por DEMO")
        comandos = {c["nombre"]: c for c in self._sp.obtener_comandos_vehiculo(unidad["id_vehiculo"])}
        capacidades = {c["codigo"]: c for c in self._sp.capacidades_listar(unidad["id_modelo"])}
        resueltos, total = [], 0
        for i, paso in enumerate(pasos, start=1):
            comando = comandos.get(paso.comando)
            if comando is None or not comando["activo"]:
                raise SolicitudInvalida(f"Paso {i}: el comando {paso.comando} no está habilitado en esta unidad")
            cap = capacidades.get(comando["codigo"])
            if cap is None or not cap["activo"]:
                raise SolicitudInvalida(f"Paso {i}: el modelo {unidad['modelo']} no admite {paso.comando}")
            if paso.duracion_ms > cap["duracion_max_ms"]:
                raise SolicitudInvalida(
                    f"Paso {i}: {paso.comando} admite como máximo {cap['duracion_max_ms']} ms en este modelo")
            total += paso.duracion_ms + paso.pausa_ms
            resueltos.append((comando["id_comando"], i, paso.duracion_ms, paso.pausa_ms))
        if total > self._s.demo_max_total_ms:
            raise SolicitudInvalida(f"La DEMO no puede durar más de {self._s.demo_max_total_ms // 1000} s en total")
        return resueltos

    def _guardar_pasos(self, id_demo: int, resueltos, conn) -> None:
        self._sp.demo_vaciar_pasos(id_demo, conn=conn)
        for id_comando, orden, duracion, pausa in resueltos:
            self._sp.demo_agregar_paso(id_demo, id_comando, orden, duracion, pausa, conn=conn)

    # ------------------------------------------------------------ escritura
    def crear(self, actor: Actor, unidad: Fila, nivel: str, datos) -> int:
        if actor.es_admin and nivel == EMPRESA:
            tipo, propietario = FABRICA, None
        elif actor.es_usuario and nivel == PROPIETARIO:
            tipo, propietario = PRIVADA, actor.id
        else:
            raise Prohibido("No puedes crear DEMO en esta unidad")
        # pasos=None: flujo heredado de 4.1 (encabezado primero, pasos con /movimientos)
        resueltos = [] if datos.pasos is None else self._resolver_pasos(unidad, datos.pasos)
        with self._db.transaccion() as conn:
            id_demo = self._sp.demo_crear_v2(unidad["id_vehiculo"], datos.nombre, datos.descripcion, tipo,
                                              propietario, conn=conn)
            self._guardar_pasos(id_demo, resueltos, conn)
        self._aud.registrar(actor, "crear_demo", "demo", id_demo,
                            detalle=f"unidad={unidad['id_vehiculo']} tipo={tipo} pasos={len(resueltos)}")
        return id_demo

    def guardar(self, actor: Actor, unidad: Fila, nivel: str, id_demo: int, datos) -> Fila:
        demo = self.obtener(actor, nivel, unidad["id_vehiculo"], id_demo)
        if not demo["editable"]:
            raise Prohibido("No puedes modificar esta DEMO")
        en_curso = self._ejecutor.demo_en_curso(unidad["id_vehiculo"])
        if en_curso and en_curso["id_demo"] == id_demo:
            raise Conflicto("La DEMO se está ejecutando: cancélala antes de editarla")
        resueltos = self._resolver_pasos(unidad, datos.pasos)
        with self._db.transaccion() as conn:
            self._sp.demo_actualizar(id_demo, datos.nombre, datos.descripcion, datos.activo, conn=conn)
            self._guardar_pasos(id_demo, resueltos, conn)
        self._aud.registrar(actor, "editar_demo", "demo", id_demo, detalle=f"pasos={len(resueltos)}")
        return self.obtener(actor, nivel, unidad["id_vehiculo"], id_demo)

    def dar_de_baja(self, actor: Actor, unidad: Fila, nivel: str, id_demo: int) -> None:
        demo = self.obtener(actor, nivel, unidad["id_vehiculo"], id_demo)
        if not demo["editable"]:
            raise Prohibido("No puedes eliminar esta DEMO")
        en_curso = self._ejecutor.demo_en_curso(unidad["id_vehiculo"])
        if en_curso and en_curso["id_demo"] == id_demo:
            raise Conflicto("La DEMO se está ejecutando: cancélala antes de eliminarla")
        self._sp.demo_actualizar(id_demo, demo["nombre"], demo["descripcion"], False)
        self._aud.registrar(actor, "baja_demo", "demo", id_demo)

    def verificar_ejecucion(self, actor: Actor, nivel: str, id_vehiculo: int, id_demo: int) -> Fila:
        """La DEMO debe ser visible y estar activa para quien la ejecuta."""
        demo = self.obtener(actor, nivel, id_vehiculo, id_demo)
        if not demo["activo"]:
            raise Conflicto("La DEMO está inactiva")
        return demo

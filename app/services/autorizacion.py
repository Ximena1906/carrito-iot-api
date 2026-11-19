"""Autorización por RECURSO (unidad física), además del rol.

Niveles de acceso de un actor sobre una unidad:
  * propietario : Usuario dueño de una unidad «asignado».
  * soporte     : Administrador sobre una unidad vendida, SOLO con permiso de
                  soporte vigente otorgado por el comprador.
  * empresa     : Administrador sobre unidades no vendidas (disponible,
                  exhibición o inactiva).
  * invitado    : sesión temporal vigente sobre SU unidad de exhibición.
Sin nivel -> se rechaza. Al Usuario se le responde 404 (no se revela si la
unidad existe); al Administrador y al Invitado, 403.
"""
import time

from app.core.errores import Conflicto, NoAutenticado, Prohibido, RecursoNoEncontrado
from app.core.seguridad import Actor
from app.db.procedimientos import Fila
from app.db.procedimientos_admin import ProcedimientosAdmin

PROPIETARIO, SOPORTE, EMPRESA, INVITADO = "propietario", "soporte", "empresa", "invitado"


# Un mismo rechazo (actor + unidad) se audita como máximo una vez por ventana,
# para que reintentos o reconexiones no llenen la bitácora.
VENTANA_AUDITORIA_S = 60


class ServicioAutorizacion:
    def __init__(self, sp: ProcedimientosAdmin, auditoria=None):
        self._sp = sp
        self._aud = auditoria
        self._ultimos: dict[tuple[str, int], float] = {}

    def _auditar_rechazo(self, actor: Actor, id_vehiculo: int, motivo: str) -> None:
        if self._aud is None:
            return
        clave, ahora = (actor.clave, id_vehiculo), time.monotonic()
        if ahora - self._ultimos.get(clave, -VENTANA_AUDITORIA_S) < VENTANA_AUDITORIA_S:
            return
        self._ultimos[clave] = ahora
        if len(self._ultimos) > 5000:
            self._ultimos = {k: v for k, v in self._ultimos.items() if ahora - v < VENTANA_AUDITORIA_S}
        self._aud.registrar(actor, "acceso_denegado", "unidad", id_vehiculo, "rechazado", motivo)

    def unidad(self, id_vehiculo: int) -> Fila:
        fila = self._sp.unidad_obtener(id_vehiculo)
        if fila is None:
            raise RecursoNoEncontrado("La unidad no existe")
        fila["conectado"] = bool(fila["conectado"])
        fila["activo"] = bool(fila["activo"])
        return fila

    def nivel(self, actor: Actor, unidad: Fila) -> str | None:
        estado = unidad["estado_comercial"]
        if actor.es_usuario:
            return PROPIETARIO if estado == "asignado" and unidad["id_propietario"] == actor.id else None
        if actor.es_invitado:
            return INVITADO if estado == "exhibicion" and unidad["id_vehiculo"] == actor.id_vehiculo_invitado else None
        if actor.es_admin:
            if estado == "asignado":
                return SOPORTE if self._sp.soporte_activo(unidad["id_vehiculo"]) else None
            return EMPRESA
        return None

    def _rechazar(self, actor: Actor | None) -> None:
        if actor is None:
            raise NoAutenticado("Se requiere iniciar sesión")
        if actor.es_usuario:
            raise RecursoNoEncontrado("La unidad no existe o no está asignada a tu cuenta")
        if actor.es_invitado:
            raise Prohibido("Tu sesión de prueba solo permite usar la unidad reservada")
        raise Prohibido("La unidad pertenece a un comprador: se requiere su autorización de soporte")

    def para_lectura(self, actor: Actor | None, id_vehiculo: int) -> tuple[Fila, str]:
        """Consultar estado, historial, comandos, demos o suscribirse por WSS."""
        if actor is None:
            raise NoAutenticado("Se requiere iniciar sesión")
        try:
            unidad = self.unidad(id_vehiculo)
        except RecursoNoEncontrado:
            self._auditar_rechazo(actor, id_vehiculo, "unidad inexistente")
            if actor.es_usuario:
                raise RecursoNoEncontrado("La unidad no existe o no está asignada a tu cuenta")
            raise
        nivel = self.nivel(actor, unidad)
        if nivel is None:
            self._auditar_rechazo(actor, id_vehiculo, f"sin permiso sobre unidad {unidad['estado_comercial']}")
            self._rechazar(actor)
        return unidad, nivel

    def para_control(self, actor: Actor | None, id_vehiculo: int) -> tuple[Fila, str]:
        """Enviar comandos o ejecutar/cancelar DEMO."""
        unidad, nivel = self.para_lectura(actor, id_vehiculo)
        if unidad["estado_comercial"] == "inactivo" or not unidad["activo"]:
            raise Conflicto("La unidad está dada de baja (inactiva)")
        if nivel == EMPRESA and unidad["estado_comercial"] == "exhibicion":
            sesion = self._sp.invitado_activa_vehiculo(id_vehiculo)
            if sesion:
                raise Conflicto("Un Invitado tiene reservada esta unidad de exhibición en este momento")
        return unidad, nivel

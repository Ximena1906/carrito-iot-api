"""Resuelve el ACTOR de un token y lo revalida contra RDS en cada uso.

* Cuenta (admin/usuario): debe existir, estar activa y conservar la misma
  version_token (logout, desactivación o cambio de contraseña la invalidan).
* Invitado: su sesión temporal debe seguir vigente en sesiones_invitado.
"""
import jwt

from app.core.errores import NoAutenticado
from app.core.seguridad import INVITADO, Actor, ServicioAutenticacion
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.usuarios import ServicioUsuarios


class ServicioIdentidad:
    def __init__(self, auth: ServicioAutenticacion, sp: ProcedimientosAdmin, usuarios: ServicioUsuarios):
        self._auth = auth
        self._sp = sp
        self._usuarios = usuarios

    def actor(self, token: str) -> Actor:
        try:
            payload = self._auth.decodificar(token)
        except jwt.ExpiredSignatureError:
            raise NoAutenticado("La sesión expiró. Inicia sesión de nuevo.")
        except jwt.PyJWTError:
            raise NoAutenticado("Token inválido")
        if payload.get("tipo") == INVITADO:
            fila = self._sp.invitado_obtener(str(payload.get("sub", ""))[:32])
            if fila is None or not fila["vigente"]:
                raise NoAutenticado("La sesión de prueba terminó")
            return Actor(INVITADO, int(fila["id_sesion"]), "Invitado", None, fila["codigo"], int(fila["id_vehiculo"]))
        return self._usuarios.actor_desde_payload(payload)

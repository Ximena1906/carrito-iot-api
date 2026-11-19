"""Cuentas (Administrador y Usuario/comprador): login, logout y gestión de clientes.

* Contraseñas con hash PBKDF2 (nunca en texto plano ni en logs).
* Login con bloqueo temporal tras 5 intentos fallidos y mensaje genérico
  (no revela si el usuario existe).
* Logout = invalidar TODOS los tokens de la cuenta (version_token + 1).
"""
import logging

from app.core.config import Settings
from app.core.errores import Conflicto, DemasiadasSolicitudes, NoAutenticado, RecursoNoEncontrado, SolicitudInvalida
from app.core.seguridad import ADMIN, HASH_FALSO, USUARIO, Actor, ServicioAutenticacion, hash_password, verificar_password
from app.db.procedimientos import Fila
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.auditoria import ServicioAuditoria

log = logging.getLogger("carrito_iot.usuarios")
MENSAJE_LOGIN = "Usuario o contraseña incorrectos"


class ServicioUsuarios:
    def __init__(self, settings: Settings, sp: ProcedimientosAdmin, auth: ServicioAutenticacion,
                 auditoria: ServicioAuditoria):
        self._s = settings
        self._sp = sp
        self._auth = auth
        self._aud = auditoria
        self._admin_listo = False

    # ---------------------------------------------------------- arranque
    def asegurar_admin_inicial(self) -> None:
        """Crea la primera cuenta Administrador desde .env si la tabla no tiene ninguno."""
        if self._admin_listo:
            return
        if self._sp.usuarios_contar_admin() == 0:
            self._sp.usuario_crear(self._s.admin_usuario, self._s.admin_nombre, None, None, ADMIN,
                                   hash_password(self._s.admin_password))
            self._aud.registrar(None, "crear_admin_inicial", "usuario", self._s.admin_usuario,
                                actor_tipo="sistema", actor_nombre="arranque")
            log.info("Cuenta administrador inicial creada (%s)", self._s.admin_usuario)
        self._admin_listo = True

    # ------------------------------------------------------------- sesión
    def login(self, usuario: str, password: str) -> dict:
        self.asegurar_admin_inicial()
        fila = self._sp.usuario_por_login(usuario)
        if fila is None:
            verificar_password(password, HASH_FALSO)  # mismo tiempo de respuesta
            self._aud.registrar(None, "login", "usuario", usuario, "rechazado", "usuario inexistente")
            raise NoAutenticado(MENSAJE_LOGIN)
        if fila["bloqueado"]:
            self._aud.registrar(None, "login", "usuario", usuario, "rechazado", "cuenta bloqueada temporalmente")
            raise DemasiadasSolicitudes("Demasiados intentos fallidos. Espera 5 minutos e intenta de nuevo.")
        if not verificar_password(password, fila["password_hash"]) or not fila["activo"]:
            if fila["activo"]:
                self._sp.usuario_login_fallido(fila["id_usuario"])
            self._aud.registrar(None, "login", "usuario", usuario, "rechazado",
                                "contraseña incorrecta" if fila["activo"] else "cuenta inactiva")
            raise NoAutenticado(MENSAJE_LOGIN)
        self._sp.usuario_login_exitoso(fila["id_usuario"])
        token, segundos = self._auth.token_usuario(fila)
        actor = Actor(fila["rol"], fila["id_usuario"], fila["nombre"], fila["usuario"])
        self._aud.registrar(actor, "login", "usuario", fila["id_usuario"])
        return {"access_token": token, "token_type": "bearer", "rol": fila["rol"],
                "expira_en_segundos": segundos, "usuario": fila["usuario"], "nombre": fila["nombre"],
                "id_usuario": fila["id_usuario"]}

    def actor_desde_payload(self, payload: dict) -> Actor:
        """Revalida en RDS una cuenta del token: existe, está activa y el token no fue invalidado."""
        try:
            id_usuario = int(payload["sub"])
        except (KeyError, ValueError):
            raise NoAutenticado("Token inválido")
        fila = self._sp.usuario_por_id(id_usuario)
        if fila is None or not fila["activo"] or int(fila["version_token"]) != int(payload.get("ver", -1)):
            raise NoAutenticado("La sesión expiró o fue cerrada. Inicia sesión de nuevo.")
        return Actor(fila["rol"], fila["id_usuario"], fila["nombre"], fila["usuario"])

    def logout(self, actor: Actor) -> None:
        self._sp.usuario_cerrar_sesiones(actor.id)
        self._aud.registrar(actor, "logout", "usuario", actor.id)

    # ---------------------------------------------------- gestión (admin)
    @staticmethod
    def _sin_hash(fila: Fila) -> Fila:
        fila.pop("password_hash", None)
        fila.pop("total", None)
        if "activo" in fila:
            fila["activo"] = bool(fila["activo"])
        return fila

    def listar(self, rol: str | None, texto: str | None, activo: bool | None, limite: int, desplazamiento: int) -> dict:
        filas = self._sp.usuarios_listar(rol, texto, None if activo is None else int(activo), limite, desplazamiento)
        total = int(filas[0]["total"]) if filas else 0
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento,
                "elementos": [self._sin_hash(f) for f in filas]}

    def obtener(self, id_usuario: int) -> Fila:
        fila = self._sp.usuario_por_id(id_usuario)
        if fila is None:
            raise RecursoNoEncontrado("El usuario no existe")
        fila.pop("version_token", None)
        fila["activo"] = bool(fila["activo"])
        return fila

    def crear(self, admin: Actor, datos) -> int:
        if datos.rol not in (ADMIN, USUARIO):
            raise SolicitudInvalida("Rol no válido")
        try:
            nuevo = self._sp.usuario_crear(datos.usuario, datos.nombre, datos.correo, datos.telefono, datos.rol,
                                           hash_password(datos.password))
        except Conflicto:
            self._aud.registrar(admin, "crear_usuario", "usuario", datos.usuario, "rechazado", "usuario o correo duplicado")
            raise Conflicto("Ya existe una cuenta con ese usuario o correo")
        self._aud.registrar(admin, "crear_usuario", "usuario", nuevo, detalle=f"rol={datos.rol} usuario={datos.usuario}")
        return nuevo

    def actualizar(self, admin: Actor, id_usuario: int, datos) -> Fila:
        self.obtener(id_usuario)
        try:
            self._sp.usuario_actualizar(id_usuario, datos.nombre, datos.correo, datos.telefono)
        except Conflicto:
            raise Conflicto("Ya existe una cuenta con ese correo")
        self._aud.registrar(admin, "actualizar_usuario", "usuario", id_usuario)
        return self.obtener(id_usuario)

    def cambiar_activo(self, admin: Actor, id_usuario: int, activo: bool) -> Fila:
        fila = self.obtener(id_usuario)
        if not activo and id_usuario == admin.id:
            raise Conflicto("No puedes desactivar tu propia cuenta")
        if not activo and fila["rol"] == ADMIN and self._sp.usuarios_contar_admin() <= 1:
            raise Conflicto("Debe quedar al menos un Administrador activo")
        self._sp.usuario_cambiar_activo(id_usuario, activo)  # también invalida sus tokens
        self._aud.registrar(admin, "activar_usuario" if activo else "desactivar_usuario", "usuario", id_usuario)
        return self.obtener(id_usuario)

    def restablecer_password(self, admin: Actor, id_usuario: int, password: str) -> None:
        self.obtener(id_usuario)
        self._sp.usuario_cambiar_password(id_usuario, hash_password(password))
        self._aud.registrar(admin, "restablecer_password", "usuario", id_usuario)

    def validar_cliente_activo(self, id_usuario: int) -> Fila:
        fila = self.obtener(id_usuario)
        if fila["rol"] != USUARIO:
            raise SolicitudInvalida("Solo se pueden asignar unidades a cuentas con rol Usuario (comprador)")
        if not fila["activo"]:
            raise Conflicto("La cuenta del comprador está inactiva")
        return fila

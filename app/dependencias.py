"""Contenedor de dependencias: crea una sola instancia de cada componente."""
from app.core.config import obtener_settings
from app.core.limites import Limitador
from app.core.seguridad import ServicioAutenticacion
from app.db.database import Database
from app.db.procedimientos_admin import ProcedimientosAdmin
from app.services.auditoria import ServicioAuditoria
from app.services.autorizacion import ServicioAutorizacion
from app.services.catalogo import ServicioComandos, ServicioDemos, ServicioEstado, ServicioVehiculos
from app.services.conexiones import ServicioConexiones
from app.services.control import EjecutorDemos, ServicioControl
from app.services.demos_editor import ServicioEditorDemos
from app.services.identidad import ServicioIdentidad
from app.services.inventario import ServicioInventario
from app.services.invitados import ServicioInvitados
from app.services.usuarios import ServicioUsuarios
from app.websocket.gestor import GestorWebSocket

settings = obtener_settings()
db = Database(settings)
sp = ProcedimientosAdmin(db)          # 21 SP originales + 44 de administración
gestor_ws = GestorWebSocket()
ejecutor_demos = EjecutorDemos(sp, gestor_ws)
auth = ServicioAutenticacion(settings)

# 4.1 / 4.2 (sin cambios de contrato)
vehiculos = ServicioVehiculos(sp)
comandos = ServicioComandos(sp, vehiculos)
estado = ServicioEstado(sp, vehiculos, settings.historial_limite)
demos = ServicioDemos(sp, vehiculos, comandos)
control = ServicioControl(settings, db, sp, vehiculos, comandos, demos, gestor_ws, ejecutor_demos)

# 4.3 · Administración, roles y autorización por unidad
auditoria = ServicioAuditoria(sp)
usuarios = ServicioUsuarios(settings, sp, auth, auditoria)
identidad = ServicioIdentidad(auth, sp, usuarios)
autorizacion = ServicioAutorizacion(sp, auditoria)
conexiones = ServicioConexiones(identidad, autorizacion, gestor_ws)
inventario = ServicioInventario(settings, db, sp, autorizacion, usuarios, control, ejecutor_demos, auditoria)
editor_demos = ServicioEditorDemos(settings, db, sp, ejecutor_demos, auditoria)
invitados = ServicioInvitados(settings, sp, auth, control, gestor_ws, conexiones, auditoria)

# Límites de solicitudes
limite_login = Limitador(10, 60, "Demasiados intentos de inicio de sesión. Espera un minuto.")
limite_invitado = Limitador(6, 60, "Demasiadas solicitudes de prueba. Espera un minuto.")
limite_comandos = Limitador(40, 10, "Demasiados comandos seguidos. Espera unos segundos.")

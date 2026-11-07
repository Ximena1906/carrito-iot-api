"""Contenedor de dependencias: crea una sola instancia de cada componente."""
from app.core.config import obtener_settings
from app.core.seguridad import ServicioAutenticacion
from app.db.database import Database
from app.db.procedimientos import ProcedimientosAlmacenados
from app.services.catalogo import ServicioComandos, ServicioDemos, ServicioEstado, ServicioVehiculos
from app.services.control import EjecutorDemos, ServicioControl
from app.websocket.gestor import GestorWebSocket

settings = obtener_settings()
db = Database(settings)
sp = ProcedimientosAlmacenados(db)
gestor_ws = GestorWebSocket()
ejecutor_demos = EjecutorDemos(sp, gestor_ws)
auth = ServicioAutenticacion(settings)

vehiculos = ServicioVehiculos(sp)
comandos = ServicioComandos(sp, vehiculos)
estado = ServicioEstado(sp, vehiculos, settings.historial_limite)
demos = ServicioDemos(sp, vehiculos, comandos)
control = ServicioControl(settings, db, sp, vehiculos, comandos, demos, gestor_ws, ejecutor_demos)

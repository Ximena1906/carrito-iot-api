"""Configuración de la aplicación leída desde variables de entorno / archivo .env.

Ninguna credencial se escribe en el código: todas provienen de .env (excluido de Git).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Aplicación
    app_nombre: str = "Carrito IoT API"
    app_version: str = "2.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Amazon RDS (MySQL)
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "carrito_iot"
    db_connect_timeout: int = 5

    # Seguridad
    jwt_secret: str
    jwt_minutos: int = 480
    # Primera cuenta Administrador: se crea en la tabla usuarios al arrancar
    # SOLO si todavía no existe ningún administrador (la contraseña se guarda como hash).
    admin_usuario: str = "administrador"
    admin_password: str
    admin_nombre: str = "Administrador de la empresa"
    # 4.1/4.2 (cuenta fija «operador»): ya no se usa; se conserva opcional para no romper .env anteriores.
    operador_usuario: str | None = None
    operador_password: str | None = None
    # Dispositivo físico (ESP32): token del .env válido solo para esta unidad
    dispositivo_token: str
    dispositivo_id_vehiculo: int = 1

    # CORS: orígenes separados por coma (ej. GitHub Pages)
    cors_origenes: str = "http://localhost:5500,http://127.0.0.1:5500"

    # Reglas de control
    duracion_default_ms: int = 1000
    duracion_max_ms: int = 10000
    historial_limite: int = 10
    # 4.3 · Invitados y seguridad física
    invitado_segundos: int = 180            # duración de la prueba temporal
    invitado_duracion_max_ms: int = 2000    # tope por movimiento para Invitado
    invitado_gracia_desconexion_s: int = 15 # sin WSS durante este tiempo -> fin de sesión
    control_exclusivo_s: int = 20           # ventana de control exclusivo por sesión
    soporte_minutos_max: int = 240          # máximo de un permiso de soporte
    demo_max_pasos: int = 30
    demo_max_total_ms: int = 120000

    # Recursos de Swagger UI (CDN por defecto)
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def obtener_settings() -> Settings:
    return Settings()

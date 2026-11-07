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
    app_version: str = "1.0.0"
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
    operador_usuario: str = "operador"
    operador_password: str
    admin_usuario: str = "administrador"
    admin_password: str
    dispositivo_token: str

    # CORS: orígenes separados por coma (ej. GitHub Pages)
    cors_origenes: str = "http://localhost:5500,http://127.0.0.1:5500"

    # Reglas de control
    duracion_default_ms: int = 1000
    duracion_max_ms: int = 10000
    historial_limite: int = 10

    # Recursos de Swagger UI (CDN por defecto)
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def obtener_settings() -> Settings:
    return Settings()

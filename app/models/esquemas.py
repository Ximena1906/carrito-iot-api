"""Modelos Pydantic de entrada y salida (validación de tipos, rangos y formatos)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NOMBRE_COMANDO = r"^[A-Z0-9_]{1,60}$"
ORIGEN = r"^[A-Za-z0-9_\-]{1,30}$"


class Mensaje(BaseModel):
    detail: str


class Creado(BaseModel):
    id: int
    mensaje: str


# ------------------------------------------------------------------ Auth
class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    rol: str
    expira_en_segundos: int


# ------------------------------------------------------------- Vehículos
class VehiculoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80, examples=["Carrito IoT"])
    modelo: str | None = Field(default=None, max_length=80, examples=["Carrito RC con garra"])
    descripcion: str | None = Field(default=None, max_length=255)
    microcontrolador: str | None = Field(default=None, max_length=50, examples=["ESP32"])


class VehiculoActualizar(VehiculoCrear):
    activo: bool = True


class Vehiculo(BaseModel):
    id_vehiculo: int
    nombre: str
    modelo: str | None
    descripcion: str | None
    microcontrolador: str | None
    fecha_registro: datetime | None
    activo: bool


# -------------------------------------------------------------- Comandos
class ComandoCrear(BaseModel):
    nombre: str = Field(pattern=NOMBRE_COMANDO, examples=["AVANZAR"],
                        description="Mayúsculas, números y guion bajo")
    codigo: int = Field(ge=1, le=9999, examples=[1])
    descripcion: str | None = Field(default=None, max_length=255)


class ComandoActualizar(ComandoCrear):
    activo: bool = True


class Comando(BaseModel):
    id_comando: int
    id_vehiculo: int
    nombre: str
    codigo: int
    descripcion: str | None
    activo: bool


# ------------------------------------------------------ Estado e historial
class Estado(BaseModel):
    id_vehiculo: int
    vehiculo: str
    id_comando: int | None = None
    comando: str | None = None
    codigo: int | None = None
    conectado: bool = False
    fecha_actualizacion: datetime | None = None
    demo_en_curso: int | None = Field(default=None, description="id_demo en ejecución, si existe")


class RegistroHistorial(BaseModel):
    id_historial: int
    id_vehiculo: int
    comando: str | None
    codigo: int | None
    fecha_hora: datetime
    origen: str


# ------------------------------------------------------------------ DEMO
class DemoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80, examples=["Demo principal"])
    descripcion: str | None = Field(default=None, max_length=255)


class DemoActualizar(DemoCrear):
    activo: bool = True


class Demo(BaseModel):
    id_demo: int
    id_vehiculo: int
    nombre: str
    descripcion: str | None
    activo: bool


class MovimientoDemoCrear(BaseModel):
    id_comando: int = Field(ge=1)
    orden: int = Field(ge=1, le=1000)
    duracion_ms: int = Field(ge=50, le=60000, examples=[2000])
    pausa_ms: int = Field(default=0, ge=0, le=60000, examples=[300])


class MovimientoDemo(BaseModel):
    id_demo_movimiento: int
    orden: int
    id_comando: int
    comando: str
    codigo: int
    duracion_ms: int
    pausa_ms: int


# --------------------------------------------------------------- Control
class SolicitudMovimiento(BaseModel):
    """Indica el comando por su nombre O por su código (exactamente uno)."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"comando": "AVANZAR", "duracion_ms": 2000}]})

    comando: str | None = Field(default=None, pattern=NOMBRE_COMANDO)
    codigo: int | None = Field(default=None, ge=1, le=9999)
    duracion_ms: int | None = Field(
        default=None, ge=50, le=10000,
        description="Tiempo máximo que el ESP32 mantiene activa la salida. Si se omite se usa el valor por defecto.",
    )
    origen: str = Field(default="API", pattern=ORIGEN, examples=["SWAGGER", "WEB"])

    @model_validator(mode="after")
    def _uno_solo(self):
        if (self.comando is None) == (self.codigo is None):
            raise ValueError("Envíe exactamente uno de los campos: 'comando' o 'codigo'")
        return self


class RespuestaMovimiento(BaseModel):
    estado: Literal["aceptado"] = "aceptado"
    id_evento: str
    id_vehiculo: int
    id_comando: int
    comando: str
    codigo: int
    duracion_ms: int
    origen: str
    timestamp: str
    clientes_notificados: int
    dispositivo_conectado: bool
    demo_cancelada: bool = False


class SolicitudDemo(BaseModel):
    origen: str = Field(default="API", pattern=ORIGEN)


class RespuestaDemo(BaseModel):
    estado: Literal["en_curso", "cancelada", "sin_demo"]
    id_vehiculo: int
    id_demo: int | None = None
    nombre: str | None = None
    total_pasos: int | None = None

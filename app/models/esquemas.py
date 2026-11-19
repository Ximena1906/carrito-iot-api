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


# =====================================================================
# 4.3 · ADMINISTRACIÓN, ROLES, DEMO EDITABLES E INVITADOS
# =====================================================================
USUARIO_LOGIN = r"^[a-zA-Z0-9_.\-]{3,40}$"
SERIE = r"^[A-Za-z0-9_\-]{3,40}$"
EstadoUnidad = Literal["disponible", "asignado", "exhibicion", "inactivo"]


class Pagina(BaseModel):
    total: int
    limite: int
    desplazamiento: int


class TokenSesion(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    rol: Literal["admin", "usuario", "invitado"]
    expira_en_segundos: int
    usuario: str | None = None
    nombre: str | None = None
    id_usuario: int | None = None


class Yo(BaseModel):
    tipo: Literal["admin", "usuario", "invitado"]
    id: int
    nombre: str
    usuario: str | None = None
    id_vehiculo_invitado: int | None = None


# -------------------------------------------------------------- usuarios
class UsuarioCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "usuario": "comprador1", "nombre": "Cliente de prueba", "correo": "cliente@ejemplo.com",
        "telefono": "7710000000", "rol": "usuario", "password": "ContraseñaSegura1"}]})
    usuario: str = Field(pattern=USUARIO_LOGIN, description="Nombre de inicio de sesión (3–40, sin espacios)")
    nombre: str = Field(min_length=2, max_length=100)
    correo: str | None = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s]{7,20}$")
    rol: Literal["usuario", "admin"] = "usuario"
    password: str = Field(min_length=8, max_length=72)


class UsuarioActualizar(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    correo: str | None = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s]{7,20}$")


class UsuarioPassword(BaseModel):
    password: str = Field(min_length=8, max_length=72)


class CambioActivo(BaseModel):
    activo: bool


class UsuarioSalida(BaseModel):
    id_usuario: int
    usuario: str
    nombre: str
    correo: str | None = None
    telefono: str | None = None
    rol: Literal["admin", "usuario"]
    activo: bool
    fecha_alta: datetime | None = None
    fecha_baja: datetime | None = None
    unidades: int | None = None


class PaginaUsuarios(Pagina):
    elementos: list[UsuarioSalida]


# --------------------------------------------------------------- modelos
class CapacidadGuardar(BaseModel):
    nombre: str = Field(pattern=NOMBRE_COMANDO, examples=["AVANZAR"])
    codigo: int = Field(ge=1, le=9999, examples=[1])
    descripcion: str | None = Field(default=None, max_length=255)
    tipo: Literal["sostenido", "pulso", "detener"] = "sostenido"
    duracion_max_ms: int = Field(default=10000, ge=50, le=10000)
    permitido_invitado: bool = False
    activo: bool = True


class Capacidad(CapacidadGuardar):
    id_modelo_comando: int
    id_modelo: int


class ModeloCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "nombre": "Excavadora IoT", "descripcion": "Excavadora a escala con brazo hidráulico",
        "microcontrolador": "ESP32", "imagen": "assets/img/modelos/excavadora.svg",
        "capacidades": [{"nombre": "AVANZAR", "codigo": 1, "permitido_invitado": True},
                        {"nombre": "DETENER", "codigo": 9, "tipo": "detener", "permitido_invitado": True}]}]})
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=500)
    imagen: str | None = Field(default=None, max_length=255, pattern=r"^[A-Za-z0-9_./\-]*$")
    microcontrolador: str | None = Field(default=None, max_length=50)
    capacidades: list[CapacidadGuardar] = Field(default_factory=list, max_length=40)


class ModeloActualizar(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=500)
    imagen: str | None = Field(default=None, max_length=255, pattern=r"^[A-Za-z0-9_./\-]*$")
    microcontrolador: str | None = Field(default=None, max_length=50)


class Modelo(BaseModel):
    id_modelo: int
    nombre: str
    descripcion: str | None = None
    imagen: str | None = None
    microcontrolador: str | None = None
    activo: bool
    fecha_alta: datetime | None = None
    unidades: int | None = None
    unidades_exhibicion: int | None = None
    capacidades: list[Capacidad] | int | None = None


# -------------------------------------------------------------- unidades
class UnidadCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "id_modelo": 1, "numero_serie": "UNI-0002", "nombre": "Carrito de exhibición 2",
        "estado_comercial": "disponible"}]})
    id_modelo: int = Field(ge=1)
    numero_serie: str = Field(pattern=SERIE, description="Identificador único de la unidad física")
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    estado_comercial: Literal["disponible", "exhibicion"] = "disponible"


class UnidadActualizar(BaseModel):
    numero_serie: str = Field(pattern=SERIE)
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)


class CambioEstadoUnidad(BaseModel):
    estado_comercial: Literal["disponible", "exhibicion", "inactivo"]


class AsignarUnidad(BaseModel):
    id_usuario: int = Field(ge=1, description="Comprador (rol usuario) que recibe la unidad")


class Asignacion(BaseModel):
    id_asignacion: int
    id_usuario: int
    usuario_nombre: str
    usuario: str
    asignado_por: int | None = None
    asignado_por_nombre: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime | None = None
    motivo_fin: str | None = None


class Unidad(BaseModel):
    id_vehiculo: int = Field(description="ID usado por CONTROL, MONITOREO, historial y ESP32")
    numero_serie: str | None = None
    nombre: str
    descripcion: str | None = None
    id_modelo: int | None = None
    modelo: str | None = None
    estado_comercial: EstadoUnidad
    activo: bool
    id_propietario: int | None = None
    propietario: str | None = None
    propietario_usuario: str | None = None
    conectado: bool = Field(description="ESP32 con sesión WSS activa en el servidor (no confirma movimiento físico)")
    fecha_registro: datetime | None = None
    fecha_baja: datetime | None = None
    soporte_hasta: datetime | None = None
    asignaciones: list[Asignacion] | None = None


class PaginaUnidades(Pagina):
    elementos: list[Unidad]


class Soporte(BaseModel):
    minutos: int = Field(default=30, ge=5, le=240, description="Duración del permiso de soporte")


class EstadoSoporte(BaseModel):
    id_vehiculo: int
    soporte_hasta: datetime | None = None


# ----------------------------------------------------------- DEMO editor
class PasoDemo(BaseModel):
    comando: str = Field(pattern=NOMBRE_COMANDO, examples=["AVANZAR"])
    duracion_ms: int = Field(ge=50, le=10000, examples=[1500])
    pausa_ms: int = Field(default=0, ge=0, le=5000, examples=[300])


class DemoEditorCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "nombre": "Mi recorrido", "descripcion": "Avanza, gira y regresa",
        "pasos": [{"comando": "AVANZAR", "duracion_ms": 1500, "pausa_ms": 300},
                  {"comando": "GIRAR_DERECHA", "duracion_ms": 800},
                  {"comando": "RETROCEDER", "duracion_ms": 1500}]}]})
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    pasos: list[PasoDemo] | None = Field(default=None, max_length=30,
                                         description="Secuencia ordenada. Omitir solo en el flujo heredado de 4.1.")


class DemoEditorGuardar(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool = True
    pasos: list[PasoDemo] = Field(min_length=1, max_length=30)


class DemoDetalle(BaseModel):
    id_demo: int
    id_vehiculo: int
    nombre: str
    descripcion: str | None = None
    tipo: Literal["fabrica", "privada"] = "fabrica"
    id_propietario: int | None = None
    activo: bool
    editable: bool = False
    total_pasos: int = 0
    duracion_total_ms: int = 0
    fecha_creacion: datetime | None = None
    fecha_modificacion: datetime | None = None
    pasos: list[MovimientoDemo] | None = None


# ------------------------------------------------------ catálogo/invitado
class SolicitudPrueba(BaseModel):
    id_vehiculo: int = Field(ge=1, description="Unidad de EXHIBICIÓN elegida en el catálogo")


class ComandoPermitido(BaseModel):
    nombre: str
    codigo: int
    tipo: str


class SesionInvitado(BaseModel):
    access_token: str | None = None
    token_type: Literal["bearer"] = "bearer"
    rol: Literal["invitado"] = "invitado"
    expira_en_segundos: int | None = None
    segundos_restantes: int | None = None
    vigente: bool | None = None
    id_vehiculo: int
    unidad: str
    modelo: str | None = None
    comandos_permitidos: list[ComandoPermitido]
    duracion_max_ms: int


class Dashboard(BaseModel):
    modelos_activos: int
    unidades_activas: int
    unidades_disponibles: int
    unidades_asignadas: int
    unidades_exhibicion: int
    unidades_inactivas: int
    clientes_activos: int
    demos_fabrica: int
    demos_privadas: int
    sesiones_invitado_activas: int
    dispositivos_conectados: int = Field(description="ESP32 con sesión WSS activa (según estado_vehiculo)")
    movimientos_24h: int
    conexiones_wss_navegador: int


class RegistroAuditoria(BaseModel):
    id_auditoria: int
    fecha_hora: datetime
    actor_tipo: str
    id_actor: int | None = None
    actor: str | None = None
    accion: str
    recurso: str | None = None
    id_recurso: str | None = None
    resultado: str
    detalle: str | None = None


class PaginaAuditoria(Pagina):
    elementos: list[RegistroAuditoria]

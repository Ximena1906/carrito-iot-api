"""Punto de entrada: python -m app.main  (Uvicorn en 0.0.0.0:8000)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import dependencias as dep
from app.core.documentacion import registrar_documentacion
from app.core.errores import registrar_manejadores
from app.routers import control, demos, sistema, vehiculos, websocket

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRIPCION = """
API del **Carrito IoT** (ESP32 + 2× 74HC595) sobre la base `carrito_iot` en **Amazon RDS**.

* Integra los **21 Stored Procedures** (vehículos 5, comandos 4, estado 2, historial 2, DEMO 4, movimientos DEMO 4).
* **GET** consulta (público, solo lectura) · **POST** crea, actualiza, elimina y ejecuta acciones (requiere token).
* Eventos en tiempo real por WebSocket: `ws(s)://<host>/ws/vehiculos/{id_vehiculo}` (ver README).

**Autenticación:** botón *Authorize* → usuario/contraseña de operador o admin.
"""

ETIQUETAS = [
    {"name": "Salud", "description": "Disponibilidad de la API y de Amazon RDS."},
    {"name": "Autenticación", "description": "Obtención de token Bearer (JWT)."},
    {"name": "Control", "description": "Movimientos individuales y ejecución de DEMO (eventos WebSocket)."},
    {"name": "Vehículos", "description": "Registro y datos generales de cada vehículo."},
    {"name": "Comandos", "description": "Catálogo de comandos de cada vehículo."},
    {"name": "Estado e historial", "description": "Último estado y bitácora de movimientos individuales."},
    {"name": "DEMO", "description": "Secuencias automáticas almacenadas."},
    {"name": "Movimientos de DEMO", "description": "Pasos ordenados de cada DEMO."},
]


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    yield
    await dep.ejecutor_demos.cancelar_todas()


app = FastAPI(
    title=dep.settings.app_nombre,
    version=dep.settings.app_version,
    description=DESCRIPCION,
    openapi_tags=ETIQUETAS,
    lifespan=ciclo_de_vida,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=dep.settings.lista_cors,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

registrar_manejadores(app)
registrar_documentacion(app, dep.settings.app_version, dep.settings.swagger_js_url, dep.settings.swagger_css_url)
app.include_router(sistema.router)
app.include_router(control.router)
app.include_router(vehiculos.router)
app.include_router(demos.router)
app.include_router(websocket.router)


@app.get("/", include_in_schema=False)
def raiz():
    return {"servicio": dep.settings.app_nombre, "documentacion": "/docs", "websocket": "/ws/vehiculos/{id}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=dep.settings.app_host,
        port=dep.settings.app_port,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )

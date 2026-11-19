"""Punto de entrada: python -m app.main  (Uvicorn en 0.0.0.0:8000)."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import dependencias as dep
from app.core.documentacion import registrar_documentacion
from app.core.errores import registrar_manejadores
from fastapi.concurrency import run_in_threadpool

from app.routers import admin, control, demos, mis_vehiculos, publico, sistema, vehiculos, websocket

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRIPCION = """
API del **Carrito IoT** sobre la base `carrito_iot` en **Amazon RDS**: CONTROL (4.1), MONITOREO (4.2) y
**ADMINISTRACIÓN (4.3)** de una empresa que comercializa vehículos IoT.

* **Roles:** `admin` (empresa: inventario, clientes, asignaciones, DEMO de fábrica), `usuario` (comprador: solo SUS
  unidades y SUS DEMO) e `invitado` (sin cuenta: catálogo y prueba temporal de una unidad de exhibición).
* **Autorización por recurso:** además del rol, cada ruta comprueba la unidad concreta (propietario, soporte
  autorizado, empresa o reserva de Invitado). 401 sin sesión · 403 sin permiso · 404 unidad ajena.
* **Datos:** solo procedimientos almacenados (21 originales + 44 de administración).
* **Tiempo real:** `wss://<host>/ws/vehiculos/{id}?token=<JWT>` con la misma autorización (ver README).

**Autenticación:** botón *Authorize* → usuario y contraseña de una cuenta (admin o usuario).
"""

ETIQUETAS = [
    {"name": "Salud", "description": "Disponibilidad de la API y de Amazon RDS."},
    {"name": "Autenticación", "description": "Inicio y cierre de sesión (JWT revalidado contra RDS)."},
    {"name": "Administración", "description": "Dashboard, modelos, unidades, clientes, asignaciones y auditoría."},
    {"name": "Mis vehículos", "description": "Unidades del comprador y permisos de soporte."},
    {"name": "Catálogo e Invitados", "description": "Catálogo público y prueba temporal con reserva exclusiva."},
    {"name": "Control", "description": "Movimientos individuales y ejecución de DEMO (eventos WebSocket)."},
    {"name": "Vehículos", "description": "Registro y datos generales de cada vehículo."},
    {"name": "Comandos", "description": "Catálogo de comandos de cada vehículo."},
    {"name": "Estado e historial", "description": "Último estado y bitácora de movimientos individuales."},
    {"name": "DEMO", "description": "Secuencias automáticas almacenadas."},
    {"name": "Movimientos de DEMO", "description": "Pasos ordenados de cada DEMO."},
]


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    try:
        await run_in_threadpool(dep.usuarios.asegurar_admin_inicial)
    except Exception as exc:  # RDS no disponible al arrancar: se reintenta en el primer login
        logging.getLogger("carrito_iot").warning("No se pudo verificar el administrador inicial: %s", exc)
    vigilancia = asyncio.create_task(dep.invitados.vigilar(), name="vigilancia-invitados")
    yield
    vigilancia.cancel()
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

registrar_manejadores(app)
registrar_documentacion(app, dep.settings.app_version, dep.settings.swagger_js_url, dep.settings.swagger_css_url)
app.include_router(sistema.router)
app.include_router(publico.router)
app.include_router(admin.router)
app.include_router(mis_vehiculos.router)
app.include_router(control.router)      # antes que demos: /demos/en-curso y /demos/cancelar
app.include_router(vehiculos.router)
app.include_router(demos.router)
app.include_router(websocket.router)


@app.get("/", include_in_schema=False)
def raiz():
    return {"servicio": dep.settings.app_nombre, "version": dep.settings.app_version, "documentacion": "/docs",
            "websocket": "/ws/vehiculos/{id}?token=<JWT>"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=dep.settings.app_host,
        port=dep.settings.app_port,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )

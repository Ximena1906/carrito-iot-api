# Carrito IoT API

API en **Python + FastAPI** (programación orientada a objetos) para controlar un carrito RC con
**ESP32 + 2× 74HC595 + PC817**. Usa la base de datos **`carrito_iot` en Amazon RDS (MySQL)**,
integra los **21 Stored Procedures**, se documenta en **Swagger UI** y publica eventos en tiempo real
por **WebSocket**.

```
Thunder Client / Swagger / Página web ──HTTP(S)──► FastAPI ──► Stored Procedures ──► Amazon RDS
                                         ◄──WS(S)──  (eventos por vehículo)  ──WS(S)──► ESP32
```

---

## 1. Estructura

```
carrito_iot_api/
├── app/
│   ├── main.py                 # Crea la app, CORS, Swagger, routers. Ejecuta Uvicorn.
│   ├── dependencias.py         # Contenedor: crea una instancia de cada componente
│   ├── core/
│   │   ├── config.py           # Settings: lee .env (sin credenciales en código)
│   │   ├── errores.py          # Excepciones de dominio -> códigos HTTP
│   │   └── seguridad.py        # JWT, roles operador/admin, token del dispositivo
│   ├── db/
│   │   ├── database.py         # Conexión PyMySQL, transacciones, traducción de errores
│   │   └── procedimientos.py   # Los 21 SP (único lugar con SQL; parámetros enlazados)
│   ├── models/esquemas.py      # Modelos Pydantic de entrada/salida y validaciones
│   ├── services/
│   │   ├── catalogo.py         # Reglas de vehículos, comandos, estado/historial y DEMO
│   │   └── control.py          # Movimiento individual (transacción) y ejecutor de DEMO
│   ├── websocket/gestor.py     # Clientes WS por vehículo, difusión de eventos
│   └── routers/                # Endpoints HTTP y WebSocket (sin lógica de persistencia)
│       ├── sistema.py          # /health, /health/db, /auth/login
│       ├── vehiculos.py        # vehículos, comandos, estado, historial
│       ├── demos.py            # DEMO y movimientos de DEMO
│       ├── control.py          # ejecutar movimiento, iniciar/cancelar DEMO
│       └── websocket.py        # /ws/vehiculos/{id}
├── requirements.txt
├── .env.example                # Plantilla de configuración SIN secretos
└── .gitignore                  # Excluye .venv, .env, cachés
```

---

## 2. Ejecución local (Windows + VS Code)

```powershell
cd C:\carrito_iot_api
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # solo si PowerShell bloquea scripts
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env        # y edita .env con tus datos reales
python -m app.main
```

* API: <http://localhost:8000>
* Swagger UI: <http://localhost:8000/docs>
* WebSocket: `ws://localhost:8000/ws/vehiculos/1`

> Requisito de red: el Security Group de RDS debe permitir **TCP 3306 desde Mi IP**.

---

## 3. Seguridad

| Qué | Cómo |
|---|---|
| Credenciales de RDS | Solo en `.env` (excluido de Git). Usuario `api_carrito` con permiso **EXECUTE** únicamente (`database/05_usuario_api.sql`). |
| SQL | Solo `CALL sp_...(%s, ...)` con parámetros enlazados; nunca concatenación. |
| GET | Públicos y de solo lectura. |
| Movimientos y DEMO | Requieren token con rol **operador** o **admin**. |
| Crear / actualizar / eliminar | Requieren rol **admin**. |
| ESP32 | Se conecta al WS con `?token=DISPOSITIVO_TOKEN`. |
| CORS | Solo los orígenes de `CORS_ORIGENES` (CORS no es autenticación). |
| Errores | 500 genérico al cliente; el detalle solo se registra en el servidor. |

**Obtener token:** `POST /auth/login` con *form-data* `username` y `password`.
En Swagger: botón **Authorize**. En Thunder Client: pestaña *Auth → Bearer* con el `access_token`.

---

## 4. Endpoints y Stored Procedures

| Método | Ruta | SP | Rol |
|---|---|---|---|
| GET | `/health` | — | público |
| GET | `/health/db` | `SELECT 1` en RDS | público |
| POST | `/auth/login` | — | público |
| GET | `/vehiculos` | sp_obtener_vehiculos | público |
| GET | `/vehiculos/{id}` | sp_obtener_vehiculo | público |
| POST | `/vehiculos` | sp_crear_vehiculo | admin |
| POST | `/vehiculos/{id}/actualizar` | sp_actualizar_vehiculo | admin |
| POST | `/vehiculos/{id}/eliminar` | sp_eliminar_vehiculo | admin |
| GET | `/vehiculos/{id}/comandos` | sp_obtener_comandos_vehiculo | público |
| POST | `/vehiculos/{id}/comandos` | sp_crear_comando | admin |
| POST | `/vehiculos/{id}/comandos/{id_comando}/actualizar` | sp_actualizar_comando | admin |
| POST | `/vehiculos/{id}/comandos/{id_comando}/eliminar` | sp_eliminar_comando | admin |
| GET | `/vehiculos/{id}/estado` | sp_obtener_estado | público |
| GET | `/vehiculos/{id}/historial?limite=10` | sp_obtener_historial (máx. 10) | público |
| **POST** | **`/vehiculos/{id}/movimientos`** | **sp_actualizar_estado + sp_registrar_historial (1 transacción)** | operador |
| GET | `/vehiculos/{id}/demos` | sp_obtener_demos | público |
| POST | `/vehiculos/{id}/demos` | sp_crear_demo | admin |
| POST | `/vehiculos/{id}/demos/{id_demo}/actualizar` | sp_actualizar_demo | admin |
| POST | `/vehiculos/{id}/demos/{id_demo}/eliminar` | sp_eliminar_demo | admin |
| GET | `/vehiculos/{id}/demos/{id_demo}/movimientos` | sp_obtener_movimientos_demo | público |
| POST | `/vehiculos/{id}/demos/{id_demo}/movimientos` | sp_agregar_movimiento_demo | admin |
| POST | `/vehiculos/{id}/demos/{id_demo}/movimientos/{id_mov}/actualizar` | sp_actualizar_movimiento_demo | admin |
| POST | `/vehiculos/{id}/demos/{id_demo}/movimientos/{id_mov}/eliminar` | sp_eliminar_movimiento_demo | admin |
| **POST** | **`/vehiculos/{id}/demos/{id_demo}/iniciar`** | sp_obtener_movimientos_demo + sp_actualizar_estado (sin historial) | operador |
| POST | `/vehiculos/{id}/demos/cancelar` | sp_actualizar_estado (DETENER) | operador |
| GET | `/vehiculos/{id}/demos/en-curso` | — (memoria del servidor) | público |

Los **21 SP** quedan integrados: vehículos (5), comandos (4), estado (2), historial (2), DEMO (4) y
movimientos de DEMO (4).

### Códigos HTTP
`200` OK · `201` creado · `202` DEMO aceptada · `400` DEMO sin movimientos / referencia inexistente ·
`401` sin token o token inválido · `403` rol sin permiso · `404` vehículo, comando o DEMO inexistente
(o que no pertenece al vehículo) · `409` duplicado, registro en uso, vehículo/comando inactivo o DEMO en
curso · `422` datos inválidos · `500` error interno · `503` RDS no disponible.

### Ejemplo: movimiento individual
```http
POST /vehiculos/1/movimientos
Authorization: Bearer <token>
Content-Type: application/json

{ "comando": "AVANZAR", "duracion_ms": 2000, "origen": "THUNDER" }
```
También se acepta `{ "codigo": 1 }`. `duracion_ms` (50–10000, por defecto 1000) es el **tiempo máximo**
que el ESP32 mantendrá activa la salida; `DETENER` libera todo antes.

---

## 5. WebSocket

**URL:** `ws://<host>:8000/ws/vehiculos/{id_vehiculo}` (en AWS con HTTPS: `wss://<dominio>/ws/vehiculos/{id}`)

| Cliente | Conexión |
|---|---|
| Monitoreo (navegador, Thunder Client) | `/ws/vehiculos/1` |
| Dispositivo ESP32 | `/ws/vehiculos/1?token=<DISPOSITIVO_TOKEN>` |

* Cada cliente recibe **solo** los eventos de su vehículo. Se admiten varios clientes simultáneos.
* Al conectarse se recibe `estado_inicial` (último estado guardado en RDS). **No es una orden nueva.**
* Todo evento lleva `tipo`, `id_evento` (único), `id_vehiculo` y `timestamp` (UTC).
* El ESP32 marca `conectado = 1` en `estado_vehiculo` mientras su sesión está abierta.

### Eventos que envía el servidor

```jsonc
// Al conectarse
{"tipo":"estado_inicial","id_evento":"…","id_vehiculo":1,"vehiculo":"Carrito IoT","id_comando":9,
 "comando":"DETENER","codigo":9,"fecha_actualizacion":"…","dispositivo_conectado":false,
 "demo_en_curso":null,"timestamp":"…"}

// POST /movimientos válido (se guarda en historial)
{"tipo":"movimiento","id_evento":"…","id_vehiculo":1,"id_comando":1,"comando":"AVANZAR","codigo":1,
 "duracion_ms":2000,"origen":"THUNDER","timestamp":"…"}

// DEMO (NO se guarda en historial)
{"tipo":"demo_inicio","id_evento":"…","id_vehiculo":1,"id_demo":1,"nombre":"Demo principal","total_pasos":8,"origen":"API","timestamp":"…"}
{"tipo":"demo_paso","id_evento":"…","id_vehiculo":1,"id_demo":1,"paso":1,"total_pasos":8,"orden":1,
 "id_comando":1,"comando":"AVANZAR","codigo":1,"duracion_ms":2000,"pausa_ms":400,"timestamp":"…"}
{"tipo":"demo_fin","id_evento":"…","id_vehiculo":1,"id_demo":1,"nombre":"Demo principal","total_pasos":8,"timestamp":"…"}
{"tipo":"demo_cancelada","id_evento":"…","id_vehiculo":1,"id_demo":1,"nombre":"Demo principal","total_pasos":8,
 "motivo":"CANCELADA_POR_USUARIO | DETENER | ERROR","timestamp":"…"}

// Presencia del ESP32
{"tipo":"dispositivo","id_evento":"…","id_vehiculo":1,"conectado":true,"timestamp":"…"}

// Confirmación de recepción enviada por el ESP32 (no prueba movimiento físico)
{"tipo":"ack_dispositivo","id_evento":"…","id_vehiculo":1,"id_evento_ref":"…","resultado":"ejecutado","timestamp":"…"}

// Errores
{"tipo":"error","id_evento":"…","id_vehiculo":1,"contexto":"demo","mensaje":"…","timestamp":"…"}
```

### Mensajes que acepta el servidor
```json
{"tipo":"ping"}                                              // responde {"tipo":"pong",...}
{"tipo":"ack","id_evento_ref":"<id_evento>","resultado":"ejecutado"}   // solo del ESP32
```
Las órdenes **nunca** entran por WebSocket: solo por `POST`.

### Reglas de DEMO
* Pasos leídos de `sp_obtener_movimientos_demo`, en orden, esperando `duracion_ms + pausa_ms` entre pasos.
* Actualiza `estado_vehiculo` en cada paso, **nunca** llama a `sp_registrar_historial`.
* Solo una DEMO por vehículo (409 si ya hay una).
* Durante la DEMO solo se acepta el movimiento `DETENER`, que la cancela de inmediato.
* La DEMO se ejecuta en segundo plano: no bloquea otras peticiones ni conexiones.

---

## 6. Pruebas funcionales con Thunder Client

1. **POST** – `POST /auth/login` → copiar token → `POST /vehiculos/1/movimientos` con
   `{"comando":"AVANZAR"}` → verificar `GET /vehiculos/1/estado` y el nuevo registro en historial.
2. **GET** – `GET /vehiculos/1/historial` → máximo 10 registros, del más reciente al más antiguo.
3. **WebSocket** – conectar `ws://localhost:8000/ws/vehiculos/1` → `POST /vehiculos/1/demos/1/iniciar`
   → observar `demo_inicio`, 8 `demo_paso` y `demo_fin` → comparar historial antes/después (sin cambios).

# Carrito IoT API

API en **Python + FastAPI** (programación orientada a objetos) para una empresa que comercializa
vehículos IoT. Cubre las prácticas **4.1 CONTROL**, **4.2 MONITOREO** y **4.3 ADMINISTRACIÓN**:
inventario de modelos y unidades físicas, clientes, asignaciones, permisos de soporte, editor de DEMO,
pruebas temporales de Invitado, auditoría y dashboard. Usa la base **`carrito_iot` en Amazon RDS (MySQL)**
solo mediante **procedimientos almacenados** (21 originales + 44 de administración), se documenta en
**Swagger UI** y publica eventos en tiempo real por **WebSocket seguro (WSS)**.

```
GitHub Pages (CONTROL | MONITOREO | ADMINISTRACIÓN)
        │  HTTPS + JWT                     ▲ WSS + JWT (solo unidades autorizadas)
        ▼                                  │
Caddy (Let's Encrypt) ──► FastAPI (EC2 Server2) ──► Stored Procedures ──► Amazon RDS
                                   │
                                   └── WSS + DISPOSITIVO_TOKEN ──► ESP32 (unidad 1)
```

---

## 1. Roles y modelo de autorización

| Rol | Quién es | Puede |
|---|---|---|
| **admin** | Empresa | Dashboard, modelos y capacidades, unidades, clientes, asignaciones, auditoría, DEMO de fábrica. Controla unidades de **exhibición** y **disponibles**. En unidades vendidas solo con **permiso de soporte** vigente otorgado por el comprador. |
| **usuario** | Comprador | Solo **sus** unidades («Mis vehículos»): CONTROL, MONITOREO, historial, DEMO de fábrica y **sus DEMO privadas**; otorga/revoca soporte. |
| **invitado** | Visitante sin cuenta | Catálogo público y **una prueba temporal** (180 s) de una unidad de exhibición con reserva exclusiva, comandos restringidos y duración máxima de 2 s por movimiento. |

Además del rol, **cada ruta valida la unidad concreta** (`services/autorizacion.py`):

| Respuesta | Cuándo |
|---|---|
| `401` | Sin token, token vencido/invalidado (logout, cuenta desactivada, contraseña restablecida) o prueba de Invitado terminada. |
| `403` | Rol sin permiso (Invitado en administración, Usuario en `/admin`, Admin en unidad vendida sin soporte, comando no permitido al Invitado). |
| `404` | Unidad ajena para un **Usuario** (no se revela que existe) o recurso inexistente. |
| `409` | Unidad ocupada por otra sesión (control exclusivo), reserva de Invitado activa, DEMO en curso, duplicados, unidad inactiva. |
| `429` | Límite de intentos (login 10/min por IP+cuenta, pruebas 6/min por IP, 40 comandos/10 s por sesión). |

**Control exclusivo:** quien envía un comando «toma» la unidad durante `CONTROL_EXCLUSIVO_S` (20 s desde el
último comando); otra sesión recibe `409`. **`DETENER` nunca se bloquea.**

---

## 2. Estructura

```
carrito-iot-api/
├── app/
│   ├── main.py                    # App, CORS, Swagger, routers, tareas de fondo (vigilancia de Invitados)
│   ├── dependencias.py            # Contenedor: una instancia de cada componente
│   ├── core/
│   │   ├── config.py              # Settings desde .env
│   │   ├── errores.py             # Excepciones de dominio → 400/401/403/404/409/429/503
│   │   ├── seguridad.py           # PBKDF2, JWT (versión de token), Actor, token del dispositivo
│   │   ├── acceso.py              # Dependencias: actor_requerido, solo_admin, solo_usuario…
│   │   └── limites.py             # Limitador en memoria (ventana deslizante)
│   ├── db/
│   │   ├── database.py            # PyMySQL, transacciones, traducción de errores
│   │   ├── procedimientos.py      # 21 SP originales
│   │   └── procedimientos_admin.py# 44 SP de administración (4.3)
│   ├── models/esquemas.py         # Pydantic: validación de entrada/salida
│   ├── services/
│   │   ├── usuarios.py            # Login, bloqueo tras 5 fallos, cuentas, admin inicial
│   │   ├── identidad.py           # Token → Actor (cuenta o sesión de Invitado)
│   │   ├── autorizacion.py        # Nivel sobre la unidad: propietario/soporte/empresa/invitado
│   │   ├── inventario.py          # Modelos, capacidades, unidades, asignaciones, soporte, dashboard
│   │   ├── demos_editor.py        # DEMO de fábrica/privadas con validación en servidor
│   │   ├── invitados.py           # Reserva exclusiva, expiración, gracia de desconexión, DETENER seguro
│   │   ├── conexiones.py          # Revalida/cierra sockets cuando cambian los permisos
│   │   ├── auditoria.py           # Registro de acciones y rechazos
│   │   ├── catalogo.py            # Reglas 4.1 de vehículos, comandos, estado, historial
│   │   └── control.py             # Movimiento (transacción), control exclusivo, ejecutor de DEMO
│   ├── websocket/gestor.py        # Suscriptores por unidad con su identidad
│   └── routers/
│       ├── sistema.py             # /health, /auth/login, /auth/logout, /auth/yo
│       ├── publico.py             # /catalogo, /invitados/…
│       ├── admin.py               # /admin/…
│       ├── mis_vehiculos.py       # /mis-vehiculos/…
│       ├── control.py             # movimientos, iniciar/cancelar DEMO
│       ├── vehiculos.py           # comandos, estado, historial (4.1/4.2, ahora autorizados)
│       ├── demos.py               # editor de DEMO + rutas heredadas
│       └── websocket.py           # /ws/vehiculos/{id}?token=
├── database/
│   ├── 01…05_*.sql                # Esquema y SP originales (4.1)
│   └── migraciones/               # 4.3: V000–V006, verificación y reversión (ver §6)
├── tests/test_practica43.py       # Pruebas P01–P17 contra una API en ejecución
├── deploy/instalar_server2.ps1    # Servicios WinSW (API + Caddy) en EC2
├── requirements.txt
└── .env.example                   # Plantilla SIN secretos
```

---

## 3. Ejecución local

```powershell
cd C:\carrito_iot_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # edita .env con tus datos reales (nunca se sube a Git)
python -m app.main
```

* Swagger UI: <http://localhost:8000/docs> → **Authorize** con usuario y contraseña de una cuenta.
* Al arrancar, si no existe ningún administrador, se crea con `ADMIN_USUARIO` / `ADMIN_PASSWORD` / `ADMIN_NOMBRE`.
  Los compradores se dan de alta desde ADMINISTRACIÓN (`POST /admin/usuarios`).

### Variables nuevas en 4.3

| Variable | Defecto | Uso |
|---|---|---|
| `ADMIN_NOMBRE` | Administrador de la empresa | Nombre de la cuenta inicial |
| `DISPOSITIVO_ID_VEHICULO` | 1 | Única unidad en la que vale `DISPOSITIVO_TOKEN` |
| `INVITADO_SEGUNDOS` | 180 | Duración de la prueba |
| `INVITADO_DURACION_MAX_MS` | 2000 | Máximo por movimiento del Invitado |
| `INVITADO_GRACIA_DESCONEXION_S` | 15 | Tiempo para reconectar antes de cerrar la prueba |
| `CONTROL_EXCLUSIVO_S` | 20 | Ventana de control exclusivo |
| `SOPORTE_MINUTOS_MAX` | 240 | Máximo de un permiso de soporte |
| `DEMO_MAX_PASOS` / `DEMO_MAX_TOTAL_MS` | 30 / 120000 | Límites del editor de DEMO |

`OPERADOR_USUARIO` / `OPERADOR_PASSWORD` (4.1) ya no se usan; pueden quedarse en `.env` sin efecto.

---

## 4. Endpoints

### Sesión y público
| Método | Ruta | Acceso |
|---|---|---|
| GET | `/health`, `/health/db` | público |
| POST | `/auth/login` (form `username`, `password`) | público |
| POST | `/auth/logout` (invalida todos los tokens de la cuenta) | cuenta |
| GET | `/auth/yo` | cualquiera con token |
| GET | `/catalogo` | público |
| POST | `/invitados/sesiones` `{"id_vehiculo":1}` → token de Invitado | público |
| GET / DELETE | `/invitados/sesion` | invitado |

### Administración (`admin`)
| Método | Ruta |
|---|---|
| GET | `/admin/dashboard` |
| GET, POST | `/admin/modelos` · GET, PUT `/admin/modelos/{id}` · PATCH `/admin/modelos/{id}/estado` · PUT `/admin/modelos/{id}/capacidades` |
| GET, POST | `/admin/unidades` · GET, PUT `/admin/unidades/{id}` · PATCH `/admin/unidades/{id}/estado` |
| PUT, DELETE | `/admin/unidades/{id}/propietario` (asignar/reasignar · liberar) |
| GET, POST | `/admin/usuarios` · GET, PUT `/admin/usuarios/{id}` · PATCH `…/estado` · PUT `…/password` |
| GET | `/admin/auditoria?actor_tipo=&accion=&resultado=&limite=&desplazamiento=` |

### Comprador (`usuario`)
| Método | Ruta |
|---|---|
| GET | `/mis-vehiculos` |
| PUT, DELETE | `/mis-vehiculos/{id}/soporte` `{"minutos":30}` |

### Unidad (autorizado por unidad)
| Método | Ruta | Notas |
|---|---|---|
| GET | `/vehiculos/{id}`, `/comandos`, `/estado`, `/historial?limite=10` | lectura |
| POST | `/vehiculos/{id}/movimientos` | `sp_actualizar_estado` + `sp_registrar_historial` en 1 transacción |
| GET, POST | `/vehiculos/{id}/demos` | fábrica + propias; crear: admin → fábrica, usuario → privada |
| GET, PUT, DELETE | `/vehiculos/{id}/demos/{id_demo}` | detalle con pasos · guardar (1 transacción) · baja lógica |
| POST | `/vehiculos/{id}/demos/{id_demo}/iniciar`, `/demos/cancelar` · GET `/demos/en-curso` | |
| GET | `/vehiculos` | admin (inventario completo) |

Las rutas heredadas de 4.1 (`…/actualizar`, `…/eliminar`, `…/movimientos/{id}/…`) siguen funcionando con las
mismas validaciones. `POST /vehiculos` queda obsoleto (409 → usar `/admin/unidades`).

---

## 5. WebSocket

`wss://<dominio>/ws/vehiculos/{id}?token=<JWT>`

| Cliente | Token |
|---|---|
| Navegador / Thunder Client | JWT de la sesión (admin, usuario o invitado). Misma autorización que REST. |
| ESP32 | `DISPOSITIVO_TOKEN`, válido solo en la unidad `DISPOSITIVO_ID_VEHICULO`. |

* Sin token: evento `error` (codigo 401) y cierre **4401**. Sin permiso: `error` + cierre **4403**/**4404**.
* Cuando cambian los permisos (reasignación, liberación, soporte revocado o vencido, logout, cuenta
  desactivada) el servidor envía `acceso_revocado` y cierra con **4403**.
* Eventos: `estado_inicial`, `movimiento`, `demo_inicio`, `demo_paso`, `demo_fin`, `demo_cancelada`,
  `dispositivo`, `ack_dispositivo`, `sesion_invitado` (`estado: finalizada`, `motivo: CERRADA | EXPIRADA |
  DESCONEXION`), `acceso_revocado`, `error`, `pong`.
* Las órdenes **nunca** entran por WebSocket; solo `ping` y el `ack` del ESP32.

**Fin seguro de la prueba de Invitado:** al cerrar, vencer o perder la conexión más de 15 s, el servidor
cancela la DEMO en curso, registra `DETENER` con origen `SISTEMA`, lo publica al ESP32, libera la reserva y
cierra los sockets del Invitado (4401).

---

## 6. Migración de la base de datos (4.3)

Scripts en `database/migraciones/`, **idempotentes** (se pueden repetir) y registrados en
`migraciones_esquema`:

| Archivo | Contenido |
|---|---|
| `00_inventario.sql` | Solo lectura: tablas, conteos, índices y SP antes de migrar |
| `V000` | Tabla `migraciones_esquema` y procedimientos auxiliares `mig_*` |
| `V001` | `usuarios`, `modelos`, `modelo_comandos` (capacidades) |
| `V002` | `vehiculos` → unidad física (serie, modelo, estado comercial, propietario), `asignaciones`, `permisos_soporte` |
| `V003` | `demos.tipo` (fabrica/privada) y `id_propietario` |
| `V004` | `sesiones_invitado` (reserva exclusiva por índice único) y `auditoria` |
| `V005` | Datos existentes: modelo desde `vehiculos.modelo`, capacidades desde `comandos`, unidad 1 = `UNI-0001` en **exhibición**, DEMO existentes = fábrica |
| `V006` | 44 procedimientos de administración |
| `99_verificacion.sql` | Debe mostrar 65 SP y 0 inconsistencias |
| `reversion/R006…R000` | Reversión completa al esquema 4.2 |

Orden: **respaldo (`mysqldump`) → 00 → V000…V006 → 99**. Las tablas e IDs de 4.1/4.2 se conservan
(`id_vehiculo`, `id_comando`, historial y DEMO), por eso CONTROL y MONITOREO siguen funcionando.
El usuario `api_carrito` sigue teniendo **solo EXECUTE**.

---

## 7. Seguridad

| Qué | Cómo |
|---|---|
| Contraseñas | PBKDF2-SHA256 (390 000 iteraciones) con sal; nunca se devuelven. Bloqueo de 5 min tras 5 fallos. Mensaje de error genérico. |
| Tokens | JWT con `version_token`: logout, desactivar la cuenta o restablecer la contraseña invalidan los tokens anteriores. |
| SQL | Solo `CALL sp_…(%s…)` con parámetros enlazados. |
| Auditoría | Logins, altas, cambios, asignaciones, soporte, DEMO, pruebas y **rechazos** (`/admin/auditoria`). |
| Secretos | Solo en `.env` (excluido de Git). |
| CORS | Orígenes de `CORS_ORIGENES`; WebSocket se autoriza con token porque CORS no aplica. |

---

## 8. Pruebas

```powershell
# API de prueba con prueba corta de Invitado (nunca contra datos reales)
$env:INVITADO_SEGUNDOS=10; $env:INVITADO_GRACIA_DESCONEXION_S=3; python -m app.main
# En otra terminal
$env:API_URL="http://localhost:8000"; $env:ADMIN_PASSWORD="<contraseña admin>"; $env:INVITADO_GRACIA_DESCONEXION_S=3
pip install pytest pytest-timeout httpx websockets
pytest -v tests/test_practica43.py
```

| Prueba | Verifica |
|---|---|
| P01 | Login admin, credenciales inválidas (401 genérico), rutas protegidas |
| P02 | Alta de unidad, serie duplicada (409), comandos desde capacidades |
| P03 | Alta de cliente, usuario duplicado, sin exponer contraseñas |
| P04 | Asignación, reasignación con revocación inmediata |
| P05 | Aislamiento de comprador (404 en unidad ajena, 403 en `/admin`) |
| P06 | Control del propietario; admin sin soporte (403) y con soporte |
| P07 | WSS: 4401 sin token, rechazo de ajeno, eventos de la unidad |
| P08 | Historial máximo 10 |
| P09 | DEMO privada persistente, validación, reordenar pasos |
| P10 | Ejecución, 409 por DEMO en curso, cancelación, fin |
| P11 | Prueba de Invitado: comandos restringidos, duración recortada, fin seguro |
| P12 | Rechazos al Invitado y al Admin durante la prueba |
| P13 | Rechazo de vehículo ajeno en todas las rutas |
| P14 | Exclusividad de la reserva (409) |
| P15 | Reconexión, revocación por WSS (4403), gracia de desconexión y expiración con DETENER |
| P16 | Responsive (pruebas del frontend) |
| P17 | Auditoría (acciones y rechazos) y dashboard |

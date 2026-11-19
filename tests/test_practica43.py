"""Pruebas P01–P17 de la práctica 4.3 contra una API EN EJECUCIÓN.

Uso (nunca contra producción con datos reales: crean cuentas, unidades y DEMO de prueba):

    API_URL=http://localhost:8000 ADMIN_USUARIO=administrador ADMIN_PASSWORD=... \
    pytest -v tests/test_practica43.py

Para que P11/P15 prueben la expiración sin esperar 3 minutos, arranca la API de
prueba con INVITADO_SEGUNDOS=10 e INVITADO_GRACIA_DESCONEXION_S=3.
P16 (responsive) se verifica en el navegador (pruebas Playwright del frontend).
"""
import asyncio
import json
import os
import time
import uuid

import httpx
import pytest
import websockets

API = os.environ.get("API_URL", "http://localhost:8000")
WS = API.replace("http", "ws", 1)
ADMIN_USUARIO = os.environ.get("ADMIN_USUARIO", "administrador")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
EXHIBICION = int(os.environ.get("ID_EXHIBICION", "1"))
SUFIJO = uuid.uuid4().hex[:6].upper()

pytestmark = pytest.mark.timeout(90)


def cli() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=15)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(usuario: str, password: str) -> httpx.Response:
    with cli() as c:
        return c.post("/auth/login", data={"username": usuario, "password": password})


@pytest.fixture(scope="module")
def admin() -> dict:
    r = login(ADMIN_USUARIO, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


@pytest.fixture(scope="module")
def escenario(admin) -> dict:
    """Unidad nueva + dos compradores; la unidad se asigna al comprador A."""
    with cli() as c:
        id_modelo = c.get("/admin/modelos", headers=admin).json()[0]["id_modelo"]
        u = c.post("/admin/unidades", headers=admin, json={
            "id_modelo": id_modelo, "numero_serie": f"TST-{SUFIJO}", "nombre": f"Unidad prueba {SUFIJO}"})
        assert u.status_code == 201, u.text
        cuentas = {}
        for letra in "AB":
            datos = {"usuario": f"cliente{letra.lower()}{SUFIJO.lower()}", "nombre": f"Cliente {letra} de prueba",
                     "rol": "usuario", "password": f"Prueba{SUFIJO}!x"}
            r = c.post("/admin/usuarios", headers=admin, json=datos)
            assert r.status_code == 201, r.text
            cuentas[letra] = {**datos, "id": r.json()["id"]}
        return {"id_modelo": id_modelo, "id_unidad": u.json()["id"], "cuentas": cuentas}


def token_cliente(escenario, letra) -> dict:
    """Un token por cuenta (el login tiene límite de intentos por minuto)."""
    cta = escenario["cuentas"][letra]
    if "token" not in cta:
        r = login(cta["usuario"], cta["password"])
        assert r.status_code == 200, r.text
        cta["token"] = bearer(r.json()["access_token"])
    return cta["token"]


async def recibir(ws, tipo: str, segundos: float = 5) -> dict:
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        evento = json.loads(await asyncio.wait_for(ws.recv(), timeout=fin - time.monotonic()))
        if evento.get("tipo") == tipo:
            return evento
    raise AssertionError(f"No llegó el evento {tipo}")


# ------------------------------------------------------------------ P01–P04
def test_p01_login_admin_y_rechazos():
    r = login(ADMIN_USUARIO, ADMIN_PASSWORD)
    assert r.status_code == 200 and r.json()["rol"] == "admin"
    malo = login(ADMIN_USUARIO, "incorrecta-" + SUFIJO)
    assert malo.status_code == 401
    inexistente = login("noexiste" + SUFIJO.lower(), "incorrecta-" + SUFIJO)
    assert inexistente.status_code == 401 and inexistente.json() == malo.json()  # mensaje genérico
    with cli() as c:
        assert c.get("/admin/dashboard").status_code == 401
        yo = c.get("/auth/yo", headers=bearer(r.json()["access_token"])).json()
        assert yo["tipo"] == "admin"


def test_p02_alta_de_unidad(admin, escenario):
    with cli() as c:
        u = c.get(f"/admin/unidades/{escenario['id_unidad']}", headers=admin).json()
        assert u["numero_serie"] == f"TST-{SUFIJO}" and u["estado_comercial"] == "disponible"
        repetida = c.post("/admin/unidades", headers=admin, json={
            "id_modelo": escenario["id_modelo"], "numero_serie": f"TST-{SUFIJO}", "nombre": "Duplicada"})
        assert repetida.status_code == 409
        sin_modelo = c.post("/admin/unidades", headers=admin, json={
            "id_modelo": 99999, "numero_serie": f"TSX-{SUFIJO}", "nombre": "Sin modelo"})
        assert sin_modelo.status_code == 404
        # Los comandos de la unidad se generan desde las capacidades del modelo.
        comandos = c.get(f"/vehiculos/{escenario['id_unidad']}/comandos", headers=admin).json()
        assert {"AVANZAR", "DETENER"} <= {x["nombre"] for x in comandos}


def test_p03_alta_de_cliente(admin, escenario):
    a = escenario["cuentas"]["A"]
    with cli() as c:
        dup = c.post("/admin/usuarios", headers=admin, json={
            "usuario": a["usuario"], "nombre": "Otro", "rol": "usuario", "password": "OtraClave123"})
        assert dup.status_code == 409
        lista = c.get("/admin/usuarios", headers=admin, params={"q": a["usuario"]}).json()
        assert any(x["id_usuario"] == a["id"] for x in lista["elementos"])
        assert all("password" not in json.dumps(x).lower() or "hash" not in json.dumps(x).lower()
                   for x in lista["elementos"])
    assert login(a["usuario"], a["password"]).status_code == 200


def test_p04_asignacion(admin, escenario):
    with cli() as c:
        url = f"/admin/unidades/{escenario['id_unidad']}/propietario"
        r = c.put(url, headers=admin, json={"id_usuario": escenario["cuentas"]["A"]["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["estado_comercial"] == "asignado"
        assert c.put(url, headers=admin, json={"id_usuario": escenario["cuentas"]["A"]["id"]}).status_code == 409
        # Reasignación (transferencia): el titular anterior pierde el acceso al instante.
        b = token_cliente(escenario, "B")
        assert c.put(url, headers=admin, json={"id_usuario": escenario["cuentas"]["B"]["id"]}).status_code == 200
        assert c.get("/mis-vehiculos", headers=token_cliente(escenario, "A")).json() == []
        assert c.get(f"/vehiculos/{escenario['id_unidad']}/estado", headers=b).status_code == 200
        assert c.put(url, headers=admin, json={"id_usuario": escenario["cuentas"]["A"]["id"]}).status_code == 200
        historial = c.get(f"/admin/unidades/{escenario['id_unidad']}", headers=admin).json()
        assert len(historial.get("asignaciones", [])) in (0, 3)  # si el detalle trae el historial, son 3
        # Un administrador no puede ser "comprador".
        assert c.put(url, headers=admin, json={"id_usuario": 1}).status_code in (400, 409, 422)


# ------------------------------------------------------------------ P05–P08
def test_p05_aislamiento_de_comprador(admin, escenario):
    a, b = token_cliente(escenario, "A"), token_cliente(escenario, "B")
    unidad = escenario["id_unidad"]
    with cli() as c:
        assert [v["id_vehiculo"] for v in c.get("/mis-vehiculos", headers=a).json()] == [unidad]
        assert c.get("/mis-vehiculos", headers=b).json() == []
        for ruta in (f"/vehiculos/{unidad}/estado", f"/vehiculos/{unidad}/historial",
                     f"/vehiculos/{unidad}/demos", f"/vehiculos/{EXHIBICION}/estado"):
            assert c.get(ruta, headers=b).status_code == 404, ruta  # ajena = no existe para él
        assert c.post(f"/vehiculos/{unidad}/movimientos", headers=b,
                      json={"comando": "AVANZAR", "duracion_ms": 300}).status_code == 404
        assert c.get("/admin/dashboard", headers=a).status_code == 403
        assert c.get("/vehiculos", headers=a).status_code == 403


def test_p06_control_propietario_y_admin_sin_soporte(admin, escenario):
    a = token_cliente(escenario, "A")
    unidad = escenario["id_unidad"]
    with cli() as c:
        r = c.post(f"/vehiculos/{unidad}/movimientos", headers=a, json={"comando": "AVANZAR", "duracion_ms": 300})
        assert r.status_code == 200, r.text
        assert c.post(f"/vehiculos/{unidad}/movimientos", headers=a,
                      json={"comando": "VOLAR"}).status_code == 404  # no es capacidad del modelo
        # El Admin no controla ni consulta una unidad vendida sin permiso de soporte...
        assert c.post(f"/vehiculos/{unidad}/movimientos", headers=admin,
                      json={"comando": "DETENER"}).status_code == 403
        assert c.get(f"/vehiculos/{unidad}/historial", headers=admin).status_code == 403
        # ...hasta que el comprador lo otorga; al revocarlo se pierde de nuevo.
        assert c.put(f"/mis-vehiculos/{unidad}/soporte", headers=a, json={"minutos": 10}).status_code == 200
        c.post(f"/vehiculos/{unidad}/movimientos", headers=a, json={"comando": "DETENER"})
        time.sleep(0.2)
        soporte = c.post(f"/vehiculos/{unidad}/movimientos", headers=admin, json={"comando": "DETENER"})
        assert soporte.status_code in (200, 409), soporte.text  # 409 = control exclusivo del comprador
        assert c.delete(f"/mis-vehiculos/{unidad}/soporte", headers=a).status_code == 200
        assert c.get(f"/vehiculos/{unidad}/historial", headers=admin).status_code == 403


def test_p07_wss_autenticacion_y_eventos(escenario):
    a, b = token_cliente(escenario, "A"), token_cliente(escenario, "B")
    unidad = escenario["id_unidad"]

    async def flujo():
        async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}") as ws:  # sin token
            assert (await recibir(ws, "error"))["codigo"] == 401
            with pytest.raises(websockets.ConnectionClosed) as cerrado:
                await ws.recv()
            assert cerrado.value.rcvd.code == 4401
        async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}?token={b['Authorization'][7:]}") as ws:
            assert (await recibir(ws, "error"))["codigo"] == 404
        token_a = a["Authorization"][7:]
        async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}?token={token_a}") as ws:
            await recibir(ws, "estado_inicial")
            with cli() as c:
                r = c.post(f"/vehiculos/{unidad}/movimientos", headers=a,
                           json={"comando": "RETROCEDER", "duracion_ms": 300, "origen": "WEB"})
            assert r.status_code == 200, r.text
            evento = await recibir(ws, "movimiento")
            assert evento["comando"] == "RETROCEDER" and evento["id_vehiculo"] == unidad

    asyncio.run(flujo())


def test_p08_historial_10(escenario):
    a = token_cliente(escenario, "A")
    unidad = escenario["id_unidad"]
    with cli() as c:
        for i in range(12):
            r = c.post(f"/vehiculos/{unidad}/movimientos", headers=a,
                       json={"comando": "AVANZAR" if i % 2 else "DETENER", "duracion_ms": 100})
            assert r.status_code == 200, r.text
        h = c.get(f"/vehiculos/{unidad}/historial", headers=a).json()
        assert len(h) == 10
        assert all(x["id_vehiculo"] == unidad for x in h) if "id_vehiculo" in h[0] else True
        assert c.get(f"/vehiculos/{unidad}/historial", headers=a, params={"limite": 11}).status_code == 422


# ------------------------------------------------------------------ P09–P10
def test_p09_demo_persistente_y_validada(admin, escenario):
    a, b = token_cliente(escenario, "A"), token_cliente(escenario, "B")
    unidad = escenario["id_unidad"]
    pasos = [{"comando": "AVANZAR", "duracion_ms": 400, "pausa_ms": 100},
             {"comando": "GIRAR_DERECHA", "duracion_ms": 300},
             {"comando": "RETROCEDER", "duracion_ms": 400}]
    with cli() as c:
        mala = c.post(f"/vehiculos/{unidad}/demos", headers=a,
                      json={"nombre": "Inválida", "pasos": [{"comando": "VOLAR", "duracion_ms": 300}]})
        assert mala.status_code in (400, 404, 422)
        larga = c.post(f"/vehiculos/{unidad}/demos", headers=a, json={
            "nombre": "Larga", "pasos": [{"comando": "AVANZAR", "duracion_ms": 10000, "pausa_ms": 5000}] * 9})
        assert larga.status_code in (400, 422)  # supera la duración total permitida
        r = c.post(f"/vehiculos/{unidad}/demos", headers=a, json={"nombre": f"Recorrido {SUFIJO}", "pasos": pasos})
        assert r.status_code == 201, r.text
        id_demo = r.json()["id"]
        detalle = c.get(f"/vehiculos/{unidad}/demos/{id_demo}", headers=a).json()
        assert detalle["tipo"] == "privada"
        assert [p["comando"] for p in detalle["pasos"]] == ["AVANZAR", "GIRAR_DERECHA", "RETROCEDER"]
        # Reordenar y guardar (una sola transacción).
        guardada = c.put(f"/vehiculos/{unidad}/demos/{id_demo}", headers=a, json={
            "nombre": f"Recorrido {SUFIJO}", "activo": True, "pasos": list(reversed(pasos))})
        assert guardada.status_code == 200, guardada.text
        assert [p["comando"] for p in guardada.json()["pasos"]][0] == "RETROCEDER"
        assert c.get(f"/vehiculos/{unidad}/demos/{id_demo}", headers=b).status_code == 404
    escenario["id_demo"] = id_demo


def test_p10_ejecucion_y_cancelacion_de_demo(escenario):
    a = token_cliente(escenario, "A")
    unidad, id_demo = escenario["id_unidad"], escenario["id_demo"]

    async def flujo():
        async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}?token={a['Authorization'][7:]}") as ws:
            await recibir(ws, "estado_inicial")
            with cli() as c:
                r = c.post(f"/vehiculos/{unidad}/demos/{id_demo}/iniciar", headers=a, json={"origen": "WEB"})
                assert r.status_code == 202, r.text
                assert c.post(f"/vehiculos/{unidad}/demos/{id_demo}/iniciar", headers=a).status_code == 409
                await recibir(ws, "demo_inicio")
                await recibir(ws, "demo_paso")
                assert c.get(f"/vehiculos/{unidad}/demos/en-curso", headers=a).json()["id_demo"] == id_demo
                assert c.post(f"/vehiculos/{unidad}/demos/cancelar", headers=a).status_code == 200
            await recibir(ws, "demo_cancelada")
            with cli() as c:
                r = c.post(f"/vehiculos/{unidad}/demos/{id_demo}/iniciar", headers=a)
                assert r.status_code == 202
            await recibir(ws, "demo_fin", 10)

    asyncio.run(flujo())


# ------------------------------------------------------------------ P11–P14
def test_p11_p12_p14_invitado_restricciones_exclusividad(admin, escenario):
    with cli() as c:
        catalogo = c.get("/catalogo").json()
        assert any(u["id_vehiculo"] == EXHIBICION for m in catalogo["modelos"] for u in m.get("unidades", [])) \
            or catalogo["modelos"]
        assert c.post("/invitados/sesiones", json={"id_vehiculo": escenario["id_unidad"]}).status_code == 404
        r = c.post("/invitados/sesiones", json={"id_vehiculo": EXHIBICION})
        assert r.status_code == 201, r.text
        sesion = r.json()
        inv = bearer(sesion["access_token"])
        assert "VELOCIDAD" not in {x["nombre"] for x in sesion["comandos_permitidos"]}
        # P14: exclusividad, un segundo Invitado no puede reservar la misma unidad.
        assert c.post("/invitados/sesiones", json={"id_vehiculo": EXHIBICION}).status_code == 409
        # P11: movimiento permitido con duración recortada, comando restringido rechazado.
        ok = c.post(f"/vehiculos/{EXHIBICION}/movimientos", headers=inv, json={"comando": "AVANZAR", "duracion_ms": 9000})
        assert ok.status_code == 200, ok.text
        assert ok.json()["duracion_ms"] <= sesion["duracion_max_ms"]
        assert c.post(f"/vehiculos/{EXHIBICION}/movimientos", headers=inv,
                      json={"comando": "VELOCIDAD"}).status_code == 403
        # P12: rechazos al Invitado (administración, otra unidad) y del Admin mientras hay prueba activa.
        assert c.get("/admin/dashboard", headers=inv).status_code == 403
        assert c.get("/mis-vehiculos", headers=inv).status_code == 403
        assert c.get(f"/vehiculos/{escenario['id_unidad']}/estado", headers=inv).status_code == 403
        assert c.post(f"/vehiculos/{EXHIBICION}/movimientos", headers=admin,
                      json={"comando": "AVANZAR", "duracion_ms": 300}).status_code == 409
        # DETENER nunca se bloquea.
        assert c.post(f"/vehiculos/{EXHIBICION}/movimientos", headers=admin,
                      json={"comando": "DETENER"}).status_code in (200, 409)
        # Fin voluntario: DETENER de sistema y el token deja de servir.
        assert c.delete("/invitados/sesion", headers=inv).status_code == 200
        assert c.post(f"/vehiculos/{EXHIBICION}/movimientos", headers=inv,
                      json={"comando": "AVANZAR"}).status_code == 401
        estado = c.get(f"/vehiculos/{EXHIBICION}/estado", headers=admin).json()
        assert estado["comando"] == "DETENER"


def test_p13_rechazo_vehiculo_ajeno(admin, escenario):
    b = token_cliente(escenario, "B")
    with cli() as c:
        for metodo, ruta, cuerpo in (
            ("POST", f"/vehiculos/{escenario['id_unidad']}/movimientos", {"comando": "AVANZAR"}),
            ("POST", f"/vehiculos/{escenario['id_unidad']}/demos/cancelar", None),
            ("PUT", f"/mis-vehiculos/{escenario['id_unidad']}/soporte", {"minutos": 10}),
            ("GET", "/vehiculos/999999/estado", None),
        ):
            r = c.request(metodo, ruta, headers=b, json=cuerpo)
            assert r.status_code == 404, (ruta, r.status_code, r.text)


# ------------------------------------------------------------------ P15
def test_p15_reconexion_revocacion_y_expiracion(admin, escenario):
    a = token_cliente(escenario, "A")
    unidad = escenario["id_unidad"]

    async def flujo():
        token_a = a["Authorization"][7:]
        for _ in range(2):  # reconexión: cada conexión recibe el estado actual
            async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}?token={token_a}") as ws:
                inicial = await recibir(ws, "estado_inicial")
                assert inicial["id_vehiculo"] == unidad
        # Revocación: al liberar la unidad, el comprador pierde la suscripción.
        async with websockets.connect(f"{WS}/ws/vehiculos/{unidad}?token={token_a}") as ws:
            await recibir(ws, "estado_inicial")
            with cli() as c:
                r = c.delete(f"/admin/unidades/{unidad}/propietario", headers=admin)
                assert r.status_code == 200, r.text
            await recibir(ws, "acceso_revocado")
            with pytest.raises(websockets.ConnectionClosed) as cerrado:
                while True:
                    await ws.recv()
            assert cerrado.value.rcvd.code == 4403
        # Invitado que se desconecta: la prueba termina tras la gracia y la unidad queda libre.
        with cli() as c:
            r = c.post("/invitados/sesiones", json={"id_vehiculo": EXHIBICION})
            assert r.status_code == 201, r.text
            inv = r.json()["access_token"]
        async with websockets.connect(f"{WS}/ws/vehiculos/{EXHIBICION}?token={inv}") as ws:
            await recibir(ws, "estado_inicial")
        gracia = int(os.environ.get("INVITADO_GRACIA_DESCONEXION_S", "15"))
        await asyncio.sleep(gracia + 2)
        with cli() as c:
            assert c.get("/invitados/sesion", headers=bearer(inv)).status_code == 401
            r = c.post("/invitados/sesiones", json={"id_vehiculo": EXHIBICION})
            assert r.status_code == 201, r.text
            otro = r.json()
        # Expiración por tiempo: el servidor envía DETENER y cierra la prueba.
        limite = otro["expira_en_segundos"]
        if limite <= 20:
            async with websockets.connect(f"{WS}/ws/vehiculos/{EXHIBICION}?token={otro['access_token']}") as ws:
                await recibir(ws, "estado_inicial")
                detenido = await recibir(ws, "movimiento", limite + 5)
                assert detenido["comando"] == "DETENER" and detenido.get("origen") == "SISTEMA"
                fin = await recibir(ws, "sesion_invitado")
                assert fin["estado"] == "finalizada" and fin["motivo"] == "EXPIRADA"
                with pytest.raises(websockets.ConnectionClosed) as cerrado:
                    while True:
                        await ws.recv()
                assert cerrado.value.rcvd.code == 4401
        else:
            with cli() as c:
                c.delete("/invitados/sesion", headers=bearer(otro["access_token"]))

    asyncio.run(flujo())


# ------------------------------------------------------------------ P17
def test_p17_auditoria(admin, escenario):
    with cli() as c:
        r = c.get("/admin/auditoria", headers=admin, params={"limite": 200})
        assert r.status_code == 200
        acciones = {x["accion"] for x in r.json()["elementos"]}
        for esperada in ("login", "crear_unidad", "crear_usuario", "asignar_unidad", "reasignar_unidad", "liberar_unidad",
                         "otorgar_soporte", "revocar_soporte", "crear_demo", "iniciar_prueba", "finalizar_prueba",
                         "acceso_denegado"):
            assert esperada in acciones, (esperada, acciones)
        assert any(x["resultado"] != "ok" for x in r.json()["elementos"])  # también registra rechazos
        assert c.get("/admin/auditoria", headers=token_cliente(escenario, "A")).status_code == 403
        d = c.get("/admin/dashboard", headers=admin).json()
        assert d["clientes_activos"] >= 2 and d["unidades_activas"] >= 2

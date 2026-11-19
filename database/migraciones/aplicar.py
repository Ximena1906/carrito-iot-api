"""Aplica la migración 4.3 a la base de datos (RDS) desde la terminal, sin Workbench.

Uso (desde la carpeta de la API, con el .venv activado):

    python database/migraciones/aplicar.py                 # respaldo + 00 + V000…V006 + 99
    python database/migraciones/aplicar.py --solo-respaldo # solo el respaldo
    python database/migraciones/aplicar.py --archivo RUTA  # ejecutar un script (reversión o restaurar respaldo)

* Lee DB_HOST, DB_PORT y DB_NAME del archivo .env de la API.
* Pide usuario y contraseña de ADMINISTRADOR de MySQL (no api_carrito, que solo tiene EXECUTE).
  La contraseña no se muestra ni se guarda.
* Entiende DELIMITER (los procedimientos almacenados), cosa que muchas extensiones de VS Code no.
* Se detiene en el primer error e indica archivo y sentencia.
* El respaldo (tablas, datos y procedimientos) queda en database/respaldos/ (excluido de Git).
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import sys
from pathlib import Path

import pymysql

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
ORDEN = [
    "00_inventario.sql",
    "V000__control_de_migraciones.sql",
    "V001__usuarios_y_modelos.sql",
    "V002__unidades_asignaciones_soporte.sql",
    "V003__demos_tipo_y_propietario.sql",
    "V004__invitados_y_auditoria.sql",
    "V005__migrar_datos_existentes.sql",
    "V006__procedimientos_administracion.sql",
    "99_verificacion.sql",
]


# --------------------------------------------------------------------- configuración
def leer_env() -> dict:
    datos = {}
    ruta = RAIZ / ".env"
    if not ruta.exists():
        sys.exit(f"No encontré {ruta}. Ejecuta el script desde la carpeta de la API.")
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            datos[clave.strip().upper()] = valor.strip().strip('"').strip("'")
    return datos


def conectar(env: dict, usuario: str, password: str, base: str | None):
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=usuario, password=password,
        database=base, charset="utf8mb4", autocommit=True, connect_timeout=10,
        read_timeout=120, write_timeout=120,
    )


# --------------------------------------------------------------------- separar sentencias
def sentencias(texto: str):
    """Divide un script respetando DELIMITER, comillas y comentarios."""
    delim, actual, i, n = ";", [], 0, len(texto)
    linea_inicio = True
    while i < n:
        if linea_inicio:
            fin = texto.find("\n", i)
            fin = n if fin == -1 else fin
            linea = texto[i:fin]
            if linea.strip().upper().startswith("DELIMITER "):
                if "".join(actual).strip():
                    yield "".join(actual).strip()
                actual = []
                delim = linea.strip().split(None, 1)[1].strip()
                i = fin + 1
                continue
        c = texto[i]
        linea_inicio = c == "\n"
        if c in ("'", '"', "`"):
            j = i + 1
            while j < n:
                if texto[j] == "\\" and c != "`":
                    j += 2
                    continue
                if texto[j] == c:
                    if j + 1 < n and texto[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            actual.append(texto[i:j + 1])
            i = j + 1
            continue
        if texto.startswith("--", i) or c == "#":
            fin = texto.find("\n", i)
            fin = n if fin == -1 else fin
            i = fin
            continue
        if texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
            continue
        if texto.startswith(delim, i):
            s = "".join(actual).strip()
            if s:
                yield s
            actual = []
            i += len(delim)
            continue
        actual.append(c)
        i += 1
    s = "".join(actual).strip()
    if s:
        yield s


def mostrar(cursor) -> None:
    filas = cursor.fetchall()
    if not cursor.description:
        return
    columnas = [d[0] for d in cursor.description]
    valores = [[("" if v is None else str(v)) for v in f] for f in filas]
    anchos = [min(60, max([len(c)] + [len(v[k]) for v in valores])) for k, c in enumerate(columnas)]
    print("   " + " | ".join(c.ljust(a) for c, a in zip(columnas, anchos)))
    print("   " + "-+-".join("-" * a for a in anchos))
    for v in valores:
        print("   " + " | ".join(x[:60].ljust(a) for x, a in zip(v, anchos)))
    print()


def ejecutar_archivo(conn, ruta: Path) -> None:
    print(f"\n=== {ruta.name} ===")
    texto = ruta.read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        for k, s in enumerate(sentencias(texto), 1):
            try:
                cur.execute(s)
                while True:
                    mostrar(cur)
                    if not cur.nextset():
                        break
            except pymysql.MySQLError as e:
                print(f"\n*** ERROR en {ruta.name}, sentencia {k}: {e}")
                print("    " + s[:400].replace("\n", "\n    "))
                print("\nSe detuvo la migración. No ejecutes los siguientes archivos; manda este mensaje.")
                sys.exit(1)
    print(f"   OK: {ruta.name}")


# --------------------------------------------------------------------- respaldo
def respaldo(conn, base: str) -> Path:
    carpeta = RAIZ / "database" / "respaldos"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"respaldo_{base}_{dt.datetime.now():%Y%m%d_%H%M%S}.sql"
    conn.select_db(base)
    with conn.cursor() as cur, ruta.open("w", encoding="utf-8") as f:
        f.write(f"-- Respaldo de {base} · {dt.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"CREATE DATABASE IF NOT EXISTS `{base}`;\nUSE `{base}`;\nSET FOREIGN_KEY_CHECKS = 0;\n\n")
        cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tablas = [r[0] for r in cur.fetchall()]
        total = 0
        for t in tablas:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            f.write(f"DROP TABLE IF EXISTS `{t}`;\n{cur.fetchone()[1]};\n")
            cur.execute(f"SELECT * FROM `{t}`")
            filas = cur.fetchall()
            total += len(filas)
            if filas:
                cols = ", ".join(f"`{d[0]}`" for d in cur.description)
                for i in range(0, len(filas), 200):
                    valores = ",\n".join("(" + ", ".join(conn.escape(v) for v in fila) + ")" for fila in filas[i:i + 200])
                    f.write(f"INSERT INTO `{t}` ({cols}) VALUES\n{valores};\n")
            f.write("\n")
        f.write("SET FOREIGN_KEY_CHECKS = 1;\n\n")
        cur.execute("SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = %s", (base,))
        rutinas = cur.fetchall()
        f.write("DELIMITER $$\n")
        for nombre, tipo in rutinas:
            cur.execute(f"SHOW CREATE {tipo} `{nombre}`")
            definicion = cur.fetchone()[2]
            f.write(f"DROP {tipo} IF EXISTS `{nombre}`$$\n{definicion}$$\n\n")
        f.write("DELIMITER ;\n")
    print(f"Respaldo: {len(tablas)} tablas, {total} filas, {len(rutinas)} procedimientos → {ruta}")
    return ruta


# --------------------------------------------------------------------- principal
def main() -> None:
    p = argparse.ArgumentParser(description="Migración 4.3 de carrito_iot")
    p.add_argument("--solo-respaldo", action="store_true")
    p.add_argument("--archivo", type=Path, help="ejecuta solo este script .sql")
    a = p.parse_args()

    env = leer_env()
    base = env.get("DB_NAME", "carrito_iot")
    print(f"Servidor: {env['DB_HOST']}  ·  Base: {base}")
    usuario = input("Usuario ADMIN de MySQL (no api_carrito): ").strip()
    password = getpass.getpass("Contraseña (no se muestra): ")
    try:
        # Sin base fija: los scripts hacen USE y así también se puede restaurar si la base no existe.
        conn = conectar(env, usuario, password, None)
    except pymysql.MySQLError as e:
        sys.exit(f"No se pudo conectar: {e}")

    if a.archivo:
        if input(f"¿Ejecutar {a.archivo} sobre {base}? (si/no): ").strip().lower() != "si":
            sys.exit("Cancelado.")
        ejecutar_archivo(conn, a.archivo)
        return

    respaldo(conn, base)
    if a.solo_respaldo:
        return
    if input("\nRespaldo listo. ¿Aplicar 00, V000…V006 y 99 ahora? (si/no): ").strip().lower() != "si":
        sys.exit("Cancelado: no se modificó nada.")
    for nombre in ORDEN:
        ejecutar_archivo(conn, AQUI / nombre)
    print("\nMigración terminada. Revisa arriba el resultado de 99_verificacion: 65 procedimientos y 0 inconsistencias.")


if __name__ == "__main__":
    main()

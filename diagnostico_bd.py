"""Diagnóstico de la conexión API -> Amazon RDS.

Uso (con el .venv activo, desde la carpeta del proyecto):
    python diagnostico_bd.py

Revisa paso a paso: .env, DNS del endpoint, puerto 3306, usuario/contraseña,
base de datos y Stored Procedures. Nunca imprime contraseñas.
"""
import socket
import sys

OK, MAL = "[ OK ]", "[FALLA]"


def paso(n, texto):
    print(f"\n{n}. {texto}")


def main() -> int:
    paso(1, "Leyendo .env")
    try:
        from app.core.config import RAIZ_PROYECTO, obtener_settings
        s = obtener_settings()
    except Exception as exc:
        print(f"   {MAL} No se pudo leer la configuración: {exc}")
        print("   -> Revisa que exista el archivo .env junto a requirements.txt y que tenga todas las variables.")
        return 1
    print(f"   {OK} Archivo: {RAIZ_PROYECTO / '.env'}")
    print(f"        DB_HOST = {s.db_host!r}")
    print(f"        DB_PORT = {s.db_port}")
    print(f"        DB_USER = {s.db_user!r}")
    print(f"        DB_NAME = {s.db_name!r}")
    print(f"        DB_PASSWORD = {'(vacía)' if not s.db_password else '*' * len(s.db_password)} "
          f"({len(s.db_password)} caracteres)")
    if s.db_host.startswith(("http://", "https://")) or s.db_host != s.db_host.strip() or ":" in s.db_host:
        print(f"   {MAL} DB_HOST no debe llevar http://, espacios ni ':puerto'. Solo el endpoint.")
        return 1

    paso(2, "Resolviendo el endpoint (DNS)")
    try:
        ip = socket.gethostbyname(s.db_host)
        print(f"   {OK} {s.db_host} -> {ip}")
    except OSError:
        print(f"   {MAL} El endpoint no existe. Cópialo otra vez desde RDS > Conectividad y seguridad > Punto de enlace.")
        return 1

    paso(3, f"Abriendo conexión TCP al puerto {s.db_port}")
    try:
        with socket.create_connection((s.db_host, s.db_port), timeout=6):
            print(f"   {OK} El puerto {s.db_port} responde")
    except OSError:
        print(f"   {MAL} No hay respuesta en el puerto {s.db_port} (timeout).")
        print("   -> RDS detenida, 'Accesible públicamente = No', o el Security Group no permite 3306 desde tu IP actual.")
        print("   -> Tu IP pública actual la puedes ver buscando 'what is my ip' en el navegador.")
        return 1

    import pymysql

    paso(4, f"Iniciando sesión como {s.db_user!r}")
    try:
        conn = pymysql.connect(host=s.db_host, port=s.db_port, user=s.db_user, password=s.db_password,
                               connect_timeout=8, charset="utf8mb4")
        print(f"   {OK} Usuario y contraseña correctos")
    except pymysql.err.OperationalError as exc:
        codigo = exc.args[0] if exc.args else "?"
        if codigo == 1045:
            print(f"   {MAL} Usuario o contraseña incorrectos (error 1045).")
            print("   -> Si usas api_carrito, confirma que ejecutaste 05_usuario_api.sql con ESA contraseña.")
        else:
            print(f"   {MAL} Error MySQL {codigo}: {exc.args[1] if len(exc.args) > 1 else exc}")
        return 1

    with conn:
        paso(5, f"Abriendo la base {s.db_name!r}")
        try:
            conn.select_db(s.db_name)
            print(f"   {OK} La base existe y el usuario tiene acceso")
        except pymysql.err.OperationalError as exc:
            print(f"   {MAL} {exc.args[1] if len(exc.args) > 1 else exc}")
            print("   -> Revisa DB_NAME=carrito_iot y los permisos (GRANT EXECUTE ON carrito_iot.*).")
            return 1

        paso(6, "Ejecutando CALL sp_obtener_vehiculos() y sp_obtener_comandos_vehiculo(1)")
        try:
            with conn.cursor() as cur:
                cur.execute("CALL sp_obtener_vehiculos()")
                vehiculos = cur.fetchall()
                while cur.nextset():
                    pass
                cur.execute("CALL sp_obtener_comandos_vehiculo(%s)", (1,))
                comandos = cur.fetchall()
                while cur.nextset():
                    pass
            print(f"   {OK} {len(vehiculos)} vehículo(s), {len(comandos)} comando(s) del vehículo 1")
        except pymysql.MySQLError as exc:
            print(f"   {MAL} {exc.args[1] if len(exc.args) > 1 else exc}")
            print("   -> Revisa que se hayan creado los 21 SP y que el usuario tenga permiso EXECUTE.")
            return 1

    print("\nTodo correcto: la API puede usar Amazon RDS. Reinicia la API (Ctrl+C y python -m app.main).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

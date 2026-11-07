-- =====================================================================
-- 05_usuario_api.sql
-- Usuario MySQL con PRIVILEGIOS MÍNIMOS para la API (práctica 2.5, paso 2).
-- La API solo necesita ejecutar los 21 Stored Procedures: no puede leer,
-- modificar ni borrar tablas directamente.
-- Ejecutar en RDS con el usuario admin.
-- ANTES de ejecutar: cambia 'CAMBIA_ESTA_CONTRASENA' por una contraseña
-- segura y guárdala SOLO en el archivo .env (DB_PASSWORD).
-- =====================================================================

CREATE USER IF NOT EXISTS 'api_carrito'@'%' IDENTIFIED BY 'CAMBIA_ESTA_CONTRASENA';

GRANT EXECUTE ON carrito_iot.* TO 'api_carrito'@'%';

FLUSH PRIVILEGES;

-- Verificación
SHOW GRANTS FOR 'api_carrito'@'%';

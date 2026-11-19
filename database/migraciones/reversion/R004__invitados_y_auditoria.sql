-- Reversión de V004. ATENCIÓN: borra las sesiones de invitado y la bitácora de auditoría.
-- Respalda antes ambas tablas (mysqldump ... sesiones_invitado auditoria).
USE carrito_iot;
DROP TABLE IF EXISTS sesiones_invitado;
DROP TABLE IF EXISTS auditoria;
DELETE FROM migraciones_esquema WHERE version = 'V004';

-- =====================================================================
-- OPCIONAL: reinicia la bitácora de auditoría y borra las pruebas de
-- Invitado ya terminadas (las activas se conservan).
-- Haz antes el respaldo:  python database/migraciones/aplicar.py --solo-respaldo
-- Ejecutar con:
--     python database/migraciones/aplicar.py --archivo database/mantenimiento/reiniciar_auditoria.sql
-- =====================================================================
USE carrito_iot;

SELECT (SELECT COUNT(*) FROM auditoria) AS auditoria_antes,
       (SELECT COUNT(*) FROM sesiones_invitado WHERE fecha_fin IS NOT NULL) AS pruebas_terminadas_antes;

TRUNCATE TABLE auditoria;
DELETE FROM sesiones_invitado WHERE fecha_fin IS NOT NULL;

SELECT (SELECT COUNT(*) FROM auditoria) AS auditoria_despues,
       (SELECT COUNT(*) FROM sesiones_invitado) AS pruebas_restantes;

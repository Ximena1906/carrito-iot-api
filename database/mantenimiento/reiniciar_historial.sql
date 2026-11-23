-- =====================================================================
-- Reinicia el historial de movimientos (sistema "como nuevo").
-- NO tiene vuelta atrás: haz antes el respaldo con
--     python database/migraciones/aplicar.py --solo-respaldo
-- Ejecutar con:
--     python database/migraciones/aplicar.py --archivo database/mantenimiento/reiniciar_historial.sql
-- Conserva: vehículos/unidades, comandos, modelos, cuentas, DEMO y sus pasos, auditoría.
-- =====================================================================
USE carrito_iot;

SELECT COUNT(*) AS movimientos_antes, MIN(id_historial) AS primer_id, MAX(id_historial) AS ultimo_id
FROM historial_comandos;

-- Vacía el historial y reinicia los ID (el siguiente movimiento será el #1).
TRUNCATE TABLE historial_comandos;

-- El "último movimiento reportado" queda en blanco (se conserva si el ESP32 está conectado).
UPDATE estado_vehiculo SET id_comando = NULL;

SELECT COUNT(*) AS movimientos_despues FROM historial_comandos;
SELECT id_vehiculo, id_comando, conectado FROM estado_vehiculo;

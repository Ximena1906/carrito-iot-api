-- Reversión de V005 (datos): devuelve las unidades a su estado previo a la 4.3.
-- No borra vehículos, comandos, historial ni demos. Solo para ambiente de PRUEBA
-- o si se va a revertir también V002/V003. Requiere que no existan asignaciones.
USE carrito_iot;
START TRANSACTION;
UPDATE demos SET tipo = 'fabrica', id_propietario = NULL WHERE id_propietario IS NULL;
UPDATE vehiculos SET estado_comercial = 'disponible', numero_serie = NULL, id_modelo = NULL
WHERE id_propietario IS NULL;
DELETE FROM modelo_comandos;
DELETE FROM modelos;
COMMIT;
DELETE FROM migraciones_esquema WHERE version = 'V005';

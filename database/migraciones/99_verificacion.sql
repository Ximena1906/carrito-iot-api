-- =====================================================================
-- 99_verificacion.sql  ·  SOLO LECTURA
-- Comprobaciones de integridad DESPUÉS de migrar. Cada consulta indica
-- el resultado esperado. Guarda la salida como evidencia.
-- =====================================================================
USE carrito_iot;

-- 1) Migraciones aplicadas (esperado: V000 a V006)
SELECT version, descripcion, fecha_aplicacion FROM migraciones_esquema ORDER BY version;

-- 2) Los datos históricos siguen completos (comparar con 00_inventario de ANTES)
SELECT 'vehiculos' AS tabla, COUNT(*) AS filas FROM vehiculos
UNION ALL SELECT 'comandos', COUNT(*) FROM comandos
UNION ALL SELECT 'estado_vehiculo', COUNT(*) FROM estado_vehiculo
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM historial_comandos
UNION ALL SELECT 'demos', COUNT(*) FROM demos
UNION ALL SELECT 'demo_movimientos', COUNT(*) FROM demo_movimientos;
SELECT MIN(id_historial) AS primer_id, MAX(id_historial) AS ultimo_id FROM historial_comandos;

-- 3) Toda unidad tiene modelo y número de serie (esperado: 0 y 0)
SELECT COUNT(*) AS unidades_sin_modelo FROM vehiculos WHERE id_modelo IS NULL;
SELECT COUNT(*) AS unidades_sin_serie FROM vehiculos WHERE numero_serie IS NULL;

-- 4) Coherencia de propietario (esperado: 0 y 0)
SELECT COUNT(*) AS asignadas_sin_dueno FROM vehiculos WHERE estado_comercial = 'asignado' AND id_propietario IS NULL;
SELECT COUNT(*) AS dueno_sin_asignado FROM vehiculos WHERE id_propietario IS NOT NULL AND estado_comercial <> 'asignado';

-- 5) Cada comando de una unidad existe como capacidad de su modelo (esperado: 0)
SELECT COUNT(*) AS comandos_fuera_del_modelo
FROM comandos c JOIN vehiculos v ON v.id_vehiculo = c.id_vehiculo
LEFT JOIN modelo_comandos mc ON mc.id_modelo = v.id_modelo AND mc.codigo = c.codigo
WHERE mc.id_modelo_comando IS NULL;

-- 6) Pasos de DEMO con comandos de OTRA unidad (esperado: 0)
SELECT COUNT(*) AS pasos_con_comando_ajeno
FROM demo_movimientos dm JOIN demos d ON d.id_demo = dm.id_demo
JOIN comandos c ON c.id_comando = dm.id_comando
WHERE c.id_vehiculo <> d.id_vehiculo;

-- 7) Historial sin vehículo o con comando inexistente (esperado: 0)
SELECT COUNT(*) AS historial_huerfano FROM historial_comandos h
LEFT JOIN vehiculos v ON v.id_vehiculo = h.id_vehiculo WHERE v.id_vehiculo IS NULL;

-- 8) Una sola asignación abierta por unidad (esperado: ninguna fila)
SELECT id_vehiculo, COUNT(*) AS abiertas FROM asignaciones WHERE fecha_fin IS NULL
GROUP BY id_vehiculo HAVING COUNT(*) > 1;

-- 9) Procedimientos: 21 originales + 44 nuevos (esperado: 65)
SELECT COUNT(*) AS procedimientos_sp FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'carrito_iot' AND ROUTINE_TYPE = 'PROCEDURE' AND ROUTINE_NAME LIKE 'sp\_%';

-- 10) Lectura por las APIs anteriores: estado, historial y demos del vehículo 1
CALL sp_obtener_estado(1);
CALL sp_obtener_demos(1);
CALL sp_unidad_obtener(1);

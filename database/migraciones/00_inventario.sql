-- =====================================================================
-- 00_inventario.sql  ·  SOLO LECTURA
-- Inventario del esquema real de carrito_iot. Ejecútalo ANTES y DESPUÉS
-- de las migraciones y guarda ambas salidas como evidencia (14.3).
-- No modifica nada.
-- =====================================================================
USE carrito_iot;

SELECT VERSION() AS version_mysql, DATABASE() AS base, NOW() AS fecha_servidor, @@time_zone AS zona;

-- 1) Tablas y filas (conteo exacto)
SELECT 'vehiculos' AS tabla, COUNT(*) AS filas FROM vehiculos
UNION ALL SELECT 'comandos', COUNT(*) FROM comandos
UNION ALL SELECT 'estado_vehiculo', COUNT(*) FROM estado_vehiculo
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM historial_comandos
UNION ALL SELECT 'demos', COUNT(*) FROM demos
UNION ALL SELECT 'demo_movimientos', COUNT(*) FROM demo_movimientos;

-- 2) Rango de llaves del historial (debe ser IGUAL antes y después)
SELECT MIN(id_historial) AS primer_id, MAX(id_historial) AS ultimo_id,
       MIN(fecha_hora) AS primera_fecha, MAX(fecha_hora) AS ultima_fecha
FROM historial_comandos;

-- 3) Todas las tablas del esquema
SELECT TABLE_NAME AS tabla, TABLE_ROWS AS filas_aprox, CREATE_TIME AS creada
FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'carrito_iot' ORDER BY TABLE_NAME;

-- 4) Llaves foráneas
SELECT TABLE_NAME AS tabla, COLUMN_NAME AS columna, CONSTRAINT_NAME AS restriccion,
       REFERENCED_TABLE_NAME AS referencia, REFERENCED_COLUMN_NAME AS columna_ref
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'carrito_iot' AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, CONSTRAINT_NAME;

-- 5) Índices y restricciones UNIQUE
SELECT TABLE_NAME AS tabla, INDEX_NAME AS indice, NON_UNIQUE AS no_unico,
       GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS columnas
FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = 'carrito_iot'
GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE ORDER BY TABLE_NAME, INDEX_NAME;

-- 6) Procedimientos almacenados
SELECT COUNT(*) AS total_procedimientos FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'carrito_iot' AND ROUTINE_TYPE = 'PROCEDURE' AND ROUTINE_NAME LIKE 'sp\_%';
SELECT ROUTINE_NAME AS procedimiento FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'carrito_iot' AND ROUTINE_TYPE = 'PROCEDURE' ORDER BY ROUTINE_NAME;

-- 7) Migraciones aplicadas (la tabla existe a partir de V000)
SELECT COUNT(*) AS existe_tabla_migraciones FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'carrito_iot' AND TABLE_NAME = 'migraciones_esquema';

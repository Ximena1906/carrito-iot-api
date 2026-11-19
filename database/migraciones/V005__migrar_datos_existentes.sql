-- =====================================================================
-- V005__migrar_datos_existentes.sql
-- Migración de DATOS (sin borrar ni cambiar IDs):
--   * Crea un MODELO por cada valor de vehiculos.modelo existente.
--   * Copia los comandos actuales de cada vehículo como capacidades del modelo.
--   * Asigna a cada vehículo su modelo, un número de serie y el estado
--     comercial «exhibicion» (decisión de la práctica: el carrito físico
--     inicia como unidad de exhibición). Inactivos → «inactivo».
--   * Las DEMO existentes quedan como DEMO de fábrica (empresa).
-- Es re-ejecutable: solo actúa sobre filas que aún no tienen dato.
-- =====================================================================
USE carrito_iot;

START TRANSACTION;

-- 1) Modelos a partir del texto de vehiculos.modelo (o del nombre si está vacío)
INSERT IGNORE INTO modelos (nombre, descripcion, microcontrolador, imagen)
SELECT DISTINCT COALESCE(NULLIF(TRIM(v.modelo), ''), v.nombre),
       MAX(v.descripcion), MAX(v.microcontrolador), 'assets/img/modelos/carrito-garra.svg'
FROM vehiculos v
WHERE v.id_modelo IS NULL
GROUP BY COALESCE(NULLIF(TRIM(v.modelo), ''), v.nombre);

-- 2) Vehículo → modelo
UPDATE vehiculos v
JOIN modelos m ON m.nombre = COALESCE(NULLIF(TRIM(v.modelo), ''), v.nombre)
SET v.id_modelo = m.id_modelo
WHERE v.id_modelo IS NULL;

-- 3) Capacidades del modelo = comandos reales de sus vehículos
INSERT IGNORE INTO modelo_comandos (id_modelo, nombre, codigo, descripcion, tipo, duracion_max_ms, permitido_invitado, activo)
SELECT v.id_modelo, c.nombre, c.codigo, c.descripcion,
       CASE WHEN c.nombre = 'DETENER' THEN 'detener'
            WHEN c.nombre IN ('LUCES','BOCINA','VELOCIDAD','DEMO_CONTROL') THEN 'pulso'
            ELSE 'sostenido' END,
       10000,
       -- Invitados: sin VELOCIDAD (potencia) ni DEMO_CONTROL (rutina de fábrica sin control)
       CASE WHEN c.nombre IN ('VELOCIDAD','DEMO_CONTROL') THEN FALSE ELSE TRUE END,
       c.activo
FROM comandos c
JOIN vehiculos v ON v.id_vehiculo = c.id_vehiculo
WHERE v.id_modelo IS NOT NULL;

-- 4) Número de serie y estado comercial de las unidades existentes
UPDATE vehiculos
SET numero_serie = CONCAT('UNI-', LPAD(id_vehiculo, 4, '0'))
WHERE numero_serie IS NULL;

UPDATE vehiculos
SET estado_comercial = IF(activo, 'exhibicion', 'inactivo')
WHERE id_propietario IS NULL AND estado_comercial = 'disponible'
  AND NOT EXISTS (SELECT 1 FROM migraciones_esquema WHERE version = 'V005');

-- 5) DEMO existentes = DEMO de fábrica
UPDATE demos SET tipo = 'fabrica'
WHERE id_propietario IS NULL AND NOT EXISTS (SELECT 1 FROM migraciones_esquema WHERE version = 'V005');

COMMIT;

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V005', 'Datos: modelos y capacidades desde vehiculos/comandos; unidades en exhibicion; demos de fabrica');

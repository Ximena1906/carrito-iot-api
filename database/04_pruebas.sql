-- =====================================================================
-- 04_pruebas.sql
-- Validación de los 21 Stored Procedures (pasos 11-13 de la práctica 2.3
-- y paso 16 de la 2.4). Ejecuta BLOQUE POR BLOQUE y toma captura.
-- Al final los datos quedan IGUAL que después de 03_datos_carrito.sql.
-- =====================================================================

USE carrito_iot;

-- ---------- 1. Comparar SELECT directo vs. SP de consulta ------------
SELECT * FROM vehiculos;
SELECT * FROM comandos;
SELECT * FROM estado_vehiculo;
SELECT * FROM historial_comandos;
SELECT * FROM demos;
SELECT * FROM demo_movimientos;

CALL sp_obtener_vehiculo(1);
CALL sp_obtener_movimientos_demo(1);   -- debe regresar 8 movimientos ordenados 1..8

-- ---------- 2. Pruebas de actualización (y regreso al valor original) --
CALL sp_actualizar_vehiculo(1,'Carrito IoT','Carrito RC con garra',
  'PRUEBA - descripcion temporal','ESP32',TRUE);
CALL sp_obtener_vehiculo(1);
CALL sp_actualizar_vehiculo(1,'Carrito IoT','Carrito RC con garra',
  'Carrito RC con garra controlado por ESP32 mediante 2x 74HC595 y PC817','ESP32',TRUE);

CALL sp_actualizar_comando(11,'BOCINA',11,'PRUEBA - descripcion temporal',TRUE);
CALL sp_obtener_comandos_vehiculo(1);
CALL sp_actualizar_comando(11,'BOCINA',11,'Sonar bocina, pulso (4 - Chip2 Q4)',TRUE);

CALL sp_actualizar_estado(1,1,0);      -- último comando = AVANZAR
CALL sp_obtener_estado(1);
CALL sp_actualizar_estado(1,9,0);      -- regresa a DETENER

CALL sp_actualizar_demo(1,'Demo principal','PRUEBA - descripcion temporal',TRUE);
CALL sp_obtener_demos(1);
CALL sp_actualizar_demo(1,'Demo principal',
  'Recorrido: avanzar, retroceder, giros, desplazamientos laterales y garra',TRUE);

CALL sp_actualizar_movimiento_demo(1,1,1,2500,400);   -- AVANZAR 2500 ms
CALL sp_obtener_movimientos_demo(1);
CALL sp_actualizar_movimiento_demo(1,1,1,2000,400);   -- regresa a 2000 ms

-- ---------- 3. Pruebas de eliminación SIN perder datos (ROLLBACK) -----
START TRANSACTION;
  CALL sp_eliminar_movimiento_demo(8);
  CALL sp_obtener_movimientos_demo(1);   -- 7 movimientos
  CALL sp_eliminar_demo(1);
  CALL sp_obtener_demos(1);              -- vacío
  CALL sp_eliminar_comando(13);
  CALL sp_eliminar_vehiculo(1);
  CALL sp_obtener_vehiculos();           -- vacío
ROLLBACK;

-- ---------- 4. Comprobar que todo regresó ----------------------------
CALL sp_obtener_vehiculos();
CALL sp_obtener_comandos_vehiculo(1);    -- 13 comandos
CALL sp_obtener_estado(1);               -- DETENER
CALL sp_obtener_historial(1);            -- 5 registros, del más reciente al más antiguo
CALL sp_obtener_demos(1);
CALL sp_obtener_movimientos_demo(1);     -- 8 movimientos

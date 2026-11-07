-- =====================================================================
-- 03_datos_carrito.sql
-- Poblado de carrito_iot con los datos REALES del carrito.
-- Todo se inserta mediante CALL (sin INSERT directos), como pide la práctica.
-- Ejecutar sobre una base RECIÉN creada (ids empiezan en 1).
--
-- Mapeo comando -> salida física (del firmware Carrito.ino, sin cambios):
--   cod  comando           tecla  74HC595        bit  tipo
--    1   AVANZAR            W     Chip1 Q4        4   sostenido
--    2   RETROCEDER         S     Chip1 Q1        1   sostenido
--    3   GIRAR_IZQUIERDA    5     Chip1 Q2        2   sostenido
--    4   GIRAR_DERECHA      6     Chip1 Q3        3   sostenido
--    5   SUBIR_BRAZO        1     Chip1 Q5        5   sostenido (garra)
--    6   BAJAR_BRAZO        2     Chip2 Q1        9   sostenido (garra)
--    7   MOVER_IZQUIERDA    A     Chip1 Q6        6   sostenido (lateral)
--    8   MOVER_DERECHA      D     Chip2 Q2       10   sostenido (lateral)
--    9   DETENER            Q     todas en 0      -   -
--   10   LUCES              8     Chip2 Q6       14   pulso 150 ms
--   11   BOCINA             4     Chip2 Q4       12   pulso 150 ms
--   12   VELOCIDAD          7     Chip2 Q5       13   pulso 150 ms
--   13   DEMO_CONTROL       3     Chip2 Q3       11   pulso 150 ms
-- =====================================================================

USE carrito_iot;

-- ---------------------------- Vehículo -------------------------------
CALL sp_crear_vehiculo(
  'Carrito IoT',
  'Carrito RC con garra',
  'Carrito RC con garra controlado por ESP32 mediante 2x 74HC595 y PC817',
  'ESP32'
);

-- ---------------------------- Comandos -------------------------------
CALL sp_crear_comando(1,'AVANZAR',1,'Desplazamiento hacia adelante (W - Chip1 Q4)');
CALL sp_crear_comando(1,'RETROCEDER',2,'Desplazamiento hacia atras (S - Chip1 Q1)');
CALL sp_crear_comando(1,'GIRAR_IZQUIERDA',3,'Giro sobre su eje a la izquierda (5 - Chip1 Q2)');
CALL sp_crear_comando(1,'GIRAR_DERECHA',4,'Giro sobre su eje a la derecha (6 - Chip1 Q3)');
CALL sp_crear_comando(1,'SUBIR_BRAZO',5,'Garra arriba (1 - Chip1 Q5)');
CALL sp_crear_comando(1,'BAJAR_BRAZO',6,'Garra abajo (2 - Chip2 Q1)');
CALL sp_crear_comando(1,'MOVER_IZQUIERDA',7,'Desplazamiento lateral a la izquierda sin girar (A - Chip1 Q6)');
CALL sp_crear_comando(1,'MOVER_DERECHA',8,'Desplazamiento lateral a la derecha sin girar (D - Chip2 Q2)');
CALL sp_crear_comando(1,'DETENER',9,'Detener todo: apaga todas las salidas (Q)');
CALL sp_crear_comando(1,'LUCES',10,'Conmutar luces, pulso (8 - Chip2 Q6)');
CALL sp_crear_comando(1,'BOCINA',11,'Sonar bocina, pulso (4 - Chip2 Q4)');
CALL sp_crear_comando(1,'VELOCIDAD',12,'Cambiar velocidad, pulso (7 - Chip2 Q5)');
CALL sp_crear_comando(1,'DEMO_CONTROL',13,'Boton Demo del control remoto, pulso (3 - Chip2 Q3)');

-- ----------------------------- Estado --------------------------------
-- Último comando = DETENER (id 9). conectado = 0: el ESP32 aún no está
-- conectado; será la API quien lo marque cuando el dispositivo se conecte.
CALL sp_actualizar_estado(1,9,0);

-- ---------------------------- Historial ------------------------------
CALL sp_registrar_historial(1,1,'WORKBENCH');
CALL sp_registrar_historial(1,3,'WORKBENCH');
CALL sp_registrar_historial(1,7,'WORKBENCH');
CALL sp_registrar_historial(1,5,'WORKBENCH');
CALL sp_registrar_historial(1,9,'WORKBENCH');

-- ------------------------------ DEMO ---------------------------------
CALL sp_crear_demo(
  1,
  'Demo principal',
  'Recorrido: avanzar, retroceder, giros, desplazamientos laterales y garra'
);

-- (id_demo, id_comando, orden, duracion_ms, pausa_ms)
CALL sp_agregar_movimiento_demo(1, 1, 1, 2000, 400);   -- AVANZAR
CALL sp_agregar_movimiento_demo(1, 2, 2, 2000, 400);   -- RETROCEDER
CALL sp_agregar_movimiento_demo(1, 3, 3, 1000, 300);   -- GIRAR_IZQUIERDA
CALL sp_agregar_movimiento_demo(1, 4, 4, 1000, 300);   -- GIRAR_DERECHA
CALL sp_agregar_movimiento_demo(1, 7, 5, 1200, 300);   -- MOVER_IZQUIERDA
CALL sp_agregar_movimiento_demo(1, 8, 6, 1200, 300);   -- MOVER_DERECHA
CALL sp_agregar_movimiento_demo(1, 5, 7, 1500, 300);   -- SUBIR_BRAZO (garra arriba)
CALL sp_agregar_movimiento_demo(1, 6, 8, 1500,   0);   -- BAJAR_BRAZO (garra abajo)

-- --------------------------- Consultas -------------------------------
CALL sp_obtener_vehiculos();
CALL sp_obtener_comandos_vehiculo(1);
CALL sp_obtener_estado(1);
CALL sp_obtener_historial(1);
CALL sp_obtener_demos(1);
CALL sp_obtener_movimientos_demo(1);

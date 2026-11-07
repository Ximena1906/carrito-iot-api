-- =====================================================================
-- 02_stored_procedures.sql
-- Los 21 Stored Procedures oficiales de la práctica 2.3 (mismos nombres y
-- parámetros para todo el grupo). Contrato entre la API y la base de datos.
--   VEHÍCULOS (5) · COMANDOS (4) · ESTADO (2) · HISTORIAL (2)
--   DEMO (4) · MOVIMIENTOS DEMO (4)
-- Ejecutar DESPUÉS de 01_esquema.sql
-- =====================================================================

USE carrito_iot;

DELIMITER $$

-- ------------------------- VEHÍCULOS (5) -----------------------------
CREATE PROCEDURE sp_crear_vehiculo(
  IN p_nombre VARCHAR(80),
  IN p_modelo VARCHAR(80),
  IN p_descripcion VARCHAR(255),
  IN p_microcontrolador VARCHAR(50)
)
BEGIN
  INSERT INTO vehiculos(nombre, modelo, descripcion, microcontrolador)
  VALUES(p_nombre, p_modelo, p_descripcion, p_microcontrolador);
  SELECT LAST_INSERT_ID() AS id_vehiculo;
END$$

CREATE PROCEDURE sp_obtener_vehiculos()
BEGIN
  SELECT * FROM vehiculos ORDER BY id_vehiculo;
END$$

CREATE PROCEDURE sp_obtener_vehiculo(IN p_id_vehiculo INT)
BEGIN
  SELECT * FROM vehiculos WHERE id_vehiculo = p_id_vehiculo;
END$$

CREATE PROCEDURE sp_actualizar_vehiculo(
  IN p_id_vehiculo INT,
  IN p_nombre VARCHAR(80),
  IN p_modelo VARCHAR(80),
  IN p_descripcion VARCHAR(255),
  IN p_microcontrolador VARCHAR(50),
  IN p_activo BOOLEAN
)
BEGIN
  UPDATE vehiculos
  SET nombre=p_nombre, modelo=p_modelo, descripcion=p_descripcion,
      microcontrolador=p_microcontrolador, activo=p_activo
  WHERE id_vehiculo=p_id_vehiculo;
END$$

CREATE PROCEDURE sp_eliminar_vehiculo(IN p_id_vehiculo INT)
BEGIN
  DELETE FROM vehiculos WHERE id_vehiculo=p_id_vehiculo;
END$$

-- ------------------------- COMANDOS (4) ------------------------------
CREATE PROCEDURE sp_crear_comando(
  IN p_id_vehiculo INT,
  IN p_nombre VARCHAR(60),
  IN p_codigo INT,
  IN p_descripcion VARCHAR(255)
)
BEGIN
  INSERT INTO comandos(id_vehiculo,nombre,codigo,descripcion)
  VALUES(p_id_vehiculo,p_nombre,p_codigo,p_descripcion);
  SELECT LAST_INSERT_ID() AS id_comando;
END$$

CREATE PROCEDURE sp_obtener_comandos_vehiculo(IN p_id_vehiculo INT)
BEGIN
  SELECT * FROM comandos
  WHERE id_vehiculo=p_id_vehiculo
  ORDER BY codigo;
END$$

CREATE PROCEDURE sp_actualizar_comando(
  IN p_id_comando INT,
  IN p_nombre VARCHAR(60),
  IN p_codigo INT,
  IN p_descripcion VARCHAR(255),
  IN p_activo BOOLEAN
)
BEGIN
  UPDATE comandos
  SET nombre=p_nombre, codigo=p_codigo,
      descripcion=p_descripcion, activo=p_activo
  WHERE id_comando=p_id_comando;
END$$

CREATE PROCEDURE sp_eliminar_comando(IN p_id_comando INT)
BEGIN
  DELETE FROM comandos WHERE id_comando=p_id_comando;
END$$

-- -------------------------- ESTADO (2) -------------------------------
CREATE PROCEDURE sp_actualizar_estado(
  IN p_id_vehiculo INT,
  IN p_id_comando INT,
  IN p_conectado BOOLEAN
)
BEGIN
  INSERT INTO estado_vehiculo(id_vehiculo,id_comando,conectado)
  VALUES(p_id_vehiculo,p_id_comando,p_conectado)
  ON DUPLICATE KEY UPDATE
    id_comando=VALUES(id_comando),
    conectado=VALUES(conectado),
    fecha_actualizacion=CURRENT_TIMESTAMP;
END$$

CREATE PROCEDURE sp_obtener_estado(IN p_id_vehiculo INT)
BEGIN
  SELECT e.id_vehiculo, v.nombre AS vehiculo,
         e.id_comando, c.nombre AS comando, c.codigo,
         e.conectado, e.fecha_actualizacion
  FROM estado_vehiculo e
  JOIN vehiculos v ON v.id_vehiculo=e.id_vehiculo
  LEFT JOIN comandos c ON c.id_comando=e.id_comando
  WHERE e.id_vehiculo=p_id_vehiculo;
END$$

-- ------------------------- HISTORIAL (2) -----------------------------
CREATE PROCEDURE sp_registrar_historial(
  IN p_id_vehiculo INT,
  IN p_id_comando INT,
  IN p_origen VARCHAR(30)
)
BEGIN
  INSERT INTO historial_comandos(id_vehiculo,id_comando,origen)
  VALUES(p_id_vehiculo,p_id_comando,p_origen);
END$$

CREATE PROCEDURE sp_obtener_historial(IN p_id_vehiculo INT)
BEGIN
  SELECT h.id_historial, h.id_vehiculo,
         c.nombre AS comando, c.codigo,
         h.fecha_hora, h.origen
  FROM historial_comandos h
  LEFT JOIN comandos c ON c.id_comando=h.id_comando
  WHERE h.id_vehiculo=p_id_vehiculo
  ORDER BY h.fecha_hora DESC, h.id_historial DESC;
END$$

-- --------------------------- DEMO (4) --------------------------------
CREATE PROCEDURE sp_crear_demo(
  IN p_id_vehiculo INT,
  IN p_nombre VARCHAR(80),
  IN p_descripcion VARCHAR(255)
)
BEGIN
  INSERT INTO demos(id_vehiculo,nombre,descripcion)
  VALUES(p_id_vehiculo,p_nombre,p_descripcion);
  SELECT LAST_INSERT_ID() AS id_demo;
END$$

CREATE PROCEDURE sp_obtener_demos(IN p_id_vehiculo INT)
BEGIN
  SELECT * FROM demos
  WHERE id_vehiculo=p_id_vehiculo
  ORDER BY id_demo;
END$$

CREATE PROCEDURE sp_actualizar_demo(
  IN p_id_demo INT,
  IN p_nombre VARCHAR(80),
  IN p_descripcion VARCHAR(255),
  IN p_activo BOOLEAN
)
BEGIN
  UPDATE demos
  SET nombre=p_nombre, descripcion=p_descripcion, activo=p_activo
  WHERE id_demo=p_id_demo;
END$$

CREATE PROCEDURE sp_eliminar_demo(IN p_id_demo INT)
BEGIN
  DELETE FROM demos WHERE id_demo=p_id_demo;
END$$

-- --------------------- MOVIMIENTOS DEMO (4) --------------------------
CREATE PROCEDURE sp_agregar_movimiento_demo(
  IN p_id_demo INT,
  IN p_id_comando INT,
  IN p_orden INT,
  IN p_duracion_ms INT,
  IN p_pausa_ms INT
)
BEGIN
  INSERT INTO demo_movimientos
    (id_demo,id_comando,orden,duracion_ms,pausa_ms)
  VALUES
    (p_id_demo,p_id_comando,p_orden,p_duracion_ms,p_pausa_ms);
END$$

CREATE PROCEDURE sp_obtener_movimientos_demo(IN p_id_demo INT)
BEGIN
  SELECT dm.id_demo_movimiento, dm.orden,
         dm.id_comando, c.nombre AS comando, c.codigo,
         dm.duracion_ms, dm.pausa_ms
  FROM demo_movimientos dm
  JOIN comandos c ON c.id_comando=dm.id_comando
  WHERE dm.id_demo=p_id_demo
  ORDER BY dm.orden;
END$$

CREATE PROCEDURE sp_actualizar_movimiento_demo(
  IN p_id_demo_movimiento INT,
  IN p_id_comando INT,
  IN p_orden INT,
  IN p_duracion_ms INT,
  IN p_pausa_ms INT
)
BEGIN
  UPDATE demo_movimientos
  SET id_comando=p_id_comando, orden=p_orden,
      duracion_ms=p_duracion_ms, pausa_ms=p_pausa_ms
  WHERE id_demo_movimiento=p_id_demo_movimiento;
END$$

CREATE PROCEDURE sp_eliminar_movimiento_demo(IN p_id_demo_movimiento INT)
BEGIN
  DELETE FROM demo_movimientos
  WHERE id_demo_movimiento=p_id_demo_movimiento;
END$$

DELIMITER ;

-- Verificación: deben aparecer 21 procedimientos
SELECT COUNT(*) AS total_sp
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'carrito_iot' AND ROUTINE_TYPE = 'PROCEDURE';

-- =====================================================================
-- V000__control_de_migraciones.sql
-- Crea la tabla que registra qué migraciones se aplicaron y un procedimiento
-- auxiliar para agregar columnas/índices solo si no existen (re-ejecutable).
-- No toca ninguna tabla existente.
-- =====================================================================
USE carrito_iot;

CREATE TABLE IF NOT EXISTS migraciones_esquema (
  version      VARCHAR(10)  NOT NULL PRIMARY KEY,
  descripcion  VARCHAR(150) NOT NULL,
  fecha_aplicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP PROCEDURE IF EXISTS mig_agregar_columna;
DROP PROCEDURE IF EXISTS mig_agregar_indice;
DROP PROCEDURE IF EXISTS mig_agregar_fk;

DELIMITER $$
-- Agrega una columna solo si todavía no existe
CREATE PROCEDURE mig_agregar_columna(IN p_tabla VARCHAR(64), IN p_columna VARCHAR(64), IN p_definicion VARCHAR(500))
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_tabla AND COLUMN_NAME = p_columna) THEN
    SET @sql_mig = CONCAT('ALTER TABLE `', p_tabla, '` ADD COLUMN `', p_columna, '` ', p_definicion);
    PREPARE s FROM @sql_mig; EXECUTE s; DEALLOCATE PREPARE s;
  END IF;
END$$
-- Agrega un índice solo si todavía no existe
CREATE PROCEDURE mig_agregar_indice(IN p_tabla VARCHAR(64), IN p_indice VARCHAR(64), IN p_definicion VARCHAR(500))
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_tabla AND INDEX_NAME = p_indice) THEN
    SET @sql_mig = CONCAT('ALTER TABLE `', p_tabla, '` ADD ', p_definicion);
    PREPARE s FROM @sql_mig; EXECUTE s; DEALLOCATE PREPARE s;
  END IF;
END$$
-- Agrega una llave foránea solo si todavía no existe
CREATE PROCEDURE mig_agregar_fk(IN p_tabla VARCHAR(64), IN p_restriccion VARCHAR(64), IN p_definicion VARCHAR(500))
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_tabla AND CONSTRAINT_NAME = p_restriccion) THEN
    SET @sql_mig = CONCAT('ALTER TABLE `', p_tabla, '` ADD CONSTRAINT `', p_restriccion, '` ', p_definicion);
    PREPARE s FROM @sql_mig; EXECUTE s; DEALLOCATE PREPARE s;
  END IF;
END$$
DELIMITER ;

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V000', 'Control de migraciones y procedimientos auxiliares');

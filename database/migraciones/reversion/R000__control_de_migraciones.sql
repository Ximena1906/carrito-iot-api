-- Reversión de V000 (último paso): elimina la tabla de control y los auxiliares.
USE carrito_iot;
DROP PROCEDURE IF EXISTS mig_agregar_columna;
DROP PROCEDURE IF EXISTS mig_agregar_indice;
DROP PROCEDURE IF EXISTS mig_agregar_fk;
DROP TABLE IF EXISTS migraciones_esquema;

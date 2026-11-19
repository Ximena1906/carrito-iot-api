-- Reversión de V002. ATENCIÓN: borra el historial de asignaciones y permisos de soporte.
-- Las unidades (vehiculos) y su historial de movimientos se conservan.
USE carrito_iot;
DROP TABLE IF EXISTS permisos_soporte;
DROP TABLE IF EXISTS asignaciones;
ALTER TABLE vehiculos DROP FOREIGN KEY fk_vehiculo_propietario;
ALTER TABLE vehiculos DROP FOREIGN KEY fk_vehiculo_modelo;
ALTER TABLE vehiculos DROP INDEX uq_vehiculos_numero_serie, DROP INDEX ix_vehiculos_estado;
ALTER TABLE vehiculos DROP COLUMN fecha_baja, DROP COLUMN id_propietario, DROP COLUMN estado_comercial,
                      DROP COLUMN numero_serie, DROP COLUMN id_modelo;
DELETE FROM migraciones_esquema WHERE version = 'V002';

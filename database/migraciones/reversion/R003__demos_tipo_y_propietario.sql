-- Reversión de V003: quita las columnas nuevas de demos (los pasos y las demos se conservan).
-- Las demos PRIVADAS se conservan como demos normales del vehículo.
USE carrito_iot;
ALTER TABLE demos DROP FOREIGN KEY fk_demo_propietario;
ALTER TABLE demos DROP INDEX ix_demos_vehiculo_tipo;
ALTER TABLE demos DROP COLUMN fecha_modificacion, DROP COLUMN fecha_creacion,
                  DROP COLUMN id_propietario, DROP COLUMN tipo;
DELETE FROM migraciones_esquema WHERE version = 'V003';

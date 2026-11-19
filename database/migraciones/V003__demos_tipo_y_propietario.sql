-- =====================================================================
-- V003__demos_tipo_y_propietario.sql
-- La tabla EXISTENTE demos recibe tipo (fábrica de la empresa / privada del
-- comprador), propietario y fechas. demo_movimientos NO cambia: ya guarda
-- pasos ordenados (UNIQUE id_demo+orden) con duración y pausa.
-- =====================================================================
USE carrito_iot;

CALL mig_agregar_columna('demos', 'tipo', "ENUM('fabrica','privada') NOT NULL DEFAULT 'fabrica' AFTER descripcion");
CALL mig_agregar_columna('demos', 'id_propietario', 'INT NULL AFTER tipo');
CALL mig_agregar_columna('demos', 'fecha_creacion', 'TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP AFTER activo');
CALL mig_agregar_columna('demos', 'fecha_modificacion', 'TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP AFTER fecha_creacion');

CALL mig_agregar_indice('demos', 'ix_demos_vehiculo_tipo', 'INDEX ix_demos_vehiculo_tipo (id_vehiculo, tipo, activo)');
CALL mig_agregar_fk('demos', 'fk_demo_propietario',
  'FOREIGN KEY (id_propietario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE');

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V003', 'demos: tipo fabrica/privada, propietario y fechas');

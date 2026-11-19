-- =====================================================================
-- V002__unidades_asignaciones_soporte.sql
-- La tabla EXISTENTE vehiculos pasa a representar la UNIDAD física.
-- Se CONSERVA id_vehiculo (lo usan CONTROL, MONITOREO, historial y el ESP32)
-- y solo se AGREGAN columnas: modelo, número de serie, estado comercial y
-- propietario. Tablas NUEVAS: asignaciones (historia de propietarios) y
-- permisos_soporte (autorización explícita del comprador al Administrador).
-- =====================================================================
USE carrito_iot;

CALL mig_agregar_columna('vehiculos', 'id_modelo',        'INT NULL AFTER id_vehiculo');
CALL mig_agregar_columna('vehiculos', 'numero_serie',     'VARCHAR(40) NULL AFTER id_modelo');
CALL mig_agregar_columna('vehiculos', 'estado_comercial',
  "ENUM('disponible','asignado','exhibicion','inactivo') NOT NULL DEFAULT 'disponible' AFTER activo");
CALL mig_agregar_columna('vehiculos', 'id_propietario',   'INT NULL AFTER estado_comercial');
CALL mig_agregar_columna('vehiculos', 'fecha_baja',       'TIMESTAMP NULL AFTER id_propietario');

CALL mig_agregar_indice('vehiculos', 'uq_vehiculos_numero_serie', 'CONSTRAINT uq_vehiculos_numero_serie UNIQUE (numero_serie)');
CALL mig_agregar_indice('vehiculos', 'ix_vehiculos_estado', 'INDEX ix_vehiculos_estado (estado_comercial)');
CALL mig_agregar_fk('vehiculos', 'fk_vehiculo_modelo',
  'FOREIGN KEY (id_modelo) REFERENCES modelos(id_modelo) ON DELETE RESTRICT ON UPDATE CASCADE');
CALL mig_agregar_fk('vehiculos', 'fk_vehiculo_propietario',
  'FOREIGN KEY (id_propietario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE');

-- Historia de propietarios: nunca se borra; al reasignar se cierra fecha_fin.
CREATE TABLE IF NOT EXISTS asignaciones (
  id_asignacion INT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo   INT NOT NULL,
  id_usuario    INT NOT NULL,
  asignado_por  INT NULL,
  fecha_inicio  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_fin     TIMESTAMP NULL,
  motivo_fin    VARCHAR(40) NULL,
  INDEX ix_asignaciones_vehiculo (id_vehiculo, fecha_fin),
  INDEX ix_asignaciones_usuario (id_usuario, fecha_fin),
  CONSTRAINT fk_asignacion_vehiculo FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_asignacion_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_asignacion_admin FOREIGN KEY (asignado_por) REFERENCES usuarios(id_usuario)
    ON DELETE SET NULL ON UPDATE CASCADE
);

-- Soporte operativo: el comprador autoriza temporalmente al Administrador.
CREATE TABLE IF NOT EXISTS permisos_soporte (
  id_permiso       INT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo      INT NOT NULL,
  otorgado_por     INT NOT NULL,                  -- comprador propietario
  fecha_inicio     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_expira     TIMESTAMP NOT NULL,
  fecha_revocacion TIMESTAMP NULL,
  INDEX ix_soporte_vehiculo (id_vehiculo, fecha_revocacion, fecha_expira),
  CONSTRAINT fk_soporte_vehiculo FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_soporte_usuario FOREIGN KEY (otorgado_por) REFERENCES usuarios(id_usuario)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V002', 'vehiculos como unidad física + asignaciones + permisos_soporte');

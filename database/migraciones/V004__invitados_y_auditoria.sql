-- =====================================================================
-- V004__invitados_y_auditoria.sql
-- Tablas NUEVAS: sesiones temporales de Invitado con reserva EXCLUSIVA por
-- unidad (UNIQUE en reserva_vehiculo) y bitácora de auditoría.
-- =====================================================================
USE carrito_iot;

CREATE TABLE IF NOT EXISTS sesiones_invitado (
  id_sesion        BIGINT AUTO_INCREMENT PRIMARY KEY,
  codigo           CHAR(32) NOT NULL,                 -- identificador aleatorio de la sesión
  id_vehiculo      INT NOT NULL,
  -- Igual a id_vehiculo mientras la sesión está activa y NULL al terminar:
  -- el UNIQUE impide que dos sesiones reserven la misma unidad a la vez.
  reserva_vehiculo INT NULL,
  fecha_inicio     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_expira     TIMESTAMP NOT NULL,
  fecha_fin        TIMESTAMP NULL,
  motivo_fin       VARCHAR(40) NULL,
  CONSTRAINT uq_invitado_codigo UNIQUE (codigo),
  CONSTRAINT uq_invitado_reserva UNIQUE (reserva_vehiculo),
  INDEX ix_invitado_vehiculo (id_vehiculo, fecha_inicio),
  INDEX ix_invitado_expira (fecha_fin, fecha_expira),
  CONSTRAINT fk_invitado_vehiculo FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Sin contraseñas, tokens ni secretos: solo quién, qué, sobre qué y resultado.
CREATE TABLE IF NOT EXISTS auditoria (
  id_auditoria BIGINT AUTO_INCREMENT PRIMARY KEY,
  fecha_hora   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  actor_tipo   ENUM('admin','usuario','invitado','sistema','anonimo') NOT NULL,
  id_actor     INT NULL,
  actor        VARCHAR(60) NULL,
  accion       VARCHAR(50) NOT NULL,
  recurso      VARCHAR(40) NULL,
  id_recurso   VARCHAR(40) NULL,
  resultado    ENUM('ok','rechazado','error') NOT NULL,
  detalle      VARCHAR(500) NULL,
  INDEX ix_auditoria_fecha (fecha_hora),
  INDEX ix_auditoria_accion (accion, fecha_hora),
  INDEX ix_auditoria_actor (actor_tipo, id_actor)
);

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V004', 'sesiones_invitado con reserva exclusiva y auditoria');

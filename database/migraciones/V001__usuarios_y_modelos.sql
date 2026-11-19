-- =====================================================================
-- V001__usuarios_y_modelos.sql
-- Tablas NUEVAS: usuarios (Administrador y Usuario/comprador), modelos
-- comerciales y capacidades (comandos que soporta cada modelo).
-- No modifica tablas existentes.
-- =====================================================================
USE carrito_iot;

-- Cuentas con rol. El Invitado NO tiene cuenta: usa una sesión temporal.
-- La contraseña se guarda como hash PBKDF2-SHA256 (nunca en texto plano).
CREATE TABLE IF NOT EXISTS usuarios (
  id_usuario        INT AUTO_INCREMENT PRIMARY KEY,
  usuario           VARCHAR(40)  NOT NULL,
  nombre            VARCHAR(100) NOT NULL,
  correo            VARCHAR(120) NULL,
  telefono          VARCHAR(20)  NULL,
  rol               ENUM('admin','usuario') NOT NULL DEFAULT 'usuario',
  password_hash     VARCHAR(255) NOT NULL,
  version_token     INT UNSIGNED NOT NULL DEFAULT 0,      -- al cambiar, invalida los tokens emitidos
  intentos_fallidos TINYINT UNSIGNED NOT NULL DEFAULT 0,
  bloqueado_hasta   TIMESTAMP NULL,
  activo            BOOLEAN NOT NULL DEFAULT TRUE,        -- baja lógica
  fecha_alta        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_baja        TIMESTAMP NULL,
  CONSTRAINT uq_usuarios_usuario UNIQUE (usuario),
  CONSTRAINT uq_usuarios_correo  UNIQUE (correo),
  INDEX ix_usuarios_rol (rol, activo)
);

-- MODELO comercial (p. ej. «Carrito RC con garra», «Excavadora IoT»).
CREATE TABLE IF NOT EXISTS modelos (
  id_modelo        INT AUTO_INCREMENT PRIMARY KEY,
  nombre           VARCHAR(80)  NOT NULL,
  descripcion      VARCHAR(500) NULL,
  imagen           VARCHAR(255) NULL,          -- ruta relativa de un asset público
  microcontrolador VARCHAR(50)  NULL,
  activo           BOOLEAN NOT NULL DEFAULT TRUE,
  fecha_alta       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_modelos_nombre UNIQUE (nombre)
);

-- Capacidades reales del hardware de cada modelo (comandos soportados).
CREATE TABLE IF NOT EXISTS modelo_comandos (
  id_modelo_comando  INT AUTO_INCREMENT PRIMARY KEY,
  id_modelo          INT NOT NULL,
  nombre             VARCHAR(60) NOT NULL,
  codigo             INT NOT NULL,
  descripcion        VARCHAR(255) NULL,
  tipo               ENUM('sostenido','pulso','detener') NOT NULL DEFAULT 'sostenido',
  duracion_max_ms    INT UNSIGNED NOT NULL DEFAULT 10000,
  permitido_invitado BOOLEAN NOT NULL DEFAULT FALSE,
  activo             BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_modelo_comando_codigo UNIQUE (id_modelo, codigo),
  CONSTRAINT uq_modelo_comando_nombre UNIQUE (id_modelo, nombre),
  CONSTRAINT ck_modelo_comando_duracion CHECK (duracion_max_ms BETWEEN 50 AND 10000),
  CONSTRAINT fk_modelo_comando_modelo FOREIGN KEY (id_modelo) REFERENCES modelos(id_modelo)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V001', 'usuarios, modelos y modelo_comandos');

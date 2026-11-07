-- =====================================================================
-- 01_esquema.sql
-- Proyecto: Carrito IoT (ESP32 + 2x 74HC595)
-- Base de datos carrito_iot - 6 tablas (mismo esquema oficial de vehiculo_iot,
-- práctica 2.3; solo cambia el nombre de la base porque en RDS ya existe otra vehiculo_iot)
-- NO modificar estructura ni nombres: es el contrato común del grupo.
-- Ejecutar en MySQL Workbench (conexión local, usuario admin).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS carrito_iot
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE carrito_iot;

-- 1) Vehículo físico
CREATE TABLE vehiculos (
  id_vehiculo INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  modelo VARCHAR(80),
  descripcion VARCHAR(255),
  microcontrolador VARCHAR(50),
  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2) Catálogo de comandos de cada vehículo
CREATE TABLE comandos (
  id_comando INT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo INT NOT NULL,
  nombre VARCHAR(60) NOT NULL,
  codigo INT NOT NULL,
  descripcion VARCHAR(255),
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_comando_codigo UNIQUE (id_vehiculo, codigo),
  CONSTRAINT uq_comando_nombre UNIQUE (id_vehiculo, nombre),
  CONSTRAINT fk_comando_vehiculo
    FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE CASCADE ON UPDATE CASCADE
);

-- 3) Último estado del vehículo (un registro por vehículo)
CREATE TABLE estado_vehiculo (
  id_estado INT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo INT NOT NULL UNIQUE,
  id_comando INT NULL,
  fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  conectado BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT fk_estado_vehiculo
    FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_estado_comando
    FOREIGN KEY (id_comando) REFERENCES comandos(id_comando)
    ON DELETE SET NULL ON UPDATE CASCADE
);

-- 4) Bitácora de movimientos individuales (las DEMO NO se registran aquí)
CREATE TABLE historial_comandos (
  id_historial BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo INT NOT NULL,
  id_comando INT NULL,
  fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  origen VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
  CONSTRAINT fk_historial_vehiculo
    FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_historial_comando
    FOREIGN KEY (id_comando) REFERENCES comandos(id_comando)
    ON DELETE SET NULL ON UPDATE CASCADE
);

-- 5) DEMO: secuencia automática almacenada como datos
CREATE TABLE demos (
  id_demo INT AUTO_INCREMENT PRIMARY KEY,
  id_vehiculo INT NOT NULL,
  nombre VARCHAR(80) NOT NULL,
  descripcion VARCHAR(255),
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_demo_vehiculo
    FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo)
    ON DELETE CASCADE ON UPDATE CASCADE
);

-- 6) Movimientos ordenados de cada DEMO
CREATE TABLE demo_movimientos (
  id_demo_movimiento INT AUTO_INCREMENT PRIMARY KEY,
  id_demo INT NOT NULL,
  id_comando INT NOT NULL,
  orden INT NOT NULL,
  duracion_ms INT UNSIGNED NOT NULL,
  pausa_ms INT UNSIGNED NOT NULL DEFAULT 0,
  CONSTRAINT uq_demo_orden UNIQUE (id_demo, orden),
  CONSTRAINT fk_mov_demo
    FOREIGN KEY (id_demo) REFERENCES demos(id_demo)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_mov_comando
    FOREIGN KEY (id_comando) REFERENCES comandos(id_comando)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Verificación rápida
SHOW TABLES;

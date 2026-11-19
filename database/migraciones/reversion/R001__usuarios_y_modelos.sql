-- Reversión de V001 (ejecutar después de R002, R003 y R005). Borra cuentas y modelos.
USE carrito_iot;
DROP TABLE IF EXISTS modelo_comandos;
DROP TABLE IF EXISTS modelos;
DROP TABLE IF EXISTS usuarios;
DELETE FROM migraciones_esquema WHERE version = 'V001';

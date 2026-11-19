-- =====================================================================
-- V006__procedimientos_administracion.sql
-- Procedimientos NUEVOS para ADMINISTRACIÓN (los 21 originales NO cambian).
-- La API sigue usando SOLO procedimientos: el usuario api_carrito conserva
-- únicamente EXECUTE (GRANT EXECUTE ON carrito_iot.* ya cubre los nuevos).
-- Re-ejecutable: cada procedimiento se elimina y se vuelve a crear.
-- =====================================================================
USE carrito_iot;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_usuario_crear$$
CREATE PROCEDURE sp_usuario_crear(IN p_usuario VARCHAR(40), IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120), IN p_telefono VARCHAR(20), IN p_rol VARCHAR(10), IN p_hash VARCHAR(255))
BEGIN
  INSERT INTO usuarios(usuario, nombre, correo, telefono, rol, password_hash)
  VALUES (p_usuario, p_nombre, NULLIF(p_correo, ''), NULLIF(p_telefono, ''), p_rol, p_hash);
  SELECT LAST_INSERT_ID() AS id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_por_login$$
CREATE PROCEDURE sp_usuario_por_login(IN p_usuario VARCHAR(40))
BEGIN
  SELECT id_usuario, usuario, nombre, correo, rol, password_hash, version_token, intentos_fallidos,
         bloqueado_hasta, (bloqueado_hasta IS NOT NULL AND bloqueado_hasta > NOW()) AS bloqueado, activo
  FROM usuarios WHERE usuario = p_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_por_id$$
CREATE PROCEDURE sp_usuario_por_id(IN p_id_usuario INT)
BEGIN
  SELECT id_usuario, usuario, nombre, correo, telefono, rol, version_token, activo, fecha_alta, fecha_baja
  FROM usuarios WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuarios_listar$$
CREATE PROCEDURE sp_usuarios_listar(IN p_rol VARCHAR(10), IN p_texto VARCHAR(100), IN p_activo TINYINT, IN p_limite INT, IN p_desplazamiento INT)
BEGIN
  SELECT u.id_usuario, u.usuario, u.nombre, u.correo, u.telefono, u.rol, u.activo, u.fecha_alta, u.fecha_baja,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_propietario = u.id_usuario) AS unidades,
         COUNT(*) OVER() AS total
  FROM usuarios u
  WHERE (p_rol IS NULL OR u.rol = p_rol)
    AND (p_activo IS NULL OR u.activo = p_activo)
    AND (p_texto IS NULL OR p_texto = '' OR u.nombre LIKE CONCAT('%', p_texto, '%')
         OR u.usuario LIKE CONCAT('%', p_texto, '%') OR u.correo LIKE CONCAT('%', p_texto, '%'))
  ORDER BY u.nombre, u.id_usuario
  LIMIT p_limite OFFSET p_desplazamiento;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_actualizar$$
CREATE PROCEDURE sp_usuario_actualizar(IN p_id_usuario INT, IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120), IN p_telefono VARCHAR(20))
BEGIN
  UPDATE usuarios SET nombre = p_nombre, correo = NULLIF(p_correo, ''), telefono = NULLIF(p_telefono, '')
  WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_cambiar_activo$$
CREATE PROCEDURE sp_usuario_cambiar_activo(IN p_id_usuario INT, IN p_activo BOOLEAN)
BEGIN
  UPDATE usuarios
  SET activo = p_activo, fecha_baja = IF(p_activo, NULL, NOW()), version_token = version_token + 1
  WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_cambiar_password$$
CREATE PROCEDURE sp_usuario_cambiar_password(IN p_id_usuario INT, IN p_hash VARCHAR(255))
BEGIN
  UPDATE usuarios SET password_hash = p_hash, version_token = version_token + 1, intentos_fallidos = 0, bloqueado_hasta = NULL
  WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_cerrar_sesiones$$
CREATE PROCEDURE sp_usuario_cerrar_sesiones(IN p_id_usuario INT)
BEGIN
  UPDATE usuarios SET version_token = version_token + 1 WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_login_fallido$$
CREATE PROCEDURE sp_usuario_login_fallido(IN p_id_usuario INT)
BEGIN
  UPDATE usuarios
  SET intentos_fallidos = IF(intentos_fallidos + 1 >= 5, 0, intentos_fallidos + 1),
      bloqueado_hasta  = IF(intentos_fallidos + 1 >= 5, NOW() + INTERVAL 5 MINUTE, bloqueado_hasta)
  WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuario_login_exitoso$$
CREATE PROCEDURE sp_usuario_login_exitoso(IN p_id_usuario INT)
BEGIN
  UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = p_id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_usuarios_contar_admin$$
CREATE PROCEDURE sp_usuarios_contar_admin()
BEGIN
  SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'admin' AND activo = TRUE;
END$$

DROP PROCEDURE IF EXISTS sp_modelo_crear$$
CREATE PROCEDURE sp_modelo_crear(IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(500), IN p_imagen VARCHAR(255), IN p_microcontrolador VARCHAR(50))
BEGIN
  INSERT INTO modelos(nombre, descripcion, imagen, microcontrolador)
  VALUES (p_nombre, NULLIF(p_descripcion, ''), NULLIF(p_imagen, ''), NULLIF(p_microcontrolador, ''));
  SELECT LAST_INSERT_ID() AS id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_modelo_actualizar$$
CREATE PROCEDURE sp_modelo_actualizar(IN p_id_modelo INT, IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(500), IN p_imagen VARCHAR(255), IN p_microcontrolador VARCHAR(50))
BEGIN
  UPDATE modelos SET nombre = p_nombre, descripcion = NULLIF(p_descripcion, ''), imagen = NULLIF(p_imagen, ''),
         microcontrolador = NULLIF(p_microcontrolador, '')
  WHERE id_modelo = p_id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_modelo_cambiar_activo$$
CREATE PROCEDURE sp_modelo_cambiar_activo(IN p_id_modelo INT, IN p_activo BOOLEAN)
BEGIN
  UPDATE modelos SET activo = p_activo WHERE id_modelo = p_id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_modelos_listar$$
CREATE PROCEDURE sp_modelos_listar(IN p_solo_activos BOOLEAN)
BEGIN
  SELECT m.id_modelo, m.nombre, m.descripcion, m.imagen, m.microcontrolador, m.activo, m.fecha_alta,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_modelo = m.id_modelo AND v.estado_comercial <> 'inactivo') AS unidades,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_modelo = m.id_modelo AND v.estado_comercial = 'exhibicion' AND v.activo) AS unidades_exhibicion,
         (SELECT COUNT(*) FROM modelo_comandos c WHERE c.id_modelo = m.id_modelo AND c.activo) AS capacidades
  FROM modelos m
  WHERE (NOT p_solo_activos OR m.activo)
  ORDER BY m.nombre;
END$$

DROP PROCEDURE IF EXISTS sp_modelo_obtener$$
CREATE PROCEDURE sp_modelo_obtener(IN p_id_modelo INT)
BEGIN
  SELECT id_modelo, nombre, descripcion, imagen, microcontrolador, activo, fecha_alta
  FROM modelos WHERE id_modelo = p_id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_capacidades_listar$$
CREATE PROCEDURE sp_capacidades_listar(IN p_id_modelo INT)
BEGIN
  SELECT id_modelo_comando, id_modelo, nombre, codigo, descripcion, tipo, duracion_max_ms, permitido_invitado, activo
  FROM modelo_comandos WHERE id_modelo = p_id_modelo ORDER BY codigo;
END$$

DROP PROCEDURE IF EXISTS sp_capacidad_guardar$$
CREATE PROCEDURE sp_capacidad_guardar(IN p_id_modelo INT, IN p_nombre VARCHAR(60), IN p_codigo INT, IN p_descripcion VARCHAR(255), IN p_tipo VARCHAR(10), IN p_duracion_max INT, IN p_permitido_invitado BOOLEAN, IN p_activo BOOLEAN)
BEGIN
  INSERT INTO modelo_comandos(id_modelo, nombre, codigo, descripcion, tipo, duracion_max_ms, permitido_invitado, activo)
  VALUES (p_id_modelo, p_nombre, p_codigo, NULLIF(p_descripcion, ''), p_tipo, p_duracion_max, p_permitido_invitado, p_activo)
  ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), descripcion = VALUES(descripcion), tipo = VALUES(tipo),
    duracion_max_ms = VALUES(duracion_max_ms), permitido_invitado = VALUES(permitido_invitado), activo = VALUES(activo);
  -- Las unidades del modelo reciben el comando (o su nuevo estado) sin perder su id_comando
  INSERT IGNORE INTO comandos(id_vehiculo, nombre, codigo, descripcion, activo)
  SELECT v.id_vehiculo, p_nombre, p_codigo, NULLIF(p_descripcion, ''), p_activo
  FROM vehiculos v WHERE v.id_modelo = p_id_modelo;
  UPDATE comandos c JOIN vehiculos v ON v.id_vehiculo = c.id_vehiculo
  SET c.activo = p_activo, c.descripcion = NULLIF(p_descripcion, '')
  WHERE v.id_modelo = p_id_modelo AND c.codigo = p_codigo;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_crear$$
CREATE PROCEDURE sp_unidad_crear(IN p_id_modelo INT, IN p_numero_serie VARCHAR(40), IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(255), IN p_estado VARCHAR(12))
BEGIN
  DECLARE v_id INT;
  INSERT INTO vehiculos(nombre, modelo, descripcion, microcontrolador, activo, id_modelo, numero_serie, estado_comercial)
  SELECT p_nombre, m.nombre, NULLIF(p_descripcion, ''), m.microcontrolador, TRUE, m.id_modelo, p_numero_serie, p_estado
  FROM modelos m WHERE m.id_modelo = p_id_modelo;
  SET v_id = LAST_INSERT_ID();
  -- Comandos habilitados = capacidades activas del modelo
  INSERT INTO comandos(id_vehiculo, nombre, codigo, descripcion, activo)
  SELECT v_id, c.nombre, c.codigo, c.descripcion, c.activo FROM modelo_comandos c WHERE c.id_modelo = p_id_modelo;
  SELECT v_id AS id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_unidades_listar$$
CREATE PROCEDURE sp_unidades_listar(IN p_estado VARCHAR(12), IN p_id_modelo INT, IN p_texto VARCHAR(80), IN p_limite INT, IN p_desplazamiento INT)
BEGIN
  SELECT v.id_vehiculo, v.numero_serie, v.nombre, v.descripcion, v.id_modelo, m.nombre AS modelo,
         v.estado_comercial, v.activo, v.id_propietario, u.nombre AS propietario, u.usuario AS propietario_usuario,
         COALESCE(e.conectado, FALSE) AS conectado, v.fecha_registro, v.fecha_baja,
         (SELECT MAX(s.fecha_expira) FROM permisos_soporte s
           WHERE s.id_vehiculo = v.id_vehiculo AND s.fecha_revocacion IS NULL AND s.fecha_expira > NOW()) AS soporte_hasta,
         COUNT(*) OVER() AS total
  FROM vehiculos v
  LEFT JOIN modelos m ON m.id_modelo = v.id_modelo
  LEFT JOIN usuarios u ON u.id_usuario = v.id_propietario
  LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
  WHERE (p_estado IS NULL OR p_estado = '' OR v.estado_comercial = p_estado)
    AND (p_id_modelo IS NULL OR v.id_modelo = p_id_modelo)
    AND (p_texto IS NULL OR p_texto = '' OR v.nombre LIKE CONCAT('%', p_texto, '%')
         OR v.numero_serie LIKE CONCAT('%', p_texto, '%') OR u.nombre LIKE CONCAT('%', p_texto, '%'))
  ORDER BY v.id_vehiculo
  LIMIT p_limite OFFSET p_desplazamiento;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_obtener$$
CREATE PROCEDURE sp_unidad_obtener(IN p_id_vehiculo INT)
BEGIN
  SELECT v.id_vehiculo, v.numero_serie, v.nombre, v.descripcion, v.id_modelo, m.nombre AS modelo,
         v.estado_comercial, v.activo, v.id_propietario, u.nombre AS propietario, u.usuario AS propietario_usuario,
         COALESCE(e.conectado, FALSE) AS conectado, v.fecha_registro, v.fecha_baja
  FROM vehiculos v
  LEFT JOIN modelos m ON m.id_modelo = v.id_modelo
  LEFT JOIN usuarios u ON u.id_usuario = v.id_propietario
  LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
  WHERE v.id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_actualizar$$
CREATE PROCEDURE sp_unidad_actualizar(IN p_id_vehiculo INT, IN p_numero_serie VARCHAR(40), IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(255))
BEGIN
  UPDATE vehiculos SET numero_serie = p_numero_serie, nombre = p_nombre, descripcion = NULLIF(p_descripcion, '')
  WHERE id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_cambiar_estado$$
CREATE PROCEDURE sp_unidad_cambiar_estado(IN p_id_vehiculo INT, IN p_estado VARCHAR(12))
BEGIN
  UPDATE vehiculos
  SET estado_comercial = p_estado,
      activo = (p_estado <> 'inactivo'),
      fecha_baja = IF(p_estado = 'inactivo', NOW(), NULL)
  WHERE id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_asignar$$
CREATE PROCEDURE sp_unidad_asignar(IN p_id_vehiculo INT, IN p_id_usuario INT, IN p_id_admin INT)
BEGIN
  UPDATE asignaciones SET fecha_fin = NOW(), motivo_fin = 'REASIGNACION'
  WHERE id_vehiculo = p_id_vehiculo AND fecha_fin IS NULL;
  UPDATE permisos_soporte SET fecha_revocacion = NOW()
  WHERE id_vehiculo = p_id_vehiculo AND fecha_revocacion IS NULL;
  INSERT INTO asignaciones(id_vehiculo, id_usuario, asignado_por) VALUES (p_id_vehiculo, p_id_usuario, p_id_admin);
  UPDATE vehiculos SET id_propietario = p_id_usuario, estado_comercial = 'asignado', activo = TRUE, fecha_baja = NULL
  WHERE id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_unidad_liberar$$
CREATE PROCEDURE sp_unidad_liberar(IN p_id_vehiculo INT, IN p_estado VARCHAR(12), IN p_motivo VARCHAR(40))
BEGIN
  UPDATE asignaciones SET fecha_fin = NOW(), motivo_fin = p_motivo
  WHERE id_vehiculo = p_id_vehiculo AND fecha_fin IS NULL;
  UPDATE permisos_soporte SET fecha_revocacion = NOW()
  WHERE id_vehiculo = p_id_vehiculo AND fecha_revocacion IS NULL;
  UPDATE vehiculos SET id_propietario = NULL, estado_comercial = p_estado
  WHERE id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_asignaciones_listar$$
CREATE PROCEDURE sp_asignaciones_listar(IN p_id_vehiculo INT)
BEGIN
  SELECT a.id_asignacion, a.id_vehiculo, a.id_usuario, u.nombre AS usuario_nombre, u.usuario,
         a.asignado_por, ad.nombre AS asignado_por_nombre, a.fecha_inicio, a.fecha_fin, a.motivo_fin
  FROM asignaciones a
  JOIN usuarios u ON u.id_usuario = a.id_usuario
  LEFT JOIN usuarios ad ON ad.id_usuario = a.asignado_por
  WHERE a.id_vehiculo = p_id_vehiculo
  ORDER BY a.fecha_inicio DESC, a.id_asignacion DESC;
END$$

DROP PROCEDURE IF EXISTS sp_mis_vehiculos$$
CREATE PROCEDURE sp_mis_vehiculos(IN p_id_usuario INT)
BEGIN
  SELECT v.id_vehiculo, v.numero_serie, v.nombre, v.descripcion, v.id_modelo, m.nombre AS modelo,
         v.estado_comercial, v.activo, v.id_propietario, u.nombre AS propietario, u.usuario AS propietario_usuario,
         COALESCE(e.conectado, FALSE) AS conectado, v.fecha_registro, v.fecha_baja,
         (SELECT MAX(s.fecha_expira) FROM permisos_soporte s
           WHERE s.id_vehiculo = v.id_vehiculo AND s.fecha_revocacion IS NULL AND s.fecha_expira > NOW()) AS soporte_hasta
  FROM vehiculos v
  LEFT JOIN modelos m ON m.id_modelo = v.id_modelo
  LEFT JOIN usuarios u ON u.id_usuario = v.id_propietario
  LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
  WHERE v.id_propietario = p_id_usuario AND v.estado_comercial = 'asignado'
  ORDER BY v.id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_soporte_otorgar$$
CREATE PROCEDURE sp_soporte_otorgar(IN p_id_vehiculo INT, IN p_id_usuario INT, IN p_minutos INT)
BEGIN
  UPDATE permisos_soporte SET fecha_revocacion = NOW()
  WHERE id_vehiculo = p_id_vehiculo AND fecha_revocacion IS NULL;
  INSERT INTO permisos_soporte(id_vehiculo, otorgado_por, fecha_expira)
  VALUES (p_id_vehiculo, p_id_usuario, NOW() + INTERVAL p_minutos MINUTE);
  SELECT LAST_INSERT_ID() AS id_permiso;
END$$

DROP PROCEDURE IF EXISTS sp_soporte_revocar$$
CREATE PROCEDURE sp_soporte_revocar(IN p_id_vehiculo INT)
BEGIN
  UPDATE permisos_soporte SET fecha_revocacion = NOW()
  WHERE id_vehiculo = p_id_vehiculo AND fecha_revocacion IS NULL;
  SELECT ROW_COUNT() AS revocados;
END$$

DROP PROCEDURE IF EXISTS sp_soporte_activo$$
CREATE PROCEDURE sp_soporte_activo(IN p_id_vehiculo INT)
BEGIN
  SELECT s.id_permiso, s.id_vehiculo, s.otorgado_por, s.fecha_inicio, s.fecha_expira
  FROM permisos_soporte s
  JOIN vehiculos v ON v.id_vehiculo = s.id_vehiculo AND v.id_propietario = s.otorgado_por
  WHERE s.id_vehiculo = p_id_vehiculo AND s.fecha_revocacion IS NULL AND s.fecha_expira > NOW()
  ORDER BY s.fecha_expira DESC LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS sp_demos_vehiculo$$
CREATE PROCEDURE sp_demos_vehiculo(IN p_id_vehiculo INT)
BEGIN
  SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.tipo, d.id_propietario, d.activo,
         d.fecha_creacion, d.fecha_modificacion,
         (SELECT COUNT(*) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS total_pasos,
         (SELECT COALESCE(SUM(dm.duracion_ms + dm.pausa_ms), 0) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS duracion_total_ms
  FROM demos d WHERE d.id_vehiculo = p_id_vehiculo
  ORDER BY d.tipo, d.nombre, d.id_demo;
END$$

DROP PROCEDURE IF EXISTS sp_demo_obtener$$
CREATE PROCEDURE sp_demo_obtener(IN p_id_demo INT)
BEGIN
  SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.tipo, d.id_propietario, d.activo,
         d.fecha_creacion, d.fecha_modificacion,
         (SELECT COUNT(*) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS total_pasos,
         (SELECT COALESCE(SUM(dm.duracion_ms + dm.pausa_ms), 0) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS duracion_total_ms
  FROM demos d WHERE d.id_demo = p_id_demo;
END$$

DROP PROCEDURE IF EXISTS sp_demo_crear_v2$$
CREATE PROCEDURE sp_demo_crear_v2(IN p_id_vehiculo INT, IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(255), IN p_tipo VARCHAR(10), IN p_id_propietario INT)
BEGIN
  INSERT INTO demos(id_vehiculo, nombre, descripcion, tipo, id_propietario)
  VALUES (p_id_vehiculo, p_nombre, NULLIF(p_descripcion, ''), p_tipo, p_id_propietario);
  SELECT LAST_INSERT_ID() AS id_demo;
END$$

DROP PROCEDURE IF EXISTS sp_demo_vaciar_pasos$$
CREATE PROCEDURE sp_demo_vaciar_pasos(IN p_id_demo INT)
BEGIN
  DELETE FROM demo_movimientos WHERE id_demo = p_id_demo;
END$$

DROP PROCEDURE IF EXISTS sp_invitado_iniciar$$
CREATE PROCEDURE sp_invitado_iniciar(IN p_codigo CHAR(32), IN p_id_vehiculo INT, IN p_segundos INT)
BEGIN
  INSERT INTO sesiones_invitado(codigo, id_vehiculo, reserva_vehiculo, fecha_expira)
  VALUES (p_codigo, p_id_vehiculo, p_id_vehiculo, NOW() + INTERVAL p_segundos SECOND);
  SELECT id_sesion, codigo, id_vehiculo, fecha_inicio, fecha_expira,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), fecha_expira), 0) AS segundos_restantes
  FROM sesiones_invitado WHERE id_sesion = LAST_INSERT_ID();
END$$

DROP PROCEDURE IF EXISTS sp_invitado_obtener$$
CREATE PROCEDURE sp_invitado_obtener(IN p_codigo CHAR(32))
BEGIN
  SELECT id_sesion, codigo, id_vehiculo, fecha_inicio, fecha_expira, fecha_fin, motivo_fin,
         (fecha_fin IS NULL AND fecha_expira > NOW()) AS vigente,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), fecha_expira), 0) AS segundos_restantes
  FROM sesiones_invitado WHERE codigo = p_codigo;
END$$

DROP PROCEDURE IF EXISTS sp_invitado_finalizar$$
CREATE PROCEDURE sp_invitado_finalizar(IN p_codigo CHAR(32), IN p_motivo VARCHAR(40))
BEGIN
  UPDATE sesiones_invitado SET fecha_fin = NOW(), motivo_fin = p_motivo, reserva_vehiculo = NULL
  WHERE codigo = p_codigo AND fecha_fin IS NULL;
  SELECT ROW_COUNT() AS finalizadas;
END$$

DROP PROCEDURE IF EXISTS sp_invitado_expirar$$
CREATE PROCEDURE sp_invitado_expirar()
BEGIN
  SELECT id_sesion, codigo, id_vehiculo FROM sesiones_invitado
  WHERE fecha_fin IS NULL AND fecha_expira <= NOW();
  UPDATE sesiones_invitado SET fecha_fin = NOW(), motivo_fin = 'EXPIRADA', reserva_vehiculo = NULL
  WHERE fecha_fin IS NULL AND fecha_expira <= NOW();
END$$

DROP PROCEDURE IF EXISTS sp_invitado_activa_vehiculo$$
CREATE PROCEDURE sp_invitado_activa_vehiculo(IN p_id_vehiculo INT)
BEGIN
  SELECT id_sesion, codigo, id_vehiculo, fecha_inicio, fecha_expira,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), fecha_expira), 0) AS segundos_restantes
  FROM sesiones_invitado
  WHERE id_vehiculo = p_id_vehiculo AND fecha_fin IS NULL AND fecha_expira > NOW()
  LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_modelos$$
CREATE PROCEDURE sp_catalogo_modelos()
BEGIN
  SELECT m.id_modelo, m.nombre, m.descripcion, m.imagen, m.microcontrolador,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_modelo = m.id_modelo AND v.estado_comercial = 'exhibicion' AND v.activo) AS unidades_exhibicion
  FROM modelos m WHERE m.activo ORDER BY m.nombre;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_exhibicion$$
CREATE PROCEDURE sp_catalogo_exhibicion()
BEGIN
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.id_modelo, m.nombre AS modelo,
         COALESCE(e.conectado, FALSE) AS conectado,
         (s.id_sesion IS NOT NULL) AS ocupada,
         IF(s.id_sesion IS NULL, NULL, GREATEST(TIMESTAMPDIFF(SECOND, NOW(), s.fecha_expira), 0)) AS segundos_para_liberarse
  FROM vehiculos v
  JOIN modelos m ON m.id_modelo = v.id_modelo
  LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
  LEFT JOIN sesiones_invitado s ON s.reserva_vehiculo = v.id_vehiculo AND s.fecha_expira > NOW()
  WHERE v.estado_comercial = 'exhibicion' AND v.activo AND m.activo
  ORDER BY v.id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_auditoria_registrar$$
CREATE PROCEDURE sp_auditoria_registrar(IN p_actor_tipo VARCHAR(10), IN p_id_actor INT, IN p_actor VARCHAR(60), IN p_accion VARCHAR(50), IN p_recurso VARCHAR(40), IN p_id_recurso VARCHAR(40), IN p_resultado VARCHAR(10), IN p_detalle VARCHAR(500))
BEGIN
  INSERT INTO auditoria(actor_tipo, id_actor, actor, accion, recurso, id_recurso, resultado, detalle)
  VALUES (p_actor_tipo, p_id_actor, p_actor, p_accion, p_recurso, p_id_recurso, p_resultado, p_detalle);
END$$

DROP PROCEDURE IF EXISTS sp_auditoria_listar$$
CREATE PROCEDURE sp_auditoria_listar(IN p_accion VARCHAR(50), IN p_actor_tipo VARCHAR(10), IN p_resultado VARCHAR(10), IN p_limite INT, IN p_desplazamiento INT)
BEGIN
  SELECT id_auditoria, fecha_hora, actor_tipo, id_actor, actor, accion, recurso, id_recurso, resultado, detalle,
         COUNT(*) OVER() AS total
  FROM auditoria
  WHERE (p_accion IS NULL OR p_accion = '' OR accion = p_accion)
    AND (p_actor_tipo IS NULL OR p_actor_tipo = '' OR actor_tipo = p_actor_tipo)
    AND (p_resultado IS NULL OR p_resultado = '' OR resultado = p_resultado)
  ORDER BY fecha_hora DESC, id_auditoria DESC
  LIMIT p_limite OFFSET p_desplazamiento;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_resumen$$
CREATE PROCEDURE sp_dashboard_resumen()
BEGIN
  SELECT
    (SELECT COUNT(*) FROM modelos WHERE activo) AS modelos_activos,
    (SELECT COUNT(*) FROM vehiculos WHERE estado_comercial <> 'inactivo') AS unidades_activas,
    (SELECT COUNT(*) FROM vehiculos WHERE estado_comercial = 'disponible') AS unidades_disponibles,
    (SELECT COUNT(*) FROM vehiculos WHERE estado_comercial = 'asignado') AS unidades_asignadas,
    (SELECT COUNT(*) FROM vehiculos WHERE estado_comercial = 'exhibicion') AS unidades_exhibicion,
    (SELECT COUNT(*) FROM vehiculos WHERE estado_comercial = 'inactivo') AS unidades_inactivas,
    (SELECT COUNT(*) FROM usuarios WHERE rol = 'usuario' AND activo) AS clientes_activos,
    (SELECT COUNT(*) FROM demos WHERE tipo = 'fabrica' AND activo) AS demos_fabrica,
    (SELECT COUNT(*) FROM demos WHERE tipo = 'privada' AND activo) AS demos_privadas,
    (SELECT COUNT(*) FROM sesiones_invitado WHERE fecha_fin IS NULL AND fecha_expira > NOW()) AS sesiones_invitado_activas,
    (SELECT COUNT(*) FROM estado_vehiculo WHERE conectado) AS dispositivos_conectados,
    (SELECT COUNT(*) FROM historial_comandos WHERE fecha_hora >= NOW() - INTERVAL 1 DAY) AS movimientos_24h;
END$$

DELIMITER ;

INSERT IGNORE INTO migraciones_esquema(version, descripcion)
VALUES ('V006', 'Procedimientos de administracion (44 nuevos)');

"""Bitácora de auditoría: quién, qué, sobre qué recurso y con qué resultado.

Nunca guarda contraseñas, tokens ni secretos. Un fallo al auditar se registra
en el log del servidor pero no interrumpe la operación del usuario.
"""
import logging

from fastapi.concurrency import run_in_threadpool

from app.core.seguridad import Actor
from app.db.procedimientos_admin import ProcedimientosAdmin

log = logging.getLogger("carrito_iot.auditoria")


class ServicioAuditoria:
    def __init__(self, sp: ProcedimientosAdmin):
        self._sp = sp

    def registrar(self, actor: Actor | None, accion: str, recurso: str | None = None, id_recurso=None,
                  resultado: str = "ok", detalle: str | None = None, actor_tipo: str | None = None,
                  actor_nombre: str | None = None) -> None:
        tipo = actor_tipo or (actor.tipo if actor else "anonimo")
        nombre = actor_nombre or (actor.usuario or actor.nombre if actor else None)
        try:
            self._sp.auditoria_registrar(
                tipo, actor.id if actor else None, (nombre or "")[:60] or None, accion[:50],
                recurso, None if id_recurso is None else str(id_recurso)[:40], resultado,
                (detalle or None) and detalle[:500],
            )
        except Exception as exc:  # la auditoría no debe tumbar la operación
            log.warning("No se pudo registrar auditoría %s: %s", accion, exc)

    async def aregistrar(self, *args, **kwargs) -> None:
        await run_in_threadpool(self.registrar, *args, **kwargs)

    def listar(self, accion, actor_tipo, resultado, limite: int, desplazamiento: int) -> dict:
        filas = self._sp.auditoria_listar(accion, actor_tipo, resultado, limite, desplazamiento)
        total = int(filas[0]["total"]) if filas else 0
        for f in filas:
            f.pop("total", None)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "elementos": filas}

"""Límite de solicitudes en memoria (ventana deslizante por clave).

Protege el login, la creación de sesiones de Invitado y el envío de comandos
contra ráfagas o fuerza bruta. Es por proceso: suficiente para un solo
servidor (EC2 con un Uvicorn).
"""
import time
from collections import deque

from app.core.errores import DemasiadasSolicitudes


class Limitador:
    def __init__(self, maximo: int, ventana_s: float, mensaje: str):
        self._max = maximo
        self._ventana = ventana_s
        self._mensaje = mensaje
        self._eventos: dict[str, deque] = {}

    def verificar(self, clave: str) -> None:
        ahora = time.monotonic()
        cola = self._eventos.setdefault(clave, deque())
        while cola and ahora - cola[0] > self._ventana:
            cola.popleft()
        if len(cola) >= self._max:
            raise DemasiadasSolicitudes(self._mensaje)
        cola.append(ahora)
        if len(self._eventos) > 5000:  # evita crecer sin límite
            for k in [k for k, c in self._eventos.items() if not c]:
                self._eventos.pop(k, None)

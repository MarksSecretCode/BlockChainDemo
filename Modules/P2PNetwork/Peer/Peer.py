"""
Representa a un peer conocido dentro de la red P2P.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional, Union

from Modules.P2PNetwork.Network.Connection import Connection


class Peer:
    def __init__(self, ip: str, puerto: int, peer_id: Optional[str] = None) -> None:
        self.peer_id = peer_id or str(uuid.uuid4())
        self.ip = ip
        self.puerto = puerto
        self.connection: Optional[Connection] = None
        self.ultimo_contacto: float = 0.0
        self.activo: bool = False

    @property
    def direccion(self) -> str:
        return f"{self.ip}:{self.puerto}"

    def marcar_como_conectado(self, connection: Optional[Connection] = None) -> None:
        self.connection = connection or self.connection
        self.activo = True
        self.ultimo_contacto = time.time()

    def marcar_como_desconectado(self) -> None:
        if self.connection:
            try:
                self.connection.cerrar()
            except Exception:
                pass
        self.connection = None
        self.activo = False

    def enviar_mensaje(self, mensaje: Union[bytes, str]) -> None:
        if not self.connection or not self.connection.esta_activa():
            raise ConnectionError(f"Peer {self.peer_id} ({self.direccion}) no está conectado.")

        if isinstance(mensaje, str):
            payload = mensaje.encode("utf-8")
        elif isinstance(mensaje, (bytes, bytearray)):
            payload = bytes(mensaje)
        else:
            raise TypeError("El mensaje debe ser bytes o str.")

        self.connection.enviar_datos(payload)


__all__ = ["Peer"]

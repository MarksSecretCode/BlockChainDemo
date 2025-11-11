"""
Abstracción de conexiones de red P2P basada en sockets TCP.

El objetivo es ofrecer una API mínima y segura para enviar/recibir datos sin
exponer directamente el descriptor de socket al resto del código.
"""

from __future__ import annotations

import socket
import threading
from typing import Tuple


class Connection:
    """Contenedor del socket subyacente junto con metadatos útiles."""

    def __init__(
        self,
        sock: socket.socket,
        direccion: Tuple[str, int],
        *,
        recv_buffer: int = 4096,
    ) -> None:
        self._socket = sock
        self._socket.setblocking(True)
        self._direccion = direccion
        self._lock = threading.Lock()
        self._activa = True
        self._recv_buffer = recv_buffer
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    @property
    def direccion_remota(self) -> Tuple[str, int]:
        return self._direccion

    def enviar_datos(self, payload: bytes) -> None:
        """Envía ``payload`` asegurando que todos los bytes salgan por el socket."""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("El parámetro 'payload' debe ser bytes o bytearray.")

        if not self._activa:
            raise ConnectionError("La conexión ya fue cerrada.")

        with self._lock:
            try:
                self._socket.sendall(payload)
            except OSError as exc:
                self._activa = False
                raise ConnectionError(f"Error enviando datos a {self._direccion}") from exc

    def recibir_datos(self) -> bytes:
        """
        Lee datos crudos desde el socket.

        Devuelve ``b''`` cuando el otro extremo cerró la conexión.
        """
        if not self._activa:
            return b""
        try:
            data = self._socket.recv(self._recv_buffer)
            if not data:
                self._activa = False
            return data
        except socket.timeout:
            return b""
        except OSError as exc:
            self._activa = False
            raise ConnectionError(f"Error recibiendo datos desde {self._direccion}") from exc

    def cerrar(self) -> None:
        """Cierra el socket de forma segura."""
        if not self._activa:
            return

        self._activa = False
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            self._socket.close()

    def esta_activa(self) -> bool:
        """Indica si la conexión continúa abierta."""
        return self._activa

    def __repr__(self) -> str:  # pragma: no cover - utilidad para depuración
        estado = "activa" if self._activa else "cerrada"
        return f"<Connection {self._direccion[0]}:{self._direccion[1]} ({estado})>"


def crear_conexion(sock: socket.socket, direccion: Tuple[str, int]) -> Connection:
    """Conveniencia para crear instancias desde ``Server``."""
    return Connection(sock, direccion)

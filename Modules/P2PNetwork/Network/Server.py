"""
Servidor TCP que escucha conexiones entrantes de peers en la red P2P.
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
from typing import Callable, Optional

from .Connection import Connection, crear_conexion

logger = logging.getLogger(__name__)


class P2PServer(threading.Thread):
    """Hilo encargado de aceptar conexiones entrantes."""

    def __init__(
        self,
        ip: str,
        puerto: int,
        *,
        backlog: int = 128,
        on_connection: Optional[Callable[[Connection], None]] = None,
    ) -> None:
        super().__init__(name=f"P2PServer-{ip}:{puerto}", daemon=True)
        self._ip = ip
        self._puerto = puerto
        self._backlog = backlog
        self._socket: Optional[socket.socket] = None
        self._stop_event = threading.Event()
        self._queue: "queue.Queue[Connection]" = queue.Queue()
        self._on_connection = on_connection

    def run(self) -> None:
        logger.info("Servidor P2P escuchando en %s:%s", self._ip, self._puerto)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv_socket:
            srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv_socket.bind((self._ip, self._puerto))
            srv_socket.listen(self._backlog)
            srv_socket.settimeout(1.0)
            self._socket = srv_socket

            while not self._stop_event.is_set():
                try:
                    client_socket, addr = srv_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                connection = crear_conexion(client_socket, addr)
                logger.debug("Nueva conexión entrante desde %s:%s", *addr)
                self._queue.put(connection)
                if self._on_connection:
                    try:
                        self._on_connection(connection)
                    except Exception:
                        logger.exception("Error al manejar la conexión entrante.")
        logger.info("Servidor P2P detenido.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                self._socket.close()

    def aceptar(self, timeout: Optional[float] = None) -> Optional[Connection]:
        """Devuelve la siguiente conexión aceptada o ``None`` si no hay disponible."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


_SERVER_INSTANCE: Optional[P2PServer] = None
_LOCK = threading.RLock()


def iniciar_servidor(
    ip: str,
    puerto: int,
    *,
    backlog: int = 128,
    on_connection: Optional[Callable[[Connection], None]] = None,
) -> P2PServer:
    """Inicializa el hilo del servidor global."""
    global _SERVER_INSTANCE
    with _LOCK:
        if _SERVER_INSTANCE and _SERVER_INSTANCE.is_alive():
            raise RuntimeError("El servidor ya está en ejecución.")

        server = P2PServer(ip, puerto, backlog=backlog, on_connection=on_connection)
        server.start()
        _SERVER_INSTANCE = server
        return server


def aceptar_nueva_conexion(timeout: Optional[float] = None) -> Optional[Connection]:
    """Obtiene la siguiente conexión aceptada (si existe)."""
    if not _SERVER_INSTANCE:
        raise RuntimeError("El servidor aún no ha sido iniciado.")
    return _SERVER_INSTANCE.aceptar(timeout)


def detener_servidor() -> None:
    """Detiene el servidor global."""
    global _SERVER_INSTANCE
    with _LOCK:
        if not _SERVER_INSTANCE:
            return
        _SERVER_INSTANCE.stop()
        _SERVER_INSTANCE.join(timeout=2.0)
        _SERVER_INSTANCE = None

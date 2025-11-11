"""
Cliente TCP básico utilizado por los nodos para iniciar conexiones salientes.
"""

from __future__ import annotations

import socket
import time
from typing import Optional

from .Connection import Connection


def conectar_a_peer(direccion_ip: str, puerto: int, *, timeout: float = 5.0) -> Connection:
    """
    Establece una conexión TCP con el peer objetivo.

    Se devuelve un objeto ``Connection`` listo para enviar/recibir datos.
    """
    try:
        sock = socket.create_connection((direccion_ip, puerto), timeout=timeout)
    except OSError as exc:
        raise ConnectionError(
            f"No se pudo conectar con el peer {direccion_ip}:{puerto}"
        ) from exc

    return Connection(sock, (direccion_ip, puerto))


def reintentar_conexion(peer, *, intentos: int = 3, espera: float = 2.0) -> Optional[Connection]:
    """
    Reintenta la conexión con un peer conocido aplicando un backoff lineal.

    Devuelve la conexión activa si tuvo éxito o ``None`` si falló.
    """
    from Modules.P2PNetwork.Peer.Peer import Peer  # importación tardía para evitar ciclos

    if not isinstance(peer, Peer):
        raise TypeError("El parámetro 'peer' debe ser una instancia de Peer.")

    for intento in range(1, intentos + 1):
        try:
            connection = conectar_a_peer(peer.ip, peer.puerto)
            peer.marcar_como_conectado(connection)
            return connection
        except ConnectionError:
            if intento == intentos:
                break
            time.sleep(espera)
    return None


def enviar_datos_a_peer(peer, payload: bytes) -> None:
    """
    Envía datos crudos a un peer conectado.

    Se valida que la conexión esté activa y se delega en ``Connection``.
    """
    from Modules.P2PNetwork.Peer.Peer import Peer  # importación tardía

    if not isinstance(peer, Peer):
        raise TypeError("El parámetro 'peer' debe ser una instancia de Peer.")

    if not peer.connection or not peer.connection.esta_activa():
        raise ConnectionError(f"El peer {peer.peer_id} no tiene una conexión activa.")

    peer.connection.enviar_datos(payload)

"""
Gestor centralizado de peers conocidos por el nodo.
"""

from __future__ import annotations

import random
import threading
from typing import Dict, List, Optional, Tuple

from .Peer import Peer
from Modules.P2PNetwork.Network.Connection import Connection


class PeerManager:
    def __init__(self) -> None:
        self._peers_by_id: Dict[str, Peer] = {}
        self._peers_by_address: Dict[Tuple[str, int], Peer] = {}
        self._peers_by_connection: Dict[Connection, Peer] = {}
        self._lock = threading.RLock()

    def agregar_peer(self, ip: str, puerto: int) -> Peer:
        """Obtiene un peer existente o crea uno nuevo para la dirección indicada."""
        clave = (ip, puerto)
        with self._lock:
            peer = self._peers_by_address.get(clave)
            if peer:
                return peer
            peer = Peer(ip, puerto)
            self._peers_by_id[peer.peer_id] = peer
            self._peers_by_address[clave] = peer
            return peer

    def obtener_peers_activos(self) -> List[Peer]:
        with self._lock:
            return [peer for peer in self._peers_by_id.values() if peer.activo]

    def obtener_peer_por_id(self, peer_id: str) -> Optional[Peer]:
        with self._lock:
            return self._peers_by_id.get(peer_id)

    def registrar_conexion(self, peer: Peer, connection: Connection) -> None:
        with self._lock:
            if peer.connection and peer.connection is not connection:
                self._peers_by_connection.pop(peer.connection, None)
            peer.marcar_como_conectado(connection)
            self._peers_by_connection[connection] = peer

    def obtener_peer_por_conexion(self, connection: Connection) -> Optional[Peer]:
        with self._lock:
            return self._peers_by_connection.get(connection)

    def eliminar_peer(self, peer: Peer) -> None:
        with self._lock:
            if peer.connection:
                self._peers_by_connection.pop(peer.connection, None)
            peer.marcar_como_desconectado()
            self._peers_by_id.pop(peer.peer_id, None)
            self._peers_by_address.pop((peer.ip, peer.puerto), None)

    def seleccionar_peers_para_broadcast(self, max_peers: Optional[int] = None) -> List[Peer]:
        activos = self.obtener_peers_activos()
        if max_peers is None or max_peers >= len(activos):
            return activos
        return random.sample(activos, max_peers)

    def todos_los_peers(self) -> List[Peer]:
        with self._lock:
            return list(self._peers_by_id.values())


__all__ = ["PeerManager"]

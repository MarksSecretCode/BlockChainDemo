"""
Orquestador del nodo P2P.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from Modules.Blockchain import Blockchain
from Modules.P2PNetwork.Network import Client, Server
from Modules.P2PNetwork.Network.Connection import Connection
from Modules.P2PNetwork.Peer.Peer import Peer
from Modules.P2PNetwork.Peer.PeerManager import PeerManager
from Modules.P2PNetwork.Protocol import Message as MessageUtils
from Modules.P2PNetwork.Protocol import MessageRouter
from Modules.P2PNetwork.Protocol import Broadcaster as BroadcasterModule

logger = logging.getLogger(__name__)


class Node:
    """
    Nodo P2P responsable de manejar conexiones entrantes/salientes y
    enrutar mensajes básicos del protocolo.
    """

    def __init__(self, config: Dict[str, any]) -> None:
        self.config = config or {}
        self.peer_manager = PeerManager()
        self.broadcaster = BroadcasterModule.configurar_broadcaster(self.peer_manager)
        self.blockchain = Blockchain(self.config)
        self.blockchain.attach_broadcaster(self.broadcaster)
        MessageRouter.configurar_router(self.peer_manager, self.broadcaster, self)

        self.ip = self.config.get("server_ip", "127.0.0.1")
        self.port = int(self.config.get("server_port", 5000))
        self.heartbeat_interval = float(self.config.get("heartbeat_interval", 15.0))
        self.api_enabled = bool(self.config.get("api_enabled", True))
        self.api_host = self.config.get("api_host", "127.0.0.1")
        self.api_port = int(self.config.get("api_port", self.port + 1000))

        self._server: Optional[Server.P2PServer] = None
        self._running = False
        self._stop_event = threading.Event()
        self._listener_threads: List[threading.Thread] = []
        self._buffers: Dict[str, bytes] = defaultdict(bytes)
        self._api_server = None

    # API pública --------------------------------------------------------- #
    def iniciar(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        self._server = Server.iniciar_servidor(
            self.ip, self.port, on_connection=self._manejar_conexion_entrante
        )
        logger.info("Nodo escuchando en %s:%s", self.ip, self.port)
        self.blockchain.start()

        bootnodes = self.config.get("bootnodes") or []
        if bootnodes:
            self.conectar_a_bootnodes(bootnodes)

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        if self.api_enabled:
            self._start_api_server()

    def detener(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._server:
            Server.detener_servidor()
            self._server = None

        for peer in self.peer_manager.todos_los_peers():
            peer.marcar_como_desconectado()
        self.blockchain.stop()
        self._stop_api_server()

    def conectar_a_bootnodes(self, lista_bootnodes: Iterable) -> None:
        for descriptor in lista_bootnodes:
            ip, port = self._parse_bootnode(descriptor)
            if not ip or port is None:
                continue
            if ip == self.ip and int(port) == self.port:
                continue
            peer = self.peer_manager.agregar_peer(ip, int(port))
            if peer.activo:
                continue
            try:
                connection = Client.conectar_a_peer(ip, int(port))
            except ConnectionError as exc:
                logger.warning("No se pudo conectar con bootnode %s:%s (%s)", ip, port, exc)
                continue
            self.peer_manager.registrar_conexion(peer, connection)
            self._inicializar_peer(peer)

    def enviar_ping_a_todos(self) -> None:
        mensaje = MessageUtils.serializar_mensaje(MessageUtils.crear_mensaje("PING"))
        for peer in self.peer_manager.obtener_peers_activos():
            try:
                peer.enviar_mensaje(mensaje)
            except Exception:
                logger.warning("No se pudo enviar ping a %s", peer.direccion)
                peer.marcar_como_desconectado()

    def recibir_mensaje_desde_red(self, connection: Connection, payload: bytes) -> None:
        peer = self.peer_manager.obtener_peer_por_conexion(connection)
        if not peer:
            logger.warning("Mensaje recibido de una conexión desconocida.")
            return
        try:
            mensaje = MessageUtils.parsear_mensaje(payload)
        except Exception as exc:
            logger.warning("No se pudo parsear mensaje desde %s: %s", peer.direccion, exc)
            return

        MessageRouter.procesar_mensaje(peer, mensaje)

    # Blockchain ---------------------------------------------------------- #
    def registrar_transaccion_remota(self, data: Dict) -> bool:
        agregado = self.blockchain.add_transaction_from_network(data)
        if agregado:
            logger.info("Transacción remota registrada (%s).", data.get("tx_id", "")[:10])
        return agregado

    def registrar_bloque_remoto(self, data: Dict) -> bool:
        resultado = self.blockchain.handle_remote_block(data)
        if resultado:
            logger.info("Bloque remoto aceptado.")
        return resultado

    def enviar_transaccion(self, destinatario: str, monto: float, metadata: Optional[Dict] = None):
        tx = self.blockchain.create_transaction(destinatario, monto, metadata)
        logger.info("Transacción local %s creada hacia %s.", tx.tx_id[:10], destinatario)
        return tx

    # Internos ------------------------------------------------------------ #
    def _parse_bootnode(self, descriptor) -> (Optional[str], Optional[int]):
        ip = None
        port = None
        if isinstance(descriptor, str):
            if ":" in descriptor:
                ip, port_str = descriptor.split(":", 1)
                if port_str.isdigit():
                    port = int(port_str)
        elif isinstance(descriptor, dict):
            ip = descriptor.get("ip") or descriptor.get("host")
            port = descriptor.get("port") or descriptor.get("puerto")
            port = int(port) if port is not None else None
        return ip, port

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval):
            self.enviar_ping_a_todos()

    def _manejar_conexion_entrante(self, connection: Connection) -> None:
        ip, port = connection.direccion_remota
        peer = self.peer_manager.agregar_peer(ip, int(port))
        self.peer_manager.registrar_conexion(peer, connection)
        self._inicializar_peer(peer)

    def _inicializar_peer(self, peer: Peer) -> None:
        self._spawn_listener(peer)
        self._enviar_peer_list(peer)
        self._enviar_ping(peer)

    def _spawn_listener(self, peer: Peer) -> None:
        hilo = threading.Thread(
            target=self._escuchar_peer, args=(peer,), name=f"PeerListener-{peer.peer_id}", daemon=True
        )
        self._listener_threads.append(hilo)
        hilo.start()

    def _escuchar_peer(self, peer: Peer) -> None:
        buffer = self._buffers[peer.peer_id]
        while self._running and peer.connection and peer.connection.esta_activa():
            try:
                data = peer.connection.recibir_datos()
            except ConnectionError:
                break
            if not data:
                continue
            buffer += data
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                raw = raw.strip()
                if not raw:
                    continue
                self.recibir_mensaje_desde_red(peer.connection, raw)
        peer.marcar_como_desconectado()
        self._buffers[peer.peer_id] = buffer

    def _enviar_peer_list(self, peer: Peer) -> None:
        peers = [
            {"ip": p.ip, "port": p.puerto}
            for p in self.peer_manager.todos_los_peers()
            if p.peer_id != peer.peer_id
        ]
        mensaje = MessageUtils.crear_mensaje("PEER_LIST", {"peers": peers})
        try:
            peer.enviar_mensaje(MessageUtils.serializar_mensaje(mensaje))
        except Exception:
            peer.marcar_como_desconectado()

    # API ---------------------------------------------------------------- #
    def _start_api_server(self) -> None:
        if self._api_server:
            return
        try:
            from Modules.API import APIServer
        except RuntimeError as exc:
            logger.error("No fue posible iniciar la API REST: %s", exc)
            return
        except Exception as exc:  # pragma: no cover
            logger.exception("Error inesperado al cargar la API REST: %s", exc)
            return

        try:
            self._api_server = APIServer(self, host=self.api_host, port=self.api_port)
            self._api_server.start()
        except OSError as exc:
            logger.error("No se pudo iniciar la API REST en %s:%s (%s)", self.api_host, self.api_port, exc)
            self._api_server = None

    def _stop_api_server(self) -> None:
        if self._api_server:
            self._api_server.stop()
            self._api_server = None

    def _enviar_ping(self, peer: Peer) -> None:
        try:
            peer.enviar_mensaje(
                MessageUtils.serializar_mensaje(MessageUtils.crear_mensaje("PING"))
            )
        except Exception:
            peer.marcar_como_desconectado()


__all__ = ["Node"]

"""
Enrutamiento de mensajes según su tipo dentro del protocolo P2P.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from Modules.P2PNetwork.Protocol.Message import crear_mensaje, serializar_mensaje
from Modules.P2PNetwork.Protocol.Broadcaster import Broadcaster
from Modules.P2PNetwork.Peer.Peer import Peer
from Modules.P2PNetwork.Peer.PeerManager import PeerManager

logger = logging.getLogger(__name__)

_PEER_MANAGER: Optional[PeerManager] = None
_BROADCASTER: Optional[Broadcaster] = None
_NODE = None


def configurar_router(peer_manager: PeerManager, broadcaster: Broadcaster, node) -> None:
    global _PEER_MANAGER, _BROADCASTER, _NODE
    _PEER_MANAGER = peer_manager
    _BROADCASTER = broadcaster
    _NODE = node


def procesar_mensaje(peer: Peer, mensaje: Dict[str, Any]) -> None:
    tipo = (mensaje.get("type") or "").upper()
    mensaje_id = mensaje.get("id")
    if mensaje_id and _BROADCASTER:
        _BROADCASTER.registrar_mensaje_visto(mensaje_id)
    handlers = {
        "PING": manejar_ping,
        "PONG": manejar_pong,
        "NEW_TX": manejar_new_tx,
        "PEER_LIST": manejar_peer_list,
        "NEW_BLOCK": manejar_new_block,
    }
    handler = handlers.get(tipo)
    if not handler:
        logger.debug("Tipo de mensaje no soportado: %s", tipo)
        return
    handler(peer, mensaje)


def manejar_ping(peer: Peer, mensaje: Dict[str, Any]) -> None:
    peer.ultimo_contacto = time.time()
    respuesta = crear_mensaje("PONG", {"echo": mensaje.get("data")})
    peer.enviar_mensaje(serializar_mensaje(respuesta))


def manejar_pong(peer: Peer, mensaje: Dict[str, Any]) -> None:
    peer.ultimo_contacto = time.time()
    logger.debug("PONG recibido desde %s", peer.direccion)


def manejar_new_tx(peer: Peer, mensaje: Dict[str, Any]) -> None:
    if not _NODE:
        logger.warning("No hay nodo configurado; se omite NEW_TX.")
        return
    data = mensaje.get("data") or {}
    _NODE.registrar_transaccion_remota(data)


def manejar_peer_list(peer: Peer, mensaje: Dict[str, Any]) -> None:
    if not _NODE:
        logger.warning("No hay nodo configurado para manejar PEER_LIST.")
        return
    lista = mensaje.get("data", {}).get("peers", [])
    nuevos = []
    for item in lista:
        ip = None
        puerto = None
        if isinstance(item, str):
            if ":" in item:
                ip, puerto_str = item.split(":", 1)
                if puerto_str.isdigit():
                    puerto = int(puerto_str)
        elif isinstance(item, dict):
            ip = item.get("ip")
            puerto = item.get("puerto") or item.get("port")
        if not ip or puerto is None:
            continue
        nuevos.append({"ip": ip, "port": int(puerto)})

    if nuevos:
        logger.debug("Recibida lista de %s peers desde %s", len(nuevos), peer.direccion)
        _NODE.conectar_a_bootnodes(nuevos)


def manejar_new_block(peer: Peer, mensaje: Dict[str, Any]) -> None:
    if not _NODE:
        logger.warning("No hay nodo configurado para manejar NEW_BLOCK.")
        return
    data = mensaje.get("data") or {}
    _NODE.registrar_bloque_remoto(data)

"""
Encargado de distribuir mensajes a todos los peers conectados evitando loops.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Optional

from Modules.P2PNetwork.Peer.Peer import Peer
from Modules.P2PNetwork.Protocol.Message import serializar_mensaje
from Modules.P2PNetwork.Peer.PeerManager import PeerManager


class Broadcaster:
    def __init__(self, peer_manager: PeerManager, *, ventana_cache: int = 1000) -> None:
        self._peer_manager = peer_manager
        self._ventana_cache = ventana_cache
        self._mensajes_vistos: Dict[str, float] = {}
        self._lock = threading.RLock()

    def broadcast_mensaje(self, mensaje, peer_origen: Optional[Peer] = None) -> int:
        """
        Envía el mensaje a todos los peers activos exceptuando el origen.
        Devuelve la cantidad de peers alcanzados.
        """
        mensaje_id = mensaje.get("id")
        if mensaje_id and not self.es_mensaje_nuevo(mensaje_id):
            return 0

        if mensaje_id:
            self.registrar_mensaje_visto(mensaje_id)

        payload = serializar_mensaje(mensaje)
        peers = self._peer_manager.seleccionar_peers_para_broadcast()
        enviados = 0
        for peer in peers:
            if peer_origen and peer.peer_id == peer_origen.peer_id:
                continue
            try:
                peer.enviar_mensaje(payload)
                enviados += 1
            except Exception:
                peer.marcar_como_desconectado()
        return enviados

    def registrar_mensaje_visto(self, mensaje_id: str) -> None:
        if not mensaje_id:
            return
        with self._lock:
            self._mensajes_vistos[mensaje_id] = time.time()
            if len(self._mensajes_vistos) > self._ventana_cache:
                # Eliminar los mensajes más antiguos para evitar crecer indefinidamente.
                ordenados = sorted(
                    self._mensajes_vistos.items(), key=lambda item: item[1]
                )
                for clave, _ in ordenados[: len(ordenados) - self._ventana_cache]:
                    self._mensajes_vistos.pop(clave, None)

    def es_mensaje_nuevo(self, mensaje_id: str) -> bool:
        if not mensaje_id:
            return True
        with self._lock:
            return mensaje_id not in self._mensajes_vistos

    def orchestration(self) -> Dict[str, int]:
        """
        Expone métricas simples para la capa de orquestación.
        """
        with self._lock:
            return {
                "mensajes_cacheados": len(self._mensajes_vistos),
                "ventana_cache": self._ventana_cache,
            }


_BROADCASTER: Optional[Broadcaster] = None


def configurar_broadcaster(peer_manager: PeerManager) -> Broadcaster:
    global _BROADCASTER
    _BROADCASTER = Broadcaster(peer_manager)
    return _BROADCASTER


def broadcast_mensaje(mensaje, peer_origen: Optional[Peer] = None) -> int:
    if not _BROADCASTER:
        raise RuntimeError("El broadcaster aún no ha sido configurado.")
    return _BROADCASTER.broadcast_mensaje(mensaje, peer_origen)


def registrar_mensaje_visto(mensaje_id: str) -> None:
    if not _BROADCASTER:
        raise RuntimeError("El broadcaster aún no ha sido configurado.")
    _BROADCASTER.registrar_mensaje_visto(mensaje_id)


def es_mensaje_nuevo(mensaje_id: str) -> bool:
    if not _BROADCASTER:
        raise RuntimeError("El broadcaster aún no ha sido configurado.")
    return _BROADCASTER.es_mensaje_nuevo(mensaje_id)


def orchestration():
    if not _BROADCASTER:
        return {"mensajes_cacheados": 0, "ventana_cache": 0}
    return _BROADCASTER.orchestration()

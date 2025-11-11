"""
Operaciones básicas sobre mensajes del protocolo P2P.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict


def crear_mensaje(tipo: str, datos: Any = None) -> Dict[str, Any]:
    if not tipo:
        raise ValueError("El tipo de mensaje es obligatorio.")
    return {
        "id": str(uuid.uuid4()),
        "type": tipo.upper(),
        "timestamp": time.time(),
        "data": datos or {},
    }


def serializar_mensaje(mensaje: Dict[str, Any]) -> bytes:
    """
    Serializa el mensaje a JSON y añade un salto de línea para delimitar frames.
    """
    payload = json.dumps(mensaje, separators=(",", ":"))
    return f"{payload}\n".encode("utf-8")


def parsear_mensaje(payload: bytes) -> Dict[str, Any]:
    """Convierte bytes (JSON) en un dict validado."""
    if isinstance(payload, bytearray):
        payload = bytes(payload)

    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("El payload debe ser bytes.")

    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("El mensaje recibido no es un objeto JSON válido.")
    return data

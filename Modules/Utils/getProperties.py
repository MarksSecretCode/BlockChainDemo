"""
Utilidades para leer parámetros de configuración desde ``parameters.yml``.

Se mantiene un caché en memoria para evitar lecturas repetidas del archivo
en disco, ya que varios componentes de la red consultan los mismos valores.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CACHE_LOCK = threading.RLock()


def _config_path() -> Path:
    """Devuelve la ruta absoluta al archivo ``parameters.yml``."""
    return Path(__file__).resolve().parents[2] / "parameters.yml"


def _load_config() -> Dict[str, Any]:
    """Carga el archivo de configuración en memoria (si es necesario)."""
    global _CONFIG_CACHE

    with _CACHE_LOCK:
        if _CONFIG_CACHE is None:
            config_path = _config_path()
            if not config_path.exists():
                raise FileNotFoundError(
                    f"No se encontró el archivo de configuración en {config_path}"
                )

            with config_path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}

            if not isinstance(data, dict):
                raise ValueError(
                    f"El archivo de configuración debe contener un objeto tipo mapa. "
                    f"Contenido inválido: {data}"
                )

            _CONFIG_CACHE = data
        return dict(_CONFIG_CACHE)


def refresh_cache() -> Dict[str, Any]:
    """Forza la recarga del archivo de configuración."""
    global _CONFIG_CACHE
    with _CACHE_LOCK:
        _CONFIG_CACHE = None
    return _load_config()


def get_properties_from_yaml(property_name: Optional[str] = None, default: Any = None) -> Any:
    """
    Obtiene el valor asociado a ``property_name`` desde ``parameters.yml``.

    Si no se especifica ``property_name`` se devuelve un dict con todos los
    valores disponibles. Cuando la clave no existe se regresa ``default``.
    """
    properties = _load_config()
    if property_name is None:
        return properties
    return properties.get(property_name, default)

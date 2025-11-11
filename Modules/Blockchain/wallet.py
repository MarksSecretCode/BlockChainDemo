from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _derive_private_key(seed: Optional[str]) -> str:
    if seed is None:
        return secrets.token_hex(32)
    return hashlib.sha256(seed.encode()).hexdigest()


@dataclass
class Wallet:
    label: str
    private_key: str = field(repr=False)
    created_at: float = field(default_factory=lambda: time.time())
    _nonce: int = 0

    def __post_init__(self) -> None:
        self.public_key = hashlib.sha256(self.private_key.encode()).hexdigest()
        self.address = hashlib.sha256(self.public_key.encode()).hexdigest()[:40]

    def sign(self, payload: str) -> str:
        """
        Firma didáctica basada únicamente en la clave pública.
        (No provee seguridad criptográfica real, pero facilita la verificación).
        """
        return hashlib.sha256((self.public_key + payload).encode()).hexdigest()

    def next_nonce(self) -> int:
        self._nonce += 1
        return self._nonce

    def sync_nonce(self, nonce: int) -> None:
        self._nonce = max(self._nonce, nonce)

    def to_dict(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "address": self.address,
            "public_key": self.public_key,
            "created_at": self.created_at,
        }


class WalletManager:
    def __init__(self) -> None:
        self._wallets: Dict[str, Wallet] = {}
        self._lock = threading.RLock()

    def create_wallet(self, label: Optional[str] = None, seed: Optional[str] = None) -> Wallet:
        private_key = _derive_private_key(seed)
        wallet = Wallet(label=label or "wallet", private_key=private_key)
        with self._lock:
            counter = 1
            base_label = wallet.label
            while wallet.address in self._wallets:
                wallet.label = f"{base_label}-{counter}"
                counter += 1
            self._wallets[wallet.address] = wallet
        return wallet

    def import_wallet(self, private_key: str, label: Optional[str] = None) -> Wallet:
        wallet = Wallet(label=label or "wallet", private_key=private_key)
        with self._lock:
            self._wallets[wallet.address] = wallet
        return wallet

    def get_wallet(self, address: str) -> Optional[Wallet]:
        with self._lock:
            return self._wallets.get(address)

    def list_wallets(self) -> List[Wallet]:
        with self._lock:
            return list(self._wallets.values())

    def sync_nonce(self, address: str, nonce: int) -> None:
        wallet = self.get_wallet(address)
        if wallet:
            wallet.sync_nonce(nonce)


__all__ = ["Wallet", "WalletManager"]

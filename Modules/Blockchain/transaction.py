from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Transaction:
    sender_address: str
    recipient_address: str
    amount: float
    timestamp: float = field(default_factory=lambda: time.time())
    nonce: int = 0
    sender_public_key: str = ""
    signature: str = ""
    metadata: Optional[Dict[str, Any]] = None
    tx_id: str = ""

    def payload(self) -> str:
        """Contenido canónico empleado para firmas e ids."""
        body = {
            "sender_address": self.sender_address,
            "recipient_address": self.recipient_address,
            "amount": float(self.amount),
            "timestamp": float(self.timestamp),
            "nonce": int(self.nonce),
            "metadata": self.metadata or {},
        }
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    def compute_id(self) -> str:
        base = f"{self.payload()}:{self.signature}"
        return hashlib.sha256(base.encode()).hexdigest()

    def ensure_id(self) -> str:
        if not self.tx_id:
            self.tx_id = self.compute_id()
        return self.tx_id

    def to_dict(self) -> Dict[str, Any]:
        self.ensure_id()
        return {
            "tx_id": self.tx_id,
            "sender_address": self.sender_address,
            "recipient_address": self.recipient_address,
            "amount": float(self.amount),
            "timestamp": float(self.timestamp),
            "nonce": int(self.nonce),
            "sender_public_key": self.sender_public_key,
            "signature": self.signature,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            sender_address=data["sender_address"],
            recipient_address=data["recipient_address"],
            amount=float(data["amount"]),
            timestamp=float(data.get("timestamp", time.time())),
            nonce=int(data.get("nonce", 0)),
            sender_public_key=data.get("sender_public_key", ""),
            signature=data.get("signature", ""),
            metadata=data.get("metadata"),
            tx_id=data.get("tx_id", ""),
        )


__all__ = ["Transaction"]

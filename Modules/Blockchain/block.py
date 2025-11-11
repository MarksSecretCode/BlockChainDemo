from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .transaction import Transaction


@dataclass
class Block:
    index: int
    previous_hash: str
    transactions: List[Transaction]
    miner_address: str
    timestamp: float = field(default_factory=lambda: time.time())
    block_hash: str = ""
    proof_nonce: int = 0
    proof_hash: str = ""

    def payload(self) -> str:
        body = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "miner_address": self.miner_address,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    def compute_block_hash(self) -> str:
        return hashlib.sha256(self.payload().encode()).hexdigest()

    @staticmethod
    def compute_proof_hash(block_hash: str, nonce: int) -> str:
        raw = f"{block_hash}:{nonce}".encode()
        return hashlib.sha256(raw).hexdigest()

    def sum_hashes_binary(self) -> str:
        try:
            total = int(self.block_hash, 16) + int(self.proof_hash, 16)
        except ValueError:
            return ""
        return bin(total)[2:]

    def validate_proof(self, leading_ones: int) -> bool:
        expected_block_hash = self.compute_block_hash()
        if self.block_hash != expected_block_hash:
            return False
        expected_proof = self.compute_proof_hash(self.block_hash, self.proof_nonce)
        if self.proof_hash != expected_proof:
            return False
        binary_sum = self.sum_hashes_binary()
        return binary_sum.startswith("1" * leading_ones)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "miner_address": self.miner_address,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "block_hash": self.block_hash,
            "proof_nonce": self.proof_nonce,
            "proof_hash": self.proof_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        transactions = [Transaction.from_dict(item) for item in data.get("transactions", [])]
        return cls(
            index=int(data["index"]),
            previous_hash=data["previous_hash"],
            transactions=transactions,
            miner_address=data.get("miner_address", ""),
            timestamp=float(data.get("timestamp", time.time())),
            block_hash=data.get("block_hash", ""),
            proof_nonce=int(data.get("proof_nonce", 0)),
            proof_hash=data.get("proof_hash", ""),
        )


__all__ = ["Block"]

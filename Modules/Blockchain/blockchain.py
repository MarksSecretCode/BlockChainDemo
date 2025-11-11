from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from Modules.P2PNetwork.Protocol import Message as MessageUtils
from Modules.P2PNetwork.Protocol import Broadcaster as BroadcasterModule

from .block import Block
from .transaction import Transaction
from .wallet import Wallet, WalletManager

logger = logging.getLogger(__name__)

SYSTEM_ADDRESS = "NETWORK"


class Blockchain:
    """
    Cadena de bloques simplificada pensada para una demo académica.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.wallet_manager = WalletManager()
        self.leading_ones = int(self.config.get("mining_leading_ones", 10))
        self.block_reward = float(self.config.get("block_reward", 25.0))
        self.max_txs_per_block = int(self.config.get("max_txs_per_block", 10))
        self.mining_enabled = bool(self.config.get("mining_enabled", True))
        self.miner_wallet = self.wallet_manager.create_wallet(
            label=self.config.get("wallet_label", "miner"),
            seed=self.config.get("wallet_seed"),
        )

        self._balances: Dict[str, float] = {}
        self._confirmed_nonce: Dict[str, int] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._miner_thread: Optional[threading.Thread] = None

        self.chain: List[Block] = []
        self.mempool: Dict[str, Transaction] = {}
        self.broadcaster: Optional[BroadcasterModule.Broadcaster] = None

        self._create_genesis_block()

    # ------------------------------------------------------------------ #
    # Inicialización y control del minero
    def attach_broadcaster(self, broadcaster: BroadcasterModule.Broadcaster) -> None:
        self.broadcaster = broadcaster

    def start(self) -> None:
        if self._miner_thread and self._miner_thread.is_alive():
            return
        self._stop_event.clear()
        self._miner_thread = threading.Thread(target=self._miner_loop, name="MinerThread", daemon=True)
        self._miner_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._miner_thread:
            self._miner_thread.join(timeout=2.0)

    # ------------------------------------------------------------------ #
    # Wallet helpers
    def default_wallet(self) -> Wallet:
        return self.miner_wallet

    def create_wallet(self, label: Optional[str] = None, seed: Optional[str] = None) -> Wallet:
        wallet = self.wallet_manager.create_wallet(label=label, seed=seed)
        logger.info("Nueva wallet creada %s (%s)", wallet.label, wallet.address)
        return wallet

    # ------------------------------------------------------------------ #
    # Transacciones
    def create_transaction(
        self, recipient_address: str, amount: float, metadata: Optional[Dict] = None, sender: Optional[Wallet] = None
    ) -> Transaction:
        wallet = sender or self.miner_wallet
        tx = Transaction(
            sender_address=wallet.address,
            recipient_address=recipient_address,
            amount=float(amount),
            nonce=wallet.next_nonce(),
            sender_public_key=wallet.public_key,
            metadata=metadata or {},
        )
        tx.signature = wallet.sign(tx.payload())
        tx.ensure_id()

        if not self.add_transaction(tx, propagate=True):
            raise ValueError("La transacción no pudo añadirse al mempool.")
        return tx

    def add_transaction(self, transaction: Transaction, *, propagate: bool = False) -> bool:
        """Valida y añade una transacción localmente."""
        transaction.ensure_id()
        with self._lock:
            if transaction.tx_id in self.mempool:
                return False
            if not self._is_transaction_valid(transaction):
                return False
            self.mempool[transaction.tx_id] = transaction
        if propagate:
            self._broadcast_transaction(transaction)
        logger.info("Transacción %s añadida al mempool.", transaction.tx_id[:10])
        return True

    def add_transaction_from_network(self, data: Dict) -> bool:
        try:
            transaction = Transaction.from_dict(data)
        except KeyError:
            return False
        return self.add_transaction(transaction, propagate=False)

    def _broadcast_transaction(self, transaction: Transaction) -> None:
        if not self.broadcaster:
            return
        mensaje = MessageUtils.crear_mensaje("NEW_TX", transaction.to_dict())
        self.broadcaster.broadcast_mensaje(mensaje)

    def _pending_spend(self, address: str) -> float:
        return sum(tx.amount for tx in self.mempool.values() if tx.sender_address == address)

    def _is_transaction_valid(self, tx: Transaction) -> bool:
        if tx.amount <= 0:
            return False
        if tx.sender_address == tx.recipient_address:
            return False

        if tx.sender_address != SYSTEM_ADDRESS:
            derived = hashlib.sha256(tx.sender_public_key.encode()).hexdigest()[:40]
            if derived != tx.sender_address:
                return False
            expected_sig = hashlib.sha256((tx.sender_public_key + tx.payload()).encode()).hexdigest()
            if expected_sig != tx.signature:
                return False
            available = self.get_balance(tx.sender_address) - self._pending_spend(tx.sender_address)
            if tx.amount > available + 1e-9:
                return False
            last_nonce = self._confirmed_nonce.get(tx.sender_address, 0)
            if tx.nonce <= last_nonce:
                return False
        return True

    # ------------------------------------------------------------------ #
    # Bloques y cadena
    def _create_genesis_block(self) -> None:
        reward = Transaction(
            sender_address=SYSTEM_ADDRESS,
            recipient_address=self.miner_wallet.address,
            amount=float(self.config.get("initial_balance", 100.0)),
            sender_public_key=SYSTEM_ADDRESS,
            signature="GENESIS",
            nonce=0,
            metadata={"note": "genesis"},
        )
        reward.ensure_id()
        genesis = Block(
            index=0,
            previous_hash="0" * 64,
            transactions=[reward],
            miner_address=self.miner_wallet.address,
        )
        self._seal_block(genesis)
        self.chain.append(genesis)
        self._apply_block(genesis)
        logger.info("Bloque génesis creado con recompensa inicial.")

    def _seal_block(self, block: Block) -> None:
        block.block_hash = block.compute_block_hash()
        nonce = 0
        while True:
            proof = Block.compute_proof_hash(block.block_hash, nonce)
            binary_sum = bin(int(block.block_hash, 16) + int(proof, 16))[2:]
            if binary_sum.startswith("1" * self.leading_ones):
                block.proof_nonce = nonce
                block.proof_hash = proof
                return
            nonce += 1

    def _miner_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self.mining_enabled:
                time.sleep(1)
                continue
            if not self.mempool:
                time.sleep(0.5)
                continue
            try:
                self._mine_next_block()
            except Exception:  # pragma: no cover
                logger.exception("Error durante el minado.")

    def _mine_next_block(self) -> None:
        with self._lock:
            if not self.mempool:
                return
            txs = list(self.mempool.values())[: self.max_txs_per_block]
            last_block = self.chain[-1]

        reward_tx = Transaction(
            sender_address=SYSTEM_ADDRESS,
            recipient_address=self.miner_wallet.address,
            amount=self.block_reward,
            sender_public_key=SYSTEM_ADDRESS,
            signature="REWARD",
            nonce=0,
            metadata={"miner": self.miner_wallet.address},
        )
        reward_tx.ensure_id()

        block = Block(
            index=len(self.chain),
            previous_hash=last_block.block_hash,
            transactions=txs + [reward_tx],
            miner_address=self.miner_wallet.address,
        )
        logger.info("Comenzando minado del bloque %s con %s transacciones.", block.index, len(block.transactions))
        self._seal_block(block)
        logger.info("Bloque %s minado. Proof nonce=%s", block.index, block.proof_nonce)

        self._append_block(block, broadcast=True)

    def _append_block(self, block: Block, *, broadcast: bool) -> None:
        with self._lock:
            if block.index != len(self.chain):
                return
            if self.chain and block.previous_hash != self.chain[-1].block_hash:
                return
            self.chain.append(block)
            self._apply_block(block)
            for tx in block.transactions:
                self.mempool.pop(tx.tx_id, None)

        if broadcast:
            self._broadcast_block(block)

    def _apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            if tx.sender_address != SYSTEM_ADDRESS:
                self._balances[tx.sender_address] = self._balances.get(tx.sender_address, 0.0) - tx.amount
                self._confirmed_nonce[tx.sender_address] = max(
                    self._confirmed_nonce.get(tx.sender_address, 0), tx.nonce
                )
                self.wallet_manager.sync_nonce(tx.sender_address, tx.nonce)
            self._balances[tx.recipient_address] = self._balances.get(tx.recipient_address, 0.0) + tx.amount

    def _broadcast_block(self, block: Block) -> None:
        if not self.broadcaster:
            return
        mensaje = MessageUtils.crear_mensaje("NEW_BLOCK", block.to_dict())
        self.broadcaster.broadcast_mensaje(mensaje)

    def handle_remote_block(self, data: Dict) -> bool:
        try:
            block = Block.from_dict(data)
        except Exception:
            return False

        with self._lock:
            if block.index != len(self.chain):
                logger.warning("Bloque fuera de secuencia (idx %s).", block.index)
                return False
            if block.previous_hash != self.chain[-1].block_hash:
                logger.warning("Hash previo inválido para bloque %s.", block.index)
                return False
            if not block.validate_proof(self.leading_ones):
                logger.warning("Proof inválido en bloque %s.", block.index)
                return False
            if not self._validate_block_transactions(block.transactions):
                logger.warning("Transacciones inválidas en bloque %s.", block.index)
                return False

            self.chain.append(block)
            self._apply_block(block)
            for tx in block.transactions:
                self.mempool.pop(tx.tx_id, None)
        logger.info("Bloque %s aceptado desde la red.", block.index)
        return True

    def _validate_block_transactions(self, transactions: Iterable[Transaction]) -> bool:
        temp_balances = self._balances.copy()
        temp_nonce = self._confirmed_nonce.copy()
        for tx in transactions:
            tx.ensure_id()
            if not self._basic_tx_checks(tx):
                return False
            if tx.sender_address != SYSTEM_ADDRESS:
                if temp_balances.get(tx.sender_address, 0.0) < tx.amount:
                    return False
                temp_balances[tx.sender_address] = temp_balances.get(tx.sender_address, 0.0) - tx.amount
                temp_nonce[tx.sender_address] = max(temp_nonce.get(tx.sender_address, 0), tx.nonce)
            temp_balances[tx.recipient_address] = temp_balances.get(tx.recipient_address, 0.0) + tx.amount
        return True

    def _basic_tx_checks(self, tx: Transaction) -> bool:
        if tx.amount <= 0:
            return False
        if tx.sender_address == tx.recipient_address:
            return False
        if tx.sender_address != SYSTEM_ADDRESS:
            derived = hashlib.sha256(tx.sender_public_key.encode()).hexdigest()[:40]
            if derived != tx.sender_address:
                return False
            expected_sig = hashlib.sha256((tx.sender_public_key + tx.payload()).encode()).hexdigest()
            if expected_sig != tx.signature:
                return False
        return True

    # ------------------------------------------------------------------ #
    def get_balance(self, address: str) -> float:
        return round(self._balances.get(address, 0.0), 8)

    def pending_transactions(self) -> List[Dict]:
        with self._lock:
            return [tx.to_dict() for tx in self.mempool.values()]

    def chain_snapshot(self) -> List[Dict]:
        with self._lock:
            return [block.to_dict() for block in self.chain]


__all__ = ["Blockchain", "SYSTEM_ADDRESS"]

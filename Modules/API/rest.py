"""
Servidor REST ligero para interactuar con el nodo y la cadena de bloques.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from flask import Flask, jsonify, render_template, request
    from werkzeug.serving import make_server
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Flask no está instalado. Ejecuta `pip install flask` para habilitar la API REST."
    ) from exc


logger = logging.getLogger(__name__)


class APIServer:
    """
    Expone endpoints para consultar la cadena, el mempool y emitir transacciones.
    """

    def __init__(self, node, host: str = "127.0.0.1", port: int = 8080) -> None:
        from Modules.P2PNetwork.Orchestration.Node import Node  # importación tardía

        if not isinstance(node, Node):
            raise TypeError("El servidor API requiere una instancia de Node.")

        self.node = node
        self.host = host
        self.port = port
        base_path = Path(__file__).resolve().parent
        self._app = Flask(
            __name__,
            template_folder=str(base_path / "templates"),
            static_folder=str(base_path / "static"),
        )
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._register_routes()

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        if self._server:
            return
        logger.info("API REST escuchando en http://%s:%s", self.host, self.port)
        self._server = make_server(self.host, self.port, self._app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._server:
            return
        logger.info("Deteniendo API REST...")
        self._server.shutdown()
        self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ------------------------------------------------------------------ #
    def _register_routes(self) -> None:
        app = self._app

        @app.get("/")
        def index():
            return render_template(
                "index.html",
                api_host=self.host,
                api_port=self.port,
                node_ip=self.node.ip,
                node_port=self.node.port,
            )

        @app.get("/health")
        def health():
            blockchain = self.node.blockchain
            peers_activos = len(self.node.peer_manager.obtener_peers_activos())
            peers_total = len(self.node.peer_manager.todos_los_peers())
            return jsonify(
                {
                    "status": "ok",
                    "node": {"ip": self.node.ip, "port": self.node.port},
                    "chain_length": len(blockchain.chain_snapshot()),
                    "mempool_size": len(blockchain.pending_transactions()),
                    "peers": {"activos": peers_activos, "total": peers_total},
                }
            )

        @app.get("/chain")
        def chain():
            limit = request.args.get("limit", type=int)
            snapshot = self.node.blockchain.chain_snapshot()
            if limit is not None and limit >= 0:
                snapshot = snapshot[-limit:] if limit > 0 else []
            return jsonify({"length": len(snapshot), "blocks": snapshot})

        @app.get("/mempool")
        def mempool():
            pending = self.node.blockchain.pending_transactions()
            return jsonify({"count": len(pending), "transactions": pending})

        @app.get("/peers")
        def peers():
            lista = [
                {
                    "peer_id": peer.peer_id,
                    "address": peer.direccion,
                    "activo": peer.activo,
                    "ultimo_contacto": peer.ultimo_contacto,
                }
                for peer in self.node.peer_manager.todos_los_peers()
            ]
            return jsonify({"count": len(lista), "peers": lista})

        @app.get("/wallets")
        def list_wallets():
            wallets = [
                {
                    **wallet.to_dict(),
                    "balance": self.node.blockchain.get_balance(wallet.address),
                }
                for wallet in self.node.blockchain.wallet_manager.list_wallets()
            ]
            return jsonify({"wallets": wallets})

        @app.get("/wallets/<address>")
        def wallet_detail(address: str):
            wallet = self.node.blockchain.wallet_manager.get_wallet(address)
            if not wallet:
                return _error_response(f"No existe una wallet con dirección {address}.", 404)
            data = wallet.to_dict()
            data["balance"] = self.node.blockchain.get_balance(address)
            return jsonify(data)

        @app.post("/wallets")
        def create_wallet():
            payload = _json_payload()
            label = payload.get("label")
            seed = payload.get("seed")
            wallet = self.node.blockchain.create_wallet(label=label, seed=seed)
            return (
                jsonify(
                    {
                        **wallet.to_dict(),
                        "balance": self.node.blockchain.get_balance(wallet.address),
                    }
                ),
                201,
            )

        @app.post("/transactions")
        def create_transaction():
            payload = _json_payload()
            recipient = payload.get("recipient")
            amount = payload.get("amount")
            sender_address = payload.get("sender_address")
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None

            if not recipient:
                return _error_response("El campo 'recipient' es obligatorio.")
            if amount is None:
                return _error_response("El campo 'amount' es obligatorio.")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return _error_response("El campo 'amount' debe ser numérico.")
            sender_wallet = None
            if sender_address:
                sender_wallet = self.node.blockchain.wallet_manager.get_wallet(sender_address)
                if not sender_wallet:
                    return _error_response("La wallet emisora no existe.", status=404)

            try:
                tx = self.node.blockchain.create_transaction(
                    recipient_address=recipient,
                    amount=amount,
                    metadata=metadata,
                    sender=sender_wallet,
                )
            except ValueError as exc:
                return _error_response(str(exc))

            return jsonify({"tx_id": tx.tx_id, "recipient": recipient, "amount": amount})

        @app.get("/transactions/history")
        def transaction_history():
            limit = request.args.get("limit", default=25, type=int)
            history = []
            for block in self.node.blockchain.chain_snapshot():
                for tx in block["transactions"]:
                    history.append(
                        {
                            "block_index": block["index"],
                            "tx_id": tx.get("tx_id"),
                            "amount": tx.get("amount"),
                            "sender": tx.get("sender_address"),
                            "recipient": tx.get("recipient_address"),
                            "timestamp": tx.get("timestamp"),
                        }
                    )
            history.sort(key=lambda item: item["timestamp"], reverse=True)
            if limit is not None and limit > 0:
                history = history[:limit]
            return jsonify({"transactions": history})


def _json_payload() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {}
    return data


def _error_response(message: str, status: int = 400):
    return jsonify({"error": message}), status


__all__ = ["APIServer"]

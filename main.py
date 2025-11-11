import argparse
import logging
import time

from Modules.P2PNetwork.Orchestration.Node import Node
from Modules.Utils.getProperties import get_properties_from_yaml


def parse_args():
    parser = argparse.ArgumentParser(description="Demo de red P2P + Blockchain.")
    parser.add_argument(
        "--show-wallet",
        action="store_true",
        help="Imprime la dirección de la wallet por defecto del nodo y su balance.",
    )
    parser.add_argument(
        "--send",
        nargs=2,
        metavar=("ADDRESS", "AMOUNT"),
        help="Crea y difunde una transacción desde la wallet local.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = get_properties_from_yaml()
    node = Node(config)
    node.iniciar()
    if args.show_wallet:
        wallet = node.blockchain.default_wallet()
        logging.info("Wallet '%s' -> %s | Balance: %s", wallet.label, wallet.address, node.blockchain.get_balance(wallet.address))
    if args.send:
        destinatario, monto = args.send
        node.enviar_transaccion(destinatario, float(monto))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Deteniendo nodo...")
        node.detener()


if __name__ == "__main__":
    main()

import logging
import time

from Modules.P2PNetwork.Orchestration.Node import Node
from Modules.Utils.getProperties import get_properties_from_yaml


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = get_properties_from_yaml()
    node = Node(config)
    node.iniciar()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Deteniendo nodo...")
        node.detener()


if __name__ == "__main__":
    main()

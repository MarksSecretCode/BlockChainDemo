import Modules.P2PNetwork.Network.Server as nw
import Modules.Utils.getProperties as gp

# Inicializar Nodo P2P
ip = gp.get_properties_from_yaml['server_ip']
puerto = gp.get_properties_from_yaml['server_port']

nw.iniciar_servidor(ip, puerto)

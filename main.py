import sys, os, re, traceback
from loguru import logger
from src.auth import start_session
from neutronclient.v2_0.client import Client as NeutronClient

def main():
    auth_server = os.environ.get('AUTH_SERVER')
    if not auth_server:
        raise Exception("no auth server is in environment variables")

    auth_password = os.environ.get('AUTH_PASSWORD')
    if not auth_password:
        raise Exception("no auth password is in environment variables")

    ks_session = start_session(auth_server,auth_password)
    net_cli = NeutronClient(session=ks_session)
    ports = net_cli.list_ports()['ports']

    logger.info(f"Number of total ports: {len(ports)}")
    expeca_ports = []
    for port in ports:
        if 'zun' in port['name'] and port['binding:vnic_type'] == 'baremetal':
            expeca_ports.append(port)

    logger.info(f"Number of expeca ports: {len(expeca_ports)}")

    

if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        logger.error(ex)
        logger.warning(traceback.format_exc())
        sys.exit(1)

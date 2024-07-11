import sys, os, re
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



if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        logger.error(ex)
        sys.exit(1)

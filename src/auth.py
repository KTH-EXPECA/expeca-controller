import os, sys, signal
from loguru import logger
from keystoneauth1 import session
from keystoneauth1.identity import v3
from neutronclient.v2_0.client import Client as NeutronClient

# environment variables must be set for authentication of admin on openstack project this in openstack horizon:
# AUTH_SERVER=https://10.0.87.254,AUTH_PASSWORD=password
#
# environment varialbes set at terminal:
# export AUTH_SERVER=https://10.0.87.254; export AUTH_PASSWORD=password;

# warning: this timeout would be the timeout for all the commands you run
TIMEOUT_SECONDS = 30
def start_session(auth_server : str,auth_password : str):

    logger.info(f'Contacting {auth_server}:5000/v3/ ...')

    # Create a password auth plugin
    auth = v3.Password(auth_url=f'{auth_server}:5000/v3/',
                       username='admin',
                       password=auth_password,
                       user_domain_name='Default',
                       project_name='openstack',
                       project_domain_name='Default')

    # Create session
    ks_session = session.Session(auth=auth,timeout=TIMEOUT_SECONDS)
    token = ks_session.get_token()
    logger.info(f"Authentication was successful, produced token: {token}")

    return ks_session



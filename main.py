import sys, os, re, traceback, time
from loguru import logger
from src.auth import start_session
from neutronclient.v2_0.client import Client as NeutronClient
from kubernetes import client, config


TASK_PERIOD_SECONDS = 10
RESTART_PERIOD_SECONDS = 10
def main():
    auth_server = os.environ.get('AUTH_SERVER')
    if not auth_server:
        raise Exception("no auth server is in environment variables")

    auth_password = os.environ.get('AUTH_PASSWORD')
    if not auth_password:
        raise Exception("no auth password is in environment variables")

    kubeconfig_path = os.environ.get('KUBECONFIG_PATH')
    if not kubeconfig_path:
        raise Exception("no kubeconfig path is in environment variables")

    # get keystone authentication session
    ks_session = start_session(auth_server,auth_password)
    net_cli = NeutronClient(session=ks_session)

    # get kubernetes cluster client ready
    # Load kube config from the specified file
    config.load_kube_config(config_file=kubeconfig_path)

    # Create an instance of the API class
    v1 = client.CoreV1Api()


    # Repeat the task
    while True:
        ports = net_cli.list_ports()['ports']

        logger.info(f"Number of total ports: {len(ports)}")
        expeca_ports = []
        for port in ports:
            if 'zun' in port['name'] and port['binding:vnic_type'] == 'baremetal':
                expeca_ports.append(port)

        logger.info(f"Number of expeca baremetal ports: {len(expeca_ports)}")

        # List all pods in all namespaces
        pods = v1.list_pod_for_all_namespaces(watch=False)
        
        # if a port's name is not part of any pod's name, it means it is dangling
        # blacklist it
        dangling_indices = list(range(len(expeca_ports)))
        for port_index,port in enumerate(expeca_ports):
            for pod in pods.items:
                if port['name'] in pod.metadata.name:
                    dangling_indices.remove(port_index)
                    # logger.info(f"Found port {port_index} related to the pod {pod.metadata.name}")

        logger.warning(f"identified {len(dangling_indices)} blacklisted ports")
        for dang_id in dangling_indices:
            dangling_port = expeca_ports[dang_id]
            logger.warning(f"removing port {dangling_port['name']}")
            net_cli.delete_port(dangling_port['id'])

        logger.info(f"Restart in {TASK_PERIOD_SECONDS} seconds")


        time.sleep(TASK_PERIOD_SECONDS)

if __name__=="__main__":
    while True:
        try:
            main()
        except Exception as ex:
            logger.error(ex)
            logger.warning(traceback.format_exc())
        time.sleep(RESTART_PERIOD_SECONDS)

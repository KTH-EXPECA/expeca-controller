import sys, os, re, traceback, time, ipaddress, json
from flask import Flask, jsonify, request
from loguru import logger
from src.auth import start_session
from blazarclient.client import Client as BlazarClient
from blazarclient.base import BaseClientManager as BlazarClientBase
from kubernetes import client, config

app = Flask(__name__)

ks_session = None
blazar_cli = None
blazer_cli_base = None
k8s_v1_client = None
k8s_api = None

def worker_answer(worker : str):
    group = "k8s.cni.cncf.io"
    version = "v1"
    plural = "network-attachment-definitions"

    # List all NetworkAttachmentDefinitions in the cluster
    interfaces = set()
    nad_list = k8s_api.list_cluster_custom_object(group, version, plural)
    for nad in nad_list['items']:
        if worker in nad['metadata']['name']:
            interfaces.add(nad['metadata']['name'])

    result = {}
    for interface in interfaces:
        short_if_name = interface.split('.')[1]
        result[short_if_name] = []
        # list all pods networking
        if_res = []
        pods = k8s_v1_client.list_pod_for_all_namespaces(watch=False)
        pods_interfaces = []
        for pod in pods.items:
            if 'zun' in pod.metadata.name:
                dict_pod = pod.to_dict()
                nets_dict = json.loads(dict_pod['metadata']['annotations']['k8s.v1.cni.cncf.io/network-status'])
                if worker in dict_pod['spec']['node_name']:
                    for net_dict in nets_dict:
                        if interface in net_dict['name']:
                            del net_dict['name']
                            result[short_if_name].append(
                                    {
                                        'container_id' : dict_pod['metadata']['labels']['zun.openstack.org/uuid'],
                                        **net_dict
                                    }
                                )
    return result


@app.route('/', methods=['GET'])
def answer_get():
    # Get the name parameter from the request
    # format must be sdr-xx, adv-xx, or ep5g
    name = request.args.get('name')

    # Define regex patterns for valid names
    pattern_sdr = re.compile(r'^sdr-\d{2}$')
    pattern_adv = re.compile(r'^adv-\d{2}$')
    pattern_worker = re.compile(r'^worker-\d{2}$')
    pattern_ep5g = re.compile(r'^ep5g$')
    

    if name:
        if pattern_sdr.match(name) or pattern_adv.match(name) or pattern_ep5g.match(name):
            networks = blazer_cli_base.request_manager.get('/networks')[1]['networks']
            result = {}
            if name.startswith('sdr') or name.startswith('adv'):
                for network in networks:
                    bmnet = json.loads(network['baremetal_ports'])
                    if name.replace('-', '_') in bmnet[0]['name']:
                        result = { **result, bmnet[0]['name']:network['segment_id'] }
            elif name == 'ep5g':
                for network in networks:
                    bmnet = json.loads(network['baremetal_ports'])
                    if name in bmnet[0]['name']:
                        result = { **result, bmnet[0]['name']:network['segment_id'] }

            if result == {}:
                return jsonify({"error": "Requested device does not exist"}), 400

            return jsonify(result)
        elif pattern_worker.match(name):
            return jsonify({name: worker_answer(name)})
        else:
            # Name does not match the required patterns
            return jsonify({"error": "Invalid name format"}), 400
    else:
        # Name parameter not provided
        return jsonify({"error": "Name not provided"}), 400

if __name__ == '__main__':

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
    blazar_cli = BlazarClient(session=ks_session)
    blazer_cli_base = BlazarClientBase(blazar_url='https://testbed.expeca.proj.kth.se:1234/v1',auth_token=ks_session.get_token(),session='')

    # fix k8s clients
    config.load_kube_config(config_file=kubeconfig_path)
    k8s_v1_client = client.CoreV1Api()
    k8s_api = client.CustomObjectsApi()

    # Run the server on a specific port, e.g., 5000
    port = 56901
    app.run(host='0.0.0.0', port=port)

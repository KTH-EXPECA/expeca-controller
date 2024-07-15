import sys, os, re, traceback, time, ipaddress, json
from flask import Flask, jsonify, request
from loguru import logger
from src.auth import start_session
from blazarclient.client import Client as BlazarClient
from blazarclient.base import BaseClientManager as BlazarClientBase
from kubernetes import client, config
from ntc_templates.parse import parse_output
import netmiko
from netmiko import ConnectHandler

app = Flask(__name__)

ks_session = None
blazar_cli = None
blazer_cli_base = None
k8s_v1_client = None
k8s_api = None
switch_config = None

def renew_authentication():
    global ks_session
    global blazar_cli
    global blazer_cli_base
    global k8s_v1_client
    global k8s_api
    global switch_config

    auth_server = os.environ.get('AUTH_SERVER')
    if not auth_server:
        raise Exception("no auth server is in environment variables")

    auth_password = os.environ.get('AUTH_PASSWORD')
    if not auth_password:
        raise Exception("no auth password is in environment variables")

    kubeconfig_path = os.environ.get('KUBECONFIG_PATH')
    if not kubeconfig_path:
        raise Exception("no kubeconfig path is in environment variables")

    switch_password = os.environ.get('SWITCH_PASSWORD')
    if not switch_password:
        raise Exception("no switch password is in environment variables")

    switch_config = {
        'device_type': 'cisco_s300',
        'host':   '10.10.1.3',
        'username': 'expeca',
        'password': switch_password,
        "session_log": 'netmiko_session.log',
        "port": '22'
    }

    # get keystone authentication session
    ks_session = start_session(auth_server,auth_password)
    blazar_cli = BlazarClient(session=ks_session)
    blazer_cli_base = BlazarClientBase(blazar_url=f"{auth_server}:1234/v1",auth_token=ks_session.get_token(),session='')

    # fix k8s clients
    config.load_kube_config(config_file=kubeconfig_path)
    k8s_v1_client = client.CoreV1Api()
    k8s_api = client.CustomObjectsApi()

    logger.success("authentication done")

def process_ports(port_str : str) -> list:
    port_list = []

    # Split the string by comma to process each segment
    segments = port_str.split(',')

    for segment in segments:
        if '-' in segment:
            # If the segment contains a range
            base = re.match(r'^(.*\/.*\/)(\d+)-(\d+)$', segment)
            if base:
                prefix = base.group(1)
                start = int(base.group(2))
                end = int(base.group(3))
                for i in range(start, end + 1):
                    port_list.append(f"{prefix}{i}")
        else:
            # If the segment is a single port
            if segment:
                port_list.append(segment)

    return port_list

def count_dashes(line):
    segments = line.split()
    return [len(segment) for segment in segments]

def process_vlans(table_str : str) -> list:

    lines = table_str.strip().split("\n")
    json_list = []
    current_data = {}
    reached_dash_line = False
    for line in lines:
        # check if the line only contains dashes
        if not reached_dash_line:
            if set(line.strip().replace(' ', '')) == {'-'}:
                # reached dash line!
                dash_counts = count_dashes(line)
                reached_dash_line = True
                #print(dash_counts)
            continue

        # dash counts example: [4, 17, 18, 18, 16]
        nl_vlan = line[0:dash_counts[0]+1].strip()
        nl_name = line[dash_counts[0]+1:dash_counts[0]+dash_counts[1]+2].strip()
        nl_tagged_ports = line[dash_counts[0]+dash_counts[1]+2:dash_counts[0]+dash_counts[1]+dash_counts[2]+3].strip()
        nl_untagged_ports = line[dash_counts[0]+dash_counts[1]+dash_counts[2]+3:dash_counts[0]+dash_counts[1]+dash_counts[2]+dash_counts[3]+4].strip()
        nl_created_by = line[dash_counts[0]+dash_counts[1]+dash_counts[2]+dash_counts[3]+4:-1].strip()
        if len(nl_vlan) == 0:
            # Continuation line
            # Assumes that only ports can extend to new lines, not the name
            pnlt_ports = process_ports(nl_tagged_ports) # returns a list
            pnlut_ports = process_ports(nl_untagged_ports) # returns a list
            current_data["tagged_ports"] = [*current_data["tagged_ports"],*pnlt_ports]
            current_data["untagged_ports"] = [*current_data["untagged_ports"], *pnlut_ports]
        else:
            # New line, parse the information
            if current_data:
                json_list.append(current_data)

            pnlt_ports = process_ports(nl_tagged_ports) # returns a list
            pnlut_ports = process_ports(nl_untagged_ports) # returns a list
            current_data = {
                "vlan": nl_vlan,
                "name": nl_name,
                "tagged_ports": pnlt_ports,
                "untagged_ports": pnlut_ports,
                "created_by": nl_created_by
            }

    # Append the last collected data
    if current_data:
        json_list.append(current_data)

    return json_list

def check_switch_port(port_id, interfaces_parsed, vlans_parsed, portid_name_mapping):

    result = {}
    for anif in interfaces_parsed:
        if anif['port'] == port_id:
            result = anif
            break

    result['stitches'] = {}
    for vlan in vlans_parsed:
        if port_id in vlan["untagged_ports"] and vlan['vlan'] != '1' and vlan['vlan'] != '2':
            stitched_ports = []
            for sport_id in vlan["untagged_ports"]: 
                if sport_id != port_id:
                    if sport_id in portid_name_mapping:
                        stitched_ports.append({"port_id":sport_id, "name":portid_name_mapping[sport_id]})
                    else:
                        stitched_ports.append({"port_id":sport_id, "name":""})
            result['stitches'][vlan['vlan']] = stitched_ports
    return result



def find_all_port_ids(nad_list,blazar_nets):
    # List all NetworkAttachmentDefinitions in the cluster
    interfaces = set()
    result = {}
    for nad in nad_list['items']:
        nad_conf = json.loads(nad['spec']["config"])
        port_id = nad_conf["local_link_information"][0]['port_id']
        if nad['metadata']['name'] not in interfaces:
            result = { **result, port_id:nad['metadata']['name'] }
        interfaces.add(nad['metadata']['name'])

    for network in blazar_nets:
        bmnet = json.loads(network['baremetal_ports'])
        net_name = bmnet[0]['name']
        port_id = bmnet[0]["binding-profile"]["local_link_information"][0]["port_id"]
        result = { **result, port_id:bmnet[0]['name'] }

    return result


def worker_answer(worker : str, nad_list, interfaces_parsed, vlans_parsed, portid_name_mapping):
    global ks_session
    global blazar_cli
    global blazer_cli_base
    global k8s_v1_client
    global k8s_api


    # List all NetworkAttachmentDefinitions in the cluster
    interfaces = set()
    result = {}
    for nad in nad_list['items']:
        if worker in nad['metadata']['name']:
            #print(nad)
            #print(nad['spec'])
            nad_conf = json.loads(nad['spec']["config"])
            port_id = nad_conf["local_link_information"][0]['port_id']
            short_if_name = nad['metadata']['name'].split('.')[1]
            if nad['metadata']['name'] not in interfaces:
                result = { 
                    **result, 
                    short_if_name: check_switch_port(port_id, interfaces_parsed, vlans_parsed, portid_name_mapping),
                }
            interfaces.add(nad['metadata']['name'])

    for interface in interfaces:
        short_if_name = interface.split('.')[1]
        result[short_if_name]['connections'] = []
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
                            result[short_if_name]['connections'].append(
                                    {
                                        'container_id' : dict_pod['metadata']['labels']['zun.openstack.org/uuid'],
                                        **net_dict
                                    }
                                )
    return result

@app.route('/', methods=['GET'])
def answer_get():
    global ks_session
    global blazar_cli
    global blazer_cli_base
    global k8s_v1_client
    global k8s_api

    # Get the name parameter from the request
    # format must be sdr-xx, adv-xx, or ep5g
    name = request.args.get('name')

    # Define regex patterns for valid names
    pattern_sdr = re.compile(r'^sdr-\d{2}$')
    pattern_adv = re.compile(r'^adv-\d{2}$')
    pattern_worker = re.compile(r'^worker-\d{2}$')
    pattern_ep5g = re.compile(r'^ep5g$')

    # check blazar and k8s
    nad_list = k8s_api.list_cluster_custom_object("k8s.cni.cncf.io", "v1", "network-attachment-definitions")
    try:
        blazar_nets = blazer_cli_base.request_manager.get('/networks')[1]['networks']
    except Exception as exp:
        logger.warning("(re)starting authentication")
        renew_authentication()
        blazar_nets = blazer_cli_base.request_manager.get('/networks')[1]['networks']
    portid_name_mapping = find_all_port_ids(nad_list,blazar_nets)

    # check interfaces and vlans on the switch to be used for check_switch_port function 
    global switch_config
    connect = ConnectHandler(**switch_config)
    connect.send_command('terminal width 511')
    connect.send_command('terminal datadump')
    output = connect.send_command('show interface status')
    interfaces_parsed = parse_output(platform="cisco_s300", command="show interface status", data=output)
    output = connect.send_command('show vlan')
    vlans_parsed = process_vlans(output)
    connect.disconnect()
    
    if name:
        if pattern_sdr.match(name) or pattern_adv.match(name) or pattern_ep5g.match(name):
            result = {}
            if name.startswith('sdr') or name.startswith('adv'):
                for network in blazar_nets:
                    bmnet = json.loads(network['baremetal_ports'])
                    if name.replace('-', '_') in bmnet[0]['name']:
                        port_id = bmnet[0]["binding-profile"]["local_link_information"][0]["port_id"]
                        result = { 
                            **result, 
                            bmnet[0]['name']:{ 
                                "segment_id" : network['segment_id'], 
                                **check_switch_port(port_id, interfaces_parsed, vlans_parsed, portid_name_mapping)
                            } 
                        }
            elif name == 'ep5g':
                for network in blazar_nets:
                    bmnet = json.loads(network['baremetal_ports'])
                    if name in bmnet[0]['name']:
                        port_id = bmnet[0]["binding-profile"]["local_link_information"][0]["port_id"]
                        result = { 
                            **result, 
                            bmnet[0]['name']: { 
                                "segment_id" : network['segment_id'], 
                                **check_switch_port(port_id, interfaces_parsed, vlans_parsed, portid_name_mapping) 
                            } 
                        }

            if result == {}:
                return jsonify({"error": "Requested device does not exist"}), 400

            return jsonify(result)
        elif pattern_worker.match(name):
            worker_ans = worker_answer(name, nad_list ,interfaces_parsed, vlans_parsed, portid_name_mapping)
            return jsonify({name: worker_ans})
        else:
            # Name does not match the required patterns
            return jsonify({"error": "Invalid name format"}), 400
    else:
        # Name parameter not provided
        return jsonify({"error": "Name not provided"}), 400

if __name__ == '__main__':

    renew_authentication()

    # Run the server on a specific port, e.g., 5000
    port = 56901
    app.run(host='0.0.0.0', port=port)

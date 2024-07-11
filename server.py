import sys, os, re, traceback, time, ipaddress
from flask import Flask, jsonify
from loguru import logger
from src.auth import start_session
from neutronclient.v2_0.client import Client as NeutronClient
from kubernetes import client, config

app = Flask(__name__)

ks_session = None
net_cli = None


def find_available_ips(cidr, allocation_pool, used_ips):
    # Parse the CIDR and create a network object
    network = ipaddress.ip_network(cidr)

    # Parse the start and end of the allocation pool
    start_ip = ipaddress.ip_address(allocation_pool['start'])
    end_ip = ipaddress.ip_address(allocation_pool['end'])

    # Convert used IPs to a set of IP address objects
    used_ip_set = set(ipaddress.ip_address(ip) for ip in used_ips)

    # Find all IPs in the allocation pool range
    available_ips = []
    for ip in network.hosts():
        if start_ip <= ip <= end_ip and ip not in used_ip_set:
            available_ips.append(str(ip))

    return available_ips


@app.route('/', methods=['GET'])
def answer_get():
    nets = net_cli.list_networks()['networks']
    serverpublic_net = None
    for net in nets:
        if net['name'] == "serverpublic":
            serverpublic_net = net

    if serverpublic_net is None:
        raise Exception("no serverpublic network found")

    serverpublic_subnet_id = serverpublic_net['subnets'][0]
    serverpublic_subnet = net_cli.show_subnet(serverpublic_subnet_id)['subnet']

    ports = net_cli.list_ports()['ports']
    serverpublic_used_ips = []
    for port in ports:
        if port['network_id'] == serverpublic_net['id']:
            for fixed_ip in port['fixed_ips']:
                serverpublic_used_ips.append(fixed_ip['ip_address'])

    available_ips = find_available_ips(serverpublic_subnet['cidr'], serverpublic_subnet['allocation_pools'][0], serverpublic_used_ips)

    return jsonify({"available_ips":available_ips})

if __name__ == '__main__':

    auth_server = os.environ.get('AUTH_SERVER')
    if not auth_server:
        raise Exception("no auth server is in environment variables")

    auth_password = os.environ.get('AUTH_PASSWORD')
    if not auth_password:
        raise Exception("no auth password is in environment variables")

    # get keystone authentication session
    ks_session = start_session(auth_server,auth_password)
    net_cli = NeutronClient(session=ks_session)

    # Run the server on a specific port, e.g., 5000
    port = 56900
    app.run(host='0.0.0.0', port=port)

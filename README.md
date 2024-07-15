# expeca-controller
The service to address ExPECA testbed needs from Chameleon

On the controller machine, run the container in network host mode, targeting the authentication server on the controller with its internal address: `10.20.111.99` and http:
```
docker run -e AUTH_PASSWORD='admin_password' -e AUTH_SERVER='http://10.20.111.99' -e KUBECONFIG_PATH='kubeconfig' -v ~/.kube/config:/usr/src/app/kubeconfig -d --name expeca-controller --net=host samiemostafavi/expeca-controller
```


## Develop

for develop, run these on the controller machine
```
AUTH_SERVER=https://testbed.expeca.proj.kth.se AUTH_PASSWORD=<admin-password> KUBECONFIG_PATH=~/.kube/config python main.py
AUTH_SERVER=https://testbed.expeca.proj.kth.se AUTH_PASSWORD=<admin-password> KUBECONFIG_PATH=~/.kube/config python server.py
AUTH_PASSWORD=<admin-password> AUTH_SERVER='http://10.20.111.99' KUBECONFIG_PATH=~/.kube/config SWITCH_PASSWORD=<tenant-switch-password> python server_2.py
```

To test the HTTP servers:
```
curl http://130.237.11.100:56900/

curl http://130.237.11.100:56901/?name=adv-02
{"adv_02_port":132}

curl http://130.237.11.100:56901/?name=sdr-02
{"sdr_02_mango":103,"sdr_02_ni":104}

curl http://130.237.11.100:56901/?name=SDR-02
{"error":"Invalid name format"}

curl http://130.237.11.100:56901/?name=sdr-02
{"sdr_02_mango":103,"sdr_02_ni":104}

curl http://130.237.11.100:56901/?name=worker-02
```

build and push the image:
```
docker build --no-cache . -t samiemostafavi/expeca-controller
docker push samiemostafavi/expeca-controller
```

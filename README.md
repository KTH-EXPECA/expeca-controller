# expeca-controller
The service to address ExPECA testbed needs from Chameleon


```
docker build --no-cache . -t samiemostafavi/expeca-controller
docker push samiemostafavi/expeca-controller
```

On the controller machine, run the container in network host mode, targeting the authentication server on the controller with its internal address: `10.20.111.99` and http:
```
docker run -e AUTH_PASSWORD='admin_password' -e AUTH_SERVER='http://10.20.111.99' -e KUBECONFIG_PATH='kubeconfig' -v ~/.kube/config:/usr/src/app/kubeconfig -d --name expeca-controller --net=host samiemostafavi/expeca-controller
```


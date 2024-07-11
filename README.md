# expeca-controller
The service to address ExPECA testbed needs from Chameleon


# Authentication setup

Download admin's openrc file and map it to `/usr/src/app/openstack-openrc.sh` while running the container. Also, add admin password as an environment variable under the name `OS_PASSWORD_INPUT`.
```
docker run -e OS_PASSWORD_INPUT='password' -v ~/expeca-controller/openstack-openrc.sh:/usr/src/app/openstack-openrc.sh -d samiemostafavi/expeca-controller
```



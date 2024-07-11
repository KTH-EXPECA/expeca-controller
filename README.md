# expeca-controller
The service to address ExPECA testbed needs from Chameleon


```
docker build --no-cache . -t samiemostafavi/expeca-controller
```

```
docker run -e AUTH_PASSWORD='admin_password' -e AUTH_SERVER='https://testbed.expeca.proj.kth.se' -it samiemostafavi/expeca-controller
```



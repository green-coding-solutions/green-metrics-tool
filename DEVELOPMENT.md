## IMPORTANT
This README file is only if you are developing Pull-Requests or changes to the Green Metrics Tool or if you are creating custom containers to measure.

Please skip this file if you just want to make measurements with the tool.

### Docker container setup for development.

For development you can overlay a temporary filesystem in the docker container as read-only.

Since some of the development containers checkout the repository in order to correctly boot you want
the filesystem to be mapped to your host OS when developing to save the need of copying changes to the inside of the container.

Start the NGINX / Gunicorn container with an appended `-v PATH_TO_YOUR_LOCAL_REPOSITORY:/var/www/green-metrics-tool:ro`

### Setting entries in /etc/hosts
We recommend the following local development URLs and their mapping in `/etc/hosts`:

```
127.0.0.1 green-coding-postgres-container
127.0.0.1 api.green-coding.internal metrics.green-coding.internal
```


### Creating demo apps / demo containers

Here we will guide you through the necessary setup if you are creating a consumeable container / demo app to measure with the Green Metrics Tool.


#### Containers with webservers
When creating containers yourself that contain a webserver AND you want to make them accessible for debugging through the host OS, you should make sure that the
port on which the webserver in the container listens is also exposed in the Dockerfile and the portmapping of the container are exactly the same portnumber.

If you swap the port along the way it may lead to unwanted redirects / ERR_CONNECTION_REFUSED.

Also you should set a Hostname that is also resolved on your Host OS.

We make now an example where your Docker container is connected to the `example-network` and has the name / hostname `my-custom-container`

Example in Dockerfile:

```
EXPOSE 9875
````

Example in Apache vHost:
```
Listen 9875
<VirtualHost *:9875>
    ServerName  my-custom-container
    ....
</VirtualHost>
```

Then in the docker run command set the hostname and map the docker internal port to the host OS port: ` --name my-custom-container -d 9875:9875`

You then must also map the containers in your `/etc/hosts` on the host OS to access them also through their internal hostname inside of the containers:

`127.0.0.1 my-custom-container`

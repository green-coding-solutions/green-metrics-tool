## Squid reverse proxy

### Hosted version

Please find it at: https://hub.docker.com/r/greencoding/squid_reverse_proxy

### Build yourself

Build command (please adjust the tag to your repository): 

```bash
docker build .
```

### How we build it

This is the command we us to update the container on Docker Hub

Details how to setup the build infrastructure here: https://docs.docker.com/build/building/multi-platform/

```bash
docker buildx build --platform linux/amd64,linux/arm64 --push -t greencoding/squid_reverse_proxy:vX .
```

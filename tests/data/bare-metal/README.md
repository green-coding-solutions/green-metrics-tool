## What is this directory?

We are using the *usage_scenario* to run the GMT tests itself in GMT.

This can be done by creating a Docker container that has systemd and Docker-in-Docker (DinD) enabled.

This Docker container can only be run with a matching container runtime. We use [sysbox](https://github.com/nestybox/sysbox).

In order to run the tests the user must have a new `docker allowed_run_args`  entry set:
- `--runtime sysbox-runc`

Example:
```json
{
    ...
            "orchestrators": {
                "docker": {
                    "allowed_run_args": [
                        '--runtime docker-args'
                    ]
                }
            },
    ...
```

Alternatively the `sysbox-runc` runtime can be set as the default runtime for the machine. This is the current setup that we are using.

## Caveats

The `Dockerfile` can currently not be built with the GMT as our build isolation layer *kaniko* has some issues with removing certain files. It sets certain paths as read-only and thus the build fails.

Thus we are using `greencoding/ubuntu-systemd-docker` as the image to pull, which is effectively the Dockerfile.

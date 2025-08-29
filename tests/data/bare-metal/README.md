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

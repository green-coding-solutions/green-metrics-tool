# Refactoring Proposal

Current structure stored in database:

```json
{
    "db": {
        "_container-info": {
            "hash": "sha256:645e932c27f7053bda80391da99f0f9d1edda8808ede7c6d742ae4263638ec1a",
            "image": "postgres13_gmt_run_tmp:latest"
        }
    },
    "web": {
        "_container-info": {
            "hash": "sha256:76116ef5d432819421334e1dfc09d6b1f3aeb98e6ee4973d4037f80f62bbb57d",
            "image": "web_4433210_gmt_run_tmp:latest"
        },
        "pip": {
            "hash": "ebaf57ca914e95bceb11b1a222f899998ca67e0b10d2d6e903ba0700dcfa8c0d",
            "scope": "project",
            "location": "/usr/local/lib/python3.13/site-packages",
            "dependencies": {
                "pip": {
                    "version": "25.2"
                }
            }
        },
        "dpkg": {
            "scope": "system",
            "dependencies": {
                "apt": {
                    "hash": "f2d367ee53b8e2f9758cbfbb0fbc9be138c165ac9b4bc471920da51b8be69fcd",
                    "version": "3.0.3 amd64"
                }
            }
        }
    }
}
```

proposal:

```json
{
    "db": {
        "container": {
            "hash": "sha256:645e932c27f7053bda80391da99f0f9d1edda8808ede7c6d742ae4263638ec1a",
            "image": "postgres13_gmt_run_tmp:latest"
        }
    },
    "web": {
        "container": {
            "hash": "sha256:76116ef5d432819421334e1dfc09d6b1f3aeb98e6ee4973d4037f80f62bbb57d",
            "image": "web_4433210_gmt_run_tmp:latest"
        },
        "pip": {
            "hash": "ebaf57ca914e95bceb11b1a222f899998ca67e0b10d2d6e903ba0700dcfa8c0d",
            "scope": "project",
            "location": "/usr/local/lib/python3.13/site-packages",
            "dependencies": {
                "pip": {
                    "version": "25.2"
                }
            }
        },
        "dpkg": {
            "scope": "system",
            "dependencies": {
                "apt": {
                    "hash": "f2d367ee53b8e2f9758cbfbb0fbc9be138c165ac9b4bc471920da51b8be69fcd",
                    "version": "3.0.3 amd64"
                }
            }
        }
    }
}
```

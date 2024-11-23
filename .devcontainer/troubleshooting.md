# Troubleshooting

## Frontend can't be open

Make sure the ports 9142 (`api`) und 9143 (`metrics page`) are public. If they are private, the metrics frontend will not be able to access the API due to CORS issues. After a restart of the codespace the ports are set to private, so you have to change the visibility manually.

You can use the following commands in the terminal to make the ports public:

```sh
gh codespace ports visibility 9142:public -c $CODESPACE_NAME
gh codespace ports visibility 9143:public -c $CODESPACE_NAME
```

## Connection to server failed

If you entcounter an error like

```log
error connecting in 'pool-1': connection failed: connection to server at "127.0.0.1", port 9573 failed: Connection refused
        Is the server running on that host and accepting TCP/IP connections?
```

then ensure that the Docker containers of GMT are running.

```sh
docker compose -f docker/compose.yml up -d
```

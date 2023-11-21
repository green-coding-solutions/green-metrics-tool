## Green Metrics Tool Codespaces Quickstart

Thank you for trying out the Green Metrics Tool :-)

First remember to activate your venv:
`source venv/bin/activate`

Then start your docker containerss
`docker compose -f /workspaces/green-metrics-tool/docker/compose.yml up -d` 

quick test:
`/workspaces/green-metrics-tool/runner.py --name test --uri /workspaces/examples/stress/`

You need to go to the ports tab in codespaces, and make the ports for 9142(api) and 9143(metrics) public by right clicking the port and setting the port visibility to public.

Alternatively run:
`gh codespace ports visibility 9142:public -c $CODESPACE_NAME`
and
`gh codespace ports visibility 9143:public -c $CODESPACE_NAME`

To see the Metrics front end, go to your ports tab and follow the forwarding address for port 9143

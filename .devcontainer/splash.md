## Green Metrics Tool Codespaces Quickstart

Thank you for trying out the Green Metrics Tool :-)

First remember to activate your venv:
`source venv/bin/activate`

Then in a second terminal window, start the docker containers:
`cd /workspaces/green-metrics-tool/docker && docker compose up`

quick test:
`/workspaces/green-metrics-tool/runner.py --name test --uri /workspaces/green-metrics-tool/tests/stress-application`

You need to go to the ports tab in codespaces, and make the ports for 9142(api) and 9143(metrics) public by right clicking the port and setting the port visibility to public.

To see the Metrics front end, go to your ports tab and follow the forwarding address for port 9143

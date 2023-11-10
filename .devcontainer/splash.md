## Green Metrics Tool Codespaces Quickstart

Thank you for trying out the Green Metrics Tool :-)

First remember to activate your venv:
`source venv/bin/activate`

Then in a second terminal window, start the docker containers:
`cd /workspaces/green-metrics-tool/docker && docker compose up `

quick test:
`/workspaces/green-metrics-tool/runner.py --name test --uri /workspaces/green-metrics-tool/tests/stress-application`

To see the Metrics front end, go to your ports tab and follow the link for port 9143
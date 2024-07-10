## Green Metrics Tool Codespaces Quickstart

Thank you for trying out the Green Metrics Tool :-)

Please run `bash .devcontainer/workshop/codespace-setup.sh` to set up everything! 🚀

It will take about 3 minutes.

Load the env: `source venv/bin/activate`

Do your first run like this: `python3 runner.py --name "Simple Test" --uri "/workspaces/green-metrics-tool/example-applications/" --filename "stress/usage_scenario.yml" --skip-system-checks --dev-no-optimizations --dev-no-build`

Then, if you want to see a more representative repository, try running our Bakery Demo repository we did together with the Wagtail Community: `python3 runner.py --uri https://github.com/green-coding-solutions/bakerydemo --branch gmt --skip-system-checks --dev-no-optimization --dev-no-build --skip-unsafe --name "Bakery Demo Test"`

To see the Metrics front end, go to your ports tab and follow the forwarding address for port 9143

Make sure the `api` port (9142) is public. If it's private, the metrics frontend will not be able to access the API due to CORS issues. After a restart of the codespace the ports are set to private, so you have to change the visibility manually.

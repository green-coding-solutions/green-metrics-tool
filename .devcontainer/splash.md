# Green Metrics Tool Codespaces Quickstart

Thank you for trying out the Green Metrics Tool :-)

Please run the following command in the terminal to set up everything! 🚀

```sh
bash .devcontainer/codespace-setup.sh
```

It will take about 3 minutes.

Afterwards, load the python environment:

```sh
source venv/bin/activate
```

Do your first measurement run like this:

```sh
python3 runner.py --name "Simple Test" --uri "/workspaces/green-metrics-tool/example-applications/" --filename "stress/usage_scenario.yml" --dev-no-system-checks --skip-optimizations --dev-cache-build
```

Then, if you want to see a more representative repository, try running our Bakery Demo repository we did together with the Wagtail Community:

```sh
python3 runner.py --uri https://github.com/green-coding-solutions/bakerydemo --branch gmt-pinned-versions --dev-no-system-checks --skip-optimizations --dev-cache-build --skip-unsafe --name "Bakery Demo Test"
```

To see the Metrics front end, go to your ports tab and follow the forwarding address for port 9143.

Make sure the `api` port (9142) is public. If it's private, the metrics frontend will not be able to access the API due to CORS issues.

If you are experiencing problems, see the file [.devcontainer/troubleshooting.md](./troubleshooting.md) for some common troubleshooting tips.

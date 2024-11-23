[![Tests Status - Main](https://github.com/green-coding-solutions/green-metrics-tool/actions/workflows/tests-vm-main.yml/badge.svg)](https://github.com/green-coding-solutions/green-metrics-tool/actions/workflows/tests-vm-main.yml)


[![Energy Used](https://api.green-coding.io/v1/ci/badge/get/?repo=green-coding-solutions/green-metrics-tool&branch=main&workflow=45267393)](https://metrics.green-coding.io/ci.html?repo=green-coding-solutions/green-metrics-tool&branch=main&workflow=45267393) (This is the energy cost of running our CI-Pipelines on Github. [Find out more about Eco-CI](https://www.green-coding.io/projects/eco-ci/))

[![Try in Github Codespaces!](https://github.com/codespaces/badge.svg)](https://codespaces.new/green-coding-berlin/green-metrics-tool)

# Introduction

The Green Metrics Tool is a developer tool indented for measuring the energy and CO2 consumption of software through a software life cycle analysis (SLCA).

Key features are:
- Reproducible measurements through configuration/setup-as-code
- [POSIX style metric providers](https://docs.green-coding.io/docs/measuring/metric-providers/metric-providers-overview/) for many sensors (RAPL, IPMI, PSU, Docker, Temperature, CPU ...)
- [Low overhead](https://docs.green-coding.io/docs/measuring/metric-providers/overhead-of-measurement-providers/)
- Statististical frontend with charts - [DEMO](https://metrics.green-coding.io/stats.html?id=7169e39e-6938-4636-907b-68aa421994b2)
- API - [DEMO](https://api.green-coding.io)
- [Cluster setup](https://docs.green-coding.io/docs/installation/installation-cluster/)
- [Free Hosted service for more precise measurements](https://docs.green-coding.io/docs/measuring/measurement-cluster/)
- Timeline-View: Monitor software projects over time - [DEMO for Wagtail](https://metrics.green-coding.io/timeline.html?uri=https://github.com/green-coding-solutions/bakerydemo-gold-benchmark&filename=usage_scenario_warm.yml&branch=&machine_id=7) / [DEMO Overview](https://metrics.green-coding.io/energy-timeline.html)
- [Energy-ID Score-Cards](https://www.green-coding.io/projects/energy-id/) for software (Also see below)

It is designed to re-use existing infrastructure and testing files as much as possible to be easily integrateable into every software repository and create transparency around software energy consumption.

It can orchestrate Docker containers according to a given specificaion in a `usage_scenario.yml` file.

These containers will be setup on the host system and the testing specification in the `usage_scenario.yml` will be
run by sending the commands to the containers accordingly.

This repository contains the command line tools to schedule and run the measurement report
as well as a web interface to view the measured metrics in some nice charts.

# Frontend
To see the frontend in action and get an idea of what kind of metrics the tool can collect and display go to out [Green Metrics Frontend](https://metrics.green-coding.io)

# Documentation

To see the the documentation and how to install and use the tool please go to [Green Metrics Tool Documentation](https://docs.green-coding.io)

# Screenshots of Single Run View

![](https://www.green-coding.io/img/projects/gmt-screenshot-1.webp)
![](https://www.green-coding.io/img/projects/gmt-screenshot-2.webp)
![](https://www.green-coding.io/img/projects/gmt-screenshot-3.webp)
![](https://www.green-coding.io/img/projects/gmt-screenshot-4.webp)
 

# Screenshots of Comparison View
![](https://www.green-coding.io/img/projects/gmt-screenshot-5.webp)
![](https://www.green-coding.io/img/projects/gmt-screenshot-6.webp)

# Energy-ID Scorecards
<img width="1034" alt="Screenshot 2023-10-24 at 10 43 28 AM" src="https://github.com/green-coding-solutions/green-metrics-tool/assets/250671/7e3e3faa-5452-4722-af70-a65114f930ac">

Details: [Energy-ID project page](https://www.green-coding.io/projects/energy-id/
)


## License and Copyright
The Green Metrics Tool is available under open-source AGPL and commercial license agreements. If you determine you cannot meet the requirements of the AGPL, please contact [Green Coding Solutions](https://www.green-coding.io/projects/green-metrics-tool) for more information regarding a commercial license.



[![Tests Status - Main](https://github.com/green-coding-berlin/green-metrics-tool/actions/workflows/tests-vm-main.yml/badge.svg)](https://github.com/green-coding-berlin/green-metrics-tool/actions/workflows/tests-vm-main.yml)

[![Energy Used](https://api.green-coding.berlin/v1/ci/badge/get/?repo=green-coding-berlin/green-metrics-tool&branch=dev&workflow=45267392)](https://metrics.green-coding.berlin/ci.html?repo=green-coding-berlin/green-metrics-tool&branch=dev&workflow=45267392) (This is the energy cost of running our CI-Pipelines on Github. [Find out more about Eco-CI](https://www.green-coding.berlin/projects/eco-ci/))

# Introduction

The Green Metrics Tool is a developer tool is indented for measuring the energy consumption of software and doing life-cycle-analysis.

It is designed to re-use existing infrastructure and testing files as much as possible to be easily integrateable into every software repository and create transparency around software energy consumption.

It can orchestrate Docker containers according to a given specificaion in a `usage_scenario.yml` file.

These containers will be setup on the host system and the testing specification in the `usage_scenario.yml` will be
run by sending the commands to the containers accordingly.

During this process the performance metrics of the containers are read through different metric providers like:
- CPU / DRAM energy (RAPL)
- System energy (IMPI / PowerSpy2 / Machine-Learning-Model / SDIA Model)
- container CPU utilization
- container memory utilization
- etc.

This repository contains the command line tools to schedule and run the measurement report
as well as a web interface to view the measured metrics in some nice charts.

# Frontend
To see the frontend in action and get an idea of what kind of metrics the tool can collect and display go to out [Green Metrics Frontend](https://metrics.green-coding.berlin)


# Documentation

To see the the documentation and how to install and use the tool please go to [Green Metrics Tool Documentation](https://docs.green-coding.berlin)

# Screenshots

![Web Flow Demo with CPU measurement provider](https://www.green-coding.berlin/img/projects/gmt-screenshot-1.webp "Web Charts demo with docker stats provider instead of energy")
> Web Flow Demo with CPU measurement provider
 
![Web Flow Demo with energy measurement provider](https://www.green-coding.berlin/img/projects/gmt-screenshot-2.webp "Web Charts demo with docker stats provider instead of energy")
> Web Flow Demo with energy measurement provider

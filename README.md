# Introduction

This repository contains the command line tools to schedule and run the measurement report
as well as a web interface to view the measured metrics in some nice charts.

# Measurement methodology

The software can orchestrate Docker containers according to a given specificaion in a usage-flow.json file.

These containers will be setup on the host system and the testing specification in the usage-flow will be
run by sending the commands to the containers accordingly.

During this process the performance metrics of the containers are read through the stream of 
`docker stats`.

The current limitation of this approach is:
- The resolution of 1s is pretty low
- Docker stats gives sometime out different value than top / /proc/stat depending on your OS configuration
- It does not directly translate into energy without an appropriate transfer model.

These problems are currently addressed by doing research on either using onboard hardware sensors or measuring 
the electrical signals directly on-chip or on the cables of the machine.

We hope to refine the approach soon and update the tool accordingly (Thanks for @mrchrisadams requesting this clarification)

The next part README will guide you through the installation on your server / cloud instance.

# Installation

## Method 1: Use our provided Dockerfiles

Please see the documentation under [Dockerfiles method](https://github.com/green-coding-berlin/green-metrics-tool/tree/main/Docker)

## Method 2: Install directly on linux machine

Please see the documentation under [Manual installation](https://github.com/green-coding-berlin/green-metrics-tool/blob/main/MANUAL_INSTALLATION.md)


# Usage

Once you have the tool either installed through the Dockerfiles or directly on your machine you can access the
web interface through: http://YOUR_URL_OR_IP_ESCAPED_HERE

If you have installed a cronjob you can insert a new job at http://YOUR_URL_OR_IP_ESCAPED_HERE/request.html

It will be automatically picked up and you will get sent an email with the link to the results.

In manual mode just go to the `/var/www/green-metrics-tool/cron` directory.

Here you can use the `runner.py` tool to trigger a run of the tool manually.
\
\
An example call would be like so: `runner.py manual --folder /path/to/my_demo_software`

The tool expects a **usage_scenario.json** inside of that folder. It will read it, orchestrate the containers
and give you the ID which you can then plugin into the web interface to access the report.

**Example: http://YOUR_URL_OR_IP_ESCAPED_HERE/?id=77960e45-372f-4295-a950-6af5ecfda205**


To see a working live example go to: https://green-metric.codetactics.de/?id=04ca9a03-a6a0-4fa5-ac84-2e0a2a5a1375


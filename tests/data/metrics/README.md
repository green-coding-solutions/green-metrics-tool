# Creating new log files

Use this usage scenario and save it to `tests/data/usage_scenarios/basic_stress.yml`:

```yml
---
name: Test Stress
author: Dan Mateas
description: test

services:
  test-container:
    type: container
    image: alpine
    setup-commands:
      - command: apk add stress-ng

  net-container:
    type: container
    image: alpine
    setup-commands:
      - command: apk add curl

flow:
  - name: Idle a bit
    container: test-container
    commands:
      - type: console
        command: sleep 3

  - name: Hidden warmup
    container: test-container
    commands:
      - type: console
        command: sleep 4

  - name: Stress
    container: test-container
    commands:
      - type: console
        command: stress-ng -c 5 -t 1 -q
        note: Starting Stress

  - name: Download
    container: net-container
    commands:
      - type: console
        command: curl https://www.google.de

  - name: Hidden cleanup
    container: test-container
    commands:
      - type: console
        command: sleep 2

```

Then activate these providers:
- memory.used
- network.io.procfs
- network.io.cgroup
- cpu.utilization.cgroup
- cpu.utilization.procfs
- cpu.energy.rapl
- psu.energy.ac.mcp / psu.energy.dc.rapl


## Then run
`python3 runner.py --uri ~/Sites/green-coding/green-metrics-tool --filename tests/data/usage_scenarios/basic_stress.yml --dev-no-sleeps`


## Capture files
$ scp -r framebook:/tmp/green-metrics-tool .

## Get phase from database
$ docker exec -it green-coding-postgres-container psql --user postgres -p9573 -hlocalhost
\c green-coding
SELECT phases FROM runs;

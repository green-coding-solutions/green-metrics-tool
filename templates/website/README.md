## What?

This repository tries to explore the question if:
- We can monitor a website over time and can see if the energy cost for rendering changes
- If different websites have different energies for rendering which is uncorrelated to the pure time it takes for rendering (aka different power draw)

That these differences do exist is already known. Parsing complex CSS structures or going through large
DOM structures is more extensive than small pages.

The main question is: Can a single change of say a reduction of DOM nodes really be measured or will
it just drown in the noise / standard deviation of a normal parsing flow of a browser. The culprits here
are async parsing, the OS scheduler, network latency etc.

## How?

We use the [Green Metrics Tool](https://github.com/green-coding-berlin/green-metrics-tool/) to setup a simple Playwright Headless Browser based benchmark.

There are some example types of pages:

- bbc.co.uk - Media. Lots of images and tracking
- theguardian.co.uk - Media. Lots if images and tracking
- michaelkors.de - Playing video
- green-coding.io - low fi
- svgator.com - SVG Animation

## Adding sites

We have a frontend to add new sites to this repo and have them tested with our [Green Metrics Tool](https://www.green-coding.io/projects/green-metrics-tool/)

See: https://website-tester.green-coding.io/

## Building in production

For production `usage_scenario.yml` files we pre-building the squid container.

Build command (please adjust the tag to your repository): 

> Please look up details how to setup your build infrastructure here: https://docs.docker.com/build/building/multi-platform/
```bash
docker buildx build --platform linux/amd64,linux/arm64 --push -t greencoding/squid_reverse_proxy:v1 .
```

### Pre-Built
We supply a pre-built container via: `greencoding/squid_reverse_proxy:v1` from Docker Hub.
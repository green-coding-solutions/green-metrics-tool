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

We use the [Green Metrics Tool](https://github.com/green-coding-solutions/green-metrics-tool/) to setup a simple Playwright Headless Browser based benchmark.

There are some example types of pages:

- bbc.co.uk - Media. Lots of images and tracking
- theguardian.co.uk - Media. Lots if images and tracking
- michaelkors.de - Playing video
- green-coding.io - low fi
- svgator.com - SVG Animation

## Adding sites

We have a frontend to add new sites to this repo and have them tested with our [Green Metrics Tool](https://www.green-coding.io/projects/green-metrics-tool/)

See: https://website-tester.green-coding.io/

## Building container with custom settings

For production `usage_scenario.yml` files we pre-building the squid container from https://hub.docker.com/r/greencoding/squid_reverse_proxy

If you want to modfiy the reverse proxy or set some custom settings you can build the container yourself.

Please look into the [./docker/auxiliary-containers/squid_reverse_proxy] folder for further instructions.


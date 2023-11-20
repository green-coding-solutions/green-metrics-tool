FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-22.04

# Copy the contents of your project into the container
COPY ../../. /workspace

# Install Docker and dependencies
# and install example applications
RUN apt-get update \
    && apt-get install -y docker.io curl git make gcc python3 python3-pip python3-venv \
    && git clone https://github.com/green-coding-berlin/example-applications.git /workspaces/examples

# rename the lm_sensors makefile so its not built
RUN mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak \

# initially run the install script
RUN /workspaces/green-metrics-tool/install_linux.sh -p testpw -a http://api.green-coding.internal:9142 -m http://metrics.green-coding.internal:9142 -t

# Expose the necessary ports
EXPOSE 9142 9143

FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-22.04


# Copy the contents of your project into the container
COPY ../../. /workspaces/green-metrics-tool

# Install Docker and dependencies
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    sudo apt update && \
    sudo apt remove docker docker-engine docker.io containerd runc -y && \
    sudo apt install ca-certificates curl gnupg lsb-release -y && \
    sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y 

# add gmt dependencies and example applications
RUN apt-get update \
    && apt-get install -y curl git make gcc python3 python3-pip python3-venv \
    && git clone https://github.com/green-coding-berlin/example-applications.git /workspaces/examples

# rename the lm_sensors makefile so its not bulit
RUN mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak

# pull the gunicorn container
#RUN docker pull ghcr.io/green-coding-berlin/green-coding-gunicorn-container:latest 
#FROM ghcr.io/green-coding-berlin/green-coding-gunicorn-container:latest

# initially run the install script
#RUN cd /workspaces/green-metrics-tool \
#    && ./install_linux.sh -p testpw -a http://api.green-coding.internal:9142 -m http://metrics.green-coding.internal:9142 -t -h

# Expose the necessary ports
EXPOSE 9142 9143

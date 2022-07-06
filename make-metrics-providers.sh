#!/bin/bash

metrics_subdir="tools/metric-providers"
parent_dir="./$metrics_subdir"
make_file="Makefile"
find "$parent_dir" -type d |
while IFS= read -r subdir; do
    make_path="$subdir/$make_file"
    if [[ -f "$make_path" ]]; then
        rm $subdir/static-binary
        make -C $subdir
        chmod +x $subdir/static-binary
    fi
done

sudo_line="$USER ALL=(ALL) NOPASSWD: $PWD/tools/metric-providers/rapl/system/MSR/static-binary -i 1000"
sudo_line_2="$USER ALL=(ALL) NOPASSWD: $PWD/tools/metric-providers/rapl/system/MSR/static-binary -i 100"
etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"

if ! sudo grep -Fxq "$sudo_line" /etc/sudoers; then
    echo $sudo_line | sudo tee -a /etc/sudoers
fi

if ! sudo grep -Fxq "$sudo_line_2" /etc/sudoers; then
    echo $sudo_line_2 | sudo tee -a /etc/sudoers
fi

if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo $etc_hosts_line_1 | sudo tee -a /etc/hosts
fi

if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
    echo $etc_hosts_line_2 | sudo tee -a /etc/hosts
fi
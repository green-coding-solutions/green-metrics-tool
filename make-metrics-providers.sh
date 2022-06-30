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
        if [[ "$subdir" == *"rapl/system/MSR"* ]] ; then

            sudo_line="$USER\tALL=(ALL) NOPASSWD: $PWD/$metrics_subdir/static-binary -i 1000"
            echo $sudo_line
            if ! sudo grep -Fxq "$sudo_line" /etc/sudoers; then
                echo $sudo_line | sudo tee -a /etc/sudoers
                echo $USER
                # echo $USER
                # whoami
            fi
        fi
    fi
done


## check /etc/hosts/ for the below lines, add if not existing
## double check in non-sudo shell (should ask for pw prompt) 
## move the /sudoers code outside the loop, hardcode the $metrics_subdir for that specifically

#127.0.0.1    green-coding-postgres-container
#127.0.0.1    api.green-coding.local metrics.green-coding.local    
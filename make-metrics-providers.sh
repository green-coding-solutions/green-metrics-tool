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
            echo $USER
            whoami
            sudo_line="$USER    ALL=(ALL) NOPASSWD: /usr/bin/stdbuf -oL $PWD/$metrics_subdir/static-binary -i 1000"
            if grep -Fxq "$sudo_line" /etc/sudoers ; then
                echo $USER
                # echo $USER
                # whoami
            fi
        fi
    fi
done
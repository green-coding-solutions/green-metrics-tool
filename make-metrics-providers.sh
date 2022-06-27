#!/bin/bash
parent_dir="./tools/metric-providers"
make_file="Makefile"
find "$parent_dir" -type d |
while IFS= read -r subdir; do
    all_present=true
    make_path="$subdir/$make_file"
    if [[ -f "$make_path" ]]; then
        rm $subdir/static-binary
        make -C $subdir
    fi
done
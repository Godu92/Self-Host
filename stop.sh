#!/usr/bin/bash

dirs=$(ls -d */)

# Loop through each directory
for dir in $dirs; do
  # Create a docker-compose command with the -f option pointing to the YAML file in the current directory
  eval "podman compose -f $dir/docker-compose.yaml down --remove-orphans"
done

eval "yes | podman network prune"

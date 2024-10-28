#!/usr/bin/bash

dirs=$(ls -d */)

eval "podman network create -d bridge main"

# Loop through each directory
for dir in $dirs; do
  # Create a docker-compose command with the -f option pointing to the YAML file in the current directory
  eval "podman compose -f $dir/docker-compose.yaml up -d"
done

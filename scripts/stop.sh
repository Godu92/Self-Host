#!/usr/bin/bash

# Loop through each directory
GLOBIGNORE=".*"
for dir in ../*/; do
  dir=${dir%/} # remove trailing slash
  # Create a docker-compose command with the -f option pointing to the YAML file in the current directory
  eval "docker compose -f $dir/docker-compose.yaml down --remove-orphans"
  # eval "podman compose -f $dir/docker-compose.yaml down --remove-orphans"
done

eval "yes | docker network prune"
# eval "yes | podman network prune"

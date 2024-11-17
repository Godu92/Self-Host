#!/usr/bin/bash

# dirs=$(ls -d -- *)
# Define the list of excluded directories
EXCLUDED_DIRS=("adminer" "appsmith" "directus" "remoteRhel" "testing" "pihole" "calibre" "gopeed")

eval "docker network create -d bridge main"
# eval "podman network create -d bridge main"

# Loop through each directory
# In the event you have "self-signed cert" issues, try running as docker run with `--volume /etc/pki/ca-trust:/etc/pki/ca-trust`
GLOBIGNORE=".*"
for dir in */; do
  dir=${dir%/} # remove trailing slash
  excluded_dirs_str=$(printf "%s " "${EXCLUDED_DIRS[@]}")
  if [[ ! ${excluded_dirs_str} =~ ${dir} ]]; then
    echo "Starting: $dir ..."
    # Run Docker Compose in the current directory
    # echo "docker compose -f ${dir}docker-compose.yaml up -d"
    eval "docker compose -f $dir/docker-compose.yaml up -d"
  fi
done

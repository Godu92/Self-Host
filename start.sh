#!/usr/bin/bash

dirs=$(ls -d ./*)

# Define the list of excluded directories
EXCLUDED_DIRS=("adminer" "appsmith" "directus" "remoteRhel" "testing" "wordle")

eval "podman network create -d bridge main"

# Loop through each directory
for dir in $dirs; do
  excluded_dirs_str=$(printf "%s " "${EXCLUDED_DIRS[@]}")
  if [[ ! ${excluded_dirs_str} =~ ${dir} ]]; then
    # Create a docker-compose command with the -f option pointing to the YAML file in the current directory
    eval "podman compose -f $dir/docker-compose.yaml up -d"
  # In the event you have "self-signed cert" issues, try running as docker run with `--volume /etc/pki/ca-trust:/etc/pki/ca-trust`
  fi
done

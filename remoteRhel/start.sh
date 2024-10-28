#!/usr/bin/bash

image=remote-rhel

eval "$(podman build -t $image .)"

# Ports are vnc and web based respectively
eval "$(podman run --name $image -p 3389:3389 -p 8888:80 $image)"

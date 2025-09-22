#!/usr/bin/bash

for CONTAINER_ID in $(docker ps -aq); do
    CONTAINER_NAME=$(docker inspect -f '{{ .Name }}' "$CONTAINER_ID" | sed 's/^\///')
    IP_ADDRESS=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_ID")
    echo "Container Name: $CONTAINER_NAME, IP Address: $IP_ADDRESS"
done

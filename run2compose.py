import yaml


def transform(cmd: str) -> str:
    """Transforms cmd into compose yaml

    Args:
      cmd (str) = the docker run command to convert

    Returns:
      (str) = the template string of a compose file
    """
    template: str = "services:\n"

    pieces: list[str] = cmd.split(" ")

    # We want just the name without the image tag, but only if there is one
    if ":" in pieces[-1]:
        name: str = pieces[-1].split(":")[0]
    else:
        name = pieces[-1]
    template += f"\t{name.split("/")[1]}:\n"

    image: str = pieces[-1]
    template += f"\timage: {image}\n"
    template += "\trestart: unless-stopped\n"
    template += f"\tcontainer_name: {name}\n"

    # TODO: Likely should be lists in the event there's more than one
    for i, item in enumerate(pieces):
        # if ports are provided
        if "-p" in item:
            # get item after flag and split
            ports: list[str] = pieces[i + 1].split(":")
            outer_port: str = ports[0]
            inner_port: str = ports[1]
            template += "\t#ports:\n"
            template += f"\t#\t- {outer_port}:{inner_port}\n"

    # if volumes are provided
    if "-v" in item:
        # get item after flag and split
        volumes: list[str] = pieces[i + 1].split(":")
        outer_path: str = volumes[0]
        inner_path: str = volumes[1]
        template += "\t#volumes:\n"
        template += f"\t#\t- {outer_path}:{inner_path}\n"

    # if environments are provided
    if "-e" in item:
        # get item after flag and split
        envs: list[str] = pieces[i + 1]
        template += "\t#environment:\n"
        template += f"\t#\t{envs}\n"

    template += "\tlabels:\n"
    template += "\t\t- traefik.enable=true\n"

    host: str = "localhost"
    template += f"\t\t- traefik.http.routers.{name}.rule=Host(`{name}.{host}`)\n"
    template += f"\t\t- traefik.http.routers.{name}.entrypoints=http\n"
    template += (
        f"\t\t- traefik.http.services.{name}.loadbalancer.server.port={inner_port}\n"
    )

    return template


def main():
    """take in `docker run` command,
    produce compose file with `traefik` tags based on image name,
    also create folder based on image name and add to root compose
    """
    cmd: str = (
        "docker run --rm -it --shm-size=512m -p 6901:6901 -e VNC_PW=password kasmweb/only-office:1.16.0"
    )
    output: str = transform(cmd)
    yaml_output: str = yaml.dump(output, default_flow_style=False)
    print(yaml_output)


if __name__ == "__main__":
    main()

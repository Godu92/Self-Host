import argparse

import docker
import yaml


def create_args() -> argparse.Namespace:
    """Method to setup argument parsing

    Returns:
        (argparse.Namespace):
            The arguments to pass along
    """
    parser = argparse.ArgumentParser(
        prog="run2compose",
        description="Process `docker run` command into compose",
        usage="%(prog)s.py docker_cmd [-h] [-f [file]] [-n [traefik_network]] [-d [domain]]",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # The version
    parser.add_argument("--version", action="version", version="%(prog)s 0.1")

    # The docker run arg
    parser.add_argument(
        "docker_cmd",
        metavar="cmd",
        type=str,
        help="the `docker run` command",
    )

    # If you want a different file name
    parser.add_argument(
        "-f",
        "--file",
        metavar="file",
        dest="file",
        nargs="?",
        default="docker-compose.yaml",
        type=str,
        help="the file name",
    )

    # If you want a different network name
    parser.add_argument(
        "-n",
        "--network",
        metavar="network",
        nargs="?",
        type=str,
        help="the network name",
    )

    # If you want a different host name
    parser.add_argument(
        "-d",
        "--domain",
        metavar="domain",
        nargs="?",
        default="localhost",
        type=str,
        help="the domain name; ie `name.localhost`",
    )

    # Parse the arguments
    args = parser.parse_args()

    return args


def transform(args) -> str:
    """Transforms cmd into compose yaml

    Args:
      args (str):
        the docker run command to convert

    Returns:
      (str):
        the template string of a compose file
    """
    # Define the docker compose JSON-like object
    template: dict = {"services": {}}
    simple_name: str = None

    pieces: list[str] = args.docker_cmd.split(" ")

    # We want just the name without the image tag, but only if there is one
    if ":" in pieces[-1]:
        name: str = pieces[-1].split(":")[0]
    else:
        name = pieces[-1]
    if "/" in name:
        simple_name: str = name.split("/")[1].replace("-", "")
    else:
        simple_name = name

    image: str = pieces[-1]
    template["services"][f"{simple_name}"] = {}
    template["services"][f"{simple_name}"]["image"] = f"{image}"
    template["services"][f"{simple_name}"]["restart"] = "always"
    template["services"][f"{simple_name}"]["container_name"] = f"{simple_name}"
    template["services"][f"{simple_name}"]["ports"] = []
    template["services"][f"{simple_name}"]["environment"] = []
    template["services"][f"{simple_name}"]["volumes"] = []
    template["services"][f"{simple_name}"]["labels"] = []

    # TODO: Likely should be lists in the event there's more than one

    for i, item in enumerate(pieces):
        match item:

            # if ports are provided
            case "-p":
                # get item after flag and split
                ports: list[str] = pieces[i + 1].split(":")
                inner_port: str = ports[1]
                template["services"][f"{simple_name}"]["ports"].append(
                    f"{':'.join(ports)}"
                )

            # if volumes are provided
            case "-v":
                # get item after flag and split
                volumes: list[str] = pieces[i + 1]
                template["services"][f"{simple_name}"]["volumes"].append(f"{volumes}")

            # if environments are provided
            case "-e":
                # get item after flag and split
                envs: list[str] = pieces[i + 1]
                template["services"][f"{simple_name}"]["environment"].append(f"{envs}")

    labels: list[str] = ["traefik.enable=true"]

    host: str = args.domain

    labels.append(
        f"traefik.http.routers.{simple_name}.rule=Host(`{simple_name}.{host}`)"
    )
    labels.append(f"traefik.http.routers.{simple_name}.entrypoints=http")
    labels.append(
        f"traefik.http.services.{simple_name}.loadbalancer.server.port={inner_port}"
    )
    template["services"][f"{simple_name}"]["labels"] = labels

    return template


def create_networks(network_name: str) -> dict:
    """
    Creates the network section at the bottom of the compose file

    Args:
        network_name (str):
            the name of the network to use.
            if not provided, will check the running containers

    Returns:
        dict: _description_
    """
    # Adding networks to bottom of file
    traefik_network: str = network_name

    if not traefik_network:
        containers = docker.from_env().containers.list()

        for container in containers:
            if container.image.tags and any(
                "traefik" in tag for tag in container.image.tags
            ):
                print(container.ports)
                traefik_network = container.network

    networks: dict = {
        "networks": {
            "default": {
                "name": f"{traefik_network}",
                "external": "true",
            }
        }
    }

    return networks


def main():
    """take in `docker run` command,
    produce compose file with `traefik` tags based on image name,
    also create folder based on image name and add to root compose
    """
    # Create the parser
    args: argparse.Namespace = create_args()

    # cmd: str = (
    #     "docker run --rm -it --shm-size=512m -p 6901:6901 -e VNC_PW=password kasmweb/only-office:1.16.0"
    # )

    output: str = transform(args)
    yaml_output: str = yaml.dump(output, default_flow_style=True, indent=4)
    print(yaml_output)

    networks: dict = create_networks(args)
    yaml_output = yaml.dump(networks, default_flow_style=True, indent=4)
    print(yaml_output)


if __name__ == "__main__":
    main()

# Self-Host

This is a collection of local tools, originally made for`RHEL 8` using `podman`. Most of this should also work for `Docker`, save a few commands in the shell scripts.

- [Self-Host](#self-host)
  - [Starting](#starting)
    - [Example](#example)
  - [Templates](#templates)
  - [Sample projects](#sample-projects)
  - [Devcontainer](#devcontainer)
  - [Storage](#storage)
    - [List of Volumes](#list-of-volumes)
      - [Monica](#monica)
      - [Uptime](#uptime)
      - [Trilium](#trilium)

## Starting

Create and edit a `./.env` file at the root of this project:

Example (also found at `./.env-dev`):

```shell
HOST=localhost
DOCKER_DIR=/var/run/docker.sock
TRILIUM_DATA_DIR=./data # optional
```

> Sadly this does not extend to `./dashy/config` files as of yet

Can be started either via the `./scripts/start.sh` or the root level `./docker-compose.yaml` file.

> Note: certain services are not started automatically for one reason or another. Check what is in `EXCLUDED_DIRS` or what is commented out.

### Example

- `./scripts/start.sh`

```bash
EXCLUDED_DIRS=("adminer" "appsmith" "directus" "remoteRhel" "testing" "wordle")
```

- `./docker-compose.yaml`

```yaml
#### Tools
# - adminer/docker-compose.yaml
- ittools/docker-compose.yaml
```

## Templates

> TODO: Make template files for commonly used files

Template Dockerfile, docker-compose.yaml can be found in `./testing`

## Sample projects

> TODO: Create sample projects
>
> - ie Sample NodeJs, Springboot Java, etc
>
> Ideally sample projects are their own project

Yes I realize it's not that hard to find and make these (Springboot can be gotten easily from their website); however I'd like to have my own copies with settings and preferences already setup

- ie NodeJs pre-configured with TypeOrm

## Devcontainer

TODO: Setup devcontainer for project with extensions and settings

## Storage

TODO: Set more containers to docker volumes

You should need to create some volumes ahead of time for the ease of launching containers.

> You could go change all instances of `external` to `false` if you don't want to do that

### List of Volumes

#### Monica

- mysql
- data

#### Uptime

- up-data

#### Trilium

- tril-data

> Also has a possible `.env` bind in the event you want it set somewhere but not tracked
>
> TODO: Add this option for all mounts

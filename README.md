# Self-Host

This is a collection of local tools for `RHEL 8` using `podman`. Most of this should also work for `Docker`, save a few commands in the shell scripts, .zsh files and aliases.

- [Self-Host](#self-host)
  - [Source files](#source-files)
    - [One Time](#one-time)
    - [Always Updated](#always-updated)
    - [ZSH](#zsh)
  - [RHEL8](#rhel8)
  - [Starting](#starting)
    - [Example](#example)
  - [Templates](#templates)
  - [Sample projects](#sample-projects)
  - [Devcontainer](#devcontainer)

## Source files

The various `profile` files are for Linux based preferences.

### One Time

They can be used by simply copying into your `home` directory and then restarting your terminal.

### Always Updated

Alternatively, you can link to the files and thus they will be updated anytime this project gets updates.

Example:

```bash
ln -s Self-Host/profile/.vimrc .vimrc
```

> Note: You can take this one step further and do the link as `root` as well to have the same alias and preferences there as well
> TODO: Make script to simplify this process

### ZSH

ZSH is currently being used with `FiraMono Nerd Font`

## RHEL8

> TODO: Move to own repo

The remote RHEL 8 Docker image is based off of [JUMP-RHEL by Venera-13](https://github.com/venera-13/jump-rhel)

## Starting

Create and edit a `.env` file at the root of this project:

Example (also found at `.env-dev`):

```shell
HOST=localhost
DOCKER_DIR=/var/run/docker.sock
```

> Sadly this does not extend to `dashy/config` files as of yet

Can be started either via the `scripts/start.sh` or the root level `docker-compose.yaml` file.

> Note: certain services are not started automatically for one reason or another. Check what is in `EXCLUDED_DIRS` or what is commented out.

### Example

- `start.sh`

```bash
EXCLUDED_DIRS=("adminer" "appsmith" "directus" "remoteRhel" "testing" "wordle")
```

- `docker-compose.yaml`

```yaml
#### Tools
# - adminer/docker-compose.yaml
- ittools/docker-compose.yaml
```

## Templates

> TODO: Make template files for commonly used files
>
> - ie Dockerfile, docker-compose.yaml, .sh, etc

## Sample projects

> TODO: Create sample projects
>
> - ie Sample NodeJs, Springboot Java, etc

Yes I realize it's not that hard to find and make these (Springboot can be gotten easily from their website); however I'd like to have my own copies with settings and preferences already setup

- ie NodeJs pre-configured with TypeOrm

## Devcontainer

TODO: Setup devcontainer for project

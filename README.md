# Tools

This is a collection of local tools for RHEL8 using podman. Most of this should also work for Docker, save a few commands in the shell scripts, .zsh files and aliases.

## ZSH

ZSH is currently being used with `FiraMono Nerd Font`

## TODO: Move Rhel8 remote to own repo

The remote RHEL 8 Docker image is based off of [JUMP-RHEL by Venera-13](https://github.com/venera-13/jump-rhel)

## Starting

Can be started either via the `start.sh` or the root level `docker-compose.yaml` file.

> Note: certain services are not started automatically for one reason or another. Check what is in `EXCLUDED_DIRS` or what is commented out.

### Example

- `start.sh`

```bash
EXCLUDED_DIRS=("adminer" "appsmith" "directus" "remoteRhel" "testing" "wordle")
```

- `docker-compose.yaml`

```yaml
### Admininstration
# - adminer/docker-compose.yaml
- ittools/docker-compose.yaml
```

# Self-Host

This is a collection of local tools, originally made for`RHEL 8` using `podman`. Most of this should also work for `Docker`, save a few commands in the shell scripts.

- [Self-Host](#self-host)
  - [Starting](#starting)
    - [Deploy styles](#deploy-styles)
    - [Secrets](#secrets)
  - [Templates](#templates)
  - [Storage](#storage)
    - [List of Volumes](#list-of-volumes)
      - [Monica](#monica)
      - [Uptime](#uptime)
      - [Trilium](#trilium)
  - [TODO](#todo)
  - [Organization](#organization)

## Starting

Copy `.env.example` to `.env` at the root of this project and edit as needed:

```shell
cp .env.example .env
```

```shell
HOST=localhost
DOCKER_DIR=/var/run/docker.sock # or wherever podman is for you
TRILIUM_DATA_DIR=./data # optional
```

> Sadly this does not extend to `./dashy/config` files as of yet

If you use [direnv](https://direnv.net/), run `direnv allow` once — the tracked `.envrc` loads
`.env` automatically and also fixes up `HOSTNAME` with your machine's real hostname (docker
compose can't shell-evaluate `.env` values itself, so this needs a real shell).

`./docker-compose.yaml` is the base file — it defines the shared `proxy` network plus Traefik
and a `whoami` test target. It's a self-contained smoke test: after cloning the repo and
setting up `.env`, you can confirm your setup works with nothing but:

```bash
docker compose up -d
```

Then visit `whoami.<HOST>` to confirm Traefik routing works end to end.

Everything beyond that smoke test is opt-in via a **deploy style** override, layered on top
with Compose's `-f` flag:

```bash
docker compose -f docker-compose.yaml -f compose.local.yaml up -d
```

To stop everything for a style:

```bash
docker compose -f docker-compose.yaml -f compose.local.yaml down
```

### Deploy styles

A deploy style is just a `compose.<style>.yaml` file at the repo root containing an
`include:` list of which additional service directories to turn on, on top of the base file's
Traefik + whoami — everything not listed (or commented out) simply isn't started.
`compose.local.yaml` is the only style defined today; it adds glances and dashy on top of the
base smoke test.

To add a new style (e.g. a media server or a work box), copy `compose.local.yaml` to
`compose.<style>.yaml` and uncomment/comment the services you want for that setup. No other
file needs to change — the base `docker-compose.yaml` and every service's own
`docker-compose.yaml` stay untouched.

### Secrets

Any service directory with real credentials keeps them out of git: a tracked
`<service>/.env.example` documents the variables (placeholder values, usually `changeme`), and
a gitignored `<service>/.env` holds the real ones — same pattern as the root `.env`. Docker
Compose resolves each service's `.env` relative to its own directory automatically, no extra
config needed.

Before enabling one of these services in a deploy style, either copy its example by hand or
generate real random values with:

```bash
./scripts/gen-secrets.sh <service-dir>   # e.g. ./scripts/gen-secrets.sh pihole
./scripts/gen-secrets.sh --all           # every service that has a *.env.example
```

It won't overwrite an existing `.env` unless you pass `--force`. See the comment header in
[scripts/gen-secrets.sh](scripts/gen-secrets.sh) for the value rules (`changeme`,
`base64:changeme`, and `$OTHERKEY` references for credentials shared across containers in the
same compose file).

## Templates

> TODO: Make template files for commonly used files

Template Dockerfile, docker-compose.yaml can be found in `./testing`

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

## TODO

- Would be neat to have a script that could auto add to the top level compose file
- also a script that could put all services into the dashboard, with running ones getting status lights
- And while we're at it, add them to the uptime monitor
  - or look more into the "autokuma" thing

## Organization

The base `docker-compose.yaml` + per-style `compose.<style>.yaml` override setup described
under [Deploy styles](#deploy-styles) is implemented. Still TODO:

- Group related services into their own sub-folder with a shared sub-compose file (with an
  optional sub-network), imported up into the next level until root is reached.
- Give each individual service compose file its own override file, for per-service tweaks
  independent of deploy style.

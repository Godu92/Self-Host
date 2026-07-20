# Self-Host

This is a collection of local tools, originally made for`RHEL 8` using `podman`. Most of this should also work for `Docker`, save a few commands in the shell scripts.

- [Self-Host](#self-host)
  - [Starting](#starting)
    - [Deploy styles](#deploy-styles)
    - [Secrets](#secrets)
    - [Versions](#versions)
  - [Templates](#templates)
  - [Storage](#storage)
    - [List of Volumes](#list-of-volumes)
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

> Sadly this does not extend to `./admin-tools/dashy/config` files as of yet

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
./scripts/gen-secrets.sh <service-dir>   # e.g. ./scripts/gen-secrets.sh network/pihole
./scripts/gen-secrets.sh --style local    # every service the base file + compose.local.yaml enable
./scripts/gen-secrets.sh --all           # every service in the repo that has a *.env.example
```

`--style` is the one to reach for when standing up a style with a lot of services at once —
it only touches what that style actually turns on, so you're not hunting through 50 directories
to figure out which ones need a `.env`. Files that are pure documentation (nothing to actually
generate — e.g. a service with only a version-pin comment, no secrets) are skipped silently,
and it won't overwrite an existing `.env` unless you pass `--force`. See the comment header in
[scripts/gen-secrets.sh](scripts/gen-secrets.sh) for the value rules (`changeme`,
`base64:changeme`, and `$OTHERKEY` references for credentials shared across containers in the
same compose file).

### Versions

Every image tag is `${SERVICE_VERSION:-latest}` — nothing to configure by default, every
service just runs the latest published image. To pin a specific version instead, set the var
in that service's `.env` (see its `.env.example` for the exact name(s); create the `.env` if it
doesn't already exist for that service). A few images use a suffix that's a real variant, not a
version — e.g. `postgres:${POSTGRES_VERSION:-latest}-alpine` — there the var only controls the
version, the variant itself is fixed. One image ([freeipa](identity/freeipa/docker-compose.yaml)) has no
`latest` tag at all, so its var defaults to the current pin instead.

## Templates

> TODO: Make template files for commonly used files

Template Dockerfile, docker-compose.yaml can be found in `./dev/testing`

## Storage

TODO: Set more containers to docker volumes (most services still just bind-mount a local
`./config`/`./data` folder instead)

Named volumes below are created automatically on first `up` — nothing to pre-create by hand.
Every one of them can be redirected to a bind mount instead (e.g. if you'd rather the data live
under a directory you control, such as an NFS-mounted home dir that should carry the data with
it) by setting the matching `*_DIR` var in that service's `.env` — see its `.env.example` for
the exact name(s).

### List of Volumes

- `fabrication/sketchforge`: `sketchforge-shared-projects`
- `finance/firefly`: `firefly_iii_upload`, `firefly_iii_db`
- `home/adventurelog`: `postgres_data`, `adventurelog_media`
- `home/airtrail`: `db_data`
- `monitoring/autokuma`: `autokuma-data`
- `monitoring/uptime`: `up-data`
- `network/phpipam`: `phpipam-db-data`, `phpipam-logo`, `phpipam-ca`
- `notes/docmost`: `docmost`, `db_data`, `redis_data`
- `notes/trilium`: `tril-data`
- `notes/wikijs`: `wiki-data`
- `productivity/focalboard`: `fbdata`
- `productivity/monica`: `mysql`, `data`
- `productivity/n8n`: `db_storage`, `n8n_storage`
- `productivity/papermerge`: `postgres_data`, `index_db`, `media`

## TODO

- Would be neat to have a script that could auto add to the top level compose file
- also a script that could put all services into the dashboard, with running ones getting status lights
- And while we're at it, add them to the uptime monitor
  - or look more into the "autokuma" thing

## Organization

The base `docker-compose.yaml` + per-style `compose.<style>.yaml` override setup described
under [Deploy styles](#deploy-styles) is implemented, and services are grouped into category
sub-folders, each with its own aggregator compose file:

- `infra`, `admin-tools`, `monitoring`, `network`, `identity`, `notes`, `ai`, `productivity`,
  `files`, `finance`, `home`, `dev`, `media`, `lowcode`, `games`, `fabrication`.
- Every group has a `<group>/docker-compose.yaml` that `include:`s all of its members — enable
  a whole category at once with `- <group>/docker-compose.yaml` in a style file, or reach into
  a specific member directly with `- <group>/<service>/docker-compose.yaml` for finer control.
  `compose.local.yaml` uses the fine-grained form so every individual service stays toggleable.

Still TODO:

- Give each individual service compose file its own override file, for per-service tweaks
  independent of deploy style.

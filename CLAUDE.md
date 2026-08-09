# Self-Host

A collection of self-hosted services. Each service lives in its own directory (with its own
`docker-compose.yaml`) nested under a category group folder — see Organization below.
Originally built for RHEL 8 + podman; also runs on Docker.

## Organization

- Services are grouped into category folders at the repo root:
  `infra`, `admin-tools`, `monitoring`, `network`, `identity`, `notes`, `ai`, `productivity`,
  `files`, `finance`, `home`, `dev`, `media`, `lowcode`, `games`, `fabrication`. Each service
  keeps its own subdirectory under its group (e.g. `monitoring/gotify/docker-compose.yaml`).
- Every group folder has its own aggregator `<group>/docker-compose.yaml` that `include:`s
  every service in that group — use it to enable a whole category at once
  (`- monitoring/docker-compose.yaml`). For finer control, reference an individual service's
  compose file directly instead (`- monitoring/gotify/docker-compose.yaml`); both are valid
  `include:` targets from any other compose file.
- This grouping (2026-07-19) was a deliberate reorg for discoverability at ~50 services — see
  CLEANUP.md's Organization item for the reasoning and what was traded off (all path references
  repo-wide had to move together; there is no per-service top-level directory anymore).

## Launch mechanism

- Root [docker-compose.yaml](docker-compose.yaml) is the **base file** — it defines the shared
  `proxy` network plus Traefik and `whoami` (under `infra/`). It's a self-sufficient smoke test:
  `docker compose up -d` alone proves the network/Traefik/`.env` setup works.
- Additional services are opt-in via a **deploy style** override file at the repo root, named
  `compose.<style>.yaml`, each holding an `include:` list of *extra* service directories to
  turn on (don't re-include `traefik`/`whoami` — the base file already does). `compose.local.yaml`
  is the only style defined today.
- Launch/stop a style with:

  ```bash
  docker compose -f docker-compose.yaml -f compose.local.yaml up -d
  docker compose -f docker-compose.yaml -f compose.local.yaml down
  ```

- To add a new style, copy `compose.local.yaml` to `compose.<style>.yaml` and
  comment/uncomment services for that setup. Don't add a service's `include:` line to more
  than the styles it's actually meant for.
- There is no other launch path — `scripts/start.sh`/`stop.sh` (the old per-directory loop
  that bypassed the shared network) were removed 2026-07-19; don't reintroduce that pattern.

## Adding a new service

1. Pick the group folder it belongs in (or add a new group if nothing fits — update this file's
   Organization list and the group's aggregator file).
2. Create `<group>/<service>/docker-compose.yaml` with a `container_name`, `restart: always`, and
   Traefik labels following the pattern in [monitoring/gotify/docker-compose.yaml](monitoring/gotify/docker-compose.yaml)
   or [admin-tools/dozzle/docker-compose.yaml](admin-tools/dozzle/docker-compose.yaml) (both are clean references).
3. Add `- <group>/<service>/docker-compose.yaml` to that group's own aggregator
   `<group>/docker-compose.yaml` AND to whichever `compose.<style>.yaml` file(s) should run it.
4. Services join the shared `proxy` network by default (no explicit `networks:` needed) so
   Traefik can route to them via labels.
5. If the service needs credentials, don't hardcode them — see Secrets below.

## Secrets

- Never hardcode a real credential in a `docker-compose.yaml`. Use `${VAR}` interpolation
  (native var name the image/app expects) and let Compose pull `<service>/.env` — this is
  resolved relative to that service's own directory automatically, even when included from the
  root file, no `env_file:` directive required (verified against Compose's `include:` behavior).
- Every service with secrets gets a tracked `<service>/.env.example` (placeholder values,
  normally `changeme`) and a gitignored `<service>/.env` (real values) — same convention at the
  repo root (`.env.example` / `.env`).
- `.gitignore` excludes `*.env` with a `!*.env.example` carve-out, plus `.direnv/`. Don't
  reintroduce a plain `.env` (bare, no suffix) rule — it wouldn't catch variants like
  `.db.env`/`docker.env`, which is exactly the gap that let several real env files get
  committed before 2026-07-19 (see CLEANUP.md item 3).
- When one credential is shared across two containers in the same compose file under two
  different var names (e.g. an app's `DB_PASSWORD` vs. its database's `MYSQL_PASSWORD`), write
  the second `.env.example` line as `MYSQL_PASSWORD=$DB_PASSWORD` — [scripts/gen-secrets.sh](scripts/gen-secrets.sh)
  resolves that reference to whatever it generated for the first key, keeping them in sync.
  This only works within a single file; a service split across multiple env files (firefly's
  `.env`/`.db.env`/`.importer.env`) needs its shared password kept in sync by hand.
- Generate real values with `./scripts/gen-secrets.sh <service-dir>`, `--style <name>` (only
  what the base file + that `compose.<name>.yaml` enable — the one to use when standing up a
  style with many services at once), or `--all`. Skips files with nothing to actually generate
  (pure version-pin documentation, no secrets) and won't overwrite an existing `.env` without
  `--force`.
- firefly/airtrail/notebook's env files were untracked from git on 2026-07-19 but their actual
  values were not rotated (low-value/high-effort for local dev credentials) — their real `.env`
  files on disk still hold what was previously committed. The old lldap `LLDAP_JWT_SECRET` *was*
  rotated since it was flagged as a real secret, not a placeholder.

## Version pinning

- Every image tag is `${SERVICE_VERSION:-latest}` (or similar) — floats to latest by default,
  pin-able per deployment by setting the var in that service's `.env`, no compose file edits
  needed. This is a deliberate policy choice (2026-07-19), not an oversight: simplicity/always-
  current by default over CLEANUP.md's original "pin everything" framing.
- When a tag encodes a real *variant* (base OS like `-alpine`, container topology like
  `-single`, or a release *channel* like `lts`/`stable`/major-only `2`) rather than just a
  version, that variant stays hardcoded and only the floatable portion is a var — e.g.
  `postgres:${POSTGRES_VERSION:-latest}-alpine`, `mariadb:${MARIADB_VERSION:-lts}`,
  `ghcr.io/requarks/wiki:${WIKIJS_VERSION:-2}`. Never collapse these to bare `${VAR:-latest}` —
  that silently swaps the variant (different base OS, wrong container topology, or a bleeding-
  edge channel the deployment didn't ask for) for anyone who doesn't override it.
- The one exception with no `latest` fallback at all:
  [identity/freeipa](identity/freeipa/docker-compose.yaml) — its tags are OS-variant-specific
  (fedora-41, rocky-9, ...), no generic rolling tag exists. Its var defaults to the current pin
  (`fedora-41`), not `latest`. Verify against the actual registry before assuming any other
  image needs the same treatment — don't guess from memory which tags exist.
- Every service directory has a `.env.example` documenting its version var(s) (commented out —
  the default already works with zero config). Compose only auto-loads a file literally named
  `.env` for `${VAR}` interpolation; a directory whose only env file is named something else
  (e.g. notebook's `docker.env`, wired via `env_file:` for app config) needs its own separate
  plain `.env`/`.env.example` just for version vars — `env_file:` and interpolation are
  unrelated mechanisms that happen to often read the same file.
- The 5 locally-built images (jenkins, sketchforge, testing/test, ai/comfyui, ai/automatic1111)
  are intentionally
  excluded — there's no registry tag to pin, they build from a local Dockerfile.

## Volumes

- Prefer bind mounts over Docker-managed named volumes — the repo owner has been burned by
  named volumes not traveling with an NFS-mounted home directory across machines the way a bind
  mount under that same home dir would. Every service with a named volume uses
  `${SERVICE_DATA_DIR:-volume-name}` on its volume mount line (same pattern as Trilium/Monica
  originally): defaults to a Docker-managed named volume with zero config, override to any bind
  path by setting that var in the service's `.env`.
- Every named volume also explicitly declares `name:` + `external: false`. Never leave a volume
  as a bare `volume-name:` with no attributes — besides being implicit about it defaulting to
  `external: false`, it's what let two *different* services (adventurelog/papermerge both used
  `postgres_data`; airtrail/docmost both used `db_data`) risk colliding onto the same actual
  Docker volume. Check for name collisions repo-wide before adding a new one:
  `grep -rhoE '^\s+name:\s*\S+' --include='docker-compose.y*ml' . | sort | uniq -c | sort -rn`.
- `external: true` is reserved for its actual purpose — pointing at a volume that already
  exists from migrating a different version of this project, or some other standalone launch —
  never the silent default.

## Docker socket access

- Never mount `/var/run/docker.sock` directly into a service. Everything that needs Docker API
  access goes through [infra/socket](infra/socket/docker-compose.yaml)
  (`tecnativa/docker-socket-proxy`) instead, at `tcp://socket-proxy:2375` — direct socket access
  is root-equivalent host control, full stop.
- The env var/flag for pointing a tool at the proxy **differs per tool** — verify against that
  tool's actual docs/source before assuming a pattern, don't guess from what another tool uses.
  Confirmed so far: generic `DOCKER_HOST` (watchtower, lazydocker, glances, olivetin — the last
  because its image bundles the real `docker` CLI, which respects that var); `DOZZLE_REMOTE_HOST`
  for dozzle (its own var, NOT `DOCKER_HOST`); `AUTOKUMA__DOCKER__HOSTS` for autokuma;
  `--providers.docker.endpoint=` for traefik. uptime-kuma is the odd one out — its Docker Host
  config lives in its own DB via the Settings UI, not an env var or compose setting at all, so
  there's nothing to wire up in the compose file beyond removing the socket mount.
- Any service switched to the proxy needs an explicit `networks: [default, socket_proxy]` (it
  no longer gets `default` implicitly once `networks:` is set at all) plus, if it has an active
  Traefik route, a `traefik.docker.network=proxy` label — Traefik needs to be told which of the
  container's two networks to route through once it's multi-homed.
- The proxy's permission env vars (`CONTAINERS`, `POST`, `EXEC`, etc. in
  infra/socket/docker-compose.yaml) gate what any connected consumer can do — check what a new
  consumer actually needs before assuming the current grants cover it. `EXEC=0` currently means
  lazydocker's "shell into a container" feature won't work through the proxy; left that way
  deliberately (security-restrictive default), not an oversight.

## Traefik labels and monitoring

- Traefik runs with `--providers.docker.exposedByDefault=false` — a route needs an explicit
  `traefik.enable=true` label, full stop. A container with a published port and no label simply
  isn't routed; don't rely on Traefik's default-rule fallback.
- Routing is subdomain-only: every rule is a `Host()` match on `name.$HOST`, never `PathPrefix`. Some
  services (confirmed for Uptime Kuma) break under a path prefix — they assume they own the
  whole origin and don't respect a base-path config. Stick to subdomains for any new service.
- A `labels:` key with every line commented out parses as an empty mapping and fails Compose
  validation — if a route is fully disabled, comment out the whole block including the
  `labels:` line itself (or drop it), don't leave a label key with nothing but comments under it.
- If a service is defined via a YAML anchor (`x-something: &common`) that itself sets `labels:`,
  remember `<<:` merge does not merge list values — a service that also defines its own
  `labels:` list overrides the anchor's entirely rather than combining with it. Put
  `traefik.enable=true` in each service's own label list, not just the shared anchor (bit us in
  `media/calibre`, see CLEANUP.md item 13).
- Every service with an active Traefik route also gets AutoKuma monitor labels
  ([monitoring/autokuma](monitoring/autokuma/docker-compose.yaml) auto-registers Uptime Kuma
  monitors from Docker labels): `kuma.<id>.http.name=<Display Name>` and
  `kuma.<id>.http.url=http://<container_name>:<port>`, reusing the same short `<id>` as the
  Traefik router. Point at the internal container:port, not the public `$HOST` hostname — it
  doesn't depend on `$HOST` resolving back to Traefik from inside Uptime Kuma's own container.
  Skip the label (with a comment explaining why) for anything not actually reachable over the
  shared network — e.g. a service on its own isolated network, or one running
  `network_mode: host`.

## Known repo debt

See [CLEANUP.md](CLEANUP.md) for the full, prioritized audit (version pinning, secrets
hygiene, dead content, Traefik/network consistency, shared compose fragments). Check items
off there as they're addressed rather than re-deriving this list from scratch.

## Experimental: living memory stack

`compose.knowledge.yaml` stands up a proof-of-concept human-writes/AI-queries loop
(Docmost + Open Notebook). See [KNOWLEDGE.md](KNOWLEDGE.md) before touching or extending
it — it records why MegaMemory was rejected for this, what's been validated, real upstream
gotchas hit along the way (Postgres 18 volume/tag changes, Open Notebook API bugs), and the
open question of whether this holds up off of one beefy box.

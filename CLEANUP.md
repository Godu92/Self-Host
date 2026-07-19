# Cleanup / Modernization TODO

Living checklist from the 2026-07-16 repo audit. Goal: turn this into a well-organized
"swiss army knife" toolkit where the right compose file gets used for the right setup.
Check items off as they're addressed; add new findings as they turn up.

## 1. Reconcile the two competing launch mechanisms (highest priority) — DONE (2026-07-19)

- [x] Decided on ONE mechanism: base [docker-compose.yaml](docker-compose.yaml) (networks only)
      plus a per-deploy-style override, e.g. [compose.local.yaml](compose.local.yaml), merged at
      launch (`docker compose -f docker-compose.yaml -f compose.local.yaml up -d`). See README.
- [x] `scripts/start.sh`/`stop.sh` retired entirely (deleted) — no more independent per-dir
      Compose projects bypassing the shared `proxy` network.
- [x] Drifting `EXCLUDED_DIRS`/enabled-service lists converged to one list: whatever's
      uncommented in the active `compose.<style>.yaml`.
- [x] The `main` docker network step is gone along with `start.sh`.
- [x] `set -e`/`eval`/cwd-assumption bugs are moot — the scripts no longer exist.
- [x] Base `docker-compose.yaml` now enables Traefik + whoami directly, making it a
      self-contained smoke test (`docker compose up -d` with no `-f` flags). `compose.local.yaml`
      layers glances + dashy on top for a small local/dev setup.
- [ ] Only `local` style is defined so far. Add more styles (`work-server`, `family-server`,
      etc.) by copying `compose.local.yaml` to `compose.<style>.yaml` and toggling services,
      once there's a concrete need for a second style.

## 2. Version pinning — DONE (2026-07-19), different resolution than originally scoped

Original framing was "standardize on pinned versions." Actual direction taken, per explicit
preference: standardize on **`${SERVICE_VERSION:-latest}`** everywhere instead — floats by
default (simplicity, always-current for a homelab), but every image becomes pin-able per
deployment by setting a var in that service's `.env`, with no compose file edits needed.

- [x] All ~49 registry-pulled images (every `docker-compose.y*ml` except the 3 locally-built
      ones: jenkins, sketchforge, testing/test) converted from a hardcoded tag (or no tag at
      all, which was silently `latest` anyway) to `${VAR:-latest}` interpolation.
- [x] Verified against the real registries (Docker Hub, ghcr.io, docker.gitea.com,
      docker.n8n.io) rather than assumed — only
      [identity/freeipa/freeipa-server](identity/freeipa/docker-compose.yaml) has **no** generic `latest` tag at
      all (its tags are OS-variant-specific: fedora-41/43/44, rocky-9, almalinux-9, ...). Its
      fallback stays the current pin (`fedora-41`), not `latest`.
- [x] Tags that encode a real *variant*, not just a version, keep that variant hardcoded and
      only the version/channel portion floats via the env var:
      - `postgres:${POSTGRES_VERSION:-latest}-alpine` / `redis:${REDIS_VERSION:-latest}-alpine`
        (wikijs, docmost, airtrail) — alpine vs. the default Debian-based image is a real base-OS
        difference, not just a version bump.
      - `postgis/postgis:${POSTGIS_VERSION:-latest}-3.3` (adventurelog) — same idea, `-3.3` is
        the PostGIS extension version bundled with the Postgis major version.
      - `lfnovo/open_notebook:${OPEN_NOTEBOOK_VERSION:-latest}-single` (notebook) — `-single` is
        a different container *topology* (single container vs. multi-container), not a version.
      - `ghcr.io/requarks/wiki:${WIKIJS_VERSION:-2}` — defaults to major-version-only `2`
        (matches upstream's own convention), not bare `latest`, since wiki.js major bumps can
        break things.
      - `mariadb:${MARIADB_VERSION:-lts}` (firefly) and `lldap/lldap:${LLDAP_VERSION:-stable}` —
        `lts`/`stable` are release *channels*, not version numbers; kept as the default rather
        than switching to bleeding-edge `latest`.
- [x] Every service directory (except the 3 local builds) now has a `.env.example` documenting
      its version var(s) (commented out, since the default already works with zero config).
      Directories that already had a `.env.example` for secrets got the version var(s) appended.
      Caveat found along the way: Compose only auto-loads a file literally named `.env` for
      interpolation — `notebook/opennotebook-single/docker.env` (env_file-only, app config) does
      **not** get read for `${VAR}` substitution, so that directory needed its own separate
      plain `.env.example` just for `OPEN_NOTEBOOK_VERSION`/`OLLAMA_VERSION`.
- [x] Found and fixed two unrelated pre-existing bugs while touching every file:
      `media/calibre/docker-compose.yaml` had `<<: &common` (defines an anchor) where it meant
      `<<: *common` (dereferences one) — silently broken YAML merge, fixed to `*common`.
      papermerge's `.env.example` was missing entirely from the secrets pass (item 3) even
      though its real `.env` existed — added.
- [ ] Not fixed (found but out of scope, pre-existing and unrelated to versioning):
      `notes/dailynotes/docker-compose.yaml` references `./config/.env` which doesn't exist on disk;
      `infra/socket/docker-compose.yaml`'s `socket-proxy` service references a `socket_proxy` network
      that's only ever defined (commented out) in the base `docker-compose.yaml` — the "eventual
      socket proxy" mentioned in README is not wired up yet.

## 3. Secrets / credentials hygiene — DONE (2026-07-19)

- [x] Rotated [identity/lldap/docker-compose.yaml](identity/lldap/docker-compose.yaml) `LLDAP_JWT_SECRET` — the
      old committed value is retired; treat it as compromised if it was ever actually deployed.
- [x] Hardcoded placeholder passwords moved to `${VAR}` interpolation + a tracked
      `.env.example`/gitignored `.env` per directory: pihole, phpipam, monica, n8n, wikijs,
      papermerge, adventurelog, freeipa, docmost, directus, lldap. Fresh random values were
      generated for all of these (none had live data — verified no running containers/volumes
      existed before rotating).
- [x] Along the way, fixed a real bug this surfaced: n8n's Postgres healthcheck was checking
      `-d changePassword` (the password, not the db name) — now `-d n8n`.
- [x] Tracked `.env` files untracked (`git rm --cached`, kept on disk) and given `.env.example`
      counterparts: `firefly/.env`, `firefly/.db.env`, `firefly/.importer.env`,
      `airtrail/.env`, `notebook/opennotebook-single/docker.env`. Their actual values were
      **not** rotated (low value for local-dev-only credentials vs. effort — they're multi-file
      services where the same password is split across files gen-secrets.sh can't link
      automatically). Root `.env-dev` renamed to `.env.example` for naming consistency; it only
      ever held non-secret values (`HOST`/`DOCKER_DIR`/etc.).
- [x] Adopted a repo-wide convention: every service with secrets gets a tracked
      `<service>/.env.example` and a gitignored `<service>/.env`. `.gitignore`'s bare `.env`
      rule was broadened to `*.env` (+ `!*.env.example`) since the bare form was only ever
      catching exact-name `.env` files, not `.db.env`/`docker.env` variants — which is exactly
      how firefly/notebook's extra env files ended up committed in the first place.
- [x] Added [scripts/gen-secrets.sh](scripts/gen-secrets.sh) to generate a real `.env` from any
      `.env.example`, including a `$OTHERKEY` reference syntax for credentials shared across two
      containers in the same file. Doesn't handle cross-*file* shared credentials (see firefly
      note above) — out of scope, do that by hand.
- [x] Added root `.envrc` (direnv) that loads `.env` and fixes `HOSTNAME` with a real
      shell-evaluated hostname — `.env` alone can't shell-substitute `$(hostname)`, which was a
      latent, silently-broken value before.
- [ ] Not addressed: git *history* still contains the old committed secret values (lldap JWT,
      firefly/airtrail/notebook passwords, etc.). Untracking only stops *future* commits from
      exposing them — a true purge needs history rewriting (e.g. `git filter-repo`), which is
      disruptive enough (rewrites shas, needs a force-push, breaks other clones) that it should
      be a deliberate, explicitly-requested follow-up, not a side effect of a cleanup pass.

## 4. Dead/stale content

- [x] `remoteRhel` and `tenable` were referenced (README, `start.sh` EXCLUDED_DIRS, root
      compose comments) but no such directories exist. Purged along with `start.sh`/`stop.sh`
      and the old root compose include list (see item 1).
- [ ] [dev/testing/docker-compose.yaml](dev/testing/docker-compose.yaml) still points at a defunct
      `Godu92/Remote-Rhel` GitHub repo — update or remove.
- [ ] Root-level `./data/` is live Trilium data (not dead) but is owned by a different Unix
      user (`geadmin`) than the repo owner — check for a permissions/ownership drift issue.
      There's also an odd nested duplicate `data/styles/document.db*` worth investigating.
      **Action needed on the real server**: `TRILIUM_DATA_DIR` moved from the root `.env` to
      [notes/trilium/.env](notes/trilium/.env) on 2026-07-19 (there was no good reason for a
      trilium-specific setting to live at the repo root, and it wasn't even being read from
      there anymore — see below). Compose resolves a relative bind path in an *included* file
      relative to *that file's own directory*, so `TRILIUM_DATA_DIR=./data` now means
      `trilium/data`, not the repo root. On the real server, either move the live data
      directory to `trilium/data` or set `TRILIUM_DATA_DIR` in `trilium/.env` to an absolute
      path pointing at wherever the old `./data` actually lives. Until that's done there,
      starting trilium fresh would silently create a new, empty `trilium/data` instead of using
      the existing one.
- [ ] [jenkins/data/](jenkins/data/) holds a full real Jenkins home dir (credentials.xml,
      secret.key, etc.) on disk next to tracked source — not git-tracked today, but consider
      moving state outside the repo tree entirely for portability.
- [ ] README's "Storage / List of Volumes" section only documents Monica/Uptime/Trilium even
      though 14 compose files define named volumes — update docs to match reality.

## 5. Traefik / networking consistency

- [ ] [finance/firefly/docker-compose.yaml](finance/firefly/docker-compose.yaml) defines its own isolated
      network — not reachable via Traefik as currently configured. Fix to join `proxy`, or
      document why it's intentionally isolated.
- [ ] Traefik provisions HTTPS (`:443`) but no service label ever uses an `https` entrypoint —
      either wire up TLS (cert resolver) or drop the unused entrypoint.
- [ ] `infra/traefik/docker-compose.yaml` runs `--api.insecure=true` and exposes the dashboard on
      `8080` with no auth — add basic auth or bind to localhost only.
- [ ] Two files use `.yml` instead of the otherwise-universal `.yaml`:
      [home/airtrail/docker-compose.yml](home/airtrail/docker-compose.yml),
      [home/adventurelog/docker-compose.yml](home/adventurelog/docker-compose.yml). Rename for consistency.
- [ ] Inconsistent `restart:` policy: `always` (majority) vs `unless-stopped` (autokuma,
      phpipam, netalertx, freeipa, notebook) — pick one default.

## 6. Structural duplication — factor into a shared fragment

Nearly every service repeats: `restart: always`, implicit `proxy` network membership, the
same 4-line Traefik label block, and `container_name`. This is exactly what the root file's
own TODO comment already flags.

- [ ] Build a Compose `x-*` anchor / shared fragment for the common boilerplate
      (restart policy, Traefik labels, network).
- [ ] Use these as the clean reference examples when designing the fragment:
      [gotify](gotify/docker-compose.yaml), [dozzle](dozzle/docker-compose.yaml),
      [netalertx](netalertx/docker-compose.yaml), [glances](glances/docker-compose.yaml).
- [ ] Multi-container stacks each hand-roll their own Postgres/MariaDB/Redis: docmost, n8n,
      firefly, phpipam, monica, adventurelog, papermerge, airtrail, wikijs. README's own TODO
      ("merge databases into one PostgreSQL") is still unaddressed — evaluate consolidating.

## 7. Tooling bugs / misc

- [ ] [scripts/run2compose.py](scripts/run2compose.py): `inner_port` is referenced
      unconditionally when building the Traefik port label but is only set if `-p` was passed
      in the source `docker run` command — throws `UnboundLocalError` otherwise. Also only
      handles `-p`/`-v`/`-e` flags (silently drops everything else, e.g. `--name`, `-d`,
      `--network`, env files).
- [ ] `run2compose.py`'s `create_networks()` (looks up a running Traefik container's network
      via the `docker` SDK) appears untested/unused by `start.sh`/`stop.sh` — decide whether to
      wire it in or drop it.
- [ ] No tracked `requirements.txt`/lockfile at the root for `run2compose.py`'s dependencies
      (`docker`, `yaml`) even though [self-host.code-workspace](self-host.code-workspace) implies
      a `.venv` convention. (Note: `scripts/requirements.txt` does exist — confirm it's current
      and referenced from docs.)
- [ ] `.vscode/` directory is empty/vestigial now that `self-host.code-workspace` covers that
      role — remove or populate.
- [ ] [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) is generic
      (docker-outside-of-docker + python) and doesn't bootstrap this repo's stack
      (no postCreateCommand, no forwarded ports) — low priority, but an opportunity.

## 8. Documentation

- [x] README's `EXCLUDED_DIRS` example vs. `scripts/start.sh`'s array — moot, both gone; the
      enabled-service list now lives in one place, `compose.<style>.yaml` (see item 1).
- [ ] README TODOs still open: "template files for commonly used files," "script to auto-add
      to top-level compose," "script to add services to dashboard + uptime monitor," "merge
      databases," "set more containers to docker volumes," "add `.env` bind option for all
      mounts." Fold into this list once prioritized, or keep as long-term wishlist below.

## 9. Folder/group reorganization — DONE (2026-07-19)

README's Organization section had long flagged "each grouping/section can be its own sub-folder"
as a TODO. Executed:

- [x] All ~51 service directories moved into 16 category folders: `infra`, `admin-tools`,
      `monitoring`, `network`, `identity`, `notes`, `ai`, `productivity`, `files`, `finance`,
      `home`, `dev`, `media`, `lowcode`, `games`, `fabrication`. Each keeps its own
      subdirectory unchanged internally (e.g. `monitoring/gotify/`), just nested one level
      deeper than before.
- [x] Every group got its own aggregator `<group>/docker-compose.yaml` that `include:`s all its
      members — lets a style enable a whole category in one line
      (`- monitoring/docker-compose.yaml`) while `compose.local.yaml` still lists every
      individual service (finer-grained toggling stays available via
      `- monitoring/gotify/docker-compose.yaml`).
- [x] Root `docker-compose.yaml`, `compose.local.yaml`, `.gitignore`, `README.md`, `CLAUDE.md`
      all updated for the new paths. `scripts/gen-secrets.sh` needed **no** changes — its path
      handling was already generic enough for nested directories.
- [x] Rationale explicitly wasn't about a live multi-user deployment: this repo is
      single-operator across ~6 machines, only 2 of which have real bind-mounted data to worry
      about, and the payoff (findability, and folders doubling as deploy-style targets) was
      judged worth the one-time churn of every path moving at once. Don't re-litigate this
      trade-off assuming a different (e.g. team/shared) context.
- [ ] Not yet done: per-service override files (README's other still-open Organization TODO,
      independent of this reorg).

---

## Longer-term wishlist (from README, not yet scoped)

- Script to auto-register a service into the root `docker-compose.yaml` `include:` list.
- Script to auto-populate the Dashy dashboard with all services, with live status.
- Script to auto-register services with the uptime monitor.
- Standardize template files (Dockerfile, docker-compose.yaml) beyond the single `dev/testing/` example.

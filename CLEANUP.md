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
- [x] [dev/testing/docker-compose.yaml](dev/testing/docker-compose.yaml) pointed at a defunct
      `Godu92/Remote-Rhel` GitHub repo and an EOL'd `debian:jessie` base image (no security
      updates since 2020) — updated example args to the real repo (`Godu92/Self-Host`) and
      `debian:bookworm` in both the compose file and `dev/testing/Dockerfile`'s default ARG.
- [x] Root-level `./data/` live Trilium data / `geadmin` ownership drift / nested duplicate
      `data/styles/document.db*` — confirmed with the repo owner this is real state on one of
      their actual running machines, not something in any checkout this assistant has access
      to, and is being handled by hand there. **Still true and unresolved on that machine**:
      `TRILIUM_DATA_DIR` moved from the root `.env` to [notes/trilium/.env](notes/trilium/.env)
      on 2026-07-19, and since Compose resolves a relative bind path in an *included* file
      relative to *that file's own directory*, `TRILIUM_DATA_DIR=./data` now means
      `notes/trilium/data`, not the repo root — the real server needs the data directory moved
      (or `TRILIUM_DATA_DIR` there set to an absolute path at the old location) before starting
      trilium fresh, or it'll silently create a new empty directory instead of using the
      existing one.
- [ ] [dev/jenkins/](dev/jenkins/) has no `data/` in this checkout (just `Dockerfile` +
      `docker-compose.yaml`) — confirmed with the repo owner: same story as Trilium above, this
      machine is clean but other machines this repo runs on are not, and `dev/jenkins/data/`
      (real credentials.xml/secret.key etc.) is expected to exist there. **Leave this note in
      place as a migration warning** rather than removing it as stale just because it's absent
      here — don't delete "lives on a real machine, not this checkout" notes without confirming
      first, since a clean checkout is exactly what you'd expect regardless of whether the note
      is still true elsewhere. The "move state outside the repo tree for portability" suggestion
      still stands as unaddressed.
- [x] README's "Storage / List of Volumes" section only documented Monica/Uptime/Trilium even
      though 14 compose files define named volumes — now lists all 14 (with their new
      group-prefixed paths). Also dropped a stale note about changing `external: true` to
      `false` — nothing in the repo actually sets that on a volume (the one `external: true` in
      the repo is a *network* declaration in notebook's compose file, not a volume).

## 5. Traefik / networking consistency

- [ ] [finance/firefly/docker-compose.yaml](finance/firefly/docker-compose.yaml) defines its own isolated
      network — not reachable via Traefik as currently configured. Fix to join `proxy`, or
      document why it's intentionally isolated. Also now blocks the autokuma monitor labels
      added in item 13 for the same reason — see the comment left in that file.
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

## 10. Volume declaration hygiene — DONE (2026-07-19)

Original framing was just "make `external: false` explicit everywhere." Revised after
discussion: the repo owner strongly prefers bind mounts over Docker-managed named volumes in
general — burned before by named volumes not traveling with an NFS-mounted home directory
across machines, unlike a bind mount under that same home dir. Final approach implemented:

- [x] Every one of the 14 services with named volumes (see README's List of Volumes) now uses
      the same pattern already established for Trilium/Monica: `${SERVICE_DATA_DIR:-volume-name}`
      on the service's volume mount line, so it defaults to a Docker-managed named volume with
      zero config, but can be redirected to any bind mount path by setting one var in that
      service's `.env` (documented, commented out, in each `.env.example`).
- [x] Every named volume also now explicitly declares `name:` + `external: false` (the original
      item 2 ask) — done as part of the same pass since both touch the same lines.
- [x] Found and fixed a real bug this surfaced, not just a style issue: `postgres_data` was
      used as the literal volume key by *both* home/adventurelog and productivity/papermerge,
      and `db_data` by *both* home/airtrail and notes/docmost. Without an explicit unique
      `name:`, two unrelated services could have collided onto the same actual Docker volume —
      renamed to `adventurelog_postgres_data`/`papermerge_postgres_data` and
      `airtrail_db_data`/`docmost_db_data` respectively. Verified no other name collisions exist
      repo-wide after the fix.
- [ ] **Migration note for any of these 10 services if actually deployed elsewhere** (this
      machine is clean, but per the Trilium/jenkins precedent, other machines may not be): 10 of
      the 14 previously declared a *bare* volume name with no explicit `name:` at all, which
      means Compose was auto-generating the actual volume name from whatever project name was
      in effect at launch time — a value that isn't even guaranteed to be the same every time
      given this repo's multiple launch paths (base+style, a group aggregator alone, or a single
      service alone all can compute a different implicit project name). If any of these 10 are
      running with real data on another machine, check what Docker volume they're actually
      using (`docker inspect <container>` or `docker volume ls`) before pulling this change and
      confirm it matches the new explicit name here, or the next `up` will silently create a
      fresh empty volume instead of finding the existing one.

## 11. Docker socket exposure — DONE (2026-07-19)

Raised while discussing network segmentation ("VLANs"): 8 services mounted the raw
`/var/run/docker.sock` directly (dozzle, glances, lazydocker, olivetin, watchtower, autokuma,
uptime-kuma, plus traefik itself). Docker socket access is root-equivalent host control —
network segmentation between groups does nothing to contain a compromised container that has
it, since it can just launch a new privileged container regardless of which network it's on.
Judged higher-value to fix than the VLAN idea (see item 12), which is deferred.

- [x] [infra/socket](infra/socket/docker-compose.yaml) (`tecnativa/docker-socket-proxy`) is now
      actually wired in — was fully defined before but never included anywhere (`socket_proxy`
      network was commented out, its own `include:` line was commented out). Now included in
      the base `docker-compose.yaml` alongside Traefik.
- [x] Every one of the 8 consumers switched from mounting `docker.sock` directly to connecting
      through the proxy over the network at `tcp://socket-proxy:2375`, verified per-app since
      the mechanism differs by tool (none of this was guessed — see chat history for the actual
      docs/source lines checked):
      - `DOCKER_HOST=tcp://socket-proxy:2375`: watchtower, lazydocker, glances (`docker.from_env()`
        respects it), olivetin (bundles the real `docker` CLI in its image, confirmed from its
        Dockerfile — needed for any button that shells out to `docker ...`).
      - `DOZZLE_REMOTE_HOST=tcp://socket-proxy:2375`: dozzle — its own var, **not** `DOCKER_HOST`.
      - `AUTOKUMA__DOCKER__HOSTS=tcp://socket-proxy:2375`: autokuma — its own var.
      - `--providers.docker.endpoint=tcp://socket-proxy:2375`: traefik.
      - uptime-kuma: **not a compose-level change at all** — its Docker Host config is stored in
        its own DB via the Settings UI, not an env var. Docker.sock mount removed; to use it,
        add a Docker Host of type `tcp` pointing at `tcp://socket-proxy:2375` through the UI.
- [x] Every switched service got an explicit `networks: [default, socket_proxy]` (previously
      relied on implicit-only `default`) plus a `traefik.docker.network=proxy` label on any
      service with an active route, needed now that Traefik has two networks to choose between
      for routing to a multi-homed container.
- [x] Found and fixed two small unrelated bugs while touching these exact files:
      `infra/socket/docker-compose.yaml` had `$DOCKER_DIR.sock` (an erroneous extra `.sock`
      suffix on a var that's already the full path — would have resolved to
      `/var/run/docker.sock.sock`); `monitoring/uptime/docker-compose.yaml` had
      `traefik.docker.network=main`, a stale reference to the `main` network `start.sh` used to
      create (removed along with `start.sh` itself back in item 1) — both fixed.
- [x] Dropped the non-functional Traefik labels on `socket-proxy` itself (it was only ever on
      the `socket_proxy` network, never `proxy`, so they could never have routed anything) —
      also not something a raw Docker API endpoint should be web-exposed through in the first
      place.
- [ ] Found but explicitly out of scope for this pass: `admin-tools/watchtower` and
      `admin-tools/lazydocker` both have Traefik routing labels despite neither tool having an
      HTTP UI to route to (watchtower's is also missing a `loadbalancer.server.port` label,
      lazydocker's targets a typo'd `lazy.locahost` host) — these routes were already
      non-functional before this change and remain so; only the socket connectivity was in
      scope here. lazydocker in particular is normally an interactive `docker run -it` tool, not
      really designed to run as a persistent background service — worth reconsidering whether
      it belongs in this stack at all, separate from this item.
- [ ] Not addressed: whether `monitoring/netalertx` (needs `network_mode: host` for ARP
      scanning, per its own compose file) actually works correctly was raised in passing and not
      investigated — separate from docker socket exposure, flagging so it isn't lost.
- [ ] EXEC is still `0` on the socket-proxy, so lazydocker's "shell into a container" feature
      won't work through it — left restricted by default per the file's existing security
      stance; revisit if that feature turns out to matter in practice.

## 12. Network segmentation ("VLANs") — discussed, deferred

Explored putting groups (or specific sensitive services) on isolated Docker networks so a
compromised container in one group can't reach another's containers/database. Not implemented
yet — deferred after realizing identity services (freeipa/lldap) would need broad reachability
across groups anyway to actually serve auth for everything else, which cuts against isolating
`identity` specifically, and that the docker-socket-exposure problem (item 11, now fixed) was
judged the bigger actual risk for this repo's threat model. Revisit if/when specific groups
still feel worth isolating despite the added complexity of every service needing an explicit
`networks:` list (today everything implicitly shares one flat `proxy` network).

## 13. Traefik label cleanup + AutoKuma wiring — DONE (2026-07-19)

Two related passes: tidying up years of copy-pasted/inconsistent Traefik labels, and actually
getting AutoKuma to auto-register Uptime Kuma monitors (it was fully defined but pointed at the
wrong URL and had no credentials — same "wired but never actually connected" pattern as the
socket-proxy in item 11).

- [x] `infra/traefik/docker-compose.yaml` now sets `--providers.docker.exposedByDefault=false`.
      Previously (Traefik's own default) *any* container on the `proxy` network with a published
      port could get auto-routed via Traefik's default-rule fallback even without a
      `traefik.enable=true` label — now every route requires explicit opt-in, matching how the
      repo already used labels everywhere in practice.
- [x] Removed `traefik.enable=true` labels that had no accompanying router (dead weight, a
      side effect of the exposedByDefault change above making them newly meaningless): the
      db/redis backends behind docmost, papermerge, monica, adventurelog, wikijs; n8n's postgres
      (whose commented-out router template pointed at port 443 — copy-pasted from an unrelated
      service and never valid for a database); autokuma itself (see below); and
      `admin-tools/watchtower` / `admin-tools/lazydocker`, previously flagged in item 11 as
      having routes with no HTTP UI to route to at all — removed rather than patched.
- [x] Found and fixed a real bug via `docker compose config` validation:
      [media/calibre/docker-compose.yaml](media/calibre/docker-compose.yaml) set
      `traefik.enable=true` only in its `x-settings` YAML anchor, but both services also define
      their own `labels:` list — the anchor's `<<:` merge doesn't merge list values, so the
      per-service list fully overrode the anchor's and `traefik.enable` never actually reached
      either container. Moved `traefik.enable=true` into each service's own label list.
- [x] Standardized label syntax: `media/gopeed`, `network/pihole`,
      `productivity/super-prod` used Traefik's map-style labels (`key: value`) instead of the
      list-style (`- key=value`) used everywhere else in the repo, and all three were missing an
      `entrypoints` label as a result. Converted to list-style, added `entrypoints=http`.
- [x] `media/gopeed` also had `Host(\`gopeed.universe-sal.duckdns.org\`)` hardcoded — a real
      domain, evidently carried over unedited from whatever CasaOS app-store template this
      service was originally copied from — genericized to `gopeed.$HOST` to match every other
      service's convention.
- [x] `network/pihole` had `VIRTUAL_HOST: pihole.$HOST` in its environment — a leftover from a
      different reverse-proxy convention (nginx-proxy/docker-gen), never consumed by Traefik at
      all. Removed.
- [x] Standardized quoting: removed unnecessary `"quotes"` around label strings in
      `admin-tools/lazydocker`, `files/filebrowser`, `productivity/ittools` to match the
      unquoted convention used by the rest of the repo. Also fixed lazydocker's `lazy.locahost`
      typo while touching that file — moot now since the whole route was removed, see above.
- [x] AutoKuma ([monitoring/autokuma](monitoring/autokuma/docker-compose.yaml)) was pointed at
      `AUTOKUMA__KUMA__URL: http://localhost:3001` — wrong, since it and Uptime Kuma are separate
      containers; fixed to `http://uptime-kuma:3001`. Added real
      `AUTOKUMA_KUMA_USERNAME`/`AUTOKUMA_KUMA_PASSWORD` env vars (`monitoring/autokuma/.env.example`)
      — Uptime Kuma has no env-based initial-admin setup, so these can't be auto-generated by
      `gen-secrets.sh`; they have to be set by hand to match an account created once through
      Uptime Kuma's own first-run web UI. Also dropped a commented-out router template pointing
      at port 3001 — AutoKuma has no HTTP server of its own (confirmed against its docs/source),
      that port was Uptime Kuma's, copy-pasted in error.
- [x] Added `kuma.<id>.http.name` / `kuma.<id>.http.url` labels (AutoKuma's Docker-label
      monitor source, default `kuma` prefix) to all 44 services that have an active Traefik
      route, one router id at a time, reusing the same short id already used for the Traefik
      router (`kuma.doc.http.name=Docmost`, etc). URLs point at the internal
      `http://<container_name>:<port>` rather than the public `$HOST`-based hostname — doesn't
      depend on `$HOST` actually resolving back to Traefik from inside Uptime Kuma's own
      container, and still works for anything without a Traefik route at all.
- [x] Two services were deliberately left without a `kuma.*` label despite having an active
      Traefik route, each with a comment explaining why: `finance/firefly` sits on its own
      isolated network (see item 5) so `http://firefly_iii_core:8080` isn't actually reachable
      from Uptime Kuma; `monitoring/netalertx` runs `network_mode: host` (needed for ARP
      scanning) so it has no container-name DNS entry on the shared network at all — reaching it
      would require the host's real LAN address, which varies per machine.
- [x] `monitoring/changedetect`'s `browser-sockpuppet-chrome` and `files/nextcloud` both had a
      `labels:` key containing only commented-out lines — parses as an empty/null mapping, which
      broke `docker compose config` validation once actually exercised end-to-end. Rewrote as a
      plain comment block (not a `labels:` key) documenting how to enable a route later.

---

## Longer-term wishlist (from README, not yet scoped)

- Script to auto-register a service into the root `docker-compose.yaml` `include:` list.
- Script to auto-populate the Dashy dashboard with all services, with live status.
- Standardize template files (Dockerfile, docker-compose.yaml) beyond the single `dev/testing/` example.
- Other auto-configuration opportunities, in the same spirit as the AutoKuma wiring in item 13
  (e.g. LDAP/IPA pre-seeded with users, groups, or service accounts for the rest of the stack to
  bind against, instead of each service being configured against identity by hand). Not scoped
  yet — flagged 2026-07-19 while working on AutoKuma as a pattern worth extending.

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

## 2. Version pinning

Roughly half of ~60 image references float. Standardize on pinned versions.

- [ ] Explicit `:latest` (pin these): pxe, dozzle, nextcloud, docmost (app image), pihole,
      jenkins (local build), notebook/opennotebook-single (open_notebook + ollama), autokuma,
      phpipam (www + cron), netalertx, super-prod, stirlingpdf, dashy, glances, adventurelog
      (frontend/backend), calibre (calibre-web + calibre), kavita, trilium, grocy.
- [ ] No tag at all (defaults to latest silently — worse, since it's invisible in the file):
      wordle, ittools, jdownloader, filebrowser, dailynotes, focalboard, lazydocker, uptime,
      monica (app image), olivetin, watchtower, drawio (both images), whoami, gotify, appsmith,
      socket.
- [ ] Rolling aliases that look pinned but aren't: `mariadb:lts` (firefly), `lldap:stable`,
      `wiki:2` (wikijs, major-only).
- [ ] Good examples already pinned properly — use as the model: `directus:11.1.2`,
      `traefik:v3.6`, `gitea:1.23.7`, `gopeed:v1.5.7`, `papermerge:3.0.3`,
      `postgres:16`/`16-alpine`/`15-alpine`, `redis:7.2-alpine`, `registry:3`,
      `freeipa:fedora-41`.

## 3. Secrets / credentials hygiene — DONE (2026-07-19)

- [x] Rotated [lldap/docker-compose.yaml](lldap/docker-compose.yaml) `LLDAP_JWT_SECRET` — the
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
- [ ] [testing/docker-compose.yaml](testing/docker-compose.yaml) still points at a defunct
      `Godu92/Remote-Rhel` GitHub repo — update or remove.
- [ ] Root-level `./data/` is live Trilium data (not dead) but is owned by a different Unix
      user (`geadmin`) than the repo owner — check for a permissions/ownership drift issue.
      There's also an odd nested duplicate `data/styles/document.db*` worth investigating.
- [ ] [jenkins/data/](jenkins/data/) holds a full real Jenkins home dir (credentials.xml,
      secret.key, etc.) on disk next to tracked source — not git-tracked today, but consider
      moving state outside the repo tree entirely for portability.
- [ ] README's "Storage / List of Volumes" section only documents Monica/Uptime/Trilium even
      though 14 compose files define named volumes — update docs to match reality.

## 5. Traefik / networking consistency

- [ ] [firefly/docker-compose.yaml](firefly/docker-compose.yaml) defines its own isolated
      network — not reachable via Traefik as currently configured. Fix to join `proxy`, or
      document why it's intentionally isolated.
- [ ] Traefik provisions HTTPS (`:443`) but no service label ever uses an `https` entrypoint —
      either wire up TLS (cert resolver) or drop the unused entrypoint.
- [ ] `traefik/docker-compose.yaml` runs `--api.insecure=true` and exposes the dashboard on
      `8080` with no auth — add basic auth or bind to localhost only.
- [ ] Two files use `.yml` instead of the otherwise-universal `.yaml`:
      [airtrail/docker-compose.yml](airtrail/docker-compose.yml),
      [adventurelog/docker-compose.yml](adventurelog/docker-compose.yml). Rename for consistency.
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

---

## Longer-term wishlist (from README, not yet scoped)

- Script to auto-register a service into the root `docker-compose.yaml` `include:` list.
- Script to auto-populate the Dashy dashboard with all services, with live status.
- Script to auto-register services with the uptime monitor.
- Standardize template files (Dockerfile, docker-compose.yaml) beyond the single `testing/` example.

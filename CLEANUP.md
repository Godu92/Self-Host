# Cleanup / Modernization TODO

Living checklist from the 2026-07-16 repo audit. Goal: turn this into a well-organized
"swiss army knife" toolkit where the right compose file gets used for the right setup.
Check items off as they're addressed; add new findings as they turn up.

## 1. Reconcile the two competing launch mechanisms (highest priority)

There is currently no single source of truth for "what's running":

- [ ] Decide on ONE mechanism: root [docker-compose.yaml](docker-compose.yaml) `include:` list
      vs. [scripts/start.sh](scripts/start.sh)/[stop.sh](scripts/stop.sh) per-directory loop.
- [ ] `start.sh`/`stop.sh` launch each service dir as an independent Compose project, so each
      gets its own isolated Docker network instead of joining the shared `proxy` network Traefik
      lives on — label-based routing likely doesn't work through this path at all. Fix or retire it.
- [ ] Three drifting `EXCLUDED_DIRS`/enabled-service lists disagree with each other:
      README example, `start.sh`'s array, and the root compose file's commented-out includes.
      Converge to one list.
- [ ] `start.sh` creates a docker network named `main` that no service ever references — dead step.
- [ ] `scripts/start.sh`/`stop.sh` assume being run from inside `scripts/` (`../*/`), no
      `cd "$(dirname "$0")"` guard; uses `eval` on hardcoded strings; no `set -e`/error handling.
- [ ] **Preferred direction:** ditch the custom shell scripts and the single giant
      commented-in/out root compose file in favor of native Compose overrides — one base
      `docker-compose.yaml` (shared network, common services) plus per-deploy-style override
      files merged at launch time (`docker compose -f docker-compose.yaml -f compose.<style>.yaml up -d`).
      Candidate styles to define: `local`/dev, `work-server`, `family-server`, etc. Each override
      just lists which service files to `include:`/enable for that style — no more editing the
      shared file or maintaining drifting `EXCLUDED_DIRS` arrays across scripts/README.

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

## 3. Secrets / credentials hygiene

- [ ] Rotate/replace [lldap/docker-compose.yaml:19](lldap/docker-compose.yaml#L19)
      `LLDAP_JWT_SECRET` — looks like a real generated secret (not an obvious placeholder),
      committed to git.
- [ ] Hardcoded placeholder passwords directly in compose files — move to `.env` +
      `.env.example` convention: pihole, phpipam (x4), monica (x2), n8n (x3), wikijs,
      papermerge (x3), adventurelog (x4), freeipa, docmost (x2), directus (x2).
- [ ] `.env` files tracked in git despite `.gitignore` excluding `.env` — untrack and replace
      with `.env.example`: `firefly/.env`, `firefly/.db.env`, `firefly/.importer.env`,
      `airtrail/.env`, `notebook/opennotebook-single/docker.env`, root `.env-dev` (keep as
      example, just confirm it has no real values).
- [ ] Adopt a repo-wide convention: every service with secrets gets a tracked
      `*.env.example` and a real `.env` that's actually gitignored (verify `.gitignore` is
      doing what it claims).

## 4. Dead/stale content

- [ ] `remoteRhel` and `tenable` are referenced (README, `start.sh` EXCLUDED_DIRS, root
      compose comments) but no such directories exist. Either recreate or purge references.
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

- [ ] README's `EXCLUDED_DIRS` example doesn't match `scripts/start.sh`'s actual array —
      keep in sync going forward (or generate one from the other).
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

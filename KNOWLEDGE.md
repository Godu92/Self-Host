# Living memory experiment

Status: **proof of concept validated 2026-07-24, not yet a production setup.** This
document exists so a future session (human or agent) can pick this back up without
re-deriving the reasoning from scratch.

**Decision (2026-07-26): Wiki.js replaces Docmost as the notes layer for this
experiment.** Docmost is the better editing/review experience and stays in `notes/docmost`
for human-facing note-taking elsewhere in this repo — but for this specific loop, the
content needs to be machine-writable and machine-readable with no account friction (git/
pipelines writing, agents reading), and Wiki.js's anonymous-read + anonymous GraphQL
metadata (see "Alternate leg" below) fits that better than Docmost's session-cookie API.
`compose.knowledge.yaml` now includes `notes/wikijs` instead of `notes/docmost`.

## The problem this is trying to solve

Cross-project knowledge at work is scattered across ~100 systems and ~90 projects (50 of
them interrelated RPMs). The question was how to make that knowledge easily accessible to
both people and coding agents, without building something that only helps one narrow slice
of it.

## Why not [MegaMemory](https://github.com/0xK3vin/MegaMemory)

Investigated first since it's purpose-built for "agent remembers project context." Ruled
out for the cross-project goal specifically:

- It's an MCP **stdio** server spawned per-session by a coding agent, not a network
  service — no daemon to containerize in the usual sense.
- Storage is one SQLite file **per project** (`.megamemory/knowledge.db`); there's no
  built-in multi-project federation. `MEGAMEMORY_DB_PATH` can point multiple repos at one
  shared file, but that fights the tool's design (no per-project isolation once merged, no
  auth, brute-force cosine search the authors themselves cap at "<10k nodes").
- No human-readable UI beyond a debug graph viewer, no connector into anything else.

Still a reasonable _narrow_ tool for a single, complex repo where an agent's own scratch
notes get unwieldy to search — just not a fit for the wider goal, and not worth the extra
moving part given the alternative below reuses infrastructure already in this repo.

## The approach instead: promote, don't federate

Rather than trying to make one tool span every project, chain three things that already
exist in this repo, each doing the part it's actually good at:

1. **Wiki.js** (`notes/wikijs`) — durable record, written by people, git pipelines, or
   agents alike, and readable by other tools with zero auth (see "Alternate leg" below).
   Chosen over Docmost for this experiment specifically because the loop needs a
   machine-friendly write/read surface; Docmost is kept for more human-facing note-taking
   use elsewhere in this repo.
2. **Open Notebook** (`ai/notebook/opennotebook-single`) — local-LLM RAG layer. Ask
   natural-language questions across whatever's been fed into it. Runs entirely on local
   Ollama models, no cloud API keys required.
3. **n8n** (`productivity/n8n`) — automation glue, _not yet built_. Would poll Wiki.js's
   anonymous `pages.list` GraphQL feed (and eventually Gitea) for new/changed content, pull
   each changed page's raw content via an authenticated `pages.single` GraphQL call (see
   "Alternate leg" below for why this needs auth and a `link`-type source doesn't work), and
   push it into Open Notebook as a `text` source, so step 2 doesn't require manually
   re-adding sources by hand.

`compose.knowledge.yaml` at the repo root currently stands up just #1 and #2 — enough to
test whether the "write once, ask forever" loop is actually useful before investing in
automation. Gitea, n8n, an LLDAP service account, and further sources (Monica for
people/business context, Grocy for household/inventory facts) are listed there as
commented-out future extensions, not wired up.

## What was actually validated (original run, Docmost-based)

This validated the core write/ask loop concept before the 2026-07-26 switch to Wiki.js —
kept as historical record of what proved the idea out; the mechanics below (Docmost export,
`/api/sources/json`) are specific to the since-replaced Docmost leg.

1. Wrote a test page in Docmost with mixed content (bullet list, task list with one item
   checked, a heading, an ordered list, and a collapsible `<details>` block).
2. Pulled it out via **Docmost's own export API** (`POST /api/pages/export`,
   `format: markdown`) rather than hand-parsing its Tiptap/ProseMirror JSON — the export
   correctly handled things a hand-rolled parser missed (the collapsible block, ordered
   list numbering).
3. Fed the exported markdown into Open Notebook as a source (`POST /api/sources/json`),
   embedded via a local `nomic-embed-text` model.
4. Asked a question answerable only by having actually ingested the content: _"which
   checklist item is marked done, and what's hidden in the collapsible section?"_
5. Got a correct answer, with source citations, from a local `llama3.2:3b` model — no
   cloud API involved anywhere in the loop.

Conclusion: the human-writes/AI-queries loop works end to end on this hardware. The open
question is whether it holds up once compute isn't sitting on one beefy box (see below).

## Gotchas hit along the way (worth knowing before re-running this)

- **`postgres:latest-alpine` / `redis:latest-alpine` no longer exist as tags** (verified
  against Docker Hub directly — they existed when this repo's version-pinning audit last
  checked). Fixed by pinning the default to a real major (`postgres:${POSTGRES_VERSION:-18}-alpine`,
  `redis:${REDIS_VERSION:-8}-alpine`) in docmost, wikijs, and airtrail's compose files.
  Worth re-checking periodically — these registries do prune floating combo tags.
- **Postgres 18 changed its data directory convention**: `PGDATA` is now version-namespaced
  and the image's declared `VOLUME` moved from `/var/lib/postgresql/data` to
  `/var/lib/postgresql`. The old mount path silently drops data into an untracked
  anonymous volume instead of the named one. Fixed in docmost, wikijs, airtrail, and n8n.
- **`OPEN_NOTEBOOK_ENCRYPTION_KEY`** is now required upstream (encrypts stored AI-provider
  keys) and was missing from this repo's config — added to
  `ai/notebook/opennotebook-single/docker.env(.example)`.
- **`POST /api/sources/json` 500s with `async_processing: false`** —
  `asyncio.run() cannot be called from a running event loop`, a real upstream bug in the
  synchronous processing path. Always use `async_processing: true` and poll
  `GET /api/sources/{id}` for status instead.
- **Docmost has no documented public API**, but a real one exists behind session-cookie
  auth (`POST /api/auth/login` with `{email, password}`, then cookie-based POST calls to
  `/api/workspace/info`, `/api/spaces`, `/api/pages/sidebar-pages`, `/api/pages/info`,
  `/api/pages/export`). Found by reconnaissance, not docs — treat as unstable and
  re-verify against whatever version is running before automating against it (e.g. in the
  n8n workflow this still needs).
- Open Notebook's `-single` image has been discouraged upstream in favor of the standard
  multi-container Compose setup since v1.8.2 (~2026-04), though it's still published and
  functional as of the version tested. Worth checking on a future revisit whether it's
  still maintained at parity.
- AI provider keys (Anthropic/OpenAI) are being migrated upstream to Settings-UI-managed
  encrypted storage rather than env vars — configure providers through the UI going
  forward, don't rely on `docker.env` for that.

## Open question: this box is not a representative target

This was tested on hardware beefy enough to run Postgres + Redis + SurrealDB + Ollama
(chat + embedding models) + the Docmost/Open Notebook app containers all on one machine
without tuning anything. Most of the ~100 systems this is meant to eventually help with
won't look like that. Before this goes beyond "proof of concept":

- `OLLAMA_API_BASE` in `ai/notebook/opennotebook-single/docker.env` is just a URL — Open
  Notebook and Ollama are already loosely coupled. Pointing it at a dedicated Ollama host
  (a beefier box, or even a shared one serving multiple lightweight app boxes) is a config
  change, not an architecture change. Worth testing that split deliberately rather than
  assuming it'll just work.
- `OPEN_NOTEBOOK_WORKER_MAX_TASKS` (added to `docker.env.example` during this experiment,
  default 5) controls how many sources get processed concurrently — matters a lot more
  once Ollama isn't sitting on the same beefy box as everything else.
- Haven't tested what happens to answer quality/latency with `llama3.2:3b` on genuinely
  modest hardware (this was fast here specifically because the box wasn't struggling).

## Next steps, roughly in order

1. ~~Set up a scoped read-only Wiki.js account for n8n to use~~ — done 2026-07-26, see
   "LLDAP + n8n test" below.
2. ~~Wire the proven n8n workflow up to Open Notebook and validate a full write-to-answer
   cycle~~ — done 2026-07-26, see "Full cycle validated end to end" below.
3. Add a real schedule trigger + checkpoint-diffing logic to the n8n workflow (it currently
   re-ingests the same fixed page on every manual run, with no dedup) — and per the
   git-folder test below, design it as delete-old-source-then-create-new, not update, since
   Open Notebook has no update-in-place mechanism. Import
   `productivity/n8n/workflows/wikijs-to-opennotebook.json` as the starting point rather than
   rebuilding from scratch (see "Exporting the n8n workflow" below).
4. Test the split-hardware Ollama setup before assuming this scales past one box.
5. Revisit Gitea as a source (LDAP + scripted token bootstrap already proven to work in
   earlier, separate testing — just not wired into this loop yet), possibly using the
   git-backed-folder pattern validated below instead of/alongside an API-based sync.
6. Monica/Grocy as additional sources, once the above feels solid.

## LLDAP + n8n test, live-tested 2026-07-26

Stood up `identity/lldap` and `productivity/n8n` alongside the Wiki.js/Open Notebook stack
(not yet added to `compose.knowledge.yaml` — tested via direct `-f` flags, same pattern as
the earlier Wiki.js standalone test) to answer: what would a shared read-only service
identity for this pipeline actually look like end to end?

**Provisioned via LLDAP's API** (not the web UI): a `svc-readonly` group and a
`svc-wikijs-ro` user in it, using LLDAP's GraphQL admin API (`/api/graphql`, bearer token
from `POST /auth/simple/login`) for creation, then LLDAP's bundled `lldap_set_password` CLI
(inside the container) to set the password — LLDAP uses the OPAQUE PAKE protocol for
password changes, so there's no plain REST field for it; the GraphQL schema has no
password mutation at all, only the CLI (or the web UI) can set one.

**Wired Wiki.js to LLDAP as an auth provider** via GraphQL
(`authentication.updateStrategies`), pointing at `ldap://lldap:3890` with `svc-wikijs-ro`
as the bind DN (`uid=svc-wikijs-ro,ou=people,dc=localhost`) — deliberately using the
read-only service account itself as the bind identity, not the LDAP admin. Two real
gotchas hit getting this working:

- Each `config` entry's `value` must be JSON-encoded as `{"v": <value>}`, not just the bare
  value — found by reading `server/graph/resolvers/authentication.js`'s
  `updateStrategies` resolver, which does `_.get(JSON.parse(value.value), 'v', null)`. A
  bare `JSON.stringify(value)` round-trips fine through `JSON.parse` but then `_.get(str,
  'v')` on a primitive returns `null`, silently dropping the value.
- A newly-added or edited strategy needs Wiki.js to be **restarted** to take effect —
  strategies are registered with passport at boot; a live `updateStrategies` call updates
  the DB but not the running passport instance (confirmed by the log line
  `Authentication Strategy LLDAP (test): [ OK ]` only appearing after a restart).

**Logged in via the GraphQL `authentication.login(strategy: "ldap")` mutation** using the
service account's real password — succeeded, issued a normal Wiki.js JWT. Confirms Wiki.js
correctly binds to LLDAP and treats an LDAP account exactly like any other user.

**The permission model needed more care than expected.** A fresh LDAP-provisioned user has
no Wiki.js group and thus zero permissions. Assigning it to a new group with
`read:pages`/`read:assets`/`read:comments` (mirroring the built-in Guests group) was
_still_ not enough to read content via GraphQL `pages.single` — that resolver requires
`manage:pages` or `delete:pages` (see the earlier note in "Alternate leg" above), which is
an editor-tier permission, not a read-only one. The actually-correct, minimally-scoped path
turned out to be different: Wiki.js has a dedicated `read:source` permission
(`server/core/auth.js` line ~507) that gates a plain HTTP download route, `GET
/d/<path>`, which returns the raw page source (frontmatter + markdown) as a file — no
GraphQL, no SPA-rendering problem, and no edit-tier permission required. Granting the
service account's group `read:source` (alongside the read:pages/etc. it already had) and
hitting `GET /d/<path>` with `Authorization: Bearer <jwt>` returned the exact raw markdown
that had been written — this supersedes the earlier "Alternate leg" plan of using
authenticated `pages.single`; `GET /d/<path>` is simpler and more correctly scoped.

**Built an actual n8n workflow** (`Wiki.js -> Open Notebook (LDAP test)`, created via n8n's
internal REST API after logging in with `POST /rest/login`) with three chained HTTP
Request nodes: (1) anonymous `pages.list(orderBy: UPDATED)` against Wiki.js, (2)
`authentication.login(strategy: "ldap")` using the service account, (3) `GET
/d/<path>` for the first page from step 1, with `Authorization: Bearer` from step 2's JWT.
Ran it via n8n's manual-execution API — completed with `status: success` across all three
nodes. One n8n-specific gotcha: the first version had "list pages" and "LDAP login" as
parallel branches off the trigger, which broke — an n8n node can only reference
`$('OtherNode')`'s output if that node is somewhere in its own upstream chain, not just
anywhere in the workflow. Fixed by chaining all three nodes linearly.

Net result: the full shared-identity chain — LLDAP account → Wiki.js LDAP login → scoped
JWT → raw content fetch — works, is scriptable end to end, and n8n can drive all of it with
plain HTTP Request nodes (no LDAP-specific n8n node or credential type needed, since Wiki.js
is the only thing that actually speaks LDAP here — n8n just calls Wiki.js's own HTTP API).

## Exporting the n8n workflow, done 2026-07-26

n8n's workflow lives in its own Postgres DB (`n8n_db_storage` volume), not in this repo — a
full teardown/volume wipe would otherwise mean rebuilding the whole four-node chain by hand
every time. Exported the live workflow via `GET /rest/workflows/{id}` and committed a
sanitized copy to `productivity/n8n/workflows/wikijs-to-opennotebook.json`.

"Sanitized" mattered here: the live workflow had the `svc-wikijs-ro` LLDAP password
hardcoded in plain text inside the LDAP Login node's JSON body (typed directly into n8n's UI
during the test above). Replaced it with an expression, `{{ $env.WIKIJS_RO_PASSWORD }}`, and
added that var to `productivity/n8n/docker-compose.yaml`'s environment (sourced from
`.env`, documented in `.env.example` as "must match the LLDAP account's real password, keep
in sync by hand" — same shape as firefly's cross-file `MYSQL_PASSWORD`/`DB_PASSWORD` case).

**Real gotcha: n8n 2.x denies node access to `$env` by default.** Older assumptions (and
older n8n docs) are that env vars are readable in expressions unless
`N8N_BLOCK_ENV_ACCESS_IN_NODE=true` is explicitly set. Not true here — the container logged
a plain `access to env vars denied` and the node failed, with `N8N_BLOCK_ENV_ACCESS_IN_NODE`
left completely unset. Confirmed the default flipped by explicitly setting
`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` in the n8n service's environment, restarting, and
re-running the workflow — went from `status: error` to `status: success`, and a new source
landed in Open Notebook. Verify this default hasn't changed again before assuming it "just
works" on whatever n8n version is actually pinned when this gets revisited.

To restore the workflow on a clean n8n instance: log into n8n's UI or hit `POST
/rest/workflows` with the contents of `workflows/wikijs-to-opennotebook.json` as the body,
then make sure `WIKIJS_RO_PASSWORD` is set in `productivity/n8n/.env` to the real service
account password before running it.

## Full cycle validated end to end, 2026-07-26: Wiki.js -> n8n -> Open Notebook -> answer

Extended the n8n workflow above with a fourth node, `POST
http://open-notebook-single:5055/api/sources/json` with `{"type": "text", "title": <page
title from step 1>, "content": <raw source from step 3>, "embed": true, "async_processing":
true}` — i.e. push the LDAP-fetched page content straight into Open Notebook as a `text`
source (not `link` — sidesteps the SPA-rendering problem from the "Alternate leg" section
entirely, since n8n already has the real raw content in hand from `GET /d/<path>`).

Ran the workflow via n8n's manual-execution API: all four nodes succeeded, and the source
showed up in Open Notebook (`GET /api/sources`) with the correct title and content.
Then asked `POST /api/search/ask` a question answerable only from that page's content —
got back a correct answer that directly quoted the source and cited it by ID. This is the
same validation as the original Docmost-based test (see "What was actually validated"
above), now proven through the full new pipeline: Wiki.js write → LDAP-authenticated n8n
fetch → Open Notebook ingest → local-LLM answer, zero manual steps once a page is written.

The workflow still uses a manual trigger and re-ingests the same fixed page every run (no
schedule, no checkpoint, no dedup against already-ingested pages) — see Next Steps above
for what's still needed to make this actually automatic.

## Alternate leg, live-tested 2026-07-26: pull instead of push (WikiJS)

Idea: instead of Docmost + an export/upload step, use Wiki.js's built-in anonymous
"Guests" read group and GraphQL API so change-detection needs no auth, and let n8n hand
Open Notebook real page content directly.

Metadata/change-detection, confirmed live, fully anonymous (no JWT, no cookie):

- `POST /graphql` with `{ pages { list(orderBy: UPDATED, orderByDirection: DESC, limit: N)
  { path title updatedAt } } }` returns every page sorted by last-modified — a built-in,
  no-auth "recently changed" feed. Better fit than the originally-considered
  changedetection.io → Gotify chain: n8n can just poll this on a schedule, compare
  `updatedAt` against a stored checkpoint, and know exactly which pages to (re-)ingest. No
  changedetection watch-per-page, no notification hop needed for the trigger itself (Gotify
  could still be wired in purely for human visibility if wanted, but isn't load-bearing for
  the pipeline).
- `pages { tree(path: "", mode: ALL, locale: "en") { path title isFolder } }` (the sidebar
  "Browse" feature) is also anonymously queryable and correctly reflects folder/child-page
  structure — useful for an initial full backfill crawl, complementing `list` for
  incremental updates.
- The admin-only page map (`/a/pages/visualize`) does require a logged-in account, as
  expected — not needed given the GraphQL queries above already cover it anonymously.

**Actual content retrieval needs auth after all — the "hand Open Notebook a bare URL"
plan doesn't work.** Confirmed from Open Notebook's source (`api/models.py`/
`api/routers/sources.py`) that `type: "link"` is real and the _server_ fetches the URL
itself (SSRF-guarded) — but tested it end to end against `http://wiki:3000/en/<path>` and
the ingested content was just the page's `<title>` tag, nothing else. Root cause: Wiki.js
pages are a client-rendered Vue SPA — the raw server HTML is basically an empty shell plus
`<meta>` tags, and Open Notebook's non-JS extraction engines (bs4/readability, and `auto`'s
Jina/Firecrawl cloud fallbacks) never see the real body. The GraphQL query that _does_
return raw content (`pages { single(id) { content render } }`) checks page-view permission
more strictly than `list`/`tree` do and rejected the same anonymous request with
`PageViewForbidden`, then succeeded immediately once a real JWT was attached. So a
scoped read-only Wiki.js account is genuinely required for this leg, confirming the
account idea from earlier discussion rather than sidestepping it — the plan is now: n8n
authenticates (a read-only local account or Wiki.js API token, LDAP optional), pulls each
changed page's raw `content` via `pages.single`, and hands that text to Open Notebook as a
`type: "text"` source (not `type: "link"`) — sidestepping the SPA-rendering problem
entirely instead of fighting it with a heavier headless-browser extraction engine.

**Real bug found and fixed along the way, unrelated to Wiki.js specifically**: while
debugging the above, `ai/notebook/opennotebook-single`'s pinned `latest-single` Docker Hub
tag turned out to be stale — last published 2025-10-15, ~9 months behind numbered releases
— and missing a real fix where Content Settings (e.g. the URL extraction engine choice)
weren't actually read from the database at all; changing it via the Settings API/UI
silently had zero effect on real extraction, always behaving as if set to `auto`. Confirmed
by diffing the code actually inside the running container against upstream `main`, which
already reads settings correctly. Fixed by pinning
`ai/notebook/opennotebook-single/docker-compose.yaml`'s default to `1.14.0` instead of
`latest` (same pattern as the postgres/redis tag fixes above) — worth remembering that
`-single`'s floating tag can't be trusted to track upstream at all, so re-check for a newer
numbered release periodically rather than assuming `latest-single` is current.

Decided 2026-07-26: `compose.knowledge.yaml` now includes `notes/wikijs` in place of
`notes/docmost` for this experiment (see the decision note at the top of this doc).
Docmost remains available standalone (`notes/docmost`) for human-facing use, just outside
this style. Not yet tested: actually wiring any of this into n8n (schedule trigger →
GraphQL `pages.list` → filter by checkpoint → authenticated `pages.single` fetch → POST to
Open Notebook `/api/sources/json` as `type: "text"`), or setting up the scoped read-only
Wiki.js account/API token itself.

## Git-backed folder as an Open Notebook source, live-tested 2026-07-26

Idea: bind-mount a folder containing a `git`-cloned project into Open Notebook's
container, and have something (cron, n8n) periodically `git pull` it so new/changed files
become queryable context automatically.

Tested with a throwaway git repo bind-mounted as a subdirectory of `UPLOADS_FOLDER` (the
`upload` source type's `file_path` is restricted to that folder — an LFI guard in
`_build_content_state` — so it has to land inside it, can't point at an arbitrary path;
`services.open-notebook-single.volumes` needs an extra bind mount like
`<host-path>:/app/data/uploads/<name>:ro` for this). Confirmed:

- `POST /api/sources/json` with `{"type": "upload", "file_path":
  "/app/data/uploads/<name>/<file>", "embed": true}` ingests a file already sitting in a
  bind mount directly — no actual HTTP file upload needed, since `file_path` just has to
  resolve inside `UPLOADS_FOLDER` (which our bind-mounted git repo now does).
- The bind mount reflects host-side `git commit`s immediately (as expected for a bind
  mount — Docker doesn't cache/snapshot the content).
- **But Open Notebook's source is a one-time snapshot, not a live view.** After editing a
  file and committing, the file inside the container updated instantly, but the
  already-ingested source's `full_text` still held the old content. Checked the API for a
  "re-sync from file" or "refresh" endpoint — `PUT /api/sources/{id}` (`SourceUpdate`) can
  only edit `title`/`topics`, and `POST /api/sources/{id}/retry` is only for
  failed/stuck jobs, not re-extracting from an already-completed source. **There is no
  update-in-place mechanism at all** — the only way to pick up a changed file is to delete
  the old source and create a new one from the same path, which does correctly pick up the
  new content.

Implication for any future automation (this git-folder idea, or the Wiki.js `pages.list`
sync described above): don't design around "update this source," design around "delete
the old source for this item, create a fresh one" whenever the underlying content changes.
That also means whatever tracks "have I already ingested this" needs to record enough to
find and delete the old source (e.g., a naming convention or a topic/tag), since Open
Notebook doesn't expose changed-since/checksum metadata on sources to diff against
automatically.

**What this does and doesn't solve.** It does give a real, working way to hand Open
Notebook a folder to reference instead of copy/pasting or uploading through the UI one
file at a time — genuinely useful for a handful of files. It does **not** solve "mount a
large git project and have all of it become context" as a single action: since Open
Notebook never scans its uploads folder on its own, something still has to walk the tree
and call `POST /api/sources/json` once per file (and, per above, delete+recreate on every
change) — a mount alone only makes the files _reachable_, not _ingested_. That directory
walk + diff + ingest loop is the same shape of automation the Wiki.js `pages.list` sync
still needs (see Next Steps) — worth building once, generically, rather than twice.

Two gotchas hit while testing this (both about the _test environment_, not the mechanism
above): after the earlier `notebook_data`/`surreal_data` wipe, Open Notebook came back up
with zero registered models and zero content-processing settings, even though the actual
Ollama models were still present on disk (`ollama_data` was kept) — had to re-register
both models (`POST /api/models`) and re-set the defaults (`PUT /api/models/defaults`)
before anything would embed; sources silently stayed `embedded: false` with the log line
"No embedding model configured" until that was done. Separately, `POST /api/sources/json`'s
`embed` field defaults to `false` and is independent of the global `default_embedding_option`
setting — that setting doesn't get auto-applied by the API, only by whatever UI dialog reads
it, so any script/workflow creating sources needs to pass `"embed": true` explicitly.

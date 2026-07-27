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

1. Set up a scoped read-only Wiki.js account (or API token) for n8n/Open Notebook to use
   against `pages.single` — required now that anonymous access has been shown to only cover
   metadata, not actual page content.
2. Decide whether to actually build the n8n workflow (Wiki.js `pages.list` → authenticated
   `pages.single` → Open Notebook `text` source sync) or keep this manual for longer while
   more content accumulates.
3. Test the split-hardware Ollama setup before assuming this scales past one box.
4. Revisit Gitea as a source (LDAP + scripted token bootstrap already proven to work in
   earlier, separate testing — just not wired into this loop yet).
5. Only after the above feel solid: LLDAP service account for shared auth (vs. a plain local
   Wiki.js account/token — worth comparing once there's a second consumer needing the same
   identity), Monica/Grocy as additional sources.

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

## Future idea: git-backed folder as an Open Notebook source

Instead of (or alongside) the wiki/API approaches above: bind-mount a folder containing
both hand-written notes and a `git`-cloned project into Open Notebook's container, and
have something (cron, n8n) periodically `git pull` it so new/changed files become
queryable context automatically.

Checked against Open Notebook's actual API code: the `upload` source type's `file_path`
is explicitly restricted to `UPLOADS_FOLDER` (an LFI guard in
`_build_content_state`) — you can't just point a source at an arbitrary bind-mounted path.
The workable version is bind-mounting the git-tracked folder _as_ `UPLOADS_FOLDER` itself
(so `git pull` updates land inside the allowed directory), but something would still need
to diff the folder after each pull and call `POST /api/sources` per new/changed file —
Open Notebook doesn't auto-scan its uploads folder. Not yet tested live.

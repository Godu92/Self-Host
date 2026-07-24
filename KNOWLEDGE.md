# Living memory experiment

Status: **proof of concept validated 2026-07-24, not yet a production setup.** This
document exists so a future session (human or agent) can pick this back up without
re-deriving the reasoning from scratch.

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

1. **Docmost** (`notes/docmost`) — durable, human-reviewed record. Things too structured
   or important for a README aside (incident reports, cross-project decisions) get written
   here, reviewable/editable by people, not buried in a per-repo agent scratchpad.
2. **Open Notebook** (`ai/notebook/opennotebook-single`) — local-LLM RAG layer. Ask
   natural-language questions across whatever's been fed into it. Runs entirely on local
   Ollama models, no cloud API keys required.
3. **n8n** (`productivity/n8n`) — automation glue, _not yet built_. Would poll
   Docmost/Gitea for new content and push it into Open Notebook as a source, so step 2
   doesn't require manually re-adding sources by hand.

`compose.knowledge.yaml` at the repo root currently stands up just #1 and #2 — enough to
test whether the "write once, ask forever" loop is actually useful before investing in
automation. Gitea, n8n, an LLDAP service account, and further sources (Monica for
people/business context, Grocy for household/inventory facts) are listed there as
commented-out future extensions, not wired up.

## What was actually validated

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

1. Decide whether to actually build the n8n workflow (Docmost → Open Notebook sync) or
   keep this manual for longer while more content accumulates.
2. Test the split-hardware Ollama setup before assuming this scales past one box.
3. Revisit Gitea as a source (LDAP + scripted token bootstrap already proven to work in
   earlier, separate testing — just not wired into this loop yet).
4. Only after the above feel solid: LLDAP service account for shared auth, Monica/Grocy as
   additional sources.

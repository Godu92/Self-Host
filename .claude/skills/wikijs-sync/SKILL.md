---
name: wikijs-sync
description: Publish or refresh markdown docs (repo docs/, notes, memory) as pages on this stack's self-hosted WikiJS instance (notes/wikijs), so the content is reachable by browser without cloning a repo — and pull pages back out as a Markdown mirror (scripts/wikijs-export.py), e.g. to index the wiki in Open WebUI. Use when asked to sync/publish/push docs or notes to the wiki, to export/mirror/index the wiki, or to check what's currently on it.
---

# wikijs-sync

This repo runs its own WikiJS instance (`notes/wikijs/docker-compose.yaml`), reachable at
`http://<HOST>:2000` once the service is up (`docker compose up -d` with a deploy style that
includes `notes`, or the service directly). It has a full GraphQL API, so any markdown tree —
this repo's own docs, another project's `docs/`, agent-memory notes — can be pushed there as
pages instead of staying reachable only from inside a clone.

## Auth

Generate an API token from WikiJS's admin UI (Administration → API Access → New API Key), not
a user/password login — tokens don't expire on password rotation and don't need a session
refresh loop. Store it in a gitignored file (e.g. a service-local `.env` alongside
`notes/wikijs/.env`, or a dedicated credentials file outside the repo) — never commit it, paste
it into a wiki page's own content, or put it in a commit message.

## The GraphQL pattern

Two calls cover create-or-update for a single page:

```python
import requests

WIKIJS_URL = "http://localhost:2000/graphql"
TOKEN = "..."  # from a gitignored env var, never hardcoded

def gql(query, variables=None):
    r = requests.post(
        WIKIJS_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]

# 1. Look up whether a page at this path already exists.
existing = gql(
    "query($path: String!, $locale: String!) { pages { singleByPath(path: $path, locale: $locale) { id } } }",
    {"path": "projects/self-host", "locale": "en"},
)["pages"]["singleByPath"]

# 2. Create if missing, update in place if found.
if existing is None:
    gql(
        """mutation($content: String!, $path: String!, $title: String!) {
          pages { create(content: $content, description: "", editor: "markdown",
                          isPublished: true, isPrivate: false, locale: "en",
                          path: $path, tags: [], title: $title) { responseResult { succeeded, message } } }
        }""",
        {"content": open("README.md").read(), "path": "projects/self-host", "title": "Self-Host"},
    )
else:
    # WikiJS's update mutation expects title/description alongside content even when
    # they haven't changed — omitting them can blank those fields out.
    gql(
        """mutation($id: Int!, $content: String!, $title: String!) {
          pages { update(id: $id, content: $content, description: "", title: $title, tags: [])
                   { responseResult { succeeded, message } } }
        }""",
        {"id": existing["id"], "content": open("README.md").read(), "title": "Self-Host"},
    )
```

Build your own script from this shape rather than re-deriving the GraphQL schema each time —
the two calls above (`singleByPath` to check, `create` vs `update` based on the result) are the
whole pattern for one page. For a whole directory of markdown files, loop over them, slugify
each relative path into a wiki path, and use each file's first `# H1` (falling back to a
humanized filename) as the title.

## Before publishing anything

- **Dry-run first**: print what would be created/updated (path, title, byte count) before
  making the GraphQL calls, especially the first sync of a given tree.
- **Scan for embedded secrets** before the first live sync of any docs tree — real passwords,
  API keys, private-key blocks, not placeholder/example values. Something like
  `grep -ril -iE "password\s*[:=]|api[_-]?key\s*[:=]|BEGIN (RSA|OPENSSH|PRIVATE)"` over the
  source files. If a file reads as carrying a live credential, stop and ask how to handle it
  (redact the wiki copy, publish as-is, or skip that file) — don't decide silently. A
  self-hosted, LAN-only wiki is still a broadcast surface to everyone with access to it.
- **Deletions (prune) are the one destructive step** — deleting a page that no longer has a
  source file. Always list what would be deleted and confirm before actually calling
  `pages { delete(id: ...) }`.
- Syncing many files means many sequential GraphQL calls — for more than a handful of pages,
  run the sync as a background task rather than blocking on it inline.

## Pulling pages back out (wiki → Markdown → Open WebUI)

The reverse direction is scripted, so don't rebuild it from GraphQL:
[scripts/wikijs-export.py](../../../scripts/wikijs-export.py) mirrors every published page
into `<out>/<locale>/<path>.md`, and [scripts/owui-sync.py](../../../scripts/owui-sync.py)
then syncs that directory into an Open WebUI knowledge collection incrementally.

```bash
scripts/wikijs-export.py --url http://<wiki-host> --out ~/wiki-mirror [--prefix projects/foo]
OWUI_TOKEN=... scripts/owui-sync.py --url http://chat.<HOST> --knowledge wiki ~/wiki-mirror
```

- **No account needed** if guests can read pages. Wiki.js renders the page body
  server-side into a `<template slot="contents">` tag that a browser expands with
  JavaScript. The script reads that tag and converts it back to Markdown (headings, code
  blocks, lists, tables).
- **With `$WIKIJS_TOKEN`** (an API key, or a read-only account whose group has "read
  source" permission), it fetches each page's exact source from `/d/<locale>/<path>`
  instead.
- **Don't point Open WebUI's web-page loader at Wiki.js.** It sees only the `<title>`,
  because the body lives in that `<template>` tag. It also refuses internal addresses unless
  `ENABLE_LOCAL_WEB_FETCH` and `WEB_FETCH_FILTER_LIST` are set.
- The output dir is a true mirror: deleted pages' files are removed on the next run, and
  unchanged pages stay byte-identical, so `owui-sync.py` skips them. The script refuses to
  prune a non-empty directory it didn't create.
- Use one output dir per `--prefix` (and one collection per wiki section, if the wiki is
  organized by project). Re-running with a different prefix into the same dir prunes the
  pages outside it.

## General pattern

This same technique applies to any markdown source, not just this repo's own docs: another
project's `docs/` tree, or per-project agent-memory notes if you're running Claude Code
elsewhere and want its `project`/`reference`-type notes visible outside `.claude/projects/`.
The only things that change per source are the path-mapping convention (how a source file's
relative path becomes a wiki path) and which subset of files counts as "worth publishing."

#!/usr/bin/env python3
"""One-off migration: export a Trilium subtree via ETAPI and load it into Wiki.js via GraphQL.

Usage:
  scripts/migrate-trilium-to-wikijs.py \
    --trilium-url http://notes.localhost \
    --note-id <note-id> \
    --wiki-url http://wiki.localhost \
    --wiki-token <api-token> \
    [--base-path trilium-demo] [--dry-run]

Trilium password is read from $TRILIUM_PASSWORD, or prompted for if unset.
Wiki.js API token can also come from $WIKIJS_API_TOKEN instead of --wiki-token.

Requires ETAPI enabled in Trilium (Options > ETAPI) and a Wiki.js API key
created in Administration > API Access (with write:pages scope), API Access
toggled on.
"""

import argparse
import getpass
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile


def http_json(url, method="GET", headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def trilium_login(base_url, password):
    url = f"{base_url}/etapi/auth/login"
    try:
        result = http_json(url, method="POST", body={"password": password})
    except urllib.error.HTTPError as e:
        sys.exit(
            f"Trilium login failed ({e.code}): {e.read().decode()[:300]}\n"
            f"Check that ETAPI is enabled (Options > ETAPI) and the password is correct."
        )
    return result["authToken"]


def trilium_export(base_url, note_id, auth_token):
    url = f"{base_url}/etapi/notes/{note_id}/export?format=markdown"
    req = urllib.request.Request(url, headers={"Authorization": auth_token})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(
            f"Trilium export failed ({e.code}): {e.read().decode()[:300]}\n"
            f"Check the note id ({note_id}) is correct and reachable from this note tree."
        )


def slugify_segment(name):
    name = re.sub(r"\.md$", "", name, flags=re.IGNORECASE)
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9\-/_]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "untitled"


def derive_title(stem, content):
    m = re.search(r"^\s*#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return stem.replace("-", " ").replace("_", " ").strip() or "Untitled"


def collect_pages(zip_bytes, base_path):
    """Walk the exported zip and yield (wiki_path, title, content) for each note."""
    pages = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [
            n
            for n in zf.namelist()
            if n.lower().endswith(".md") and not n.endswith("/")
        ]
        for name in names:
            parts = name.split("/")
            stem = re.sub(r"\.md$", "", parts[-1], flags=re.IGNORECASE)
            dir_parts = parts[:-1]
            # Trilium's markdown export writes a note's own content as a file
            # sitting alongside its children's folder (both named after the
            # note), e.g. "Foo.md" next to "Foo/". The root note's file has
            # no parent directory at all - it maps to base_path itself, with
            # no extra segment.
            if not dir_parts:
                path_parts = []
            else:
                path_parts = dir_parts + [stem]
            slug_parts = [slugify_segment(p) for p in path_parts if p]
            wiki_path = "/".join(([base_path] if base_path else []) + slug_parts)
            content = zf.read(name).decode("utf-8", errors="replace")
            title = derive_title(stem, content)
            pages.append((wiki_path, title, content))
    return pages


PAGES_CREATE_MUTATION = """
mutation (
  $content: String!, $description: String!, $editor: String!,
  $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!,
  $path: String!, $tags: [String]!, $title: String!
) {
  pages {
    create(
      content: $content, description: $description, editor: $editor,
      isPublished: $isPublished, isPrivate: $isPrivate, locale: $locale,
      path: $path, tags: $tags, title: $title
    ) {
      responseResult { succeeded errorCode slug message }
      page { id path }
    }
  }
}
"""


def wiki_create_page(wiki_url, token, wiki_path, title, content):
    url = f"{wiki_url}/graphql"
    variables = {
        "content": content,
        "description": "",
        "editor": "markdown",
        "isPublished": True,
        "isPrivate": False,
        "locale": "en",
        "path": wiki_path,
        "tags": [],
        "title": title,
    }
    result = http_json(
        url,
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        body={"query": PAGES_CREATE_MUTATION, "variables": variables},
    )
    if "errors" in result:
        return False, result["errors"][0]["message"]
    rr = result["data"]["pages"]["create"]["responseResult"]
    return rr["succeeded"], rr["message"]


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--trilium-url", required=True, help="e.g. http://notes.localhost")
    p.add_argument(
        "--note-id", required=True, help="Trilium noteId of the subtree root"
    )
    p.add_argument("--wiki-url", required=True, help="e.g. http://wiki.localhost")
    p.add_argument("--wiki-token", default=os.environ.get("WIKIJS_API_TOKEN"))
    p.add_argument(
        "--base-path",
        default="",
        help="Wiki.js path prefix for imported pages, e.g. trilium-demo",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print planned pages, don't call Wiki.js"
    )
    args = p.parse_args()

    if not args.wiki_token and not args.dry_run:
        sys.exit("Wiki.js API token required: --wiki-token or $WIKIJS_API_TOKEN")

    password = os.environ.get("TRILIUM_PASSWORD") or getpass.getpass(
        "Trilium password: "
    )

    print(f"Logging into Trilium at {args.trilium_url} ...")
    auth_token = trilium_login(args.trilium_url, password)

    print(f"Exporting note {args.note_id} as markdown ...")
    zip_bytes = trilium_export(args.trilium_url, args.note_id, auth_token)

    pages = collect_pages(zip_bytes, args.base_path)
    print(f"Found {len(pages)} note(s) to migrate.")

    for wiki_path, title, content in pages:
        if args.dry_run:
            print(f"  [dry-run] {wiki_path!r}  <-  {title!r} ({len(content)} chars)")
            continue
        ok, message = wiki_create_page(
            args.wiki_url, args.wiki_token, wiki_path, title, content
        )
        status = "OK" if ok else "FAILED"
        print(f"  [{status}] {wiki_path}  ({message})")


if __name__ == "__main__":
    main()

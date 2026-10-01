#!/usr/bin/env python3
"""Sync a directory (usually a git checkout) into an Open WebUI knowledge collection.

Incremental: uses Open WebUI's own sync endpoints (/knowledge/{id}/sync/diff and
/sync/cleanup, the same ones its UI uses for directory sync), so only new or changed files
are uploaded and embedded, and files deleted from the source are removed from the
collection. Re-running on an unchanged tree uploads nothing.

Usage:
  scripts/owui-sync.py --url http://127.0.0.1 --host-header chat.localhost --knowledge ai ai/
  scripts/owui-sync.py --url https://chat.example --knowledge my-project ~/src/my-project --dry-run

Auth: an Open WebUI API key or session JWT from $OWUI_TOKEN (or --token).

File selection: inside a git repo only *tracked* files are considered (`git ls-files`), so
gitignored secrets (.env), data dirs and build output never leave the machine. Outside git,
everything under the directory is walked. Binary files and files over --max-kb are skipped.

Standard library only, so it runs on a locked-down host without pip.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

# Never upload these, even if they're tracked in git.
ALWAYS_SKIP_SUFFIXES = ('.env', '.pem', '.key', '.crt', '.p12', '.pfx')


HOST_HEADER = None  # set from --host-header


class ApiError(Exception):
    pass


def api(base, token, method, path, body=None, raw=None, content_type=None, timeout=600, fatal=True):
    """Call the Open WebUI API; return parsed JSON. `raw` sends pre-encoded bytes.
    With fatal=False an HTTP error raises ApiError instead of exiting (per-file failures)."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base.rstrip('/') + path, data=data, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    if HOST_HEADER:
        req.add_header('Host', HOST_HEADER)
    if raw is not None:
        req.add_header('Content-Type', content_type)
    elif body is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        msg = f'{method} {path} -> HTTP {e.code}: {e.read().decode()[:500]}'
        if not fatal:
            raise ApiError(msg)
        sys.exit(msg)
    except urllib.error.URLError as e:
        sys.exit(f'cannot reach {base}: {e.reason} (try --host-header if DNS is not set up)')


def multipart(filename, content, metadata):
    """Encode a single-file multipart/form-data body (urllib has no helper for this)."""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode(),
        json.dumps(metadata).encode(),
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: text/plain\r\n\r\n'.encode(),
        content,
        f'\r\n--{boundary}--\r\n'.encode(),
    ]
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def list_files(root):
    """Tracked files if root is in a git repo, else a plain walk. Paths relative to root."""
    try:
        out = subprocess.run(
            ['git', '-C', root, 'ls-files', '-z', '--', '.'],
            capture_output=True, check=True,
        ).stdout.decode()
        return [p for p in out.split('\0') if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for name in filenames:
                found.append(os.path.relpath(os.path.join(dirpath, name), root))
        return found


def display_name(project, rel):
    """Unique, path-bearing upload name: 'monitoring__autokuma__docker-compose.yaml'.

    Multi-project codebases are full of identically named files (docker-compose.yaml,
    README.md, main.py, pom.xml). Open WebUI labels each retrieved chunk with its file name,
    both in the prompt the model sees and in the hybrid-search keyword index, so bare
    basenames make chunks from different projects indistinguishable. Slashes can't be used
    (the server strips everything before the last one), hence '__'.
    """
    return '__'.join([project] + rel.replace(os.sep, '/').split('/'))


def build_manifest(root, max_kb, project):
    manifest, contents, skipped = [], {}, 0
    for rel in sorted(list_files(root)):
        full = os.path.join(root, rel)
        name = os.path.basename(rel)
        if (not os.path.isfile(full) or name.endswith(ALWAYS_SKIP_SUFFIXES)
                or ('.env.' in name and not name.endswith('.example'))):
            skipped += 1
            continue
        if os.path.getsize(full) > max_kb * 1024:
            skipped += 1
            continue
        with open(full, 'rb') as f:
            content = f.read()
        if b'\0' in content[:8192] or not content.strip():
            skipped += 1  # binary or empty
            continue
        path = os.path.dirname(rel).replace(os.sep, '/')
        name = display_name(project, rel)
        manifest.append({
            'filename': name,
            'path': path,
            'checksum': hashlib.sha256(content).hexdigest(),
            'size': len(content),
        })
        contents[(path, name)] = content
    return manifest, contents, skipped


def find_or_create_knowledge(base, token, name, dry_run):
    page = api(base, token, 'GET', '/api/v1/knowledge/')
    items = page.get('items', page) if isinstance(page, dict) else page
    for kb in items or []:
        if kb.get('name') == name:
            return kb['id']
    if dry_run:
        return None
    kb = api(base, token, 'POST', '/api/v1/knowledge/create',
             {'name': name, 'description': f'Synced by owui-sync.py'})
    print(f'created knowledge collection "{name}" ({kb["id"]})')
    return kb['id']


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', help='directory to sync (a git checkout, ideally)')
    ap.add_argument('--url', required=True, help='Open WebUI base URL')
    ap.add_argument('--knowledge', required=True, help='collection name (created if missing)')
    ap.add_argument('--token', default=os.environ.get('OWUI_TOKEN'))
    ap.add_argument('--host-header', help='send this Host header, e.g. --url http://127.0.0.1 '
                    '--host-header chat.localhost to reach Traefik before DNS exists')
    ap.add_argument('--max-kb', type=int, default=512, help='skip files larger than this')
    ap.add_argument('--dry-run', action='store_true', help='show the diff, change nothing')
    args = ap.parse_args()
    if not args.token:
        sys.exit('set $OWUI_TOKEN or pass --token')
    global HOST_HEADER
    HOST_HEADER = args.host_header

    manifest, contents, skipped = build_manifest(args.source, args.max_kb, args.knowledge)
    print(f'{len(manifest)} files to consider ({skipped} skipped: binary/empty/large/secret)')

    kb_id = find_or_create_knowledge(args.url, args.token, args.knowledge, args.dry_run)
    if kb_id is None:
        print(f'dry run: collection "{args.knowledge}" does not exist yet; would upload all')
        return

    diff = api(args.url, args.token, 'POST', f'/api/v1/knowledge/{kb_id}/sync/diff',
               {'manifest': manifest})
    print(f'added {len(diff["added"])}, modified {len(diff["modified"])}, '
          f'deleted {len(diff["deleted"])}, unchanged {diff["unmodified_count"]}')
    if args.dry_run:
        for f in diff['added'] + diff['modified']:
            print(f'  ~ {f["path"] + "/" if f["path"] else ""}{f["filename"]}')
        for f in diff['deleted']:
            print(f'  - {f["filename"]}')
        return

    # Stale copies of modified files go first so the collection never holds both versions.
    stale = [f['file_id'] for f in diff['deleted']] + [f['stale_file_id'] for f in diff['modified']]
    if stale or diff['rmdir']:
        api(args.url, args.token, 'POST', f'/api/v1/knowledge/{kb_id}/sync/cleanup',
            {'file_ids': stale, 'dir_ids': diff['rmdir']})

    # mkdir comes back sorted shallowest-first, so each parent exists before its children.
    dirs = dict(diff['directory_map'])
    for path in diff['mkdir']:
        parent, _, name = path.rpartition('/')
        d = api(args.url, args.token, 'POST', f'/api/v1/knowledge/{kb_id}/dirs/create',
                {'name': name, 'parent_id': dirs.get(parent) if parent else None})
        dirs[path] = d['id']

    todo = diff['added'] + diff['modified']
    start = time.monotonic()
    failed = 0
    for i, f in enumerate(todo, 1):
        key = (f['path'], f['filename'])
        content = contents[key]
        checksum = hashlib.sha256(content).hexdigest()
        body, ctype = multipart(f['filename'], content, {'file_hash': checksum})
        # Synchronous processing: the upload returns once the file is chunked + embedded,
        # which gives honest per-file timing and avoids racing the knowledge add below.
        label = f'{f["path"] + "/" if f["path"] else ""}{f["filename"]}'
        uploaded = None
        try:
            uploaded = api(args.url, args.token, 'POST',
                           '/api/v1/files/?process=true&process_in_background=false',
                           raw=body, content_type=ctype, fatal=False)
            if (uploaded.get('data') or {}).get('status') == 'failed':
                raise ApiError('processing failed')
            api(args.url, args.token, 'POST', f'/api/v1/knowledge/{kb_id}/file/add',
                {'file_id': uploaded['id'],
                 'directory_id': dirs.get(f['path']) if f['path'] else None}, fatal=False)
        except ApiError as e:
            # One unreadable file (no extractable text, odd format) shouldn't stop a run
            # across many projects. It stays out of the collection, so the next run's diff
            # retries it.
            failed += 1
            print(f'  ! [{i}/{len(todo)}] {label}: {e}')
            if uploaded:  # don't leave an orphaned upload behind on every retry
                try:
                    api(args.url, args.token, 'DELETE', f'/api/v1/files/{uploaded["id"]}', fatal=False)
                except ApiError:
                    pass
            continue
        print(f'  + [{i}/{len(todo)}] {label}')

    took = time.monotonic() - start
    rate = f', {len(todo) / took:.2f} files/s' if todo and took else ''
    print(f'done: {len(todo) - failed} uploaded, {failed} failed in {took:.0f}s{rate}')


if __name__ == '__main__':
    main()

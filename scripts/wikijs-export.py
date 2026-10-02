#!/usr/bin/env python3
"""Mirror a Wiki.js 2.x wiki into a directory of Markdown files (one file per page).

The pull half of the wiki loop: wikijs-sync (.claude/skills) pushes docs *into* Wiki.js;
this pulls pages back *out*, so they can be indexed elsewhere, e.g.:

  scripts/wikijs-export.py --url http://wiki.example --out ~/wiki-mirror
  scripts/owui-sync.py --url http://chat.example --knowledge wiki ~/wiki-mirror

Two ways to get each page's content, picked automatically per page:

1. Raw source (`/d/<locale>/<path>`): exact Markdown as written. Needs a token whose
   group has "read source" permission ($WIKIJS_TOKEN: an API key, or a JWT from a
   read-only account's login).
2. Rendered HTML, converted back to Markdown: works anonymously on any wiki where guests
   can read pages. Wiki.js renders the page body server-side into a <template> tag that a
   browser expands with JavaScript, so generic web-page loaders (Open WebUI's included)
   see only the title. This reads that tag directly.

Only published pages are exported. Re-running rewrites changed pages and deletes files
for pages that no longer exist, so the output dir is a true mirror. Output is
deterministic (no timestamps), so unchanged pages produce byte-identical files and
owui-sync.py's checksum diff skips them.

Standard library only.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

MARKER = '.wikijs-export'  # marks a directory this script owns, so pruning is safe

LIST_QUERY = """{ pages { list(limit: 100000) {
  id path locale title description contentType isPublished isPrivate } } }"""


# --- HTML -> Markdown -------------------------------------------------------

class MarkdownWriter(HTMLParser):
    """Small, dependency-free HTML -> Markdown converter for Wiki.js-rendered pages.

    Keeps what matters for RAG: heading structure (Open WebUI splits Markdown on
    headings), code blocks verbatim, lists, tables, link text. Drops Wiki.js chrome such as
    the heading anchor links.
    """

    BLOCKS = {'p', 'div', 'section', 'article', 'blockquote', 'figure', 'details', 'summary'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf = []
        self.lists = []  # stack of [tag, counter]
        self.pre = False
        self.skip = 0  # depth inside elements whose text is dropped
        self.marks = []  # (tag, buffer index, extra) for elements rewritten on close
        self.row = None
        self.table = None

    def text(self):
        out = ''.join(self.buf)
        out = re.sub(r'[ \t]+\n', '\n', out)
        out = re.sub(r'\n{3,}', '\n\n', out)
        return out.strip() + '\n'

    def _block(self):
        if self.buf and not ''.join(self.buf[-2:]).endswith('\n\n'):
            self.buf.append('\n\n')

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class') or ''
        if self.skip:
            if tag not in ('br', 'img', 'hr'):  # void elements never close
                self.skip += 1
            return
        if tag in ('script', 'style', 'svg') or 'toc-anchor' in cls:
            self.skip = 1
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._block()
            self.buf.append('#' * int(tag[1]) + ' ')
            self.marks.append(('h', len(self.buf), None))
        elif tag in self.BLOCKS:
            self._block()
            if tag == 'blockquote':
                self.marks.append((tag, len(self.buf), None))
        elif tag == 'br':
            self.buf.append('\n')
        elif tag == 'hr':
            self._block()
            self.buf.append('---\n\n')
        elif tag in ('ul', 'ol'):
            if not self.lists:
                self._block()
            self.lists.append([tag, 0])
        elif tag == 'li':
            depth = len(self.lists)
            kind = self.lists[-1] if self.lists else ['ul', 0]
            kind[1] += 1
            bullet = f'{kind[1]}. ' if kind[0] == 'ol' else '- '
            self.buf.append('\n' + '  ' * max(depth - 1, 0) + bullet)
        elif tag == 'pre':
            self._block()
            self.pre = True
            self.marks.append(('pre', len(self.buf), ''))
        elif tag == 'code':
            if self.pre:
                lang = next((c[9:] for c in cls.split() if c.startswith('language-')), '')
                tag_, idx, _ = self.marks[-1]
                self.marks[-1] = (tag_, idx, lang)
            else:
                self.buf.append('`')
        elif tag in ('strong', 'b'):
            self.buf.append('**')
        elif tag in ('em', 'i'):
            self.buf.append('*')
        elif tag == 'a':
            self.marks.append(('a', len(self.buf), a.get('href') or ''))
        elif tag == 'img':
            alt = a.get('alt') or ''
            if alt:
                self.buf.append(f'[image: {alt}]')
        elif tag == 'table':
            self._block()
            self.table = []
        elif tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.marks.append(('cell', len(self.buf), None))

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            if self.marks and self.marks[-1][0] == 'h':
                _, idx, _ = self.marks.pop()
                heading = ' '.join(''.join(self.buf[idx:]).split())
                del self.buf[idx:]
                self.buf.append(heading)
            self.buf.append('\n\n')
        elif tag in self.BLOCKS:
            if tag == 'blockquote' and self.marks and self.marks[-1][0] == 'blockquote':
                _, idx, _ = self.marks.pop()
                inner = ''.join(self.buf[idx:]).strip()
                del self.buf[idx:]
                self.buf.append('\n'.join('> ' + line for line in inner.splitlines()))
            self._block()
        elif tag in ('ul', 'ol'):
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.buf.append('\n\n')
        elif tag == 'pre':
            self.pre = False
            if self.marks and self.marks[-1][0] == 'pre':
                _, idx, lang = self.marks.pop()
                code = ''.join(self.buf[idx:]).strip('\n')
                del self.buf[idx:]
                self.buf.append(f'```{lang}\n{code}\n```\n\n')
        elif tag == 'code' and not self.pre:
            self.buf.append('`')
        elif tag in ('strong', 'b'):
            self.buf.append('**')
        elif tag in ('em', 'i'):
            self.buf.append('*')
        elif tag == 'a' and self.marks and self.marks[-1][0] == 'a':
            _, idx, href = self.marks.pop()
            label = ''.join(self.buf[idx:]).strip()
            del self.buf[idx:]
            # Keep external/page links as Markdown; anchors and empty links as plain text.
            if href and not href.startswith('#') and label and label != href:
                self.buf.append(f'[{label}]({href})')
            else:
                self.buf.append(label or href)
        elif tag in ('td', 'th') and self.marks and self.marks[-1][0] == 'cell':
            _, idx, _ = self.marks.pop()
            cell = ' '.join(''.join(self.buf[idx:]).split()).replace('|', '\\|')
            del self.buf[idx:]
            if self.row is not None:
                self.row.append(cell)
        elif tag == 'tr' and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            rows = [r for r in self.table if r]
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [''] * (width - len(r)) for r in rows]
                lines = ['| ' + ' | '.join(rows[0]) + ' |',
                         '| ' + ' | '.join(['---'] * width) + ' |']
                lines += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
                self.buf.append('\n'.join(lines) + '\n\n')
            self.table = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.pre:
            self.buf.append(data)
        else:
            collapsed = re.sub(r'\s+', ' ', data)
            if collapsed.strip() or (self.buf and not self.buf[-1].endswith((' ', '\n'))):
                self.buf.append(collapsed)


def html_to_markdown(html):
    w = MarkdownWriter()
    w.feed(html)
    w.close()
    return w.text()


# --- Wiki.js access ---------------------------------------------------------

def fetch(url, token=None, data=None):
    req = urllib.request.Request(url, data=data)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', 'replace')


def list_pages(base, token):
    body = json.dumps({'query': LIST_QUERY}).encode()
    try:
        data = json.loads(fetch(f'{base}/graphql', token, body))
    except urllib.error.URLError as e:
        sys.exit(f'cannot reach {base}: {getattr(e, "reason", e)}')
    if data.get('errors'):
        sys.exit(f'pages.list failed: {data["errors"][0].get("message")}')
    return data['data']['pages']['list']


FRONTMATTER = re.compile(r'\A(?:---\n.*?\n---\n|<!--\n.*?\n-->\n)', re.S)


def raw_source(base, page, token):
    """Exact page source via /d/, or None if this token/guest can't read source."""
    url = f'{base}/d/{page["locale"]}/{urllib.parse.quote(page["path"])}'
    try:
        src = fetch(url, token)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None
        raise
    src = FRONTMATTER.sub('', src.replace('\r\n', '\n'), count=1)
    if page.get('contentType') == 'html':  # visual-editor pages store HTML
        src = html_to_markdown(src)
    return src


CONTENTS = re.compile(r'<template slot="contents">(.*?)</template>', re.S)


def rendered_source(base, page, token):
    url = f'{base}/{page["locale"]}/{urllib.parse.quote(page["path"])}'
    m = CONTENTS.search(fetch(url, token))
    return html_to_markdown(m.group(1)) if m else ''


# --- mirror -----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--url', required=True, help='Wiki.js base URL')
    ap.add_argument('--out', required=True, help='output directory (created; owned by this script)')
    ap.add_argument('--token', default=os.environ.get('WIKIJS_TOKEN'),
                    help='optional; enables exact raw source (default $WIKIJS_TOKEN)')
    ap.add_argument('--prefix', action='append', default=[],
                    help='only pages under this path prefix (repeatable), e.g. projects/foo')
    ap.add_argument('--locale', help='only this locale, e.g. en')
    args = ap.parse_args()
    base = args.url.rstrip('/')

    out = os.path.abspath(args.out)
    if os.path.isdir(out) and os.listdir(out) and not os.path.exists(os.path.join(out, MARKER)):
        sys.exit(f'{out} is not empty and was not created by this script; refusing to prune it')
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, MARKER), 'w').close()

    pages = [p for p in list_pages(base, args.token)
             if p['isPublished']
             and (not args.locale or p['locale'] == args.locale)
             and (not args.prefix or any(p['path'].startswith(x) for x in args.prefix))]
    print(f'{len(pages)} published pages to export')

    written, counts = set(), {'raw': 0, 'rendered': 0, 'empty': 0}
    for page in sorted(pages, key=lambda p: (p['locale'], p['path'])):
        body = raw_source(base, page, args.token)
        how = 'raw'
        if body is None:
            body, how = rendered_source(base, page, args.token), 'rendered'
        if not body.strip():
            counts['empty'] += 1
            continue
        counts[how] += 1
        # A title + source line up front: the title is page metadata (often not in the body),
        # and the URL lets an answer cite the page.
        header = f'# {page["title"]}\n\nWiki page: {base}/{page["locale"]}/{page["path"]}\n'
        if page.get('description'):
            header += f'\n{page["description"]}\n'
        rel = os.path.join(page['locale'], *page['path'].split('/')) + '.md'
        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        content = header + '\n' + body
        old = open(dest, encoding='utf-8').read() if os.path.exists(dest) else None
        if content != old:
            with open(dest, 'w', encoding='utf-8') as f:
                f.write(content)
        written.add(os.path.normpath(dest))

    removed = 0
    for dirpath, _, files in os.walk(out):
        for name in files:
            path = os.path.normpath(os.path.join(dirpath, name))
            if name.endswith('.md') and path not in written:
                os.remove(path)
                removed += 1
    print(f'done: {counts["raw"]} raw source, {counts["rendered"]} from rendered HTML, '
          f'{counts["empty"]} empty skipped, {removed} stale files removed')


if __name__ == '__main__':
    main()

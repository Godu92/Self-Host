#!/usr/bin/env -S python3 -u
"""Benchmark a CPU-only Open WebUI + Ollama setup: raw model speed, then RAG end to end.

1. Raw speed (per model): one fixed ~1.5k-token prompt through Open WebUI's Ollama proxy,
   reporting Ollama's own timing stats — prompt reading (prefill) tok/s, generation tok/s,
   load time. These are the numbers to compare across hardware.
2. RAG (per model, per question): time to first token and total time through Open WebUI's
   chat API, with the question's knowledge collections attached and, for comparison,
   without them. Answers are written to a Markdown report for a human to judge quality.

Usage:
  scripts/owui-bench.py --url http://127.0.0.1 --host-header chat.localhost \\
      --model qwen2.5-coder:7b --questions scripts/owui-bench.selfhost.json

Questions file: a JSON list of {"q": "...", "collections": ["name", ...]}. Keep
environment-specific question sets out of the public repo (docs/private/).

Auth: an Open WebUI admin API key or session JWT from $OWUI_TOKEN (or --token); the raw
speed test uses the admin-only Ollama proxy. Standard library only.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ~1.5k tokens of plausible code-review context, so prefill speed is measured on a prompt
# the size of a modest RAG request rather than a one-liner.
RAW_PROMPT = (
    'You are reviewing a Docker Compose deployment. Summarize in three bullet points what '
    'the following service definitions have in common.\n\n'
    + '\n'.join(
        f'services:\n  svc{i}:\n    image: example/app{i}:${{APP{i}_VERSION:-latest}}\n'
        f'    container_name: svc{i}\n    restart: always\n    labels:\n'
        f'      - traefik.enable=true\n      - traefik.http.routers.svc{i}.rule=Host(`svc{i}.$HOST`)\n'
        f'      - traefik.http.services.svc{i}.loadbalancer.server.port=80{i:02d}\n'
        for i in range(24)
    )
)


class Client:
    def __init__(self, url, token, host_header):
        self.url, self.token, self.host = url.rstrip('/'), token, host_header

    def request(self, method, path, body=None, timeout=1800):
        req = urllib.request.Request(
            self.url + path, method=method,
            data=json.dumps(body).encode() if body is not None else None)
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Content-Type', 'application/json')
        if self.host:
            req.add_header('Host', self.host)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            sys.exit(f'{method} {path} -> HTTP {e.code}: {e.read().decode()[:500]}')
        except urllib.error.URLError as e:
            sys.exit(f'cannot reach {self.url}: {e.reason} (try --host-header)')

    def json(self, method, path, body=None):
        with self.request(method, path, body) as r:
            return json.loads(r.read().decode())


def raw_speed(c, model):
    # Don't set num_ctx: Ollama reloads the model whenever the context size changes, so a
    # different value here than the chat requests use would add a reload to the first RAG
    # timing. Both inherit the server default (OLLAMA_CONTEXT_LENGTH) instead.
    # A unique first line defeats Ollama's prompt cache: otherwise the second (warm) call
    # reuses the first call's processed prompt and reports an impossible prefill speed.
    stats = c.json('POST', '/ollama/api/generate', {
        'model': model, 'prompt': f'Request {time.time_ns()}.\n{RAW_PROMPT}', 'stream': False,
        'options': {'num_predict': 128, 'temperature': 0},
    })
    ns = 1e9
    return {
        'load_s': stats.get('load_duration', 0) / ns,
        'prompt_tokens': stats.get('prompt_eval_count', 0),
        'prefill_tps': stats.get('prompt_eval_count', 0) / max(stats.get('prompt_eval_duration', 1) / ns, 1e-9),
        'gen_tokens': stats.get('eval_count', 0),
        'gen_tps': stats.get('eval_count', 0) / max(stats.get('eval_duration', 1) / ns, 1e-9),
    }


def chat(c, model, question, collection_ids):
    """Stream one chat completion; return (ttft_s, total_s, answer, usage, sources)."""
    body = {'model': model, 'stream': True,
            'messages': [{'role': 'user', 'content': question}]}
    if collection_ids:
        body['files'] = [{'type': 'collection', 'id': i} for i in collection_ids]
    start = time.monotonic()
    ttft, parts, usage, sources = None, [], {}, []
    with c.request('POST', '/api/chat/completions', body) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event.get('sources'):
                sources = event['sources']
            if event.get('usage'):
                usage = event['usage']
            for choice in event.get('choices') or []:
                text = (choice.get('delta') or {}).get('content')
                if text:
                    if ttft is None:
                        ttft = time.monotonic() - start
                    parts.append(text)
    return ttft, time.monotonic() - start, ''.join(parts), usage, sources


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--url', required=True)
    ap.add_argument('--host-header')
    ap.add_argument('--token', default=os.environ.get('OWUI_TOKEN'))
    ap.add_argument('--model', action='append', required=True, help='repeatable')
    ap.add_argument('--questions', help='JSON list of {q, collections} (required unless --raw-only)')
    ap.add_argument('--no-baseline', action='store_true', help='skip the without-RAG runs')
    ap.add_argument('--raw-only', action='store_true', help='only the raw speed test')
    ap.add_argument('--report', default='owui-bench-report.md')
    args = ap.parse_args()
    if not args.token:
        sys.exit('set $OWUI_TOKEN or pass --token')

    c = Client(args.url, args.token, args.host_header)
    if args.raw_only:
        questions = []
    elif not args.questions:
        sys.exit('--questions is required unless --raw-only')
    else:
        with open(args.questions) as f:
            questions = json.load(f)
    kbs = c.json('GET', '/api/v1/knowledge/')
    kbs = kbs.get('items', kbs) if isinstance(kbs, dict) else kbs
    kb_ids = {kb['name']: kb['id'] for kb in kbs}
    missing = {n for q in questions for n in q['collections']} - kb_ids.keys()
    if missing:
        sys.exit(f'collections not found: {", ".join(sorted(missing))}')

    report = [f'# Open WebUI benchmark, {time.strftime("%Y-%m-%d %H:%M")}\n']
    for model in args.model:
        print(f'== {model}: raw speed (first call includes model load)')
        cold = raw_speed(c, model)
        warm = raw_speed(c, model)
        print(f'   load {cold["load_s"]:.1f}s | prefill {warm["prefill_tps"]:.0f} tok/s '
              f'({warm["prompt_tokens"]} tok) | generation {warm["gen_tps"]:.1f} tok/s')
        report += [f'## {model}\n',
                   f'Raw speed (warm): prefill **{warm["prefill_tps"]:.0f} tok/s** over '
                   f'{warm["prompt_tokens"]} prompt tokens, generation **{warm["gen_tps"]:.1f} '
                   f'tok/s**. Cold load {cold["load_s"]:.1f}s.\n',
                   '| Question | RAG | First token | Total | Prompt tok |',
                   '| --- | --- | --- | --- | --- |']
        if args.raw_only:
            continue
        answers = []
        for q in questions:
            modes = [('on', [kb_ids[n] for n in q['collections']])]
            if not args.no_baseline:
                modes.append(('off', []))
            for mode, ids in modes:
                ttft, total, answer, usage, sources = chat(c, model, q['q'], ids)
                ptok = usage.get('prompt_tokens') or usage.get('prompt_eval_count') or '?'
                first = f'{ttft:.1f}s' if ttft is not None else 'none'
                print(f'   RAG {mode:3} | first token {first:>6} | total {total:5.1f}s | '
                      f'prompt {ptok} tok | {q["q"][:60]}')
                report.append(f'| {q["q"][:70]} | {mode} | {first} | {total:.1f}s | {ptok} |')
                cited = sorted({m.get('name', '?') for s in sources for m in s.get('metadata') or []})
                answers.append(f'### {q["q"]}\n\nRAG {mode}, collections: '
                               f'{", ".join(q["collections"]) if ids else "none"}'
                               + (f'; sources: {", ".join(cited)}' if cited else '')
                               + f'\n\n{answer.strip()}\n')
        report += ['', '### Answers\n'] + answers

    with open(args.report, 'w') as f:
        f.write('\n'.join(report) + '\n')
    print(f'report written to {args.report}')


if __name__ == '__main__':
    main()

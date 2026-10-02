# Multi-project RAG on CPU-only hardware

Status: **design, nothing built yet (2026-10-01).** It builds on the living-memory experiment
([KNOWLEDGE.md](KNOWLEDGE.md)), which is paused while this is worked on (see "Relation to the
living-memory work" below).

## The problem

You have a self-hosted code assistant, and it needs to answer questions across a codebase
made of **many interrelated projects**: dozens to hundreds of repos that build one product,
some with hundreds of files each, plus supporting infrastructure repos. Most RAG guides
assume one repo or one document pile. At high project counts, the naive approach falls apart.

## Design target

This is a deliberately constrained baseline, because it's what many regulated or air-gapped
organizations actually have:

- **CPU only, no GPU.**
- **Offline-capable:** no reliance on internet access at runtime or install time.
- **Self-hosted end to end:** nothing leaves the local network.
- **Open WebUI + Ollama**, from this repo's [ai/webui](../ai/webui/docker-compose.yaml) and
  [ai/ollama](../ai/ollama/docker-compose.yaml).
- **One user first.** Only plan for concurrency once one person finds it worth using.

Anything that works under these limits gets better with a GPU. The reverse isn't true.

Ollama can run on its own box, with Open WebUI and the editor pointing at it over the
network. That's the same split-hardware step KNOWLEDGE.md lists as next.

## CPU-only reality check

Two different speeds matter, and the second is what makes RAG hard on CPU:

- **Generating output (tokens/sec)** is limited by memory bandwidth. Rough expectations on a
  decent server CPU: a 7–8B model at Q4 ≈ 5–12 tok/s, 14B ≈ 3–6 tok/s, and 30B+ dense models
  are too slow for interactive use. Mixture-of-experts models (few active parameters per
  token) suit CPU best.
- **Reading the prompt (prefill)** may run at only ~50–150 tok/s. A RAG prompt with 6k tokens
  of retrieved chunks plus pasted code means a minute or more before the first word of the
  answer. Every RAG setting (top-k, chunk size, reranker, `num_ctx`) is really a latency
  setting.

Realistic uses: autocomplete, "explain this function", "where/how does X happen", searching
docs. Not realistic on CPU: agents that work autonomously across many files.

## VM sizing (KVM example)

- **CPU mode `host-passthrough`** (or `host-model`). A generic virtual CPU model can hide
  AVX2/AVX-512 and make inference several times slower. To check from inside the guest:
  `grep -o 'avx[^ ]*' /proc/cpuinfo | sort -u`.
- **16 vCPUs, all on one NUMA node / socket.** Ollama scales with physical cores, not
  hyperthreads.
- **64 GB RAM.** Enough for the chat, autocomplete and embedding models loaded at once, plus
  the context cache, Open WebUI and the vector DB.
- **100 GB disk** for models and the vector index.

A plain VM is the quickest way to get a yes/no answer. Kubernetes adds nothing at one user.

## Models

Three roles, sized very differently:

| Role | Size | Notes |
| --- | --- | --- |
| Chat / explain | 7–14B, or an MoE | The one people notice; the biggest speed/quality tradeoff |
| Autocomplete (FIM) | 1–3B | Must be fast and support fill-in-the-middle |
| Embeddings | ~100–500M | Used for indexing (batch) and on every query |

In regulated environments, **where a model comes from** can matter as much as how good it
is. The strongest open coding models aren't automatically allowed. Candidates whose origin
is easier to defend: IBM Granite (Apache 2.0, has code variants), Llama (Meta), Phi
(Microsoft), Gemma (Google). Codestral's license doesn't allow production use. Check the
current versions on the Ollama/HF registries before choosing; don't rely on a model list
from memory.

## RAG design: three tiers

Putting every project into one Open WebUI knowledge collection fails in three ways:

- Search results get noisy, because the same function names appear in many projects.
- Fixed-size text chunking cuts functions in half.
- Every irrelevant chunk adds to prompt-reading time.

Instead, three tiers, each built and tested before the next:

1. **The repo you have open, in the editor.** Most everyday questions are about the repo
   already open. The VS Code extension supplies the context: open files, the selection, and
   its own workspace index if that's good enough. No central index needed. Covers "explain or
   fix this".
2. **A central map across projects.** One collection that holds *generated* material, not raw
   code:
   - per-project READMEs and docs
   - package and build manifests (RPM `.spec`, `package.json`, `pom.xml`, `go.mod`, ...),
     whose dependencies are exactly how the projects connect
   - API and interface definitions
   - a generated summary and "repo map" per project (file tree plus class and function
     signatures, ctags/tree-sitter style)

   The local model can write the summaries as an overnight batch, where CPU speed doesn't
   matter. Answers "which project handles X" and "what talks to Y".

   **If project documentation already exists in a wiki, tier 2 is mostly done.** Those
   pages are the derived material. See "Feeding a wiki into tier 2" below.
3. **A full code index per project, only if tier 2 isn't enough.**
   - **Scope:** one collection per project or subsystem, chosen per chat.
   - **Chunking:** split by function/class rather than by character count, done by an
     external indexer that pushes chunks in through Open WebUI's API.
   - **Search:** turn on hybrid search (keyword BM25 plus vectors). Exact identifiers matter
     more in code than meaning-based similarity.
   - **Storage:** at this size, move the vector DB from the built-in Chroma to Qdrant or
     pgvector.

A rough indexing cost for tier 3 at ~100 projects: hundreds of thousands of chunks. With a
small embedding model on CPU that takes hours, not days. Run it overnight, then re-index
incrementally from git diffs.

**Test with 2–3 closely related projects first**, not the whole codebase.

## Feeding a wiki into tier 2

Two ways to get an existing Wiki.js into an Open WebUI knowledge collection:

- **Wiki.js Git storage (recommended).** Wiki.js's built-in Git storage module syncs every
  page as a Markdown file to a git repo, which is the app's own export with no custom
  scraping. An ingest script then pushes changed files into Open WebUI through its knowledge
  API, using `git diff` to find what changed since the last run. The same script later
  handles tier 3, since a code repo is just another git repo. Bonus: the wiki gets version
  history and a backup.
- **The n8n workflow from [KNOWLEDGE.md](KNOWLEDGE.md)** (list pages over GraphQL → log in
  as a read-only LDAP service account → fetch raw Markdown from `/d/<path>`). It's already
  proven; only the final step changes, from Open Notebook to Open WebUI. Use this if n8n is
  already running where the wiki lives.

Wiki pages are prose with headings, so turn on Open WebUI's Markdown-header-aware text
splitting rather than fixed-size chunks. Start with one collection for the whole wiki; split
it by top-level wiki section only if answers start mixing unrelated projects.

## Memory budget (32 GB VM example)

Rough figures for Q4 quantization, single user:

| Component | Approx. RAM |
| --- | --- |
| OS, Docker, Traefik, Open WebUI | 3–4 GB |
| Embedding model | < 1 GB |
| Autocomplete model (1.5B) | ~1 GB |
| Chat model: 30B MoE (~3B active) | ~19 GB + context cache |
| Chat model: 14B dense (alternative) | ~9 GB + context cache |

A 30B MoE fits in 32 GB with a 16k context, but only one chat model can be loaded at a
time, so benchmark candidates one after another. On CPU, an MoE is faster than a 14B dense
model at *both* generating and reading the prompt, because the work per token scales with
the active parameters, not the total. That makes it the better RAG choice even though it
uses more memory. 48–64 GB is enough to keep two chat models loaded or run longer contexts.

Ollama settings to check against the version you run:

- `OLLAMA_NUM_PARALLEL=1`: each parallel slot gets its own context cache, which wastes
  memory with one user.
- `OLLAMA_MAX_LOADED_MODELS=3`: keeps chat, autocomplete and embedding loaded together.
- `OLLAMA_KEEP_ALIVE=-1` (or a long duration): reloading ~19 GB from disk after an idle
  timeout adds its own delay.
- `OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0`: roughly halves the context
  cache's memory.
- `OLLAMA_CONTEXT_LENGTH`: the default context size for every request.

**Keep Ollama from starving everything else.** Even on a dedicated VM, use `cpuset` to give
Ollama all but a couple of cores, and set `mem_limit` on it. A test on a shared workstation
that eats every free core and all free memory produces no usable numbers, because
everything slows down together.

## Hosting layout

Build it in phases. Each phase only changes where things run, not how they're configured:

1. **Pilot: one VM.** Ollama and Open WebUI side by side, launched from this repo's compose
   files. Put it on the host with the newest CPU generation and the most memory channels, and
   **pin its vCPUs** rather than sharing them. CPU inference uses every core it's given, so
   overcommitted cores hurt both this VM and its neighbors.
2. **Split.** Once there's more than one user, or batch indexing starts competing with
   interactive use, move Ollama to its own VM. Open WebUI is a light web app and can go
   anywhere, Kubernetes included.
3. **Ollama on Kubernetes**, only with dedicated nodes or Guaranteed-QoS pods using the static
   CPU manager policy, plus a PVC big enough for the models. Without that, it competes with
   whatever else is on the node.

**Don't expose Ollama directly.** It has no authentication. Put Open WebUI in front as the
only entry point. It proxies Ollama and offers an OpenAI-compatible API protected by per-user
API keys, so editor extensions point at Open WebUI, not at Ollama. The Ollama port then
doesn't need to be reachable from workstations at all.

## Editor integration

- **Continue:** fully local and needs no account. It handles chat and fill-in-the-middle
  autocomplete, with a separate model for each. This is the default choice when nothing may
  leave the network.
- **Copilot Chat with a local model** (bring-your-own-model): before relying on it, check
  three things.
  - It still needs a GitHub sign-in, which may not work from a locked-down network.
  - It may still send some requests (titles, intent detection, indexing) to GitHub's
    services when the chat model is local.
  - Inline autocomplete may not support local models.

## Corporate TLS interception

Many corporate networks intercept HTTPS and re-sign it with an internal CA. Tools that use
their own trust store then fail even though the host's `curl` works. A typical symptom is
`ollama pull` failing with `x509: certificate signed by unknown authority`. Before building
a manual download workaround, give the containers the corporate CA:

- **Ollama (Go):** mount the CA bundle and set `SSL_CERT_FILE` to it, or build a derived
  image that runs `update-ca-certificates`. Add `HTTPS_PROXY` if the proxy is explicit
  rather than transparent.
- **Open WebUI (Python):** set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` to the same bundle.
  That covers its HuggingFace downloads and any outbound API calls.

**Simplest version on RHEL: mount the host's own trust bundle.** If the host already trusts
the right CAs (installed with `update-ca-trust`, usually by config management), then
`/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` already holds every root the containers
need. That's both the interception CA for outbound traffic and the internal CA for services
like GitLab or a wiki. Mount that file read-only and point `SSL_CERT_FILE` (and, for Python,
`REQUESTS_CA_BUNDLE`) at it. Containers then follow whatever the host trusts, with no custom
images to rebuild when a CA changes.

If pulls still fail after that, the registry itself is blocked, and the offline import path
below is the fallback.

### Serving HTTPS from an internal CA

This repo's Traefik routes only plain HTTP today. To serve Open WebUI over HTTPS with a
certificate from an internal CA such as FreeIPA:

- **certmonger (simplest):** on a host enrolled as an IPA client, `ipa-getcert request`
  issues a certificate and renews it automatically. Traefik's file provider loads the cert
  and key from disk.
- **ACME (scales better):** FreeIPA can act as an ACME server (`ipa-acme-manage enable`).
  Traefik's certificate resolver then points at it with `caServer`. This is worth it once
  more than a few services need certificates.

## Local test corpus

This repo makes a decent stand-in for a large multi-project codebase. Treat each category
folder (`ai/`, `identity/`, `monitoring/`, ...) as a "project".

The cross-project relationships are real, which makes for good tier 2 test questions:

- Which services share the one Ollama?
- What goes through the Docker socket proxy?
- What authenticates against LLDAP?
- Which services publish ports without a Traefik route?

**Limitation:** it's mostly YAML and Markdown, so it doesn't test how actual code gets
chunked. Add a code-heavy open-source project before judging tier 3.

## Getting models from Hugging Face

If Hugging Face is reachable but Ollama's own registry isn't (or is less trusted), Ollama can
pull GGUF files directly from it. Tested 2026-10-02 with `OLLAMA_NO_CLOUD=true` set; that only
blocks *remote inference*, not downloads:

```bash
docker exec ollama ollama pull hf.co/<org>/<repo>-GGUF:<quant>   # e.g. :Q4_K_M
```

- **Prefer the model publisher's own repo** (e.g. `Qwen/...-GGUF`, `ibm-granite/...-GGUF`)
  over third-party re-quantizations. It's one less party to trust, which matters wherever
  model origin gets questioned.
- **Downloads go through the same TLS path** as everything else, so a TLS-intercepting proxy
  needs the CA bundle fix first. Hugging Face also redirects file downloads to its own CDN
  hosts, which must be reachable too.
- **Downloading a model is not the same as using hosted inference.** Hugging Face also offers
  hosted chat and inference APIs. Pointing Open WebUI at those would send every prompt,
  including retrieved code, to an outside service, which defeats the "nothing leaves the
  network" design target. The override keeps `ENABLE_OPENAI_API=false` partly so that this
  can't happen by accident.

## Offline setup

- **Models:** download on a connected machine and import on the target. Either copy Ollama's
  models directory, or download GGUF files and run `ollama create` with a Modelfile. A
  generic import script belongs under `scripts/`.
- **Open WebUI** downloads a sentence-transformers embedding model from HuggingFace the first
  time it starts. To stop that, set `OFFLINE_MODE=true` / `HF_HUB_OFFLINE=1` and
  `RAG_EMBEDDING_ENGINE=ollama`, so embeddings come from a model already loaded into Ollama.
- **VS Code extension:** may need an offline VSIX install if the marketplace is blocked.
- **Container images:** use `podman save`/`load` if registries are blocked too.

## RHEL 9 notes

With Docker Engine on RHEL, this repo's compose files run as they are. The podman points
below apply only if you stick with podman.

- This repo's launch method depends on Compose `include:`, and `podman-compose` doesn't
  handle that reliably. Instead, use `podman compose` with the real `docker-compose` v2
  binary as the provider, talking to the podman socket. Check this first: it decides how much
  of this repo's structure works unchanged.
- SELinux: bind mounts need `:Z`.

## Relation to the living-memory work

Tier 2 is the same "promote, don't federate" idea as KNOWLEDGE.md: collect curated, generated
knowledge in one place instead of indexing everything raw. If tier 2 works, the Wiki.js/n8n
pipeline built there could hold the generated project summaries.

## Running it

The `codeassist` deploy style wires everything above together:

| File | What it does |
| --- | --- |
| [compose.codeassist.yaml](../compose.codeassist.yaml) | Includes Ollama and Open WebUI, each with a CPU override |
| [ai/ollama/cpu-only.override.yaml](../ai/ollama/cpu-only.override.yaml) | No host port or Traefik route; `cpuset`/`mem_limit`; the Ollama settings above; cloud models off; host CA bundle |
| [ai/webui/cpu-rag.override.yaml](../ai/webui/cpu-rag.override.yaml) | Offline mode; Ollama embeddings; hybrid search; small top-k; background LLM tasks off; API keys on; host CA bundle |
| [scripts/owui-sync.py](../scripts/owui-sync.py) | Syncs a directory/git checkout into a knowledge collection, incrementally |
| [scripts/owui-bench.py](../scripts/owui-bench.py) | Raw model speed plus RAG time-to-first-token, with a Markdown report of the answers |

Steps on a fresh host:

1. **Configure.** Copy `ai/ollama/.env.example` and `ai/webui/.env.example` to `.env`, then
   run `scripts/gen-secrets.sh ai/webui`. Set `OLLAMA_CPUSET`/`OLLAMA_MEM_LIMIT` for the VM.
   On RHEL, also set `HOST_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` in
   both files. Set `HOST` in the root `.env`.
2. **Start:** `docker compose -f docker-compose.yaml -f compose.codeassist.yaml up -d`.
3. **Pull models** (Ollama has no published port in this style):
   `docker exec ollama ollama pull nomic-embed-text`, then the chat model(s). If this fails
   with a certificate error, the CA bundle isn't being trusted. See "Corporate TLS
   interception".
4. **Create the admin account** at `http://chat.$HOST`, the first sign-up, and create an
   API key under Settings > Account.
5. **Index:** `OWUI_TOKEN=<key> scripts/owui-sync.py --url http://chat.$HOST --knowledge
   <name> <dir>`, one collection per project. Re-running only sends what changed.
6. **Benchmark:** write a questions file (see `scripts/owui-bench.selfhost.json` for the
   format), then `scripts/owui-bench.py --url ... --model <m> --questions <file>`.

### Gotchas found in the first run

- **Settings come from env only on the first start.** Open WebUI stores most settings in its
  own database once it has started. After that, changing an env var does nothing. Change
  settings in Admin > Settings (or the API), or start with an empty data volume.
- **Recent Ollama versions can run "cloud" models** on ollama.com. The override sets
  `OLLAMA_NO_CLOUD=true` so a model picked in the UI can never send prompts off the network.
- **Embedding batch size defaults to 1** (`RAG_EMBEDDING_BATCH_SIZE`), meaning one Ollama
  call per chunk. Raise it (Admin > Settings > Documents, or the env var on the first start).
  It matters more for many-chunk files than for small configs.
- **Files with no extractable text get rejected** when added to a collection, for example
  an HTML file that's only a `<script>` block. The HTML loader strips the tags and nothing
  is left. The sync script logs these, skips them and cleans up the upload. Worth checking
  before indexing a code-heavy repo with many such files.
- **Hybrid search rebuilds its keyword index over the whole collection on every query.**
  This is another reason to keep one collection per project.
- **Identical file names make chunks indistinguishable.** This is the biggest retrieval
  problem for a multi-project codebase. Open WebUI labels every chunk with its bare file
  name, in both the prompt and the keyword index. In a repo where every service has a
  `docker-compose.yaml`, a question about one service retrieved another service's file, and
  neither the model nor the search could tell them apart. `owui-sync.py` therefore uploads
  each file under a project-and-path name (`monitoring__autokuma__docker-compose.yaml`), and
  the override turns on `ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS` so those names count in
  keyword search. Any real codebase has the same problem (`README.md`, `main.py`, `pom.xml`).

## First results (2026-10-01, test laptop)

**Hardware:** an 11-core laptop CPU (AVX2, no AVX-512) under WSL. Ollama was capped at
10 GB and 20 threads. The corpus was this repo, one collection per category folder: 16
collections, ~150 files, mostly YAML.

**Raw speed** (`owui-bench.py --raw-only`, ~2k-token prompt):

| Model | Prompt reading | Generation |
| --- | --- | --- |
| qwen2.5-coder 7B | 43 tok/s | 8.5 tok/s |
| llama3.2 3B | 85 tok/s | 14.5 tok/s |

Turning flash attention off (with an f16 context cache) gave +9% / +16% prompt-reading speed
for more memory. These are single runs, so repeat on the target hardware before changing
the default.

**RAG, time to first token:** 7B 6–32 s, 3B 3–17 s, for 550–1,650 prompt tokens. Without
RAG it's under 1 s. That's roughly prompt tokens ÷ prompt-reading speed, plus a couple of
seconds for retrieval, which confirms prompt reading is the bottleneck. Attaching more
collections grows the prompt: one collection gave ~600 tokens, three gave ~1,600.

**Quality:**

- **Without RAG**, both models invent generic answers, e.g. "LLDAP is probably a typo for
  LDAP".
- **With RAG and bare file names**, retrieval picked the wrong `docker-compose.yaml`. With
  path-bearing names (see "Gotchas"), every question retrieved the right files.
- **Answers are only as good as what's written down.** A question whose answer appeared only
  in the docs (the AutoKuma label format) failed against the config files. It was answered
  correctly once a `docs` collection was attached. Documentation is the high-value tier 2
  content.
- **The 3B model makes things up from retrieved context.** For example, it presented a
  registry README's `insecure-registries` snippet as how the socket proxy works. Use 7B+ for
  answers; the 3B is only good for speed testing.

**Indexing speed:** ~1–3 files/s for small config files. Long Markdown documents take ~10 s
each, since time scales with the number of chunks, not files.

## Next steps

1. ~~Add `compose.codeassist.yaml` with CPU limits, Ollama tuning and the CA mount~~
   (done 2026-10-01, see "Running it").
2. Check whether the CA mount fixes `ollama pull` on a TLS-intercepting network. If not, add
   a generic model-import script under `scripts/`.
3. Feed a wiki into Open WebUI (Git storage → `owui-sync.py`) and test tier 2 questions
   against it.
4. Benchmark candidate chat models on the real target VM, one at a time.
5. Point an editor extension (Continue) at Open WebUI's API with an API key.

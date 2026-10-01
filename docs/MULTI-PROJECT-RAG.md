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

## Offline setup

- **Models:** download on a connected machine and import on the target. Either copy Ollama's
  models directory, or download GGUF files and run `ollama create` with a Modelfile. A
  generic import script belongs under `scripts/`.
- **Open WebUI** downloads a sentence-transformers embedding model from HuggingFace the first
  time it starts. To stop that, set `OFFLINE_MODE=true` / `HF_HUB_OFFLINE=1` and
  `RAG_EMBEDDING_ENGINE=ollama`, so embeddings come from a model already loaded into Ollama.
- **VS Code extension:** may need an offline VSIX install if the marketplace is blocked.
- **Container images:** use `podman save`/`load` if registries are blocked too.

## RHEL 9 / podman notes

- This repo's launch method depends on Compose `include:`, and `podman-compose` doesn't
  handle that reliably. Instead, use `podman compose` with the real `docker-compose` v2
  binary as the provider, talking to the podman socket. Check this first: it decides how much
  of this repo's structure works unchanged.
- SELinux: bind mounts need `:Z`.

## Relation to the living-memory work

Tier 2 is the same "promote, don't federate" idea as KNOWLEDGE.md: collect curated, generated
knowledge in one place instead of indexing everything raw. If tier 2 works, the Wiki.js/n8n
pipeline built there could hold the generated project summaries.

## Next steps

1. Add `compose.codeassist.yaml` (base + `ai/ollama` + `ai/webui`) with `cpus:`/`mem_limit:`
   set to match the target VM, so local tests behave like the real hardware.
2. Add a generic model-import script under `scripts/`.
3. Benchmark 2–3 candidate chat models: tok/s and time to first token, with and without RAG.
4. Build tier 2 for 2–3 related projects and judge whether the answers are useful.
5. Record the results here.

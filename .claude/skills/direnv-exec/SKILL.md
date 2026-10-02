---
name: direnv-exec
description: Run shell commands with this project's direnv environment (.envrc) actually loaded, instead of silently missing it. Use whenever a repo has a tracked .envrc — including this one, which uses it for COMPOSE_FILE/deploy-style selection and .env loading — especially before docker compose, or any command whose behavior depends on env vars .envrc sets.
---

# direnv-exec

## The problem this solves

An agent's shell tool runs each command in a fresh, non-interactive shell. direnv's hook
only fires on an interactive `cd` or shell prompt — it does **not** fire for a one-off
non-interactive command. So a plain `cd <repo> && <command>` picks up whatever's already
on `$PATH`/in the environment, silently skipping anything `.envrc` would have set up.

This repo's own `.envrc` is a concrete example of what gets missed:

```bash
dotenv_if_exists .env
export HOSTNAME="$(hostname)"
# ...
if [[ -n "${DEPLOY_STYLE:-}" ]]; then
  export COMPOSE_FILE="docker-compose.yaml:compose.${DEPLOY_STYLE}.yaml"
fi
```

Without it having actually run, `docker compose up -d` targets only the base
`docker-compose.yaml` (Traefik + whoami) even if the user has a `DEPLOY_STYLE` set for a
fuller stack, and `HOSTNAME` interpolation in compose files falls back to whatever the
non-interactive shell already had (often unset or wrong). Never assume the ambient shell
environment matches what an interactive shell with direnv would have.

## The fix: `direnv exec`

Use `direnv exec <repo-dir> <command...>` instead of `cd <repo-dir> && <command...>`:

```bash
direnv exec /path/to/this/repo docker compose up -d
direnv exec /path/to/this/repo docker compose ps
```

This loads `.envrc` in a throwaway subshell and execs the given command inside that
environment — no need to `cd` first, and no environment state lingers between separate
tool calls the way it would in a persistent interactive shell.

## Guardrail: don't run `direnv allow` yourself

If `direnv exec` errors out or silently doesn't apply the environment, it usually means
`.envrc` hasn't been trusted on this machine yet (`direnv allow` was never run for this
directory). Don't work around this by hand-exporting the variables yourself — tell the
user to run `direnv allow <repo-dir>`. Trusting a `.envrc` means agreeing to run arbitrary
shell code in it automatically; that's a decision that belongs to whoever owns the
machine, not something to wave through on their behalf.

## General pattern

Any directory with a tracked `.envrc` — in this repo or another project — should be
treated the same way: don't trust the ambient shell environment, route explicitly through
`direnv exec <that-dir> <command>` any time the command's correctness depends on env vars
the `.envrc` sets.

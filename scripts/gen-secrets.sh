#!/usr/bin/env bash
# Generate a real .env from a service's .env.example, filling in random
# secrets so nothing ships with "changeme" or a shared committed default.
#
# Usage:
#   scripts/gen-secrets.sh <service-dir> [<service-dir> ...]
#   scripts/gen-secrets.sh --all
#   scripts/gen-secrets.sh --force <service-dir>   # overwrite an existing .env
#
# For each <service-dir>/*.env.example found, writes the matching real file
# (.env.example -> .env, .db.env.example -> .db.env, etc.) next to it.
#
# Value rules, read top-to-bottom per file:
#   KEY=changeme        -> random hex string
#   KEY=base64:changeme -> "base64:" + random base64 (e.g. Laravel APP_KEY)
#   KEY=$OTHERKEY        -> reuse the value already generated for OTHERKEY
#                           earlier in the same file (shared credentials)
#   KEY=anything-else    -> left as-is (not a secret, e.g. an email/username)

set -euo pipefail
cd "$(dirname "$0")/.."

force=0
targets=()
all=0

for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    --all) all=1 ;;
    *) targets+=("$arg") ;;
  esac
done

gen_hex() { openssl rand -hex 24; }
gen_b64() { openssl rand -base64 32; }

process_file() {
  local example="$1"
  local real="${example%.example}"

  if [[ -e "$real" && "$force" -ne 1 ]]; then
    echo "skip: $real already exists (use --force to regenerate)"
    return
  fi

  declare -A generated=()
  local out=""
  local line key value new_value refkey

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]]; then
      out+="$line"$'\n'
      continue
    fi
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      if [[ -z "$value" ]]; then
        new_value=""
      elif [[ "$value" =~ ^\$([A-Za-z_][A-Za-z0-9_]*)$ ]]; then
        refkey="${BASH_REMATCH[1]}"
        if [[ -v generated["$refkey"] ]]; then
          new_value="${generated[$refkey]}"
        else
          echo "warn: $example: $key references undefined \$$refkey, generating independently" >&2
          new_value="$(gen_hex)"
        fi
      elif [[ "$value" == base64:changeme ]]; then
        new_value="base64:$(gen_b64)"
      elif [[ "$value" == "changeme" ]]; then
        new_value="$(gen_hex)"
      else
        new_value="$value"
      fi
      generated["$key"]="$new_value"
      out+="${key}=${new_value}"$'\n'
    else
      out+="$line"$'\n'
    fi
  done < "$example"

  printf '%s' "$out" > "$real"
  chmod 600 "$real"
  echo "wrote: $real"
}

if [[ "$all" -eq 1 ]]; then
  while IFS= read -r -d '' f; do
    process_file "$f"
  done < <(find . -path ./.git -prune -o -name '*.env.example' -print0)
elif [[ "${#targets[@]}" -eq 0 ]]; then
  echo "Usage: $0 <service-dir> [<service-dir> ...] | --all [--force]" >&2
  exit 1
else
  for dir in "${targets[@]}"; do
    dir="${dir%/}"
    shopt -s nullglob dotglob
    examples=("$dir"/*.env.example)
    shopt -u nullglob dotglob
    if [[ "${#examples[@]}" -eq 0 ]]; then
      echo "warn: no *.env.example found in $dir" >&2
      continue
    fi
    for f in "${examples[@]}"; do
      process_file "$f"
    done
  done
fi

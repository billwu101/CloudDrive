#!/usr/bin/env bash
#
# Point the assistant at a model: rotate the API token, switch the model id, or
# both — then prove it actually works before you find out from a 503.
#
#   ./scripts/set-llm.sh                      # prompt for a new token
#   ./scripts/set-llm.sh --model qwen3.6:35b  # switch model, keep the token
#   ./scripts/set-llm.sh --model gemma4:31b --token-stdin < key.txt
#   ./scripts/set-llm.sh --list               # just show what the gateway serves
#
# Why this exists rather than "edit .env":
#
#   1. There are TWO .env files and they are read by different processes.
#      Docker Compose reads ./.env; pytest reads ./backend/.env, because
#      Settings uses env_file=".env" which resolves against the working
#      directory. Updating only one produces a working browser and a failing
#      test suite with no visible connection between them — that has already
#      cost an afternoon once.
#   2. A model id that the gateway does not serve fails at chat time as
#      "Could not connect to the local model", which sends you looking at the
#      network instead of at the model name. This checks the id against
#      /v1/models up front.
#
# The token is never echoed, never passed as a command-line argument (so it
# stays out of shell history and the process list), and both .env files are
# gitignored.

set -euo pipefail

cd "$(dirname "$0")/.."

ROOT_ENV=".env"
BACKEND_ENV="backend/.env"

MODEL=""
TOKEN_FROM_STDIN=0
LIST_ONLY=0
RESTART=1

usage() {
  sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="${2:-}"; [ -n "$MODEL" ] || { echo "--model needs a value" >&2; exit 2; }; shift 2 ;;
    --token-stdin) TOKEN_FROM_STDIN=1; shift ;;
    --list) LIST_ONLY=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 ;;
  esac
done

for f in "$ROOT_ENV" "$BACKEND_ENV"; do
  [ -f "$f" ] || { echo "missing $f — run ./scripts/start.sh first" >&2; exit 1; }
done

# ── Collect the new token, if any ────────────────────────────────────────────
NEW_TOKEN=""
if [ "$LIST_ONLY" -eq 0 ]; then
  if [ "$TOKEN_FROM_STDIN" -eq 1 ]; then
    IFS= read -r NEW_TOKEN
  elif [ -z "$MODEL" ]; then
    # No model given and no stdin: the intent is a token rotation.
    printf 'New LLM API token (input hidden, Enter to keep the current one): ' >&2
    IFS= read -rs NEW_TOKEN
    printf '\n' >&2
  fi
fi

# ── Apply to both .env files ─────────────────────────────────────────────────
if [ "$LIST_ONLY" -eq 0 ]; then
  MODEL="$MODEL" NEW_TOKEN="$NEW_TOKEN" python3 - "$ROOT_ENV" "$BACKEND_ENV" <<'PY'
import os, re, sys

model = os.environ.get("MODEL") or ""
token = os.environ.get("NEW_TOKEN") or ""

def put(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    if re.search(rf"^{key}=", text, re.M):
        return re.sub(rf"^{key}=.*$", line, text, flags=re.M)
    return text.rstrip("\n") + "\n" + line + "\n"

for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    if token:
        s = put(s, "LLM_API_KEY", token)
    if model:
        s = put(s, "ASSISTANT_MODEL", model)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(s)

changed = [n for n, v in (("LLM_API_KEY", token), ("ASSISTANT_MODEL", model)) if v]
print("updated in both .env files: " + (", ".join(changed) if changed else "nothing"))
PY

  # The two files must not drift — that is the whole point of this script.
  if ! diff -q \
      <(grep -E '^(LLM_BASE_URL|ASSISTANT_MODEL|LLM_API_KEY)=' "$ROOT_ENV" | sort) \
      <(grep -E '^(LLM_BASE_URL|ASSISTANT_MODEL|LLM_API_KEY)=' "$BACKEND_ENV" | sort) >/dev/null; then
    echo "! ${ROOT_ENV} and ${BACKEND_ENV} disagree on base_url/model/key." >&2
    echo "  Docker reads the first, pytest the second — fix before continuing." >&2
    exit 1
  fi
  echo "✓ ${ROOT_ENV} and ${BACKEND_ENV} agree"
fi

# ── Verify against the gateway ───────────────────────────────────────────────
# Runs on the host with the values just written, so it checks the same thing
# pytest will see. Prints the served model list either way.
python3 - "$ROOT_ENV" <<'PY'
import json, sys, urllib.error, urllib.request

env = {}
with open(sys.argv[1], encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

base = env.get("LLM_BASE_URL", "").rstrip("/")
key = env.get("LLM_API_KEY", "")
want = env.get("ASSISTANT_MODEL", "")
if not base:
    print("! LLM_BASE_URL is empty"); raise SystemExit(1)

# A browser-ish UA: Cloudflare in front of this gateway rejects the default
# Python-urllib signature with a 1010, which would otherwise read as "bad key".
req = urllib.request.Request(
    base + "/models",
    headers={
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        ids = [m["id"] for m in json.load(resp)["data"]]
except urllib.error.HTTPError as exc:
    body = exc.read()[:200].decode("utf-8", "replace").replace("\n", " ")
    if exc.code == 401:
        print(f"! HTTP 401 — the token was rejected. {body}")
    else:
        print(f"! HTTP {exc.code} — {body}")
    raise SystemExit(1)
except Exception as exc:  # noqa: BLE001 - surfacing any transport failure verbatim
    print(f"! could not reach {base}: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

print(f"✓ gateway reachable, token accepted — {len(ids)} models served:")
for i in ids:
    print(("   * " if i == want else "     ") + i)

if want and want not in ids:
    print(f"\n! ASSISTANT_MODEL={want} is NOT in that list.")
    print("  The assistant will answer 503 with a misleading "
          "'could not connect' message. Pick one of the ids above:")
    print(f"      ./scripts/set-llm.sh --model {ids[0]}")
    raise SystemExit(1)
PY

# ── Restart so the running backend picks the values up ───────────────────────
if [ "$LIST_ONLY" -eq 0 ] && [ "$RESTART" -eq 1 ]; then
  if docker compose ps --status running --services 2>/dev/null | grep -qx backend; then
    echo "→ restarting backend to pick up the new settings"
    docker compose up -d backend >/dev/null
    echo "✓ backend restarted (in-container ASSISTANT_MODEL: $(docker compose exec -T backend printenv ASSISTANT_MODEL 2>/dev/null || echo '?'))"
  else
    echo "· backend is not running; start it with ./scripts/start.sh when you need it"
  fi
fi

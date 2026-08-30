#!/usr/bin/env bash
#
# Register the gateway's models as named assistant connections, so they show up
# in the model picker in the chat panel.
#
#   ./scripts/setup-model-connections.sh --email you@example.com
#   ./scripts/setup-model-connections.sh --email you@example.com --list
#   ./scripts/setup-model-connections.sh --email you@example.com --purge
#
# Connections are per user: each row carries its own base_url, model id and
# encrypted credential, so the same gateway appears once per model you want to
# offer. `GET /assistant/models` returns "local" (the server default from
# ASSISTANT_MODEL) plus every connection, and that list is what the picker shows.
#
# Reads base_url and the API key from ./.env, so it always registers the same
# gateway the server itself is pointed at. The password is prompted for, never
# passed as an argument.
#
# Requires CREDENTIAL_ENCRYPTION_KEY to be set for the *running* backend —
# without it the API answers 500 and nothing is stored. Note that key lives in
# both ./.env (Docker) and ./backend/.env (pytest); they must match.

set -euo pipefail

cd "$(dirname "$0")/.."

API="${API:-http://localhost:8001/api/v1}"
EMAIL=""
LIST_ONLY=0
PURGE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --email) EMAIL="${2:-}"; shift 2 ;;
    --api) API="${2:-}"; shift 2 ;;
    --list) LIST_ONLY=1; shift ;;
    --purge) PURGE=1; shift ;;
    -h|--help) sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -n "$EMAIL" ] || { echo "--email is required" >&2; exit 2; }

printf 'Password for %s (hidden): ' "$EMAIL" >&2
IFS= read -rs PASSWORD
printf '\n' >&2

export API EMAIL PASSWORD LIST_ONLY PURGE

python3 - <<'PY'
import json, os, pathlib, sys, urllib.error, urllib.request

API = os.environ["API"].rstrip("/")
EMAIL, PASSWORD = os.environ["EMAIL"], os.environ["PASSWORD"]
LIST_ONLY, PURGE = os.environ["LIST_ONLY"] == "1", os.environ["PURGE"] == "1"

# Models to offer, in the order they should appear. Keep the display names
# short: the picker shows "<label> - <model id>" and the panel is narrow.
MODELS = [
    ("Qwen3.6 35B", "qwen3.6:35b"),
    ("Gemma4 31B", "gemma4:31b"),
    ("Qwen3.8 27B", "qwen3.8:27b"),
    ("Nemotron 3 Super 120B", "nemotron-3-super:120b"),
    ("Muse Glimmer 30B", "muse-glimmer:30b"),
    ("Nemotron 3 Nano 30B", "nemotron-3-nano:30b"),
]

env = {}
for line in pathlib.Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
BASE_URL, API_KEY = env.get("LLM_BASE_URL", ""), env.get("LLM_API_KEY", "")
if not BASE_URL or not API_KEY:
    print("! LLM_BASE_URL / LLM_API_KEY missing from .env"); sys.exit(1)


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:200].decode("utf-8", "replace")


status, body = call("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
if status != 200:
    print(f"! login failed ({status}): {body}"); sys.exit(1)
token = body["access_token"]
print(f"✓ signed in as {EMAIL}")

status, existing = call("GET", "/users/me/model-connections", token=token)
if status != 200:
    print(f"! could not list connections ({status}): {existing}"); sys.exit(1)

if PURGE:
    for c in existing:
        call("DELETE", f"/users/me/model-connections/{c['id']}", token=token)
        print(f"  removed {c['label']}")
    existing = []

if LIST_ONLY:
    status, options = call("GET", "/assistant/models", token=token)
    print(f"\nModel picker shows {len(options)} option(s):")
    for o in options:
        print(f"   {'✓' if o['available'] else '✗'} {o['label']}")
    sys.exit(0)

have = {c["model"] for c in existing}
created = skipped = failed = 0
for label, model in MODELS:
    if model in have:
        print(f"  · {label:24} already registered"); skipped += 1
        continue
    status, body = call(
        "POST", "/users/me/model-connections",
        {"label": label, "kind": "openai_compatible",
         "base_url": BASE_URL, "model": model, "secret": API_KEY},
        token=token,
    )
    if status in (200, 201):
        print(f"  ✓ {label:24} {model}"); created += 1
    else:
        detail = body.get("error", {}).get("message") if isinstance(body, dict) else body
        print(f"  ✗ {label:24} {status} {detail}"); failed += 1

print(f"\ncreated {created}, already present {skipped}, failed {failed}")

status, options = call("GET", "/assistant/models", token=token)
print(f"\nModel picker now shows {len(options)} option(s):")
for o in options:
    print(f"   {'✓' if o['available'] else '✗'} {o['label']}")
if failed:
    sys.exit(1)
PY

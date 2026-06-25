#!/usr/bin/env bash
#
# Cloud Drive — one-command bootstrap.
# Creates .env (with a random JWT secret) on first run, then builds and starts
# the full stack with Docker Compose. Re-runnable and idempotent.
#
#   ./scripts/start.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Ensure .env exists. On first creation, generate a strong JWT secret so the
#    deployment isn't left on the insecure default.
if [ ! -f .env ]; then
  echo "→ Creating .env from .env.example"
  cp .env.example .env
  if command -v openssl >/dev/null 2>&1; then
    secret="$(openssl rand -hex 32)"
    if sed --version >/dev/null 2>&1; then
      sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${secret}|" .env       # GNU sed
    else
      sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${secret}|" .env    # BSD/macOS sed
    fi
    echo "→ Generated a random JWT_SECRET_KEY"
  else
    echo "! openssl not found — edit JWT_SECRET_KEY in .env before any real use" >&2
  fi
fi

# 2. Resolve the compose command (v2 plugin or legacy binary).
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "Docker Compose not found. Install Docker Desktop, or docker + the compose plugin." >&2
  exit 1
fi

# 3. Build and start in the background.
echo "→ Building images and starting services (first run also runs DB migrations)..."
# shellcheck disable=SC2086
$DC up --build -d

# 4. Report where to go.
port="$(grep -E '^FRONTEND_PORT=' .env | head -n1 | cut -d= -f2 | tr -d '[:space:]')"
port="${port:-8088}"
echo ""
echo "✓ Cloud Drive is up."
echo "    App:    http://localhost:${port}"
echo "    Logs:   ${DC} logs -f"
echo "    Stop:   ${DC} down        (data is kept; add -v to wipe it)"

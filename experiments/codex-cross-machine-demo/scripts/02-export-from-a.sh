#!/usr/bin/env bash
# machine-a: copy auth.json to the shared transfer point + report what's inside.
set -euo pipefail

AUTH="$CODEX_HOME/auth.json"
if [ ! -f "$AUTH" ]; then
  echo "RESULT: PRIVATE KEY NOT IN auth.json"
  echo "（machine-a 沒有 auth.json：憑證在 OS keyring，無法以檔案搬到別機 → 集中式判不可行）"
  exit 0
fi

mkdir -p /transfer
cp "$AUTH" /transfer/auth.json
chmod 600 /transfer/auth.json

has_pk=$(jq -r 'if (.agent_identity.agent_private_key // "") != "" then "yes" else "no" end' "$AUTH" 2>/dev/null || echo "unknown")
has_tokens=$(jq -r 'if .tokens then "yes" else "no" end' "$AUTH" 2>/dev/null || echo "unknown")

echo "→ 已把 machine-a 的 auth.json 複製到 /transfer（搬運點）"
echo "  agent_private_key 在 auth.json 內 : $has_pk"
echo "  含 OAuth tokens                  : $has_tokens"
if [ "$has_pk" = "no" ]; then
  echo "  ⚠️ 私鑰不在 auth.json（可能在 keyring）——若 machine-b 用不起來即印證綁機。"
fi

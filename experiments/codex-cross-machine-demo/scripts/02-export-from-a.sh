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

# Scan ALL key paths for anything that looks like a private key, instead of
# guessing one exact field name (the JSON shape varies across codex versions).
has_pk=$(jq -r '[paths(scalars) as $p | ($p[-1]|tostring|ascii_downcase) | select(test("priv|pkcs8|secret_key|jwk"))] | if length>0 then "yes" else "no" end' "$AUTH" 2>/dev/null || echo "unknown")
has_tokens=$(jq -r 'if .tokens then "yes" else "no" end' "$AUTH" 2>/dev/null || echo "unknown")

echo "→ 已把 machine-a 的 auth.json 複製到 /transfer（搬運點）"
echo "  疑似私鑰欄位在 auth.json 內 : $has_pk"
echo "  含 OAuth tokens             : $has_tokens"
echo "  auth.json 的欄位路徑（只列 key 名、不含任何 value，可安全貼回）："
jq -r 'paths(scalars) as $p | "    ." + ($p|join("."))' "$AUTH" 2>/dev/null | sed -E 's/\.[0-9]+/[]/g' | sort -u
echo "  → 不論上面偵測如何，最終以 machine-b 實測為準（03-test-on-b.sh）。"

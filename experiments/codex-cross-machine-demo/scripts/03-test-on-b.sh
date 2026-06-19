#!/usr/bin/env bash
# machine-b: actually call codex with the transferred credential, and check refresh.
set -uo pipefail

AUTH="$CODEX_HOME/auth.json"
echo "================ machine-b 跨機驗證 ================"
echo "host=$(hostname)  CODEX_HOME=$CODEX_HOME"

if [ ! -f "$AUTH" ]; then
  echo "RESULT: PRIVATE KEY NOT IN auth.json"
  echo "（machine-b 沒有可用 auth.json —— 憑證留在原機/keyring，無法跨機）"
  exit 0
fi

has_pk=$(jq -r '[paths(scalars) as $p | ($p[-1]|tostring|ascii_downcase) | select(test("priv|pkcs8|secret_key|jwk"))] | if length>0 then "yes" else "no" end' "$AUTH" 2>/dev/null || echo unknown)
has_tokens=$(jq -r 'if .tokens then "yes" else "no" end' "$AUTH" 2>/dev/null || echo unknown)
echo "auth.json: suspected_private_key=$has_pk, tokens=$has_tokens"
# Only bail early if there's truly nothing usable. tokens alone may suffice if the
# token isn't device-bound — the real call below is the ground truth either way.
if [ "$has_pk" = "no" ] && [ "$has_tokens" = "no" ]; then
  echo "RESULT: PRIVATE KEY NOT IN auth.json"
  exit 0
fi

before=$(jq -r '.last_refresh // "none"' "$AUTH" 2>/dev/null || echo none)
echo "last_refresh(before call): $before"
echo "--- 在 machine-b 用搬來的憑證實際呼叫（消耗一次訂閱額度）---"

# codex exec runs a one-shot non-interactive task. --skip-git-repo-check avoids
# codex's "trusted directory" guard (an environment check, unrelated to auth).
out=$(codex exec --skip-git-repo-check "Reply with exactly: CROSS_MACHINE_OK" 2>&1)
rc=$?
echo "$out" | tail -25
echo "exit code: $rc"

after=$(jq -r '.last_refresh // "none"' "$AUTH" 2>/dev/null || echo none)
echo "last_refresh(after call):  $after"

echo "==================================================="
if [ "$rc" -eq 0 ] && echo "$out" | grep -q "CROSS_MACHINE_OK"; then
  echo "RESULT: CROSS-MACHINE OK"
  if [ "$after" != "$before" ]; then
    echo "  （access token 在非原機成功 refresh：last_refresh 有更新）"
  fi
elif echo "$out" | grep -qiE 'log ?in|unauthor|401|403|expired|re-?authenticate|sign ?in|invalid.*token|token.*invalid'; then
  echo "RESULT: DEVICE-BOUND / FAILED（明確的授權失敗 → 憑證可能綁原機）"
elif echo "$out" | grep -qiE 'trusted directory|skip-git-repo-check|usage:|unexpected argument|unknown option|no such|command not found'; then
  echo "RESULT: INCONCLUSIVE（環境/指令用法問題，與授權無關 —— 調整指令後重試）"
else
  echo "RESULT: INCONCLUSIVE（呼叫未成功，但非明確授權失敗；原因見上方輸出）"
fi

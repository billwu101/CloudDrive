#!/usr/bin/env bash
# machine-a: log in with the device-code flow (works in a headless container).
set -euo pipefail

echo "→ machine-a (host=$(hostname)): codex login --device-auth"
echo "  終端會給你一個 URL + 一次性碼；到瀏覽器登入你的 Codex/ChatGPT 訂閱並輸入碼。"
echo "  (前提：已在 ChatGPT Settings → Security 開啟 device code login)"
echo

codex login --device-auth

echo
echo "✓ 登入流程結束。檢查憑證："
if [ -f "$CODEX_HOME/auth.json" ]; then
  echo "  auth.json 在 $CODEX_HOME/auth.json"
  ls -l "$CODEX_HOME/auth.json"
else
  echo "  ! 找不到 $CODEX_HOME/auth.json —— 憑證可能存進了 OS keyring（SecretAuthStorage）。"
  echo "    若如此，後續會判定「無法只靠 auth.json 跨機」。"
fi

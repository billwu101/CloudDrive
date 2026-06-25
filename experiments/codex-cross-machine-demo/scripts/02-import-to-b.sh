#!/usr/bin/env bash
# machine-b (never logged in): import the transferred auth.json into its own CODEX_HOME.
set -euo pipefail

if [ ! -f /transfer/auth.json ]; then
  echo "! /transfer/auth.json 不存在 —— 先在 machine-a 跑 02-export-from-a.sh"
  exit 1
fi

echo "→ machine-b (host=$(hostname)): 匯入搬來的 auth.json 到乾淨 CODEX_HOME=$CODEX_HOME"
mkdir -p "$CODEX_HOME"
if [ -f "$CODEX_HOME/auth.json" ]; then
  echo "  (machine-b 原本就有 auth.json，覆蓋以確保只用搬來的這份)"
fi
cp /transfer/auth.json "$CODEX_HOME/auth.json"
chmod 600 "$CODEX_HOME/auth.json"
echo "✓ 已匯入。machine-b 從未自己 codex login，現在只持有從 machine-a 搬來的憑證。"

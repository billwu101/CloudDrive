#!/usr/bin/env bash
#
# deploy/setup-runner.sh — 一次性設定「部署主機」（Ubuntu）。
# 把 README「一次性：部署主機」的手動 5 步收斂成一支可重複執行的腳本：
#   Docker → 專用 gha-runner 帳號 → 下載/註冊 self-hosted runner（systemd 常駐）
#   → bootstrap 佈署檔（compose.prod.yml / deploy-cloud-drive / .env）→ sudoers。
# 之後每次部署，deploy-cloud-drive 會自動從 repo@SHA 同步 compose 與腳本本身，
# 因此本腳本只做「首次安裝」；唯 .env 永遠手動維護在主機。
#
# 用法（在 clone 下來的 repo 根目錄，以 root 執行）：
#   sudo bash deploy/setup-runner.sh <RUNNER_REGISTRATION_TOKEN>
#
# token 來源：GitHub → 該 repo → Settings → Actions → Runners → New self-hosted runner
#             （短效、約 1 小時內有效）。
#
# 可用環境變數覆寫預設：
#   REPO_URL       (預設 https://github.com/billwu101/CloudDrive)
#   RUNNER_NAME    (預設 <hostname>-production)
#   RUNNER_LABELS  (預設 production,docker)
#   RUNNER_VERSION (預設 抓 GitHub 最新)
#   RUNNER_USER    (預設 gha-runner)   RUNNER_DIR (預設 /opt/actions-runner)
#   APP_DIR        (預設 /opt/cloud-drive)
#
set -Eeuo pipefail

REG_TOKEN="${1:-}"
if [[ -z "${REG_TOKEN}" ]]; then
  echo "用法：sudo bash deploy/setup-runner.sh <RUNNER_REGISTRATION_TOKEN>" >&2
  echo "token 來源：GitHub → repo → Settings → Actions → Runners → New self-hosted runner" >&2
  exit 1
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "請以 root 執行（sudo）。" >&2
  exit 1
fi

REPO_URL="${REPO_URL:-https://github.com/billwu101/CloudDrive}"
RUNNER_USER="${RUNNER_USER:-gha-runner}"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
APP_DIR="${APP_DIR:-/opt/cloud-drive}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)-production}"
RUNNER_LABELS="${RUNNER_LABELS:-production,docker}"

# 本腳本位於 repo 的 deploy/ 下；REPO_ROOT 用來取 compose.prod.yml / deploy-cloud-drive / .env.prod.example。
SRC="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SRC}/.." && pwd)"
for f in "${REPO_ROOT}/compose.prod.yml" "${SRC}/deploy-cloud-drive" "${SRC}/.env.prod.example"; do
  [[ -f "${f}" ]] || { echo "錯誤：找不到 ${f}（請在 clone 下來的 repo 根目錄執行）。" >&2; exit 1; }
done

echo "==> 1/7 安裝 Docker + compose plugin"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 curl
systemctl enable --now docker

echo "==> 2/7 建立部署使用者 ${RUNNER_USER} 與目錄"
id -u "${RUNNER_USER}" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "${RUNNER_USER}"
mkdir -p "${RUNNER_DIR}"
chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_DIR}"

echo "==> 3/7 下載並解壓 GitHub Actions runner"
if [[ ! -f "${RUNNER_DIR}/config.sh" ]]; then
  RUNNER_VERSION="${RUNNER_VERSION:-$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | grep -oP '"tag_name":\s*"v\K[^"]+' | head -1)}"
  TARBALL="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
  curl -fsSL -o "/tmp/${TARBALL}" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${TARBALL}"
  tar xzf "/tmp/${TARBALL}" -C "${RUNNER_DIR}"
  rm -f "/tmp/${TARBALL}"
  chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_DIR}"
  "${RUNNER_DIR}/bin/installdependencies.sh"
else
  echo "   ${RUNNER_DIR} 已有 runner，略過下載。"
fi

echo "==> 4/7 註冊 runner（labels=${RUNNER_LABELS}）"
sudo -u "${RUNNER_USER}" "${RUNNER_DIR}/config.sh" \
  --url "${REPO_URL}" --token "${REG_TOKEN}" \
  --name "${RUNNER_NAME}" --labels "${RUNNER_LABELS}" \
  --work _work --unattended --replace

echo "==> 5/7 安裝 runner systemd 服務並啟動（開機自動啟動）"
( cd "${RUNNER_DIR}" && ./svc.sh install "${RUNNER_USER}" && ./svc.sh start )

echo "==> 6/7 Bootstrap 佈署檔到 ${APP_DIR}"
mkdir -p "${APP_DIR}"
install -m 640 -o root -g root "${REPO_ROOT}/compose.prod.yml" "${APP_DIR}/compose.prod.yml"
install -m 750 -o root -g root "${SRC}/deploy-cloud-drive"     /usr/local/sbin/deploy-cloud-drive
if [[ -f "${APP_DIR}/.env" ]]; then
  echo "   ${APP_DIR}/.env 已存在，保留不動（不覆蓋既有 secret）。"
else
  install -m 600 -o root -g root "${SRC}/.env.prod.example" "${APP_DIR}/.env"
  jwt="$(openssl rand -hex 32)"; pgpw="$(openssl rand -hex 24)"
  # .env.prod.example 中 POSTGRES_PASSWORD 與 DATABASE_URL 用同一個密碼佔位符，一次替換兩處。
  sed -i "s|__請替換成高強度密碼__|${pgpw}|g" "${APP_DIR}/.env"
  sed -i "s|__請用 openssl rand -hex 32 產生__|${jwt}|g" "${APP_DIR}/.env"
  echo "   已建立 ${APP_DIR}/.env 並產生隨機 JWT_SECRET_KEY 與 POSTGRES_PASSWORD。"
fi

echo "==> 7/7 設定 sudoers（只允許 ${RUNNER_USER} 免密跑部署腳本）"
echo "${RUNNER_USER} ALL=(root) NOPASSWD: /usr/local/sbin/deploy-cloud-drive" \
  > /etc/sudoers.d/cloud-drive-deploy
chmod 440 /etc/sudoers.d/cloud-drive-deploy
visudo -cf /etc/sudoers.d/cloud-drive-deploy

echo ""
echo "✓ 部署主機設定完成。"
# 提醒仍需手動填的密鑰（.env 範本裡剩下的 __佔位符__）
remaining="$(grep -oE '^[A-Z_]+=__[^_].*__$|^[A-Z_]+=__.*__' "${APP_DIR}/.env" 2>/dev/null \
  | sed -E 's/=.*//' | sort -u | tr '\n' ' ' || true)"
if [[ -n "${remaining}" ]]; then
  echo "⚠️ 下列 .env 鍵仍是佔位符、請手動填入真值（sudo 編輯 ${APP_DIR}/.env）：${remaining}"
fi
echo ""
echo "後續："
echo "  1. 確認 runner 已在 GitHub repo 的 Settings → Actions → Runners 顯示 online。"
echo "  2. 補齊上述 ${APP_DIR}/.env 待填密鑰（如 TUNNEL_TOKEN、LLM_API_KEY）。"
echo "  3. 首次部署：GitHub → Actions → Deploy production → Run workflow 輸入 40 字元 commit SHA，"
echo "     或 merge 一個 PR 到 main（會自動部署最新 commit）。"

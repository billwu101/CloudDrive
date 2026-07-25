# 部署設置（GitHub Actions + Self-hosted Runner）

CI/CD 規格見 [detailed-design.md §22](../doc/detailed-design.md)、規劃見 [proposal.md §26](../doc/proposal.md)、決策見 DEC-025/028。

CI 由 GitHub 託管 runner 執行（`.github/workflows/ci.yml`）；CD 由部署主機上的 self-hosted runner 執行（`.github/workflows/deploy.yml` → 本目錄的 `deploy-cloud-drive` 腳本）。

## 一次性：部署主機（Ubuntu）設置

### 一鍵設定（推薦）

clone 此 repo 到部署主機後，於 repo 根目錄以 root 執行：

```bash
sudo bash deploy/setup-runner.sh <RUNNER_REGISTRATION_TOKEN>
```

一支腳本完成下列全部：安裝 Docker + compose、建立 `gha-runner` 帳號、下載並註冊 self-hosted runner（labels `production,docker`）、裝成 systemd 常駐（開機自動啟動）、bootstrap 佈署檔到 `/opt/cloud-drive`、設定 sudoers。`.env` 若不存在會由 `.env.prod.example` 建立並自動產生隨機 `JWT_SECRET_KEY`/`POSTGRES_PASSWORD`；其餘須手動填的密鑰（如 `TUNNEL_TOKEN`、`LLM_API_KEY`）腳本結束時會列出提醒。可用環境變數 `REPO_URL`/`RUNNER_NAME`/`RUNNER_LABELS`/`RUNNER_VERSION` 等覆寫預設（見腳本開頭註解）。

> token 來源：GitHub → 該 repo → Settings → Actions → Runners → New self-hosted runner（短效，約 1 小時內有效）。

裝好後：確認 runner 於 repo 的 Settings → Actions → Runners 顯示 online → 補齊 `/opt/cloud-drive/.env` 待填密鑰 → 首次部署（Actions → Deploy production，或 merge 到 `main` 自動部署）。

### 手動（等價步驟，供理解／客製）

```bash
# 1) 專用帳號（不要用 root / 日常帳號）
sudo adduser --disabled-password --gecos "" gha-runner
sudo mkdir -p /opt/actions-runner && sudo chown -R gha-runner:gha-runner /opt/actions-runner

# 2) 安裝 self-hosted runner（指令以 GitHub → Settings → Actions → Runners → New 為準）
#    註冊時 labels 用：production,docker
sudo -iu gha-runner
cd /opt/actions-runner
# ... 依 GitHub 頁面下載/解壓 ...
./config.sh --url https://github.com/billwu101/CloudDrive \
  --token <GitHub 產生的短效 token> \
  --name ubuntu-production-01 --labels production,docker --work _work --unattended
exit
sudo ./svc.sh install gha-runner && sudo ./svc.sh start   # 裝成 systemd 常駐

# 3) 正式環境檔案
sudo mkdir -p /opt/cloud-drive
sudo cp compose.prod.yml /opt/cloud-drive/
sudo cp deploy/.env.prod.example /opt/cloud-drive/.env   # 然後編輯填入真實 secret
sudo chown root:root /opt/cloud-drive/.env && sudo chmod 600 /opt/cloud-drive/.env
sudo chmod 640 /opt/cloud-drive/compose.prod.yml

# 4) 部署腳本（root 擁有、不可被 runner 改）
sudo cp deploy/deploy-cloud-drive /usr/local/sbin/deploy-cloud-drive
sudo chown root:root /usr/local/sbin/deploy-cloud-drive && sudo chmod 750 /usr/local/sbin/deploy-cloud-drive

# 5) 只允許 runner sudo 執行這一個腳本（不加入 docker 群組）
echo 'gha-runner ALL=(root) NOPASSWD: /usr/local/sbin/deploy-cloud-drive' \
  | sudo tee /etc/sudoers.d/cloud-drive-deploy
sudo chmod 440 /etc/sudoers.d/cloud-drive-deploy
```

## 一次性：GitHub 設置

- **main 分支保護（Ruleset）**：禁止直接 push、要求 PR + ≥1 review、要求 `Backend tests`/`Frontend tests` 通過才可 merge。
- GHCR 由 CI 的 `GITHUB_TOKEN`（`packages: write`）推送，無需額外 secret。
- self-hosted runner **只用於 private repo、只跑 deploy.yml**；PR 一律 `ubuntu-latest`。

## 一次性：Cloudflare Tunnel（對外曝露正式站台；僅 CD）

正式環境以 Cloudflare Tunnel 對外，主機**不需開任何對外 port、不受動態 IP 影響**（規格見 [detailed-design §21.9](../doc/detailed-design.md)、需求見 [proposal §26.6](../doc/proposal.md)）。`cloudflared` 服務已在 `compose.prod.yml`，隨 `up -d` 一併啟動——只差 token 與 Cloudflare 端綁定：

1. **Cloudflare 端（Zero-Trust 儀表板，需你操作）**
   - `Cloudflare Dashboard → Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared`。
   - 建好後複製 **tunnel token**（`eyJ...` 那串）。
   - 在該 tunnel 的 **Public Hostname** 加一筆：`<CloudDrive 網域>`（例 `drive.example.com`）→ Service `HTTP` → `frontend:80`。
     （因 `cloudflared` 與 `frontend` 在同一 compose 網路，用服務名 `frontend:80` 即可。）
   - 網域需已加入你的 Cloudflare 帳號（DNS 由 Cloudflare 託管）；建 hostname 時會自動加 CNAME。
2. **主機端**
   - 把 token 寫進 `/opt/cloud-drive/.env` 的 `TUNNEL_TOKEN=`（檔案 `chmod 600`、不進 Git）。
   - `cd /opt/cloud-drive && docker compose -f compose.prod.yml --env-file .env up -d cloudflared`（或整包 `up -d`）。
3. **驗證**：`docker compose logs cloudflared` 應顯示 `Registered tunnel connection`；瀏覽器開 `https://<網域>` 可達前端、`/api` 正常。
4. **（可選）收斂暴露面**：確認 Tunnel 可用後，可移除 `compose.prod.yml` 中 frontend 的 `8088:80` 對外映射，改為只走 Tunnel。
5. **（可選後續）Cloudflare Access**：對該網域套 Zero-Trust policy（Google/Email OTP），加一道網路層前置登入閘。

> ⚠️ `TUNNEL_TOKEN` 等同 tunnel 的完整存取權，只存主機 `.env`、不進 Git、不外流。

## 設定同步（部署時自動；.env 除外）

部署腳本（見 [detailed-design §21.5](../doc/detailed-design.md)）在每次部署時，會**依要部署的 commit SHA 從 public repo 自動同步非機密設定到主機**：

- ✅ **`compose.prod.yml`**：自動抓 repo@SHA 覆蓋主機版 → 部署拓撲改動（如新增 `cloudflared`）**隨程式碼落地，不需手動 cp**。回滾時抓舊 SHA 的 compose，拓撲一併回滾。
- ✅ **部署腳本本身**：自動抓 repo@SHA、原子替換後以新版接手 → 腳本邏輯隨部署演進。
- ❌ **`.env` 真密鑰不同步**：只做**漂移檢查**——若範本（`.env.prod.example`）新增了主機 `.env` 沒有的鍵（如 `TUNNEL_TOKEN`），部署 log 會警告提醒你手動補值。
- 🔒 前置安全：只允許部署 **`main` 歷史上的 commit**（`compare/main...<SHA>`），即使 runner 被攻陷也無法部署未合併的惡意 commit。

> 上面「一次性：部署主機」的第 3、4 步（`cp compose.prod.yml`、`cp deploy-cloud-drive`）為 **bootstrap 首次安裝**；裝好含本機制的腳本後，之後 compose 與腳本都自動同步，不再需要手動 cp。**唯 `.env` 永遠手動維護在主機。**

## 日常流程

1. feature branch → PR → CI 通過 + review → merge `main`
2. merge 後 CI 自動建 image、以 commit SHA 推 GHCR
3. **自動部署**：CI 在 `main` 成功後，`deploy.yml` 由 `workflow_run` 自動觸發，部署該 commit（`head_sha`）到 self-hosted runner。無需手動操作。
4. self-hosted runner 執行 `deploy-cloud-drive`：pull → up -d → `/health` 檢查 → 成功或自動回滾

**手動部署／回滾**（仍保留）：**GitHub → Actions → Deploy production → Run workflow**，輸入要部署的 40 字元 commit SHA。用於重新部署舊版或回滾。

> ⚠️ 不使用 `latest` 部署；一律用完整 commit SHA（自動觸發用 CI commit 的 `head_sha`）。`.env` 只存主機、不進 Git。
> ⚠️ 自動觸發只在「push 到 `main` 且 CI 成功」時發生；PR 的 CI 與失敗的 CI 不會部署。

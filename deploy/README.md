# 部署設置（GitHub Actions + Self-hosted Runner）

CI/CD 規格見 [detailed-design.md §22](../doc/detailed-design.md)、規劃見 [proposal.md §26](../doc/proposal.md)、決策見 DEC-025/028。

CI 由 GitHub 託管 runner 執行（`.github/workflows/ci.yml`）；CD 由部署主機上的 self-hosted runner 執行（`.github/workflows/deploy.yml` → 本目錄的 `deploy-cloud-drive` 腳本）。

## 一次性：部署主機（Ubuntu）設置

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

## 日常流程

1. feature branch → PR → CI 通過 + review → merge `main`
2. merge 後 CI 自動建 image、以 commit SHA 推 GHCR
3. **自動部署**：CI 在 `main` 成功後，`deploy.yml` 由 `workflow_run` 自動觸發，部署該 commit（`head_sha`）到 self-hosted runner。無需手動操作。
4. self-hosted runner 執行 `deploy-cloud-drive`：pull → up -d → `/health` 檢查 → 成功或自動回滾

**手動部署／回滾**（仍保留）：**GitHub → Actions → Deploy production → Run workflow**，輸入要部署的 40 字元 commit SHA。用於重新部署舊版或回滾。

> ⚠️ 不使用 `latest` 部署；一律用完整 commit SHA（自動觸發用 CI commit 的 `head_sha`）。`.env` 只存主機、不進 Git。
> ⚠️ 自動觸發只在「push 到 `main` 且 CI 成功」時發生；PR 的 CI 與失敗的 CI 不會部署。

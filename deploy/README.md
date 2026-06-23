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

## 日常流程

1. feature branch → PR → CI 通過 + review → merge `main`
2. merge 後 CI 自動建 image、以 commit SHA 推 GHCR
3. **GitHub → Actions → Deploy production → Run workflow**，輸入要部署的 40 字元 commit SHA
4. self-hosted runner 執行 `deploy-cloud-drive`：pull → up -d → `/health` 檢查 → 成功或自動回滾

> ⚠️ 不使用 `latest` 部署；一律用完整 commit SHA。`.env` 只存主機、不進 Git。

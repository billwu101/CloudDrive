## 21. CI/CD 與部署實作

> 對應 proposal §26（規劃）與 §3.5 部署圖。本章為**實作規格**——實際檔案落在 repo 的 `.github/workflows/` 與部署主機 `/opt/cloud-drive/`，**以實際檔案為準**。適用：10 人以下小團隊、private repo、Ubuntu 內網部署主機、Docker Compose。範例已**適配本專案**（pgvector image、env 名稱、uv/npm 指令、`/health` endpoint）。

### 21.1 整體流程

```text
開發者 push / PR → GitHub-hosted Runner（CI：pytest·ruff·mypy / npm lint·test·build / docker build）
  → 合併 main 後建置正式 image → 以 commit SHA 推送 GHCR
  → 手動 workflow_dispatch → Ubuntu self-hosted Runner（CD）
  → 登入 GHCR → 固定部署腳本：compose pull → up -d → /health 檢查 → 失敗回滾
```

部署主機不需開放埠、不需讓 GitHub SSH 進入；Runner 以 `systemd` 常駐、主動連線 GitHub 領取工作。正式 image 只由 CI 產生，開發者不從本機推送。

### 21.2 檔案結構

```text
repo:   .github/workflows/{ci.yml,deploy.yml}、.github/CODEOWNERS、compose.prod.yml
主機:   /opt/cloud-drive/{compose.prod.yml,.env,.deploy.env}   # .env 只存主機、不進 Git
```

`.env`：DB 密碼、JWT secret 等正式設定；`.deploy.env`：目前部署的 image SHA；`compose.prod.yml`：正式容器配置。

### 21.3 Self-hosted Runner（安裝與安全）

- 專用帳號 `gha-runner`（**不用 root、不用日常帳號、不共用**）；以 `config.sh --labels production,docker --unattended` 註冊到 private repo；以 `svc.sh install/start` 裝成 `systemd` 服務常駐。
- **Runner 不加入 `docker` 群組**（docker 群組 ≈ root 權限）；改為**只能 `sudo` 執行單一固定部署腳本**，由 `/etc/sudoers.d/cloud-drive-deploy` 限定：
  ```text
  gha-runner ALL=(root) NOPASSWD: /usr/local/sbin/deploy-cloud-drive
  ```

### 21.4 compose.prod.yml（適配本專案）

```yaml
name: cloud-drive
services:
  postgres:
    image: pgvector/pgvector:pg16        # 適配：語意搜尋需 pgvector，非 postgres:16-alpine
    restart: unless-stopped
    env_file: [.env]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
  backend:
    image: ghcr.io/YOUR_OWNER/cloud-drive-backend:${IMAGE_TAG}
    restart: unless-stopped
    env_file: [.env]
    depends_on:
      postgres: {condition: service_healthy}
    volumes: [storage_data:/app/storage]   # 適配：LOCAL_STORAGE_PATH
    ports: ["127.0.0.1:8001:8000"]         # 只綁 loopback，由 nginx/前端對外
  frontend:
    image: ghcr.io/YOUR_OWNER/cloud-drive-frontend:${IMAGE_TAG}
    restart: unless-stopped
    depends_on: [backend]
    ports: ["8088:80"]
volumes: {postgres_data: {}, storage_data: {}}
```

`.env`（**env 名稱適配本專案**）：

```env
POSTGRES_DB=cloud_drive
POSTGRES_USER=cloud_drive
POSTGRES_PASSWORD=<高強度密碼>
DATABASE_URL=postgresql+asyncpg://cloud_drive:<密碼>@postgres:5432/cloud_drive  # 適配：asyncpg driver
JWT_SECRET_KEY=<高強度隨機值>          # 適配：非 JWT_SECRET
LOCAL_STORAGE_PATH=/app/storage
ASSISTANT_ENABLED=false                # 無 Ollama 時關閉
EMBEDDING_ENABLED=false
CREDENTIAL_ENCRYPTION_KEY=<Fernet key> # 啟用外部模型憑證才需
```

主機檔案權限：`.env` 設 `root:root 600`、`compose.prod.yml` 設 `640`。

正式環境的 secret（`JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、SMTP 密碼、LLM API key、`CREDENTIAL_ENCRYPTION_KEY` 等）一律由 secret manager 或 CI-CD secrets／受控環境變數注入，不寫入版控、不寫進文件；開發階段才以 `core/config.py` 預設值搭配本機 `.env`（不進版控）提供。系統內部的 refresh token 與 share token 僅儲存 hash，使用者外部模型憑證則加密存於 `user_external_credentials.secret_encrypted`。詳見[附錄 A](./appendix-a-decisions.md) DEC-028。

### 21.5 部署腳本 `/usr/local/sbin/deploy-cloud-drive`

固定流程（root 擁有、`750`）：(1) 驗證參數為完整 40 字元 commit SHA；(2) `docker compose -f compose.prod.yml pull` 先確認 image 可拉；(3) 寫入 `.deploy.env` 記錄 SHA；(4) `up -d --remove-orphans`；(5) 輪詢 **`http://127.0.0.1:8001/health`**（適配：對應 backend 容器 `8000`、compose 映射 `8001`）最多 30 次；(6) 成功則結束，**失敗則回滾**到 `.deploy.env` 的前一個 SHA 並重新 `up -d`。

### 21.6 CI Workflow（`.github/workflows/ci.yml`，指令適配本專案）

- **backend-test**（`working-directory: backend`）：`uv sync --frozen` → `uv run pytest` → `uv run ruff check app tests` → `uv run mypy app tests` → `docker build`。
- **frontend-test**（`working-directory: frontend`）：`npm ci` → `npm run lint` → `npm test -- --run` → `npm run build` → `docker build`。
- **publish-images**（僅 `push` 到 `main`、`needs` 前兩者、`permissions: packages: write`）：`docker/login-action` 登入 GHCR（`${{ secrets.GITHUB_TOKEN }}`）→ `build-push-action` 推 `cloud-drive-backend`/`cloud-drive-frontend:${{ github.sha }}`，用 `cache-from/to: type=gha`。
- **backend 映像依賴**：backend `Dockerfile` 需安裝 LibreOffice（headless），供 Preview 模組把 Office 文書轉 PDF 預覽（見 §6.9.5）；映像因此較大，屬已知取捨，不需此功能的部署可改用未含 LibreOffice 的映像（`document` 型自動退化為 `unsupported`）。

### 21.7 CD Workflow（`.github/workflows/deploy.yml`）

`on: workflow_dispatch`（input：完整 commit SHA）；`concurrency: cloud-drive-production`（同時只一個部署）；`runs-on: [self-hosted, linux, x64, production]`。步驟：驗證 SHA → 登入 GHCR → `sudo /usr/local/sbin/deploy-cloud-drive "${IMAGE_TAG}"`。**不 checkout、不 git pull、不 build**，只拉 CI 已建的 image。

### 21.8 GitHub 權限與安全規則

- **main 分支保護**：禁止直接 push、要求 PR + ≥1 review、要求 `backend-test`/`frontend-test` 通過才可 merge。
- **CODEOWNERS**：`.github/workflows/`、`*/Dockerfile`、部署設定由 maintainer review。
- **必要安全規則**：self-hosted 只用於 private repo、只跑 CD；PR 一律 `ubuntu-latest`、禁止 PR 用 self-hosted；Runner 非 root、不入 docker 群組、只能 sudo 固定腳本；正式 image 只由 CI 建、**用完整 SHA 不用 `latest`**；`.env` 只存主機；第三方 Action 正式上線釘完整 commit SHA。

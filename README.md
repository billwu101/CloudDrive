# Cloud Drive

React + TypeScript + Vite 前端與 FastAPI 後端的雲端硬碟專案。

## 快速啟動（Docker，推薦）

只需要安裝 **Docker**（含 Compose）。把 repo 拉下來後，一行指令啟動整套（前端 + 後端 + PostgreSQL，並自動套用資料庫 migration）：

```bash
./scripts/start.sh
```

首次執行會由 `.env.example` 建立 `.env` 並自動產生隨機 `JWT_SECRET_KEY`，接著 `docker compose up --build -d`。完成後開啟：

- 應用程式：<http://localhost:8088>

等價的手動方式：

```bash
cp .env.example .env      # 視需要編輯；保持預設即可在本機跑
docker compose up --build
```

所有設定都有可用預設值。通常只有非本機部署時才需要動 `.env`（至少改 `JWT_SECRET_KEY` 與 `POSTGRES_PASSWORD`）。
瀏覽器只會連到前端同源的 `/api`，由 nginx 反向代理到後端，因此**部署到任何主機都不需要改前端設定、也不會有 CORS 問題**。
AI 助理為選用功能：若沒有可連的 Ollama，將 `.env` 的 `ASSISTANT_ENABLED=false`，其餘功能（檔案、分享、搜尋、時光機）照常運作。

常用指令：

```bash
docker compose logs -f    # 看日誌
docker compose down       # 停止（保留資料；加 -v 連資料一起清除）
```

## 本機開發環境需求

僅在不透過 Docker、直接跑原始碼開發時需要：

- uv、Python 3.12（由 uv 管理）
- Node.js 22 以上、npm
- Docker Compose（整合測試需要 PostgreSQL）

## 後端

```bash
cd backend
uv sync --all-extras --dev
uv run uvicorn app.main:app --reload
```

健康檢查位於 <http://localhost:8000/health>。

後端品質檢查：

```bash
cd backend
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app tests
uv run pytest --cov=app --cov-report=term-missing
```

## 前端

```bash
cd frontend
npm ci
npm run dev
```

前端位於 <http://localhost:5173>。

前端品質檢查：

```bash
cd frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e
```

首次執行 E2E 前安裝 Chromium：

```bash
cd frontend
npm run playwright:install
```

## 服務與連接埠

`docker compose up --build` 啟動的服務（連接埠可在 `.env` 調整）：

| 服務 | 預設網址 / 埠 | 說明 |
| --- | --- | --- |
| frontend | <http://localhost:8088> | nginx 提供 SPA，並把 `/api` 反代到 backend |
| backend | <http://localhost:8000> | FastAPI；啟動時自動 `alembic upgrade head` |
| postgres | `localhost:5432` | 資料存於具名 volume `postgres_data` |

所有可調環境變數見 [`.env.example`](.env.example)。`.env` 不會進版控。

**部署到正式環境時務必覆寫**：`JWT_SECRET_KEY`（用 `openssl rand -hex 32`）、`POSTGRES_PASSWORD`；Compose 內的預設值只供本機使用。

## 正式環境部署與運維

> 設計目標：拉下 code、填最少參數、一行啟動。決策見 [decisions.md](doc/decisions.md) DEC-025。

### 對外暴露面

上述 port 映射方便本機開發與除錯；正式環境建議：

| 服務 | 正式環境建議 |
| --- | --- |
| frontend／nginx | 唯一對外入口，通常 `80/443`；展示環境可保留 `8088` |
| backend | 不直接對公網開放，只允許 nginx 或內部服務連線 |
| postgres | 不對公網開放，只允許 backend 內網連線 |
| Ollama／LLM | 若用本地模型，限制於主機或內網，不暴露公網 |

可用 compose override 移除 backend/postgres 的 `ports`，或以防火牆／security group 限制來源。

### 前端同源、nginx 反代 `/api`

瀏覽器只連到前端自己的 origin，由 nginx（[`frontend/nginx.conf`](frontend/nginx.conf)）把 `/api` 反代到 `backend:8000`；前端建置的 `VITE_API_BASE_URL` 預設相對路徑 `/api/v1`。好處：**部署到任何主機都不必重建前端、也完全避開 CORS**。只有 API 服務於不同 origin 時，才需把 `VITE_API_BASE_URL` 設為絕對網址。

### 設定與選用功能

`.env` 留空也能開機；需留意：

- `JWT_SECRET_KEY` — **正式部署必改**（`start.sh` 首次自動產生隨機值）。
- `POSTGRES_PASSWORD` — 任何共享／公開部署都要改。
- `ASSISTANT_ENABLED=false` — 沒有 Ollama 也能跑（檔案、分享、搜尋、時光機照常）。
- `EMBEDDING_ENABLED=false` — 不做語意搜尋（檔名 + 全文關鍵字搜尋仍可用）。
- `SNAPSHOT_SCHEDULER_ENABLED` — 時光機背景排程（自動快照 + blob GC）；compose 預設開（單 worker 安全），多 worker 部署需關閉並改外部 cron。

### Secret 管理

`.env` 不進版控；`.env.example` 只放可啟動的範例值。正式環境用 secret manager／CI-CD secrets／受控環境變數注入：

| Secret | 用途 | 注意 |
| --- | --- | --- |
| `JWT_SECRET_KEY` | 簽發 access/refresh token | 必須隨機高熵值 |
| `POSTGRES_PASSWORD` | PostgreSQL 密碼 | 不用 compose 範例密碼 |
| `EMAIL_PROVIDER` / `SMTP_*` | 忘記密碼與通知寄信 | 無 SMTP 可用 console provider |
| `LLM_API_KEY` | OpenAI 相容或私有模型 | 用 Ollama 時可為 dummy |
| `CREDENTIAL_ENCRYPTION_KEY` | 加密使用者外部模型憑證 | 未設定時 per-user 外部憑證視為關閉 |

系統內部不存明文 token：refresh token、分享連結 token 只存 hash；外部模型使用者憑證存於 `user_external_credentials.secret_encrypted`，API 只回遮罩。

### 連到主機上的 Ollama

啟用助理／語意搜尋需可連的 Ollama。compose 預設 `LLM_BASE_URL=http://host.docker.internal:11434`，並對 backend 加 `extra_hosts: host.docker.internal:host-gateway`，讓容器（含 Linux 原生 Docker）連到主機上的 Ollama。語意搜尋另需 `ollama pull nomic-embed-text`。

### 運維注意事項

- **多 worker／多副本**：in-process 時光機排程器（[`app/snapshot/scheduler.py`](backend/app/snapshot/scheduler.py)）假設單一程序。水平擴展時設 `SNAPSHOT_SCHEDULER_ENABLED=false`，改用外部 cron 呼叫 `SnapshotService` 的 `run_scheduled_snapshot`／`collect_garbage`。
- **資料保留**：`docker compose down` 保留資料 volume；`down -v` 連 Postgres 與 blob 一起清除。
- **Migration**：新增 migration 後，重啟 backend 容器即自動 `alembic upgrade head`。
- **嵌入維度**：`file_embeddings.embedding` 是 `vector(768)`，須與 `EMBEDDING_MODEL` 輸出維度一致；換模型維度不同時，需改 migration 0012 與 `Settings.embedding_dim`。
- **上傳大小**：nginx `client_max_body_size`（110m）與後端 `MAX_UPLOAD_SIZE_BYTES`（預設 100MB）要一起調整。

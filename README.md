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

部署架構、運維注意事項（多 worker、資料保留、選用功能、Ollama 連線等）詳見 [doc/deployment.md](doc/deployment.md)。

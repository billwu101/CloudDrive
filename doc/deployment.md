# 部署指南

本專案的目標是：**把 code 拉下來、填最少的環境參數、執行一行指令就能跑起來**，不需要手動調一堆設定。本文件說明部署架構、設定項與運維注意事項。

決策記錄見 [decisions.md](./decisions.md) DEC-025。

## 一行啟動

只需要安裝 **Docker**（含 Compose）。

```bash
./scripts/start.sh
```

腳本的行為（可重複執行、幂等）：

1. 若 `.env` 不存在 → 由 [`.env.example`](../.env.example) 建立，並用 `openssl rand -hex 32` 產生隨機 `JWT_SECRET_KEY`（不會停在不安全的預設值）；已存在則不覆蓋。
2. 自動偵測 `docker compose`（v2 plugin）或 `docker-compose`（舊版）。
3. `up --build -d` 啟動全部服務。
4. 印出應用程式網址。

等價手動方式：

```bash
cp .env.example .env      # 視需要編輯；保持預設即可在本機跑
docker compose up --build
```

啟動後開啟 <http://localhost:8088>。後端容器在啟動時會自動 `alembic upgrade head`，資料庫 schema 免手動處理。

## 服務組成

`docker-compose.yml` 啟動的服務（連接埠可在 `.env` 調整）：

| 服務 | 預設 | 說明 |
| --- | --- | --- |
| frontend | `:8088` | nginx 提供 SPA，並把 `/api` 反向代理到 backend |
| backend | `:8000` | FastAPI（單一 uvicorn worker）；啟動時自動套用 migration |
| postgres | `:5432` | `pgvector/pgvector:pg16`（Postgres 16 + `vector` 擴充，供語意搜尋）；資料在具名 volume `postgres_data` |

檔案 blob 存於具名 volume `storage_data`（容器內 `/app/storage`）。

## 部署友善的關鍵設計

### 前端同源、nginx 反向代理 `/api`

瀏覽器只會連到**前端自己的 origin**，由 nginx（[`frontend/nginx.conf`](../frontend/nginx.conf)）把 `/api` 反代到 `backend:8000`。前端建置時的 `VITE_API_BASE_URL` 預設是相對路徑 `/api/v1`。

帶來的好處：

- **部署到任何主機（不同 IP／網域）都不必重建前端、不必改設定** —— 不像把 API 網址編譯進前端那樣綁死 `localhost`。
- **完全避開 CORS** —— 因為是同源請求。

只有在「API 服務於不同 origin」的特殊情況才需要把 `VITE_API_BASE_URL` 設為絕對網址。

### 設定都有安全預設，選用功能可關閉

`.env` 留空也能開機。需要留意的設定：

- `JWT_SECRET_KEY` — **正式部署必改**（`start.sh` 首次會自動產生隨機值）。
- `POSTGRES_PASSWORD` — 任何共享／公開部署都要改。
- AI 助理與語意搜尋為**選用**，關閉時不影響其餘功能：
  - `ASSISTANT_ENABLED=false` → 沒有 Ollama 也能跑（檔案、分享、搜尋、時光機照常）。
  - `EMBEDDING_ENABLED=false` → 不做語意搜尋（檔名 + 全文關鍵字搜尋仍可用）。
- `SNAPSHOT_SCHEDULER_ENABLED` — 時光機背景排程（自動快照 + blob GC）。compose 預設開（單 worker 安全），多 worker 部署需關閉並改外部 cron。

完整清單見 [`.env.example`](../.env.example)。

### 連到主機上的 Ollama

若要啟用助理／語意搜尋，需要可連的 Ollama。compose 預設 `LLM_BASE_URL=http://host.docker.internal:11434`，並對 backend 加 `extra_hosts: host.docker.internal:host-gateway`，讓容器（含 Linux 原生 Docker）能連到**主機上**的 Ollama。語意搜尋另需 `ollama pull nomic-embed-text`。

## 運維注意事項

- **多 worker／多副本**：in-process 的時光機排程器（[`app/snapshot/scheduler.py`](../backend/app/snapshot/scheduler.py)）假設單一程序。若水平擴展，請把 `SNAPSHOT_SCHEDULER_ENABLED=false`，改用外部 cron 呼叫同樣的 `SnapshotService` 方法（`run_scheduled_snapshot` / `collect_garbage`），避免重複執行。
- **資料保留**：`docker compose down` 保留資料 volume；`docker compose down -v` 會連 Postgres 與 blob 一起清除。
- **Migration**：新增 migration 後，重啟 backend 容器即會自動 `alembic upgrade head`。
- **嵌入維度**：`file_embeddings.embedding` 是 `vector(768)`，必須與 `EMBEDDING_MODEL` 的輸出維度一致；換模型若維度不同，需改 migration 0012 與 `Settings.embedding_dim`。
- **上傳大小**：nginx `client_max_body_size` 設為 110m，對應後端 `MAX_UPLOAD_SIZE_BYTES` 預設（100MB）。兩者要一起調整。

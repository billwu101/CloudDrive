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

## 助理模型設定

助理可接兩種後端：本機 Ollama（`LLM_PROVIDER=ollama`，預設），或任何 OpenAI 相容的
`/v1/chat/completions` 端點（`LLM_PROVIDER=openai_compatible`，例如自架 gateway）。

### 切換模型或輪換 token

用 [`scripts/set-llm.sh`](scripts/set-llm.sh)，不要手動改 `.env`：

```bash
./scripts/set-llm.sh                       # 互動式輸入新 token（隱藏輸入）
./scripts/set-llm.sh --model qwen3.6:35b   # 只換模型，token 不動
./scripts/set-llm.sh --list                # 列出端點目前服務的模型
./scripts/set-llm.sh --token-stdin < key.txt
```

腳本會寫入設定、驗證、然後重啟 backend。**手動改檔容易踩到下面兩個坑，這正是它存在的理由**：

- **設定有兩份 `.env`，由不同行程讀取。** Docker Compose 讀根目錄的 `.env`，
  pytest 讀 `backend/.env`——因為 `Settings` 的 `env_file=".env"` 是相對於行程的工作目錄。
  只改一份的症狀是「瀏覽器裡好好的，整合測試卻以憑證錯誤失敗」，而且兩者看不出關聯。
  腳本一律同時寫入兩份並在寫完後比對。
- **模型 id 打錯不會有明確錯誤。** 設成端點沒有服務的 id，對話時只會回
  「Could not connect to the local model」，把人引導去查網路而不是查模型名稱。
  腳本套用後會對 `/v1/models` 檢查該 id 是否真的存在，不存在就中止並列出可用的。

token 全程不回顯、不經命令列參數（不進 shell history 與 process list）；兩份 `.env` 都在 `.gitignore` 內。

### 讓使用者在對話中切換多個模型

上面設定的是**預設模型**（助理面板中的 `Local (...)`）。若要讓下拉選單出現更多選項，
在「設定 → 模型連線」新增具名連線，或呼叫 API：

```bash
curl -X POST http://localhost:8088/api/v1/users/me/model-connections \
  -H "Authorization: Bearer <access-token>" -H 'Content-Type: application/json' \
  -d '{"label":"Qwen3.6 35B","kind":"openai_compatible",
       "base_url":"https://<你的-gateway>/v1","model":"qwen3.6:35b","secret":"<api-key>"}'
```

每筆連線各自帶 base_url、model 與憑證，因此同一個 gateway 的不同模型各建一筆即可。
`GET /api/v1/assistant/models` 會回傳 `local` 加上所有連線，即為面板下拉的內容。
憑證以 Fernet 加密存放（需設 `CREDENTIAL_ENCRYPTION_KEY`），API 只回遮罩值、永不回明文。

> **模型相容性**：助理的 planner 會送出**連續兩則 system 訊息**加 JSON schema 的
> `response_format`。部分模型的 chat template 不接受連續 system 訊息，會在上游回 5xx，
> 而使用者只會看到「連不上模型」。換用不熟悉的模型後，請實際對話一次確認。

實測結果（2026-08-30，對自架 gateway；「完整 planner」欄是把攔截到的真實請求原樣重送）：

| 模型 | 單一 system | 連續兩則 system | 完整 planner | planner 耗時 |
| --- | --- | --- | --- | --- |
| `nemotron-3-nano:30b` | ✅ | ✅ | ✅ | **10.4s**（最快） |
| `qwen3.8:27b` | ✅ | ✅ | ✅ | 19.5s |
| `gemma4:31b` | ✅ | ✅ | ✅ | 23.3s |
| `qwen3.6:35b` | ✅ | ✅ | ⚠️ 偶發空白 | 20–46s |
| `nemotron-3-super:120b` | ✅ | ✅ | ✅ | 53.5s |
| `muse-glimmer:30b` | ❌ | ❌ | ❌ | — |

- **`muse-glimmer:30b` 不可用**：任何請求都回 HTTP 200 但 `content` 為空字串，
  `finish_reason: stop`、`completion_tokens: 3`——模型產出的 token 被 chat template
  當成特殊標記剝除。屬 gateway 上該模型的設定問題，不是本專案的問題。
- **`qwen3.6:35b` 偶發空白**：完整 planner 請求曾出現一次 `content` 為空
  （其餘各次正常）。原因未確認；`max_tokens` 不是主因——實測 2048 的預算下
  reasoning 僅用約 500 token，四次連續請求皆正常。
- 連續兩則 system 訊息在這批模型上都能通過，但這是 gateway 端修過 chat template
  之後的結果；先前 `qwen3.6:35b` 曾因此對每個請求回 502。

## 部署與設定須知

除了上面的 `JWT_SECRET_KEY`／`POSTGRES_PASSWORD`，正式部署還有幾個不知道容易設定錯的地方：

- **選用功能可關** — 沒有 Ollama 時設 `ASSISTANT_ENABLED=false`；不需語意搜尋設 `EMBEDDING_ENABLED=false`，核心（檔案／分享／搜尋／時光機）照常運作。
- **要用 AI／語意搜尋** — 需可連的模型端點（Ollama 或 OpenAI 相容 gateway，見上方「助理模型設定」）；compose 預設連主機 `host.docker.internal:11434`，語意搜尋另需 `ollama pull nomic-embed-text`。
- **多 worker／多副本** — in-process 的時光機排程器假設單一程序，水平擴展時設 `SNAPSHOT_SCHEDULER_ENABLED=false` 並改用外部 cron。
- **換嵌入模型** — `file_embeddings.embedding` 為 `vector(768)`，維度須與 `EMBEDDING_MODEL` 一致，否則要改對應 migration 與 `Settings.embedding_dim`。
- **調上傳上限** — nginx `client_max_body_size` 與後端 `MAX_UPLOAD_SIZE_BYTES` 必須一起調整。

### 正式部署（CI/CD）

採 **GitHub Actions + self-hosted runner**：push／PR 跑 CI、合併 `main` 建 image 推 GHCR、手動觸發部署到 Ubuntu 主機（`pull` → `/health` 檢查 → 失敗回滾）。

- Workflow：[`.github/workflows/ci.yml`](.github/workflows/ci.yml)、[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)
- 正式環境 compose：[`compose.prod.yml`](compose.prod.yml)
- **主機與 GitHub 一次性設置步驟**：[`deploy/README.md`](deploy/README.md)

> 架構決策見 [decisions.md](doc/decisions.md) DEC-025／028；規劃見 [proposal.md](doc/proposal.md) §26；實作規格見 [detailed-design.md](doc/detailed-design.md) §22。

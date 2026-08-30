# Project Setup 與開發環境任務

## 完成定義

- 前後端專案可在本機啟動。
- PostgreSQL 與必要服務可透過 Docker Compose 啟動。
- 開發、測試與格式檢查指令可重複執行。

## 最小可執行任務

- [x] 建立 `frontend/` 目錄。
- [x] 使用 Vite 初始化 React + TypeScript。
- [x] 建立 `backend/` 目錄。
- [x] 初始化 Python 專案與 `pyproject.toml`。
- [x] 安裝 FastAPI 與 Uvicorn。
- [x] 安裝 SQLAlchemy、asyncpg、Alembic。
- [x] 安裝 PyJWT。
- [x] 安裝 `pwdlib[argon2]`。
- [x] 安裝 pytest 與 async test 工具。
- [x] 安裝 React Router。
- [x] 安裝 TanStack Query。
- [x] 安裝 Zustand。
- [x] 安裝 Tailwind CSS。
- [x] 初始化 shadcn/ui。
- [x] 安裝 React Hook Form 與 Zod。
- [x] 安裝 Vitest 與 React Testing Library。
- [x] 安裝 Playwright。
- [x] 建立 backend Dockerfile。
- [x] 建立 frontend Dockerfile。
- [x] 建立 `docker-compose.yml`。
- [x] 加入 PostgreSQL service。
- [x] 不保留未使用的 Redis service；背景需求由現有 service / scheduler 處理，未來需要 queue 時再新增。
- [x] 建立 PostgreSQL volume。
- [x] 建立 `.gitignore`。
- [x] 建立前端 lint 指令。
- [x] 建立後端 lint/format 指令。
- [x] 建立前端 test 指令。
- [x] 建立後端 test 指令。
- [x] 建立 README 啟動說明。
- [x] 驗證 frontend 可啟動。
- [x] 驗證 backend `/health` 可存取。
- [x] 驗證 backend 可連接 PostgreSQL。

## 助理模型與憑證切換腳本（2026-08-30）

`scripts/set-llm.sh` —— 輪換 LLM token、切換模型 id，並在套用後**實地驗證**。

- [x] 同時寫入 `.env` 與 `backend/.env`，並在寫入後比對兩者是否一致。
      兩份檔案由不同行程讀取（Compose 讀根目錄、pytest 讀 `backend/`，因為
      `Settings` 的 `env_file=".env"` 相對於工作目錄），只改一份會造成
      「瀏覽器正常但測試失敗」且兩者看不出關聯——此坑已實際發生過一次。
- [x] 對 `/v1/models` 驗證 token，並檢查 `ASSISTANT_MODEL` 是否在 gateway 的
      服務清單內。清單外的 model id 會在對話時變成
      「Could not connect to the local model」，把人引導去查網路而非模型名稱。
- [x] token 不經命令列參數（避免進入 shell history 與 process list）、
      不回顯、不寫入 repo（兩份 `.env` 皆在 `.gitignore` 內）。
- [x] 驗證請求帶瀏覽器 User-Agent：gateway 前面的 Cloudflare 會以 1010 拒絕
      預設的 `Python-urllib` 簽章，那個 403 看起來會像是 key 有問題。
- [x] 套用後自動重啟 backend 容器並印出容器內實際生效的 `ASSISTANT_MODEL`。
- [x] 實測：故意讓兩份 `.env` 漂移後執行，腳本正確修復並回報一致；
      token 失效時以離開碼 1 中止並印出 gateway 的原始訊息。

用法：

```bash
./scripts/set-llm.sh                       # 互動式輸入新 token（隱藏輸入）
./scripts/set-llm.sh --model qwen3.6:35b   # 只換模型
./scripts/set-llm.sh --list                # 只列出 gateway 目前服務的模型
./scripts/set-llm.sh --token-stdin < key.txt
```

## Cloudflare Tunnel（僅 CD 端；proposal §26.6 / detailed-design §21.9）

> 對外曝露正式站台，dev 不動。網域待使用者提供（proposal §26.6 待確認①）。

- [x] `compose.prod.yml` 新增 `cloudflared` 服務（`cloudflare/cloudflared`、`command: tunnel --no-autoupdate run`、`env_file: [.env]`、`depends_on: [frontend]`、`restart: unless-stopped`、無 `ports`）。
- [x] `deploy/.env.prod.example` 加入佔位鍵 `TUNNEL_TOKEN=`（示例值，不放真 token）。
- [x] 確認 `docker-compose.yml`（dev）**未**新增 cloudflared（範圍限定驗收）。
- [x] `deploy/README.md` 補說明：於 Cloudflare Zero-Trust 建立 remote-managed tunnel、取得 `TUNNEL_TOKEN` 寫入主機 `.env`、儀表板設 ingress（`<CloudDrive 網域>` → `frontend:80`）。
- [ ]（待網域）在 Cloudflare 儀表板綁定實際網域並設 ingress 路由。
- [ ]（待網域，決策②）決定前端是否移除 `8088:80` 對外映射、改由 Tunnel 內部直達。
- [ ] 驗收：正式主機 `docker compose -f compose.prod.yml up -d` 後 `cloudflared` 起、`https://<網域>` 可達前端、`/api` 正常；主機未開任何對外埠；`TUNNEL_TOKEN` 不在 Git。
- [ ]（可選後續）Cloudflare Access Zero-Trust 前置登入閘。

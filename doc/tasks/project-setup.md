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

# Cloud Drive

React + TypeScript + Vite 前端與 FastAPI 後端的雲端硬碟專案。

## 環境需求

- uv
- Python 3.12（由 uv 管理）
- Node.js 22 以上
- npm
- Docker Compose（完整環境啟動時需要）

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

## Docker Compose

```bash
docker compose up --build
```

預設服務：

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>
- PostgreSQL: `localhost:5432`

Redis 為保留的可選服務：

```bash
docker compose --profile cache up --build
```

Compose 中的預設密碼只供本機開發使用；部署時必須透過環境變數覆寫。

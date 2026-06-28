# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開發流程規則（Vibe Coding，強制遵守）

> **本節為最高優先的工作規則，每次執行都必須嚴格遵守，優先於下方 Commands／Architecture 等參考資訊。**
> 核心不可違反：不猜測使用者意圖（不明確即提問）、文件先行（proposal → detailed-design → tasks → prompt）、任務最小化、所有結果可驗證、不偽造或跳過測試、不在未確認時擅自決定範圍或刪改既有功能。

> 本文件定義使用 AI／Agent 進行 Vibe Coding 時，從需求確認、詳細設計、任務拆分、Prompt 生成，到自動化開發與驗收的統一規則。

### 一、核心原則

1. **不得猜測使用者意圖（使AI成果不發散）**
   - 任何需求、技術選型、功能邊界、驗收方式或執行環境不明確時，必須先提問。
   - 在重要問題尚未確認前，不得直接進入設計或程式實作。
   - 可以提出建議方案，但必須明確標示為「建議」，並由使用者確認。
2. **文件先行，程式後做（使AI成果不發散）**
   - 開發前必須依序完成：`doc/proposal.md` → `doc/detailed-design.md` → `doc/tasks/` → `doc/prompt.md`。
   - 文件內容未確認完成前，不得直接大量產生程式碼。
3. **模組化與低耦合**：系統拆分成職責清楚、相互獨立、可獨立開發測試驗收的模組；模組間只透過明確介面／資料結構／API 溝通。
4. **任務必須最小化**：每個任務只處理一個清楚、可驗證的目標，具備輸入、輸出、依賴、實作要求與驗收條件。
5. **所有結果必須可驗證**：不以「看起來完成」為標準；每項功能都有可重複執行的驗證；測試、型別檢查與品質檢查必須通過。

### 二、標準專案文件流程

- **階段 1 需求（`doc/proposal.md`）**：專案背景與目標、使用者角色、使用情境、功能／非功能需求、執行平台、輸入輸出、技術限制、安全與授權、不在範圍、驗收標準、待確認事項。不清楚處逐項提問；不自行決定未確認範圍；不把未確認方案寫成既定事實；目標須能轉成可測試驗收條件。
- **階段 2 詳細設計（`doc/detailed-design.md`）**：整體架構、模組劃分與職責、依賴關係、資料流程、核心資料結構、類別／函式／介面設計、API／事件格式、錯誤處理、日誌、設定與環境變數、效能限制、安全考量、測試設計、各模組驗收條件。每模組只負責一類工作；禁止循環依賴；核心邏輯不綁定 UI／FS／外部服務；外部依賴經抽象介面隔離；支援 Mock/Stub/Fake；公開介面說明輸入／輸出／錯誤／副作用；設計須可直接供任務拆分。
- **階段 3 任務拆分（`doc/tasks/<module>.md` + `progress.md`）**：每模組一份任務文件（目標／範圍／不含範圍／前置依賴／輸入／輸出／公開介面／子任務 checklist／測試要求／驗收條件／風險／完成紀錄）。子任務狀態：`[ ]` 未完成、`[-]` 進行中、`[x]` 完成、`[!]` 阻塞。標示依賴順序與可平行任務；不同 Agent 不得同時改同檔；任務變更時同步更新設計與進度。
- **階段 4 Prompt（`doc/prompt.md`）**：定義專案目標、文件讀取順序、主／子 Agent 責任、任務分派、依賴處理、平行規則、測試與品質要求、進度更新、問題處理、整合與最終驗收、禁止事項。

### 三、Agent 執行規則

- **主 Agent**：先讀所有輸入文件；驗證需求／設計／任務一致；依賴未完成不啟動後續；依模組分派子 Agent；追蹤進度；防止改同檔；檢查輸出與測試；整合；更新 `progress.md`；執行最終完整測試；彙整未完成／已知問題／技術債。
- **子 Agent**：只處理被指派模組與檔案；先讀任務文件；不自行擴大範圍；不改他人公開介面；實作前確認相依介面；同時寫完整測試；完成後跑該模組測試；回報修改檔案／測試結果／剩餘問題；更新 checklist；遇不明確立即停止並回報。
- **平行執行**：僅當無前後依賴、不改同檔、不動同一公開介面、已定義共用資料格式與整合測試方式時才可平行。

### 四、程式碼品質規則

- 使用專案既有 Python 版本與 `uv`；新增依賴先確認必要性；禁止改全域環境；公開函式／類別提供型別註記與 Docstring；不留無用測試碼／除錯輸出／註解掉的大段程式。
- 必過檢查：`uv run pytest`、`uv run mypy .`、`uv run ruff check .`、`uv run ruff format --check .`（專案有不同指令以專案設定為準）。
- 測試：每模組單元測試；核心流程整合測試；每個錯誤分支至少一測試；不依賴不穩定外部網路；外部 API／FS／時間／隨機可替換或 Mock；修 Bug 先寫能重現的測試；驗證行為而非追覆蓋率數字；測試全通過前任務不得標完成。
- **完成定義**：功能實作 + 單元測試通過 + 型別檢查通過 + Ruff 通過 + 文件已更新 + checklist 已更新 + 無未說明技術債 + 主 Agent 已審查。

### 五、需求與變更管理

1. 新需求不得直接插入實作階段。
2. 需求變更依序更新 `proposal.md` → `detailed-design.md` → `tasks/` → `prompt.md`。
3. 每次變更記錄：原因、影響模組、是否影響公開介面、是否需 Migration、是否需新增／修改測試。
4. 需求與現有設計衝突時，停止開發並要求確認。
5. 不得為了快速完成而默默改變驗收標準。
6. **程式碼／功能變更完成後，必須回填同步設計文件**（即使是先實作再補文件的情況也一樣）：把該變更寫進 `doc/proposal.md` 與 `doc/detailed-design.md`。
   - **分層**：`proposal.md` 只寫**需求面**（使用者可見的功能、行為、對應的 API 端點）；`detailed-design.md` 寫**實作面**（模組職責、資料結構、公開介面、設定與決策，例如 CORS／檔名規則／串流方式等）。實作細節不要寫進 proposal。
   - **不重複**：兩份文件中**已經提到的就不再重寫**，只補真正缺漏或被本次變更改動的部分。
   - **不確定就問**：某項該進 proposal 還是 detailed、是否算「已提到」、要補到哪個章節不清楚時，**先停下來問使用者，不擅自決定範圍**。

### 六、安全與敏感資訊規則

- 禁止把密碼／Token／API Key／私鑰／真實帳號寫入程式碼；敏感設定經環境變數提供；`.env` 不入 Git，提供僅含示例值的 `.env.example`；日誌不輸出敏感資訊；測試用虛構／匿名化資料；外部檔案／ROM／模型／資料集須確認合法來源與授權；未確認授權不得把受版權保護檔案加入公開儲存庫。

### 七、Git 與版本控制規則

- 每個 Commit 只處理一個主題；Commit 前跑相關測試；禁止提交 `.env`／密鑰／大型暫存檔／測試輸出／IDE 個人設定／未授權 ROM／模型／資料；功能／重構／格式盡量分開提交；不以重寫歷史掩蓋錯誤；合併前確認測試通過、無衝突、文件同步、公開介面未被破壞。
- Commit 格式：`feat:`／`fix:`／`test:`／`docs:`／`refactor:`／`chore:`。

### 八、禁止事項

- 不得在需求未確認時直接建立完整系統；不得猜測偏好的框架／UI／資料庫／部署；不得讓一個 Agent 負責所有模組；不得產生無法執行或未測試的大量程式碼；不得跳過測試換速度；不得任意改已確認公開介面；不得隱藏錯誤／忽略失敗測試／偽造測試結果；不得在文件與程式碼不一致時標完成；不得未經同意刪除既有功能或資料；不得把暫時性實作當最終設計而不加說明。

### 九、最終原則

Vibe Coding 的重點是建立「需求明確、設計可落地、任務可拆分、模組可獨立、結果可測試、進度可追蹤、問題可回溯、整體可維護」的自動化開發流程，而非單純讓 AI 快速產生程式碼。


## Commands

### Backend (`cd backend`)

```bash
uv sync --all-extras --dev          # install deps
uv run uvicorn app.main:app --reload  # dev server (localhost:8000)

# Quality checks
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app tests
uv run pytest                        # all unit tests
uv run pytest tests/integration      # integration tests (needs Postgres)
uv run pytest tests/drive/test_router.py::test_list_items_returns_page  # single test
uv run pytest -k "test_quota"        # filter by name
uv run pytest --cov=app --cov-report=term-missing
```

Integration tests require a running PostgreSQL instance. The default URL is `postgresql+asyncpg://postgres:postgres@localhost:5432/clouddrive_test` (set via `DATABASE_URL` env var or start with `docker compose up postgres`).

### Frontend (`cd frontend`)

```bash
npm ci                    # install deps
npm run dev               # dev server (localhost:5173)
npm run lint
npm run typecheck
npm run test -- --run     # all unit tests (one-shot)
npm run test              # watch mode
npx vitest run src/api/authApi.test.ts   # single file
npx vitest run -t "stores access token"  # filter by test name
npm run build
npm run playwright:install  # first-time only
npm run test:e2e
```

### Docker

```bash
docker compose up --build   # start all services
docker compose up postgres  # Postgres only (for integration tests)
```

## Architecture

### Backend

Every domain is a self-contained package under `backend/app/<module>/` with four files: `router.py`, `service.py`, `repository.py`, `schemas.py`. Modules never import from each other's internals — they import each other's services via FastAPI dependency injection.

```
app/
  core/          config, security (JWT), exceptions, dependencies
  models/        SQLAlchemy ORM models (all imported into Base metadata)
  schemas/       shared Pydantic response types (DriveItemResponse, Page, etc.)
  api/v1/router.py   aggregates all module routers
  <module>/
    router.py    FastAPI routes; depends on service via _module_service factory
    service.py   business logic; takes AsyncSession + other services
    repository.py  DB queries (raw SQLAlchemy)
    schemas.py   module-specific Pydantic I/O schemas
```

**Auth flow:** `get_current_user_id` (in `core/dependencies.py`) extracts a UUID from the JWT Bearer token. Every protected router depends on `CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]`.

**Error handling:** Raise typed subclasses of `AppError` — `NotFoundError` (404), `ForbiddenError` (403), `QuotaExceededError` (413), `NameConflictError` (409), `InvalidOperationError` (422). The global handler in `main.py` converts them to `{ "error": { "code": "...", "message": "...", "details": {} } }`.

**Migrations:** `backend/alembic/` — run `uv run alembic upgrade head` to apply.

**Storage:** `StorageProvider` protocol (in `app/storage/`) abstracts file I/O. `LocalStorageProvider` is the only implementation. The `LOCAL_STORAGE_PATH` env var must be set before app import because `get_settings()` is `@lru_cache`.

**Data model notes:**
- `user_item_preferences` table stores per-user starred state (not a column on `drive_items`)
- "Recent" items are derived from `activity_logs`, not `drive_items.updated_at`
- Refresh token and public share token are stored as hashes only

### Frontend

```
src/
  api/           authApi, driveApi, uploadApi, etc. — thin wrappers over axios
  app/           AuthInitializer, RequireAuth, RedirectIfAuth, router, ProtectedLayout
  stores/        authStore (Zustand) — access token only; uiStore, uploadStore
  hooks/         useAuth, useDrive, useUpload, etc. — TanStack Query wrappers
  pages/         one file per route
  components/    drive/, layout/, preview/, share/, trash/, upload/
```

**Auth / token lifecycle:**
- `authStore` holds the access token in memory only — no localStorage, no sessionStorage, no Zustand persist middleware.
- On every page load, `AuthInitializer` (`src/app/AuthInitializer.tsx`) calls `POST /auth/refresh` before the router renders. If the HttpOnly refresh token cookie is still valid, the access token is restored in Zustand and the user stays on their page. Until the attempt settles, `AuthInitializer` returns `null` to prevent `RequireAuth` from prematurely redirecting.
- `RequireAuth` then just reads `authStore.accessToken` — non-null means authenticated.
- The Axios interceptor in `client.ts` handles 401s on subsequent API calls by calling refresh again and retrying. It uses a separate `refreshClient` (no interceptors) to avoid infinite loops.

**API client:** `src/api/client.ts` exports `api` (main Axios instance) and `refreshClient` (interceptor-free, for refresh calls). `toApiError()` reads `d['code']` directly from the response body — MSW error handlers must return `{ code: '...', message: '...' }` flat, not nested.

**State:** Server state via TanStack Query (v5); UI/upload/auth state via Zustand (v5). Query keys are defined per-hook file using factory functions (`driveKeys.items(parentId)` etc.).

## Testing Patterns

### Backend unit tests

Each module's `tests/<module>/test_router.py` follows this pattern — no real DB needed:

```python
def _make_app(service: SomeService, user_id: UUID) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppError, ...)      # inline error handler
    app.dependency_overrides[get_db] = _fake_db   # AsyncMock session
    app.dependency_overrides[_some_service] = lambda: service
    app.include_router(some_router)
    return app

async def test_something(user_id, headers):
    svc = AsyncMock(spec=SomeService)
    svc.some_method.return_value = expected
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/endpoint", headers=headers)
    assert resp.status_code == 200
```

Auth header: `{"Authorization": f"Bearer {create_access_token(user_id)}"}` — creates a real JWT, no mocking needed.

### Backend integration tests

Live in `tests/integration/`. Require Postgres. Each test gets a clean DB via `TRUNCATE ... RESTART IDENTITY CASCADE` (automatic via the `_truncate_tables` fixture in `tests/integration/conftest.py`). Use `register_and_login(client)` helper to get a real access token. `LOCAL_STORAGE_PATH` must be set before any app import — the conftest handles this.

### Frontend unit tests

Use Vitest + MSW. Per-test MSW overrides: `server.use(http.get(...))` inside the test. Shared baseline handlers live in `src/test/handlers.ts`.

- Component tests **must** call `afterEach(() => cleanup())` explicitly — Vitest does not auto-clean the DOM.
- `queryByRole('cell')` also matches `<th>` — use `document.querySelectorAll('tbody td')` to check for empty table bodies.
- Axios encodes spaces as `+` in query strings — use `new URL(url).searchParams.get('q')` instead of `decodeURIComponent` in MSW handlers.
- `request.formData()` fails in MSW handlers with jsdom `File` objects (undici incompatibility) — use `request.text()` to inspect raw multipart bodies.

## Design Documents

`doc/` contains the authoritative design for the project:

| File | Purpose |
|---|---|
| `doc/prompt.md` | Codex multi-agent orchestration prompt + confirmed technical decisions |
| `doc/detailed-design.md` | Module-level architecture, service interfaces, API contracts |
| `doc/proposal.md` | Product requirements and feature design |
| `doc/tasks/<module>.md` | Per-module task checklist (checked = implemented + tested) |
| `doc/tasks/progress.md` | Overall 28-module completion status |
| `doc/decisions.md` | Architecture decision records (DEC-XXX format) |

**After adding any new feature**, update `doc/prompt.md` (Stage extra requirements + file ownership table), `doc/detailed-design.md` (relevant module section), and the affected `doc/tasks/<module>.md` (new items, checked).

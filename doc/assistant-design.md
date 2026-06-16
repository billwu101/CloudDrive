# In-App AI Assistant 設計文件

## 1. 文件目的

本文件定義在 CloudDrive 網頁應用內，新增一個「AI 助理」功能的完整設計：使用者透過對話面板，用自然語言操作自己的雲端硬碟（搜尋、列檔、整理、分享等）。本文件為實作前的權威設計，實作時須據此並更新 `doc/detailed-design.md`、`doc/prompt.md` 與本模組的 `doc/tasks/*.md`。

## 2. 背景與方案抉擇

### 2.1 評估起點：OpenClaw

最初的需求是「接入 [openclaw](https://github.com/openclaw/openclaw)」。經評估，OpenClaw 是一個 **Node.js/TypeScript 的個人 AI 助理 daemon**，主打跨通訊平台（WhatsApp/Telegram/Slack…）、語音、單人 local-first。它與 CloudDrive（Python FastAPI + React、多使用者 web 服務）在技術棧與使用模型上都不相符。

### 2.2 三條整合路線比較

| 路線 | 做法 | 重用業務邏輯 | 多人安全 | 結論 |
|---|---|---|---|---|
| A. CloudDrive 當 OpenClaw 的 MCP 工具 | 外部 MCP server 包 REST API 給 OpenClaw | ✅ | 取決於認證 | OpenClaw 過重、單人設計不符 |
| B. 後端內建 MCP server，直接呼叫 service 層 | MCP endpoint 跑在 FastAPI 內 | ✅ | ✅ | 可行，但仍需 OpenClaw 當前端 |
| C. OpenClaw 直接操作 DB + 檔案 | TS 直連 Postgres/storage | ❌（須重寫全部邏輯） | ❌ | **否決**：繞過配額/權限/活動紀錄/軟刪除等不變量 |

### 2.3 最終決策：自建 In-App Assistant，不使用 OpenClaw

由於目標是「在 CloudDrive 網頁內用對話操作檔案」（多使用者），OpenClaw 的核心價值（跨通訊平台、單人 daemon）皆用不到。真正需要的只是「能呼叫工具的對話 agent」。因此決定**自建**：

- **後端**：一個 `/api/v1/assistant/chat` endpoint，內部跑 Claude tool-use 迴圈，工具直接呼叫既有 service 層。
- **前端**：React 聊天面板。
- **MCP**：v1 不需要（工具只給自家對話框用，直接在 agent loop 內定義即可）。若未來要讓同一套工具被多個 AI 客戶端共用，可再抽成 MCP server。

詳見 [decisions.md](./decisions.md) DEC-016、DEC-017。

## 3. 範圍

### 3.1 納入
- 後端 `assistant` 模組（router / service / schemas / tools）。
- Claude API 整合（官方 `anthropic` Python SDK，模型 `claude-opus-4-8`）。
- 工具集：對應既有 Drive/Search/Upload/Download/Trash/Share/User service。
- 前端聊天面板與串接。

### 3.2 不納入（v1）
- MCP server（保留為未來擴充）。
- 對話歷史持久化到 DB（v1 由前端在記憶體保留 session 內歷史）。
- 串流（streaming）回應（v1 先一次回完；可作為後續優化）。
- 語音、檔案內容問答（RAG）。

## 4. 整體架構

```
前端 ChatPanel (React)
   │  POST /api/v1/assistant/chat  { messages: [...] }   (JWT Bearer)
   ▼
AssistantRouter ──depends──> CurrentUserId
   │
   ▼
AssistantService.chat(user_id, messages)
   │   ── Claude tool-use 迴圈 (anthropic SDK, claude-opus-4-8) ──
   │        Claude 回 tool_use ─► dispatch 到工具
   ▼
ToolDispatcher ──呼叫──> DriveService / SearchService / UploadService
                          TrashService / ShareService / UserService
   （每次呼叫都帶 user_id，重用配額/權限/活動紀錄/軟刪除等既有邏輯）
```

關鍵原則：**助理不直接碰 DB 或 storage，一律經 service 層**，因此所有不變量（配額、權限、命名衝突、軟刪除、活動紀錄、分享 token 雜湊）自動沿用，且每個工具呼叫都被綁定在當前 JWT 的 `user_id`，天然多租戶安全。

## 5. 後端設計

### 5.1 模組檔案（沿用四檔慣例）

```
app/assistant/
  __init__.py
  router.py      # POST /assistant/chat；依賴 CurrentUserId 與各 service factory
  service.py     # AssistantService：Claude tool-use 迴圈與工具 dispatch
  schemas.py     # ChatMessage / ChatRequest / ChatResponse / ToolCallLog
  tools.py       # 工具 JSON schema 定義 + name → 處理函式 對應表
```

不需 `repository.py`（v1 無自有資料表）。

### 5.2 Config 與依賴

`app/core/config.py` 的 `Settings` 新增：

| 欄位 | 預設 | 說明 |
|---|---|---|
| `anthropic_api_key` | `""` | Claude API key，由環境變數 `ANTHROPIC_API_KEY` 提供 |
| `assistant_model` | `"claude-opus-4-8"` | 對話模型 ID |
| `assistant_enabled` | `True` | 功能開關；無 key 時自動視為停用 |
| `assistant_max_tool_iterations` | `8` | tool-use 迴圈安全上限，避免無限迴圈 |

`pyproject.toml` 新增依賴：`anthropic`（官方 SDK）。

### 5.3 ChatRequest / ChatResponse Schema

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]   # 完整對話歷史（API 為無狀態，每次帶全量）

class ToolCallLog(BaseModel):
    name: str
    input: dict
    ok: bool

class ChatResponse(BaseModel):
    reply: str                    # 助理最終文字回覆
    tool_calls: list[ToolCallLog] # 本回合執行過的工具（供前端顯示「已搜尋…」等）
```

### 5.4 AssistantService 介面

```python
class AssistantService:
    def __init__(self, anthropic_client, drive, search, upload, download,
                 trash, share, user_service): ...

    async def chat(self, user_id: UUID, messages: list[ChatMessage]) -> ChatResponse:
        """跑 Claude 手動 tool-use 迴圈，直到 stop_reason == 'end_turn' 或達上限。"""
```

迴圈邏輯（手動 agentic loop，採用 `claude-api` skill 指引）：
1. 組 system prompt（說明助理身分、可用工具、當前使用者語境，**不含**任何隨機/時間戳以利 prompt caching）。
2. 呼叫 `client.messages.create(model=settings.assistant_model, max_tokens=4096, thinking={"type":"adaptive"}, output_config={"effort":"medium"}, tools=TOOL_SCHEMAS, messages=...)`。
3. 若 `stop_reason == "tool_use"`：對每個 `tool_use` block，用 `ToolDispatcher` 執行（**帶入 `user_id`**），把 `tool_result` 接回 messages，續迴圈。
4. 達 `assistant_max_tool_iterations` 強制停止並回覆「處理過久」。
5. 回傳最終文字 + 工具紀錄。

採**手動迴圈**而非 tool runner 的理由：每次工具呼叫都要注入當前 `user_id` 並做權限/錯誤包裝，需要細粒度控制。

### 5.5 工具集（對應既有 service / 真實 endpoint）

**第一階段（唯讀，先驗證端到端）**

| 工具 | 對應 service / endpoint | 輸入 |
|---|---|---|
| `list_items` | DriveService.list_items / `GET /drive/items` | `parent_id?`, `page?` |
| `search` | SearchService / `GET /search?q=` | `query` |
| `recent` | DriveService / `GET /drive/recent` | — |
| `storage_quota` | UserService / `GET /users/me` | — |

**第二階段（寫入）**

| 工具 | 對應 | 輸入 |
|---|---|---|
| `create_folder` | `POST /drive/folders` | `name`, `parent_id?` |
| `rename_item` | `PATCH /drive/items/{id}/name` | `item_id`, `name` |
| `move_item` | `PATCH /drive/items/{id}/parent` | `item_id`, `parent_id` |
| `star_item` | `PUT /drive/items/{id}/star` | `item_id`, `starred` |
| `trash_item` / `restore_item` / `list_trash` | TrashService | `item_id` |
| `share_item` | `POST /share` | `item_id` |

每個工具的 JSON schema 都要寫清楚「何時該呼叫」（提升 Claude 觸發精準度），並標 `required`。寫入型工具回傳精簡結果（id、名稱、狀態），避免灌爆 context。

注意：`upload_file` / `download_file` 涉及二進位內容，在純對話介面中語義不自然，v1 **不納入**（如需，前端用既有上傳/下載 UI）。

### 5.6 認證與安全

- Router 依賴 `CurrentUserId`；`user_id` 一路傳入每個工具呼叫，使用者**只能操作自己有權限的項目**（重用 PermissionService）。
- 工具執行的例外一律轉成 `tool_result` 的 `is_error: true` + 友善訊息回給 Claude，不讓堆疊細節外洩；對應 `AppError` 子類別轉成可讀說明。
- `anthropic_api_key` 只存在後端環境變數，永不進前端、永不寫入回應。
- system prompt 不放使用者祕密；對話歷史不持久化（v1）。

### 5.7 錯誤處理

| 情境 | 行為 |
|---|---|
| 未設定 API key / `assistant_enabled=False` | router 回 503 + 明確訊息（前端隱藏入口） |
| Claude API 錯誤（429/5xx） | SDK 自動重試；仍失敗回 502 + 訊息 |
| 工具執行 AppError | 轉 `tool_result` is_error，讓模型改方式或說明 |
| 迴圈達上限 | 回覆「這次處理較複雜，請縮小範圍再試」 |

## 6. 前端設計

```
src/
  api/assistantApi.ts        # POST /assistant/chat 包裝
  hooks/useAssistant.ts      # TanStack Query mutation；保存 session 內 messages
  components/assistant/
    AssistantPanel.tsx       # 浮動聊天面板（開關鈕 + 訊息列 + 輸入框）
    MessageBubble.tsx        # 使用者/助理訊息泡泡
    ToolCallChip.tsx         # 顯示「已搜尋 / 已建立資料夾」等工具動作
```

- 入口：ProtectedLayout 右下角浮動按鈕，登入後可見。
- 狀態：對話歷史存在 component/zustand（記憶體），每次送出帶全量 `messages`。
- 助理操作改動檔案後，invalidate 對應 TanStack Query key（如 `driveKeys.items(parentId)`）讓畫面即時更新。

## 7. 測試策略

- **後端單元測試** `tests/assistant/test_router.py`：依現有 pattern，`AsyncMock(spec=AssistantService)`，驗證 endpoint 行為與認證；另測 `ToolDispatcher` 把工具名稱正確路由到 mock service 並帶對 `user_id`。Claude API 以 mock client 取代，不打真網路。
- **前端單元測試**：MSW mock `/assistant/chat`，測 panel 送出、顯示回覆與工具 chip、改檔後 query 失效。
- **整合測試**（可選）：以 mock 的 anthropic client 跑一輪「搜尋→回覆」流程。

## 8. 環境變數

```
ANTHROPIC_API_KEY=sk-ant-...     # 必填（缺少則助理停用）
ASSISTANT_MODEL=claude-opus-4-8  # 可選
ASSISTANT_ENABLED=true           # 可選
```

## 9. 里程碑

1. **M1 唯讀（後端）**：config + 依賴 + 模組骨架 + `list_items`/`search`/`recent`/`storage_quota` + 單元測試。可用 curl/測試端到端驗證。
2. **M2 前端**：聊天面板 + hook + api，串 M1。
3. **M3 寫入工具**：create_folder/rename/move/star/trash/share + query 失效 + 測試。
4. **M4 優化（可選）**：串流回應、對話歷史持久化、抽成 MCP server 供外部客戶端共用。

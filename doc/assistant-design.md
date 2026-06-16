# In-App AI Assistant 設計文件（HARNESS v1.0）

## 1. 目的與背景

在 CloudDrive 網頁應用內，新增一個 **自我擴充型 AI 助理（agent）**。它不只是用對話操作既有功能，更能**依使用者需求現場「製作新功能」並掛進 UI**。

核心情境（驅動整個設計）：

> CloudDrive 目前沒有解壓縮功能。使用者對助理說「幫我做一個 7zip 解壓縮功能」。助理撰寫一個 `decompress_7z` 技能（後端解壓 handler + 右鍵選單註冊），經使用者核可、沙箱驗證後安裝。之後對 `.7z`/`.zip` 檔案按右鍵，選單就出現「解壓縮」，點了就呼叫這個新技能。

因此助理本質是一個 **harness**：一個能跑工具迴圈、管理 context、載入/撰寫技能、開子代理、持久化 session、組系統提示、掛生命週期 hook、並嚴格控管權限與安全的執行框架。本文件依 HARNESS v1.0 的九大組件逐一定義「責任 + 具體要做到的事 + 對應檔案」。

### 1.1 模型

- **模型：Gemma 4 26B（本地執行）**，非雲端 API。
- 透過本地推論服務提供，預設 **Ollama**（`/api/chat`，支援 tools 欄位），亦可指向任何 **OpenAI 相容** 端點（`/v1/chat/completions`）。
- 後端以 `LLMClient` 抽象層封裝，**不綁定特定供應商**；只用 `httpx` 呼叫本地端點，不引入雲端 SDK。
- 因為是 26B 本地模型，function-calling 可靠度低於前沿雲端模型，因此 harness 的**穩健迴圈、輸出解析/修復、驗證、重試**特別重要（見 01、03）。

## 2. 方案抉擇（沿用並更新）

- **不採用 OpenClaw**（DEC-016）：它是單人 local-first 的跨通訊平台 daemon，與多人 web 服務不符；自建更合身。
- **助理一律經 service 層或受控沙箱，不直接亂碰 DB／檔案**（DEC-017）。
- **改用本地 Gemma，非 Claude**（DEC-018）：自訂、離線、資料不外流。
- **允許「自我撰寫技能」但需核可 + 沙箱**（DEC-019）：這是本功能的核心價值，也是最大安全面。

## 3. HARNESS 九大組件

> 對應檔案以 `app/assistant/` 為根。

### 01 while loop — agent 主迴圈

**責任**：驅動「送訊息 → 取得模型輸出 → 若要呼叫工具則執行 → 回填結果 → 再送」直到產生最終答覆或命中停止條件。

**具體要做到的事**
- `service.py::AgentLoop.run(session, user_message)`：實作迴圈。
- 每輪呼叫 `LLMClient.chat(messages, tools=available_tools)`。
- 解析模型輸出為「文字答覆」或「工具呼叫」；Gemma 經 Ollama 回 `tool_calls` 結構，OpenAI 相容回 `tool_calls`；**另備純文字 JSON 解析 + 修復**（模型不照格式時，要求重出或修補）。
- 工具呼叫經 `ToolDispatcher` 執行（帶 `user_id`），結果以 `tool` 角色回填。
- 停止條件：模型給最終文字、命中 `max_tool_iterations`（config，預設 8）、錯誤、使用者中斷。
- 命中上限時優雅收尾並回報，不無限迴圈。
- 每輪前後觸發 lifecycle hooks（見 08）。

### 02 context management — 上下文視窗管理

**責任**：確保送進 Gemma 的內容不超出可用 context（本地服務常受 `num_ctx` 限制，預設可能僅 8k）。

**具體要做到的事**
- `context.py::ContextBudget`：以 token/字元估算追蹤用量，`num_ctx` 可由 config 設定。
- 組裝順序：system prompt（穩定前綴）→ 摘要的舊歷史 → 最近 N 輪原文 → 當前訊息。
- 超預算策略：先裁切/摘要最舊的 tool 結果與對話，保留最近輪次與系統提示。
- **大型工具輸出先瘦身**再回填（如檔案清單只留必要欄位、截斷超長內容並附「已截斷」提示）。
- 提供「本回合估算 token 數」供前端/日誌參考。

### 03 skills & tools — 技能與工具（含自我撰寫）

**責任**：可擴充的能力層。**Tool** 是 agent 迴圈內可呼叫的單一函式；**Skill** 是更上層、使用者可安裝的能力，能同時註冊「後端 handler + 前端 UI 動作（如右鍵選單）」。自我撰寫技能是本功能核心。

**具體要做到的事**
- `skills/registry.py`：工具與技能的註冊表；依相關性只把需要的工具 schema 放進 prompt（避免灌爆 context）。
- `skills/manifest.py`：技能 manifest schema —
  ```
  name, description, trigger(對話觸發說明),
  ui: { context_menu: { label, file_extensions[] } },
  backend: { handler 入口、輸入 schema },
  code: 產生的 handler 程式碼,
  status: draft|pending_approval|approved|installed|disabled
  ```
- `skills/authoring.py`：**技能撰寫 meta-skill**。流程：辨識「做新功能」意圖 → 開子代理（04）產生 handler 程式碼 + manifest → 經 hooks 要求核可（08）→ 沙箱驗證（09）→ 安裝並持久化（06）→ 通知前端刷新可用動作。
- 工具與技能皆有 JSON schema，描述需寫清「何時該呼叫」以提升 Gemma 觸發精準度。
- 安裝後的技能會：(a) 註冊一個後端 endpoint/handler；(b) 在 manifest 的 `ui.context_menu` 宣告右鍵項目，前端據此渲染。

### 04 sub-agents — 子代理

**責任**：把有界子任務交給獨立 context 的子代理，避免主迴圈 context 被污染。

**具體要做到的事**
- `subagent.py::spawn(role, system_prompt, tools_subset, task)`：開一個獨立訊息歷史的子迴圈，完成後只回傳結果給主代理。
- 主要用途：**技能程式碼生成**（codegen）、大量/平行檔案操作、需要乾淨上下文的分析。
- 限制：**單層委派**（子代理不再開子代理）、各自的工具子集、結果交回主代理。
- 子代理同樣受 hooks 與 permissions 管轄。

### 05 built-in skills — 內建技能

**責任**：隨應用出廠、永遠可用、非使用者撰寫的技能。

**具體要做到的事**
- `skills/builtin/`：將既有 CloudDrive 操作包成內建技能 —
  - 檔案管理：`list_items` / `search` / `recent` / `storage_quota`（唯讀，第一階段）；`create_folder` / `rename` / `move` / `star` / `trash` / `restore` / `share`（寫入，第二階段）。
  - **`author_skill`（meta-skill）**：撰寫新技能的能力本身，內建提供。
- 內建技能一律經既有 service 層、帶 `user_id`，重用配額/權限/活動紀錄。
- 內建技能不可被使用者刪除，只能停用。

### 06 session persistence — 對話與技能持久化

**責任**：對話歷史與已安裝技能跨 session 留存（**取代舊設計的「記憶體 only」**）。

**具體要做到的事**
- 新增資料表（Alembic migration）：
  - `assistant_sessions(id, user_id, title, created_at, updated_at)`
  - `assistant_messages(id, session_id, role, content, tool_calls JSONB, created_at)`
  - `assistant_skills(id, user_id, name, description, manifest JSONB, code TEXT, status, created_at, updated_at)`（使用者自訂技能，依 `user_id` 隔離）
- `repository.py`：sessions/messages/skills 的 CRUD。
- 支援：建立/續接/列出 session；啟動時載入該使用者已安裝技能並註冊進 registry。
- 技能程式碼存 DB（或受控檔案路徑）；安裝狀態持久化。

### 07 system prompt assembly — 系統提示動態組裝

**責任**：每次請求依當下狀態組出 system prompt。

**具體要做到的事**
- `prompt.py::assemble(user, installed_skills, available_tools)`：
  - 基礎人設與行為規範（穩定前綴，放最前以利快取/決定性）。
  - 安全規則（破壞性操作要先確認、技能安裝要核可）。
  - 可用工具/技能清單與其「何時使用」（含使用者已安裝的自訂技能，讓 agent 知道有哪些能力）。
  - 必要的使用者語境（**不放祕密、不放隨機/時間戳**，避免破壞快取）。
  - 漸進揭露：只在相關時帶入特定技能的詳細指示。

### 08 lifecycle hooks — 生命週期掛鉤

**責任**：在迴圈關鍵節點插入可插拔行為（稽核、權限閘、驗證、量測）。

**具體要做到的事**
- `hooks.py::HookRegistry`，支援節點：
  - `on_session_start` / `on_session_end`
  - `before_tool_call` / `after_tool_call`
  - `before_skill_install` / `after_skill_install`
  - `before_code_execution`
  - `on_error`
- 內建 hooks：
  - 稽核：所有工具/技能動作寫入 `activity_logs`（重用既有）。
  - 權限閘：破壞性與安裝/執行碼動作 → 要求使用者核可（回傳「待確認」狀態給前端）。
  - 驗證：技能安裝前做靜態檢查；工具輸入驗證。
  - 量測：每輪 token/耗時。
- Hook 可阻擋（回 block）一個動作並把原因回饋給 agent。

### 09 permissions & safety — 權限與安全（最關鍵）

**責任**：限制 agent 能做什麼，尤其是它**會撰寫並執行程式碼**。

**具體要做到的事**
- **多租戶**：每個工具/技能呼叫綁當前 JWT `user_id`，只能碰自己有權限的項目（重用 PermissionService）。
- **分層權限**（`permissions.py`）：
  - 唯讀（list/search）→ 自動執行。
  - 破壞性（trash/delete/move）→ 需使用者確認。
  - **技能安裝 / 執行生成程式碼 → 必須明確核可 + 沙箱**。
- **沙箱**（`skills/sandbox.py`）執行生成的技能程式碼：
  - 獨立子行程，設 CPU/記憶體/逾時上限。
  - 檔案存取只限該使用者的 storage 範圍（經 StorageProvider，不給任意路徑）。
  - 無對外網路（或白名單）。
  - 禁止 shell 注入；參數化呼叫（如 7z 二進位以 arg list 呼叫，不拼字串）。
- **絕不自動執行未審核的程式碼**：生成 → 顯示給使用者 → 核可 → 沙箱。
- 稽核：所有 agent 動作可追溯（activity_logs）。
- 失敗/例外轉成 `tool_result` is_error + 友善訊息，不外洩堆疊。

## 4. 端到端範例：7zip 解壓縮技能

1. 使用者：「幫我做一個 7zip 解壓縮功能」。
2. **01 迴圈** 收到 → 系統提示（07）讓 agent 認出這是 `author_skill`（05 內建 meta-skill）意圖。
3. **04 子代理** 被開來 codegen：產生 `decompress_7z` 的 handler（用 `py7zr` 或系統 `7z`，參數化）+ manifest（`ui.context_menu: { label: "解壓縮", file_extensions: ["7z","zip"] }`）。
4. **08 hook** `before_skill_install`：暫停，把生成的程式碼與 manifest 回給前端，要求使用者核可。
5. 使用者核可 → **09 沙箱** 驗證（試解一個小檔、限資源）→ 通過。
6. **06 持久化**：寫入 `assistant_skills`（status=installed），註冊後端 handler。
7. 前端依 manifest 在 `.7z`/`.zip` 檔的右鍵選單加入「解壓縮」。
8. 之後使用者右鍵點「解壓縮」→ 呼叫該技能 handler → 沙箱內解壓 → 結果以新 drive items 寫回（經 service 層、重用配額/活動紀錄）。

## 5. 模組檔案結構

```
app/assistant/
  __init__.py
  router.py            # POST /assistant/chat、技能核可/安裝、技能 handler 觸發
  service.py           # AgentLoop（01 while loop）
  schemas.py           # Chat/Message/ToolCall/SkillManifest/Approval 等
  context.py           # 02 context budget
  prompt.py            # 07 system prompt assembly
  hooks.py             # 08 lifecycle hooks
  permissions.py       # 09 權限分層與閘門
  subagent.py          # 04 sub-agents
  repository.py        # 06 sessions/messages/skills 持久化
  llm/
    client.py          # LLMClient 協定（chat(messages, tools)->text|tool_calls）
    ollama.py          # Gemma via Ollama / OpenAI 相容實作（httpx）
  skills/
    registry.py        # 03 工具/技能註冊與相關性挑選
    manifest.py        # 03 技能 manifest schema 與驗證
    authoring.py       # 03 自我撰寫技能流程
    sandbox.py         # 09 受控執行
    builtin/           # 05 內建技能（檔案管理 + author_skill）
```

## 6. 認證與安全總結

- Router 依賴 `CurrentUserId`；`user_id` 貫穿工具、技能、沙箱。
- 自訂技能依 `user_id` 隔離，互不可見。
- 本地模型，資料不外流；無雲端 API key。
- 生成程式碼：核可 → 沙箱 → 稽核，三道關卡缺一不可。

## 7. 測試策略

- **後端單元**：`tests/assistant/` —
  - `test_router.py`：mock AgentLoop，驗證 endpoint 與認證（沿用 `_make_app` pattern）。
  - `test_loop.py`：mock `LLMClient` 回 tool_call → 執行 → end，驗證迴圈、上限、錯誤包裝。
  - `test_dispatch.py`：工具名稱正確路由、帶對 `user_id`。
  - `test_context.py`：超預算裁切/摘要。
  - `test_authoring.py`：技能撰寫流程到 `pending_approval` 停住（不自動執行）。
  - `test_sandbox.py`：沙箱限制（逾時、路徑限制、無網路）。
  - `test_hooks.py`：權限閘正確阻擋破壞性/安裝動作。
- **LLM 一律 mock**，不打真模型。
- **前端**：MSW mock chat 與核可流程；測右鍵選單依 manifest 動態渲染。

## 8. 環境變數

```
LLM_PROVIDER=ollama                  # ollama | openai_compatible
LLM_BASE_URL=http://localhost:11434  # 本地推論端點
ASSISTANT_MODEL=gemma-4-26b          # 模型名稱（依本地服務命名）
LLM_NUM_CTX=8192                     # context 視窗（依服務設定）
ASSISTANT_ENABLED=true
ASSISTANT_MAX_TOOL_ITERATIONS=8
ASSISTANT_SANDBOX_TIMEOUT_SEC=30
```

## 9. 里程碑

1. **M1 迴圈骨架（01/02/07）**：AgentLoop + LLMClient(Ollama/Gemma) + context budget + prompt 組裝 + 唯讀內建技能（list/search/recent/quota）+ 單元測試。可端到端對話驗證。
2. **M2 前端對話**：聊天面板 + hook + api，串 M1。
3. **M3 技能框架（03/05/06）**：registry + manifest + 內建寫入技能 + session/skills 持久化（含 migration）。
4. **M4 自我撰寫 + 安全（04/08/09）**：sub-agent codegen + hooks 核可閘 + sandbox。完成 7zip 範例端到端。
5. **M5 前端動態 UI**：依 manifest 渲染右鍵選單、技能核可介面。

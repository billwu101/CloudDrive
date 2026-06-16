# In-App AI Assistant 設計文件（HARNESS 引擎 + Workflow 管線）

## 1. 目的與背景

在 CloudDrive 網頁應用內，新增一個 **可對話、可自我擴充的 AI 助理（agent）**。使用者用自然語言描述需求，助理把需求轉成一個**可檢視、可確認、可執行、可記錄的 Workflow**，用既有或現場生成的技能完成各類檔案／資料夾操作。

兩個關鍵特性：

1. **通用日常操作**：不限於單一功能。使用者可自由對話，助理涵蓋各類檔案／資料夾的日常操作（列檔、搜尋、整理、批次改名、移動、複製、去重、分享、壓縮/解壓、轉檔…）。
2. **現場生成新功能**：若需求對應的能力尚未內建，助理**現場生成新技能**（例如「做一個 7zip 解壓縮功能」），經核可與沙箱後安裝；安裝後該技能可被工作流程使用，並可掛上 UI（如右鍵選單）。7zip 只是其中一例。

整體採**兩層架構**：

- **Workflow 管線（做什麼）**：把一次需求變成「候選工作流程 → 檢查技能 → 權限安全 → 顯示計畫 → 確認 → 執行 → 記錄」的可控流程（見第 3 節，對應需求流程圖）。
- **HARNESS 引擎（怎麼跑）**：驅動上述每一步的底層機制 —— while loop、context、skills & tools、sub-agents、built-in skills、session persistence、system prompt assembly、lifecycle hooks、permissions & safety（見第 7 節）。

### 1.1 模型

- **Gemma 4 26B（本地）**，預設經 Ollama（`/api/chat`，支援 tools），亦可指向 OpenAI 相容端點。
- 後端以 `LLMClient` 抽象封裝，只用 `httpx`，**不引入雲端 LLM SDK**。
- 26B 本地模型 function-calling 與規劃可靠度有限，因此管線的**結構化輸出 + 驗證 + 修復重試 + 使用者確認閘**特別重要。

### 1.2 方案抉擇（沿用）

不採用 OpenClaw（DEC-016）；一律經 service 層或沙箱（DEC-017）；本地 Gemma（DEC-018）；自我撰寫技能須核可+沙箱+稽核（DEC-019）；session/技能/工作流程持久化（DEC-020）；以 Workflow 管線 + 計畫確認為執行模型（DEC-021）。

## 2. 名詞定義

| 名詞 | 定義 |
|---|---|
| **Tool** | agent 迴圈內可呼叫的單一函式（有 JSON schema）。 |
| **Skill** | 使用者可安裝的能力，封裝一或多個 handler，並可宣告 UI 動作（右鍵選單）。可內建或現場生成。 |
| **Workflow** | 由需求產生的**有序步驟計畫**，每步驟綁定一個 skill 呼叫與參數；可含相依、可儲存重用。單一動作即 1 步驟工作流程。 |
| **Workflow Run** | 一次工作流程的執行實例，含每步驟結果與稽核。 |

## 3. Workflow 執行管線（對應需求流程圖）

```
使用者自然語言描述需求
   ↓
LLM 解析需求
   ↓
轉成候選 Workflow
   ↓
檢查可用 Skill ──(缺技能)──► 生成技能子流程（見 3.1）──► 安裝後回到此處
   ↓
權限與安全檢查
   ↓
顯示執行計畫
   ↓
使用者確認? ──否──► 修改需求或取消（帶修正回「LLM 解析需求」）
   │是
   ↓
執行 Workflow
   ↓
記錄操作與結果
```

各階段職責與其使用的 HARNESS 組件：

| 階段 | 要做到的事 | 使用的 HARNESS 組件 |
|---|---|---|
| **1. NL 描述需求** | 前端聊天輸入；寫入 session。 | 06 persistence |
| **2. LLM 解析需求** | Gemma 理解意圖、抽出目標物件（哪些檔案/資料夾）、判斷需要的能力。 | 01 loop、02 context、07 prompt |
| **3. 轉成候選 Workflow** | LLM 以**結構化輸出**產生 workflow（步驟序列、每步 skill+參數+相依）；registry 提供可用 skill 清單供規劃；輸出經 schema 驗證，不合格要求重出/修補。 | 03 skills（registry）、07 prompt |
| **4. 檢查可用 Skill** | 比對每個步驟所需 skill 是否已註冊。**全有** → 續往權限檢查；**有缺** → 進入「生成技能子流程」(3.1)，安裝後回到本階段重檢。 | 03 skills（registry/authoring）、04 sub-agents |
| **5. 權限與安全檢查** | 逐步驟判定權限層級（唯讀/破壞性/需沙箱）、綁定 `user_id`、標記需使用者核可的步驟；不通過則擋下並說明。 | 09 permissions、08 hooks |
| **6. 顯示執行計畫** | 把 workflow 計畫（步驟、影響範圍、破壞性/沙箱標記、預估）回前端供檢視。 | 08 hooks（before_execution） |
| **7. 使用者確認?** | 是/否閘。**否** → 修改需求或取消，帶使用者修正回階段 2。**是** → 執行。唯讀且非破壞的工作流程可依權限設定自動確認（fast-path）。 | 09 permissions、前端 |
| **8. 執行 Workflow** | 依序執行每步驟：呼叫 skill handler（經 service 層或沙箱，帶 `user_id`），處理相依與錯誤（單步失敗可中止或續做，依設定）。 | 01 loop、09 safety、04 sub-agents |
| **9. 記錄操作與結果** | 每步驟與整體結果寫入稽核（activity_logs）與 workflow run 持久化；成功的工作流程可另存重用。 | 09 audit、06 persistence |

### 3.1 生成技能子流程（缺技能 → 現場生成，workflow 化）

當階段 4 發現需要的能力未內建/未安裝，把「生成該技能」本身表達成一段**前置子流程**，接到主工作流程之前：

```
辨識缺少的能力
   ↓
開子代理 codegen（產生 handler 程式碼 + manifest）   ← HARNESS 04 + 03 authoring
   ↓
靜態驗證 + 顯示生成內容給使用者                       ← HARNESS 08 hooks
   ↓
使用者核可?  ──否──► 取消/調整需求
   │是
   ↓
沙箱試跑驗證（限資源/路徑/網路、參數化）             ← HARNESS 09 sandbox
   ↓
安裝技能並持久化（assistant_skills, status=installed） ← HARNESS 06
   ↓
（若有 UI 宣告）前端據 manifest 加入右鍵選單項目
   ↓
回到主工作流程「檢查可用 Skill」重檢 → 續往執行
```

生成出的技能與整段工作流程皆可儲存重用（見 4.2）。

## 4. Workflow 資料模型與重用

### 4.1 Workflow schema（結構化計畫）

```
Workflow {
  id, user_id, name, source_nl,            # 由哪句需求產生
  steps: [
    { id, skill, params, depends_on[],     # 綁定的 skill 與參數
      permission_tier, requires_sandbox,
      requires_approval }
  ],
  created_at
}
WorkflowRun {
  id, workflow_id, user_id, status,        # pending/running/succeeded/failed/cancelled
  step_results: [ { step_id, ok, output, error } ],
  created_at, finished_at
}
```

### 4.2 重用

- 使用者確認並成功執行的工作流程可**命名儲存**，日後一鍵重跑或排程（如「每週整理下載資料夾」）。
- 已存工作流程在規劃階段可被 LLM 參考或直接套用，減少重複規劃。
- 與技能持久化一致：工作流程依 `user_id` 隔離。

## 5. Skill 目錄

### 5.1 內建技能（出廠、永遠可用、經 service 層、帶 user_id）

| 類別 | 技能 |
|---|---|
| 檔案/資料夾基本 | `list_items`、`get_info`、`search`、`recent`、`storage_quota`、`create_folder`、`rename`、`move`、`copy`、`trash`、`restore`、`star`、`share` |
| 批次/組織 | `batch_rename`、`organize_by_type`、`organize_by_date`、`deduplicate`、`bulk_move` |
| Meta | `author_skill`（現場生成新技能的能力本身） |

> 內建技能盡量覆蓋日常操作，降低「動不動就要生成新功能」的需求；真正缺的才走生成路徑。

### 5.2 生成式技能（現場生成、需核可+沙箱）

任何內建未涵蓋的能力（如 `decompress_7z`、`compress_zip`、`convert_image`、`extract_pdf_text`…）由 `author_skill` 經 3.1 子流程生成、核可、沙箱、安裝。安裝後即與內建技能一樣可被工作流程編排，並可掛右鍵選單。

## 6. 端到端範例

- **單一新功能（7zip）**：「做一個 7zip 解壓縮功能」→ 解析 → 候選 workflow（1 步：`decompress_7z`）→ 檢查發現缺 → 生成子流程（codegen→核可→沙箱→安裝，掛右鍵選單）→ 回主流程 → 權限/安全 → 顯示計畫 → 確認 → 執行（沙箱解壓，結果寫回成 drive items）→ 記錄。
- **多步驟日常操作（已內建）**：「把『下載』裡的圖片依日期分資料夾，重複的刪掉」→ 候選 workflow（`search`→`organize_by_date`→`deduplicate`）→ 技能皆有 → 權限檢查（含破壞性 `deduplicate` 需確認）→ 顯示計畫 → 確認 → 依序執行 → 記錄；可另存為「整理下載圖片」工作流程重用。

## 7. HARNESS 九大組件（引擎，精簡定義）

| # | 組件 | 要做到的事（重點） | 檔案 |
|---|---|---|---|
| 01 | while loop | 驅動「送訊息→解析→執行→回填」直到完成/上限；停止條件、迴圈上限、hook 觸發。 | `service.py` |
| 02 | context management | token 預算、超量裁切/摘要、大型工具輸出瘦身；`num_ctx` 可設。 | `context.py` |
| 03 | skills & tools | 工具/技能 registry、相關性挑選、manifest、`author_skill` 撰寫流程。 | `skills/registry.py`、`skills/manifest.py`、`skills/authoring.py` |
| 04 | sub-agents | 單層子代理（主要用於 codegen、平行/有界子任務），獨立 context、回傳結果。 | `subagent.py` |
| 05 | built-in skills | 出廠技能目錄（5.1）+ `author_skill`，經 service 層、帶 user_id。 | `skills/builtin/` |
| 06 | session persistence | sessions/messages/skills/workflows 持久化；啟動載入使用者技能與已存工作流程。 | `repository.py` |
| 07 | system prompt assembly | 動態組裝：人設+安全規則+可用技能清單+語境（穩定前綴在前、無隨機/時間戳）。 | `prompt.py` |
| 08 | lifecycle hooks | session/tool/skill/code-exec/error 節點；稽核、權限閘、計畫顯示、安裝前驗證。 | `hooks.py` |
| 09 | permissions & safety | 多租戶 user_id 綁定；分層權限（唯讀自動/破壞性確認/安裝+執行碼核可）；沙箱（資源/路徑/網路限制、參數化）；稽核。 | `permissions.py`、`skills/sandbox.py` |

（各組件的完整「具體要做到的事」與 7zip 子流程細節，於實作時依本節與第 3 節展開；DEC-018/019/020/021 為其決策依據。）

## 8. 模組檔案結構

```
app/assistant/
  __init__.py
  router.py            # /assistant/chat、計畫確認、技能核可/安裝、工作流程儲存/重跑、技能 handler 觸發
  service.py           # 01 AgentLoop
  planner.py           # 階段 2-3：NL → 候選 Workflow（結構化輸出 + 驗證）
  workflow.py          # Workflow/WorkflowRun 模型、執行器（階段 8）、相依與錯誤策略
  context.py           # 02
  prompt.py            # 07
  hooks.py             # 08
  permissions.py       # 09
  subagent.py          # 04
  repository.py        # 06（sessions/messages/skills/workflows）
  llm/
    client.py          # LLMClient 協定
    ollama.py          # Gemma via Ollama / OpenAI 相容（httpx）
  skills/
    registry.py        # 03
    manifest.py        # 03
    authoring.py       # 03 + 3.1 生成子流程
    sandbox.py         # 09
    builtin/           # 05 技能目錄
```

## 9. 資料模型（新增表，Alembic migration）

- `assistant_sessions(id, user_id, title, created_at, updated_at)`
- `assistant_messages(id, session_id, role, content, tool_calls JSONB, created_at)`
- `assistant_skills(id, user_id, name, description, manifest JSONB, code TEXT, status, created_at, updated_at)`
- `assistant_workflows(id, user_id, name, source_nl, steps JSONB, created_at)`
- `assistant_workflow_runs(id, workflow_id, user_id, status, step_results JSONB, created_at, finished_at)`

全部依 `user_id` 隔離。

## 10. 安全總結

- 每個 skill/步驟綁 `user_id`，只能碰自己有權限的項目（重用 PermissionService）。
- 破壞性步驟需確認；技能安裝與執行生成程式碼需核可 + 沙箱 + 稽核。
- 計畫先顯示再執行（階段 6-7），不先斬後奏。
- 本地模型，資料不外流，無雲端 key。
- 所有步驟與結果可追溯（activity_logs + workflow_runs）。

## 11. 測試策略

- **後端單元** `tests/assistant/`：
  - `test_router.py`（mock 服務 + 認證）、`test_loop.py`（迴圈/上限/錯誤）、`test_dispatch.py`（路由+user_id）、`test_context.py`（裁切）。
  - `test_planner.py`：NL → 候選 workflow 結構化輸出與驗證（mock LLM）。
  - `test_workflow.py`：步驟相依、錯誤策略、唯讀 fast-path vs 需確認。
  - `test_authoring.py`：生成停在 pending_approval，不自動執行。
  - `test_sandbox.py`：逾時/路徑/網路限制。
  - `test_hooks.py`：權限閘擋破壞性/安裝。
- **LLM 一律 mock**。
- **前端**：MSW mock；測計畫顯示與確認、技能核可、依 manifest 動態右鍵選單、改檔後 query 失效。

## 12. 環境變數

```
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
ASSISTANT_MODEL=gemma-4-26b
LLM_NUM_CTX=8192
ASSISTANT_ENABLED=true
ASSISTANT_MAX_TOOL_ITERATIONS=8
ASSISTANT_SANDBOX_TIMEOUT_SEC=30
```

## 13. 里程碑

1. **M1 引擎骨架（HARNESS 01/02/05/07）**：AgentLoop + LLMClient(Gemma) + context + prompt + 唯讀內建技能 + 測試。
2. **M2 Workflow 管線（planner/workflow + 08/09）**：NL→候選 workflow→技能檢查→權限→顯示計畫→確認→執行→記錄；唯讀 fast-path。前端聊天面板 + 計畫確認 UI。
3. **M3 技能框架與持久化（03/05/06）**：registry + manifest + 寫入/批次內建技能 + sessions/skills/workflows 持久化（migration）+ 工作流程重用。
4. **M4 自我撰寫 + 安全（04/03/08/09）**：sub-agent codegen + 生成子流程 + 核可閘 + sandbox。完成 7zip 範例端到端。
5. **M5 動態 UI**：依 manifest 渲染右鍵選單、技能核可介面、已存工作流程一鍵重跑。

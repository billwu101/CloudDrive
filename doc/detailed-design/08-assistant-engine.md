## 8. In-App AI Assistant（引擎設計）

### 8.1 目的與背景

在 CloudDrive 網頁應用內，新增一個 **可對話、可自我擴充的 AI 助理（agent）**。使用者用自然語言描述需求，助理把需求轉成一個**可檢視、可確認、可執行、可記錄的 Workflow**，用既有或現場生成的技能完成各類檔案／資料夾操作。

兩個關鍵特性：

1. **通用日常操作**：不限於單一功能。使用者可自由對話，助理涵蓋各類檔案／資料夾的日常操作（列檔、搜尋、整理、批次改名、移動、複製、去重、分享、壓縮/解壓、轉檔…）。
2. **現場生成新功能**：若需求對應的能力尚未內建，助理**現場生成新技能**（例如「做一個 7zip 解壓縮功能」），經核可與沙箱後安裝；安裝後該技能可被工作流程使用，並可掛上 UI（如右鍵選單）。7zip 只是其中一例。

整體採**兩層架構**：

- **Workflow 管線（做什麼）**：把一次需求變成「候選工作流程 → 檢查技能 → 權限安全 → 顯示計畫 → 確認 → 執行 → 記錄」的可控流程（見第 3 節，對應需求流程圖）。
- **HARNESS 引擎（怎麼跑）**：驅動上述每一步的底層機制 —— while loop、context、skills & tools、sub-agents、built-in skills、session persistence、system prompt assembly、lifecycle hooks、permissions & safety（見第 7 節）。

### 8.91.1 模型

- **預設：Gemma 4 26B（本地）**，經 Ollama（`/api/chat`，支援 tools）或 OpenAI 相容端點。
- **升級路徑**：當本地 Gemma 反覆做不出可接受結果，且符合隱私條件時，可升級呼叫**外部大型模型 API**（見 1.3）。
- 後端以 `LLMClient` 抽象封裝本地與外部執行器；本地端只用 `httpx`，外部端為可設定、可關閉、且受隱私閘控管。
- **本機執行器 provider（`llm_provider`）**：`router.py` 的 `_build_local_client(settings)` 依 `llm_provider` 建本機 client——`ollama`→`OllamaLLMClient`（原生 `/api/chat`）；`openai_compatible`→`ExternalLLMClient`（OpenAI 相容 `POST /v1/chat/completions`，可指向本機 Ollama 的 `/v1`、或任何 OpenAI 相容 gateway，後端仍可為 gemma4:26b）。兩者共用 `LLM_BASE_URL`／`ASSISTANT_MODEL`／`LLM_API_KEY`（見 §8.12）；`openai_compatible` 路徑不帶 `num_ctx`／`keep_alive`（Ollama 專屬），由 gateway 後端自理。
- 26B 本地模型 function-calling 與規劃可靠度有限，因此管線的**結構化輸出 + 驗證 + 修復重試 + 升級 + 使用者確認閘**特別重要。

### 8.91.2 方案抉擇（沿用）

不採用 OpenClaw（DEC-016）；一律經 service 層或沙箱（DEC-017）；**預設本地、條件式外部升級**（DEC-018 經 DEC-023 修訂）；自我撰寫技能須核可+沙箱+稽核（DEC-019）；session/技能/工作流程持久化（DEC-020）；以 Workflow 管線 + 計畫確認為執行模型（DEC-021）；驗證/評分 harness 把關（DEC-022）。

### 8.91.3 模型策略與升級（隱私閘 + 複雜度路由 + 失敗升級）

每個 LLM 工作（解析需求、規劃 workflow、技能 codegen…）依下列策略選擇執行器：

```
任務進入
   ↓
是否涉及隱私資料?
   ├─是→ 標記 privacy_sensitive：限本地模型；若需外部，須先去識別化（去識別化失敗則禁止外部）
   └─否→ 允許外部
   ↓
任務是否複雜?
   ├─簡單→ 規則/傳統程式/小模型（能用非 LLM 規則就不呼叫模型；否則本地 Gemma）
   └─複雜→ 傾向較強模型（先本地 Gemma；必要時升級外部）
   ↓
執行 → 回傳結果
```

**升級判斷（本題重點）**：本地 Gemma 為預設執行器。系統追蹤該工作的嘗試次數 `local_attempts`；當 **Gemma 連續 `max_local_attempts` 次仍做不出可接受結果**時觸發升級評估：

- **「做不出可接受結果」的判定訊號**：結構化輸出/工具呼叫反覆無法通過 schema 驗證；產生的 workflow 步驟驗證失敗；執行迴圈無進展（no-progress）；或執行後自我檢查/驗證器判定未達需求。
- **升級資格（且）**：`external_llm_enabled=true`（且使用者未關閉外部）**且**（`privacy_sensitive=false` **或** 去識別化成功）。
- **符合資格** → 經 `LLMClient` 的外部執行器重試失敗的子工作；外部回來的計畫/結果仍走原本的權限、安全、沙箱、確認閘。
- **不符資格**（隱私鎖定或外部停用）→ **不外送任何資料**，停止並向使用者說明「本地無法完成」，提供縮小需求/手動處理的選項。
- 升級事件經 lifecycle hook 記錄（稽核），並可由使用者層級設定全面禁用外部。


### 8.2 名詞定義

| 名詞 | 定義 |
|---|---|
| **Tool** | agent 迴圈內可呼叫的單一函式（有 JSON schema）。 |
| **Skill** | 使用者可安裝的能力，封裝一或多個 handler，並可宣告 UI 動作（右鍵選單）。可內建或現場生成。 |
| **Workflow** | 由需求產生的**有序步驟計畫**，每步驟綁定一個 skill 呼叫與參數；可含相依、可儲存重用。單一動作即 1 步驟工作流程。 |
| **Workflow Run** | 一次工作流程的執行實例，含每步驟結果與稽核。 |

### 8.3 Workflow 執行管線（對應需求流程圖）

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
| **8. 執行 Workflow** | 依序執行每步驟：呼叫 skill handler（經 service 層或沙箱，帶 `user_id`）；失敗處理與執行隔離語意（失敗只斷真正下游、每步恰一筆 ok/failed/skipped、誠實報告 + 有限度 replan）見 §11.11（規劃／待落地）。 | 01 loop、09 safety、04 sub-agents |
| **9. 記錄操作與結果** | 每步驟與整體結果寫入稽核（activity_logs）與 workflow run 持久化；成功的工作流程可另存重用。 | 09 audit、06 persistence |

### 8.93.1 生成技能子流程（缺技能 → 現場生成，workflow 化）

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

### 8.4 Workflow 資料模型與重用

### 8.94.1 Workflow schema（結構化計畫）

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

### 8.94.2 重用

- 使用者確認並成功執行的工作流程可**命名儲存**，日後一鍵重跑或排程（如「每週整理下載資料夾」）。
- 已存工作流程在規劃階段可被 LLM 參考或直接套用，減少重複規劃。
- 與技能持久化一致：工作流程依 `user_id` 隔離。

### 8.5 Skill 目錄

### 8.95.1 內建技能（出廠、永遠可用、經 service 層、帶 user_id）

| 類別 | 技能 |
|---|---|
| 檔案/資料夾基本 | `list_items`、`get_info`、`search`、`recent`、`storage_quota`、`create_folder`、`rename`、`move`、`copy`、`trash`、`restore`、`star`、`share` |
| 批次/組織 | `batch_rename`、`organize_by_type`、`organize_by_date`、`deduplicate`、`bulk_move` |
| Meta | `author_skill`（現場生成新技能的能力本身） |


### 8.95.2 生成式技能（現場生成、需核可+沙箱）

任何內建未涵蓋的能力（如 `decompress_7z`、`compress_zip`、`convert_image`、`extract_pdf_text`…）由 `author_skill` 經 3.1 子流程生成、核可、沙箱、安裝。安裝後**可掛右鍵選單對單檔執行**；但**預設不進對話 planner**——自建／生成技能屬不可信程式碼，需逐個手動開啟 `chat_enabled`（「允許在對話中使用」）才會被載入 planner registry，且一律以 **write 級**編排、用到即進確認閘、經沙盒執行（完整設計見 §8.95.4）。

<!-- 原 v1 設計（已由 §8.95.4 chat_enabled 安全閘取代）：「安裝後即與內建技能一樣可被工作流程編排，並可掛右鍵選單。」——舊做法為安裝即自動可被 planner 編排、無 opt-in 閘；新做法改為預設關閉、逐個手動開啟、用到必確認，以收緊不可信程式碼的執行面。 -->


### 8.95.3 技能管理（檢視 / 編輯 / 刪除）

已安裝技能不是只能新增——使用者可在側欄 **Skills 管理頁（`/skills`）** 檢視目前有多少已寫過的技能、編輯或刪除它們，形成完整生命週期：**生成 → 核可安裝 → 執行 → 編輯 / 刪除**。

- **檢視**：`GET /assistant/skills?status=installed` 列出已安裝技能（數量、描述、右鍵動作、更新時間）。前端 `pages/SkillsPage.tsx`。
- **編輯**：`PATCH /assistant/skills/{id}`（`AssistantSkillUpdateRequest`）改描述/程式碼。**改程式碼會重跑 `codeguard` 靜態驗證**——手動編輯不得繞過安全掃描；描述同步寫回 manifest。前端 `SkillEditDialog.tsx`。
- **刪除**：`DELETE /assistant/skills/{id}`（回 204），連同其右鍵動作一併移除。
- service 層 `update_skill`/`delete_skill`、repository `update`/`delete`；皆依 `user_id` 隔離。

### 8.95.4 自建技能在對話中使用（chat_enabled）

> **落地狀態**：本節設計已於 main 分支實作（2026-06-25），**fix 分支待落地**。需求面見 proposal §12（「自建技能用於對話」「勾選檔案帶入」「Skills 頁 toggle」）。落地時 §8.9 資料模型加 `chat_enabled` 欄、§13.5 端點清單與 §7.12 Migration 演進表需同步。

原本 planner 只認內建 skill；自建／生成的 skill（如 `compress_zip`）只能透過右鍵 `POST /assistant/skills/{id}/execute` 對單檔執行，對話中說「用我的 skill 壓縮」會被回「沒有這個功能」。本功能讓自建 skill 也能被 planner 排進計畫——因屬**不可信程式碼**，採多層管控（呼應 §8.95.2 已解衝突的新說法：安裝不再等於自動可編排）。

- **逐個 opt-in（D3）**：`assistant_skills` 加 `chat_enabled BOOLEAN NOT NULL DEFAULT false`（migration，落地時併入 §7.12 演進表）。**只有 `installed` 且 `chat_enabled`** 的 skill 才載入 planner registry；`PATCH /assistant/skills/{id}` 可切換（前端 SkillsPage 卡片 toggle）。
- **一律 write 級（D1）**：載入時以 `tier="write"` + 固定參數 `{ item_id }` + **橋接 closure handler** 註冊——closure 捕捉 `AssistantSkillService`，被呼叫時把該 skill 的 DB `code` 交沙盒執行（重用 `execute_skill` → `_execute_generated`：複製原檔 → 沙盒 → 可信層上傳，執行前先快照，見 §12.134.3）。用到自建 skill 的計畫**一律進確認閘**（`is_auto_confirmable` 回 false），不自動執行；批次（勾多檔）時，確認畫面**逐檔列出對應步驟**（FR5）。
- **勾選帶入目標檔（D2）**：`AssistantChatRequest` 加 `selected_item_ids: list[UUID]`；自建 skill 步驟的 `item_id` 由**勾選清單**帶入（不靠 LLM 猜檔名）。勾一個 → 對該檔執行；**勾多個 → 對每檔各跑一次（批次，執行層迴圈）**；勾零個 → 提示先選檔。前端沿用硬碟頁多選 state，對話框顯示已選檔 chips（可單獨移除）。
- **名稱衝突（FR6）**：自建 skill 名稱與內建衝突 → **跳過不載入並提示改名**。
- **planner prompt**：系統提示告知自建 skill 需 `item_id`、且**僅在有勾選檔時可用**，避免 LLM 在未選檔時把自建 skill 排入計畫。

**planner 提示必須交代每個技能的輸出形狀（2026-07-28，由 E9 eval 抓到並修正）**：步驟引用 `{"from": i, "path": ...}` 的 `path` 寫法取決於被引用步驟回傳什麼，但系統提示原本只說明了 `search`/`list_items` 的分頁形狀，且所有範例都是 `items.0.id`。實測後果（`eval/cases/generated/gen-m3-101`，真實 gemma4:26b）：模型要引用「自己剛用 `create_folder` 建立的資料夾」時照抄 `items.0.id`，執行期報 `cannot resolve path 'items.0.id' from step 1`，整批搬移失敗。已於 `build_planner_prompt` 補上三種形狀（依 `skills/builtin/{read_only,write}.py` 實作核對）：

| 技能 | 回傳 | `path` 寫法 |
|---|---|---|
| `search` / `list_items` / `list_trash` | `{"items": [...], "total": N}` | `items.0.id`、`items.*.id` |
| `recent` | 直接是 list | `0.id`、`*.id` |
| `get_info` / `create_folder` / `rename_item` / `move_item` / `star_item` | 項目物件本身 | `id` |
| `organize_by_type` | `{"moved_files": N, "folders": [...]}` | （不作為引用來源）|

**修正後的真模型對照（同 4 案，修改前後各跑一次）**：`execution` 維度 0.67 → **1.00**（引用解析錯誤消失，確認此缺口為主因之一）。但同一批案例仍然失敗，且暴露出**另一個層次的能力缺口**：模型改用 `move_item` 對 `list_items` 的結果做 `*` 全量 fan-out，等於把根目錄**所有**項目（含兩個 canary 資料夾）一起搬進最後建立的那個資料夾，而非依檔名分組。這正是 §10.16 的 canary 檢查要抓的「要的事做了、但別的東西被亂動」。結論：**選擇性批次分類（先分組再各自搬移）是這個模型目前做不到的**，記錄為能力邊界，不再放寬案例。
- **安全多層**：預設關 + 逐個 opt-in → write 級必確認 → codeguard 靜態掃描 + 沙盒隔離（網路／檔案／行程封鎖）→ 執行前自動快照；沙盒在本機執行，不送外部模型。

**影響範圍（落地時）**：`assistant_skills.chat_enabled` migration、`assistant/{router,service,planner}.py`（registry 載入橋接 handler、`selected_item_ids` 下傳）、`assistant/schemas.py`、前端 `pages/SkillsPage.tsx`（toggle）+ `components/assistant/AssistantPanel.tsx`（已選檔 chips）。

### 8.95.5 資料夾技能（item_types 權威化，DEC-035）

> **落地狀態**：整體資料夾（B）**已實作，待 merge**（分支 `feat/assistant-folder-skills`）；逐檔批次（A）設計保留、**未實作**（見 tasks 後續）。需求面見 proposal §12「技能可對資料夾執行」。

原 §8.95.2 生成技能「安裝後可掛右鍵選單對**單檔**執行」——`_execute_generated` 寫死只收 `FILE`（`item.item_type != FILE → "This skill runs on a file"`）。本設計讓技能能對**資料夾**執行，型別以 manifest `item_types` 為權威：

- **執行層分流（`_execute_generated`）**：先驗證 `目標.item_type ∈ skill.item_types`（不符回明確錯、訊息帶支援型別，取代原本硬擋 FILE）。
  - `FILE`：維持現況——下載單一 `storage_key` → `input_path` = 檔案。
  - `FOLDER`：`DriveService.collect_folder_descendants` **遞迴撈整棵子樹（檔案 + 資料夾）** → 先重建所有子目錄（**含空目錄**）、再把每個 FILE 下載到暫存目錄保留相對結構 → `input_path` = **該目錄**。**空資料夾或只含子資料夾的資料夾也可**（落地成空/僅結構目錄，不因「無檔」報錯）；上限只計 FILE。
  - `params` 加 `"item_type": "FILE"|"FOLDER"`（保留現有 `"filename"`），生成 code 據以分流；輸出沿用既有 `_ingest`（已支援多檔/巢狀回寫）。
- **兩種資料夾模式（DEC-035）**：
  - **A 逐檔批次**（「對資料夾內每個檔做 X」）：重用「勾多檔 fan-out」——對子樹每個 FILE 各跑一次 FILE 技能，不改 `run()` 契約。
  - **B 整體資料夾**（「把資料夾壓成一個 zip」）：走上面 FOLDER 分流，把整個目錄交給技能。
- **codegen `_CODEGEN_SYSTEM`**：教模型「`input_path` 是選取的項目——選檔為檔案、選資料夾為目錄；用 `os.path.isdir(input_path)` 或 `params["item_type"]` 分流，目錄用 `os.walk`/`pathlib` 走訪」。**單一技能涵蓋所有合理型別**：一個操作若對檔案與資料夾都合理（如壓縮/打包），就宣告 `item_types:["FILE","FOLDER"]` 並讓 code 同時處理兩者——**不分成兩個技能**；只有真正僅適用一種（如解 `.7z` → `["FILE"]`）才用單型別。json_schema 的 `item_types` enum 已含 `FOLDER`，不動。
- **已知取捨（codegen 品質變異）**：`author()` 只做靜態驗證（codeguard/manifest），**不執行 code**，故執行期 typo（真模型觀察到偶發 `os.pathlext`/`osorm` 類 token 走樣，think:OFF+temp 0.8）會溜過；使用者核可前可 review code、失敗可重生。若要根治可在 repair loop 加「沙盒 smoke 試跑 → 執行期錯誤回饋重生」（另立決策，見 tasks 待評估項）。
- **安全上限**：資料夾攝取設檔數/總量上限（`core/config.py`，建議 1000 檔 / 500MB），超過在攝取前回明確錯，防大資料夾打爆暫存/沙箱。
- **前端**：`DrivePage` 已依 `item_type` 過濾 `ui.context_menu`——宣稱 `FOLDER` 的技能**自動**出現在資料夾右鍵，無需改前端。
- **向後相容**：既有 FILE 技能與其 code 不動、無 migration；資料夾能力為加法。

### 8.6 端到端範例

- **單一新功能（7zip）**：「做一個 7zip 解壓縮功能」→ 解析 → 候選 workflow（1 步：`decompress_7z`）→ 檢查發現缺 → 生成子流程（codegen→核可→沙箱→安裝，掛右鍵選單）→ 回主流程 → 權限/安全 → 顯示計畫 → 確認 → 執行（沙箱解壓，結果寫回成 drive items）→ 記錄。
- **多步驟日常操作（已內建）**：「把『下載』裡的圖片依日期分資料夾，重複的刪掉」→ 候選 workflow（`search`→`organize_by_date`→`deduplicate`）→ 技能皆有 → 權限檢查（含破壞性 `deduplicate` 需確認）→ 顯示計畫 → 確認 → 依序執行 → 記錄；可另存為「整理下載圖片」工作流程重用。

### 8.7 HARNESS 九大組件（引擎，精簡定義）

| # | 組件 | 要做到的事（重點） | 檔案 |
|---|---|---|---|
| 01 | while loop | 驅動「送訊息→解析→執行→回填」直到完成/上限；停止條件、迴圈上限、hook 觸發。 | `service.py` |
| 02 | context management | token 預算、超量裁切/摘要、大型工具輸出瘦身；`num_ctx` 可設。 | `context.py` |
| 03 | skills & tools | 工具/技能 registry、相關性挑選、manifest、`author_skill` 撰寫流程。 | `skills/registry.py`、`skills/manifest.py`、`skills/authoring.py` |
| 04 | sub-agents | 單層子代理（主要用於 codegen、平行/有界子任務），獨立 context、回傳結果。 | `subagent.py` |
| 05 | built-in skills | 出廠技能目錄（5.1）+ `author_skill`，經 service 層、帶 user_id。 | `skills/builtin/` |
| 06 | session persistence | sessions/messages/skills/workflows 持久化；啟動載入使用者技能與已存工作流程。 | `repository.py` |
| 07 | system prompt assembly | 動態組裝：人設+安全規則+可用技能清單+語境（穩定前綴在前、無隨機/時間戳）。**無獨立 `prompt.py`**——各 agent 自組。 | `planner.py`（`build_planner_prompt`）、`subagent.py`（`build_codegen_prompt`） |
| 08 | lifecycle hooks | session/tool/skill/code-exec/error 節點；稽核、權限閘、計畫顯示、安裝前驗證。 | `hooks.py` |
| 09 | permissions & safety | 多租戶 user_id 綁定；分層權限（唯讀自動/破壞性確認/安裝+執行碼核可）；沙箱（資源/路徑/網路限制、參數化）；稽核。 | `permissions.py`、`skills/sandbox.py` |

（各組件的完整「具體要做到的事」與 7zip 子流程細節，於實作時依本節與第 3 節展開；DEC-018/019/020/021 為其決策依據。）

### 8.8 模組檔案結構

```
app/assistant/
  __init__.py
  router.py            # /assistant/chat、計畫確認、技能核可/安裝、工作流程儲存/重跑、技能 handler 觸發
  schemas.py           # Pydantic I/O schemas（chat / plan / skill / workflow）
  service.py           # 01 AgentLoop
  planner.py           # 階段 2-3：NL → 候選 Workflow（結構化輸出 + 驗證）；+ 07 build_planner_prompt
  workflow.py          # Workflow/WorkflowRun 模型、執行器（階段 8）、相依與錯誤策略
  context.py           # 02
  # 07 system prompt：無獨立 prompt.py，內嵌於 planner / subagent 各自的 build_*_prompt
  hooks.py             # 08
  permissions.py       # 09
  subagent.py          # 04；+ 07 build_codegen_prompt
  repository.py        # 06（sessions/messages/skills/workflows）
  llm/
    client.py          # LLMClient 協定（本地與外部共用介面）
    ollama.py          # 本地 Gemma via Ollama / OpenAI 相容（httpx）
    external.py        # 外部大型模型 API 執行器（OpenAI API key 路徑；EM2）
    router.py          # 1.3 模型策略：隱私閘 + 複雜度路由 + 失敗升級
    privacy.py         # 隱私分類 + 去識別化（升級前置）
  skills/
    registry.py        # 03
    manifest.py        # 03
    authoring.py       # 03 + 3.1 生成子流程
    codeguard.py       # 09 生成碼靜態安全驗證（網路/subprocess/eval 禁用等）
    sandbox.py         # 09
    builtin/           # 05 技能目錄
```


### 8.95.6 兩段式規劃（先偵察，看到結果再決定要動誰；2026-07-29，實驗性、預設關閉）

單次規劃的結構限制：模型必須在看到任何資料**之前**決定全部步驟，而規劃期唯一能篩選項目的手段是 `search`（字面 ILIKE 比對）。因此「把這堆檔案依它們是什麼分類收好」這種請求在規劃期無解——需求是語意的，工具是字面的。歸因實驗確認**不是模型能力問題**：把檔名先告訴模型、要求逐一搜尋再引用，它能產出 10 步計畫並端到端成功。

**設計**：同一個請求分兩次規劃，產出**同一份計畫**。

1. 模型判斷「非看到資料不能決定對象」時，只規劃唯讀偵察步驟，並把輸出欄位 `needs_followup` 設為 true（`PlanResult` 的**公開**欄位——這個值由模型產生，與 `llm_meta` 那種事後才知道的 `PrivateAttr` 相反，見 §10 的設計陷阱）。
2. 服務層執行其中**唯讀的子集**（寫入步驟一律丟棄不執行，見下），把實際結果與原始請求餵回規劃器，並告知新步驟從第幾步開始。
3. 第二次規劃的步驟**接在保留下來的偵察步驟之後合併成一份計畫**，再走既有的確認閘與執行流程。使用者確認的是完整計畫（查詢＋寫入）。

**為何合併而非新增跨計畫引用語法**：合併後索引天然連續，既有引用語法、確認閘、執行器、評測的引用接地檢查全部不用改，也不需要定義引用有效期。代價是偵察步驟在最終執行時會再跑一次——唯讀，安全且便宜。

**四個實作約束，全部由真模型實測逼出來（單元測試事後才補得上）**：

| 約束 | 不這樣做的後果（實測） |
|---|---|
| 第一段的寫入步驟**丟棄**，不進最終計畫 | 模型在第二段重複規劃同一個寫入 → `'發票' already exists` 連鎖失敗 |
| 保留的偵察步驟必須**重新編號**（`_renumber_kept`） | `depends_on` 指向已丟棄的步驟 → HTTP 400 `Step 0 has an invalid dependency: 1` |
| 回饋的觀察要含**名稱以外的事實**（類型／大小／更新時間，不含 id） | 沿用對話記憶的「只列檔名」渲染，「搬走最大的檔案」5/5 全錯（模型看不到大小） |
| 觀察每一行標的編號必須是**合併後**的編號 | 模型照抄第一段的舊編號，`item_id` 指到 `create_folder` 的輸出 → `cannot resolve path` |

**只有唯讀步驟能當偵察**：模型即使被明確禁止，仍慣性把「先建好目的地資料夾」折進第一段。直接拒收這種計畫等於讓功能永遠不啟動，因此改為**跳過**寫入步驟——未確認的寫入絕不執行，第二段會重新規劃那些準備工作。判斷「哪些讀取可以先跑」只看**參數引用**，不看 `depends_on`：模型常常把「列出根目錄」標成依賴「建立資料夾」，當成資料依賴會讓偵察集合變空、功能靜默失效。

**提示詞必須與旗標一致（回歸事故）**：`needs_followup` 的說明一度**無條件**寫進系統提示，旗標關閉時也照教。模型於是照樣拆兩段、只回傳唯讀查詢，而沒有第二段補上寫入——請求安靜地退化成一次列表。同 20 個 M3 案例：旗標關但提示照教 **0/20**（全數 `state_mismatch`，寫入步驟消失）；提示改為依旗標切換後 **20/20**。`build_planner_prompt(registry, *, two_phase)` 與 `WorkflowPlanner` 因此都讀同一個設定，與 `WorkflowService` 保持一致。**教一條不會被兌現的規則，比不教更糟。**

**成效與預設值**（各 5 次、真模型、每案例獨立帳號；詳見 `doc/tasks/backend-assistant.md`）：語意分類（單輪）0/5 → **5/5**、搬走最大的檔案 0/5 → **5/5**（基準線還會誤搬 canary）、重複檔案 0/5 → 4/5、語意分類（多輪）0/5 → 1/5；合計 **0/20 → 15/20**。仍**預設關閉**：同 20 個 M3 一般案例旗標開為 7/20，13 個失敗全部是同一項檢查（未呼叫 `get_info`，`state`／`execution` 兩維度仍 20/20、工具呼叫數更少），亦即不是做錯而是少做一次冗餘查詢；但一般案例本來就不需要偵察，多一次 LLM 呼叫的延遲與詞元（輸入 1799 vs 1406）沒有回報。以 `ASSISTANT_TWO_PHASE_PLANNING` 環境變數開啟。

**已知缺口**：`validate_plan` 只檢查「引用必須指向更早的步驟」，不檢查**被引用步驟的輸出型別是否合用**。多輪語意分類殘餘的失敗即是模型把 `parent_id` 指向一個 `move_item` 的輸出，規劃期驗證放行、執行期才報 `Destination must be a folder`。加上型別感知的引用檢查可讓它落進既有的修補迴圈，記為待辦。

### 8.95.7 計畫驗證：引用要對得上被引用步驟的輸出（2026-07-29）

`validate_plan` 原本只檢查「引用指向更早的步驟」，不檢查**那一步吐出來的東西合不合用**。兩類錯誤因此逃過規劃期、留到執行期才爆——而那時計畫裡更早的寫入步驟已經生效了：

| 錯誤 | 執行期症狀 |
|---|---|
| 路徑形狀不符（對 `create_folder` 用 `items.0.id`） | `cannot resolve path 'items.0.id' from step 0` |
| 拿「剛被改動的項目」當目的地（`parent_id` 指向某個 `move_item`） | `Destination must be a folder`，且前面幾步已經搬完 |

做法：`RegisteredSkill` 新增 `output: SkillOutput` 欄位宣告回傳形狀（`paged_items` / `item_list` / `item` / `new_folder` / `mutated_item` / `opaque`），內建技能逐一標註，**自建技能維持 `opaque` 不猜**。驗證據此判斷路徑前綴是否可能解得開，並禁止把 `mutated_item` 當 `parent_id`。

- 系統提示原本用散文列出同一份對照表，等於同一事實有兩個真相來源。提示文字**不動**（改提示的風險已經吃過一次虧），改以測試釘住兩者一致（`test_prompt_output_shapes_match_what_the_skills_declare`）。
- 代價：會擋掉一種罕見但合法的計畫（「把資料夾 A 搬進 B，再把檔案放進 A」）。修補迴圈的訊息會指名改引用「建立或找到目的地資料夾的那一步」，模型可以自行修正。

**修補迴圈的訊息措辭是有後果的（實測）**：原本的訊息結尾一律附上「如果做不到，就回傳空的 steps 並簡短說明」。加上新驗證後，模型在真實多輪測試裡 5/5 選擇了這條退路的變形——回「請先在硬碟勾選要操作的檔案」——而不是修掉一個步驟編號。改成「照這些修正改，其餘不要動；不要叫使用者去勾檔案，也不要對可修的步驟放棄」，並且**只有在它想用的技能根本不存在時**才提供退路，同一任務 0/5 → 3/5。

**沒有勾選檔案時要明說**（同批實測逼出來）：規劃提示只在**有**勾選時才附上選取清單，沒勾選時什麼都不說，模型於是假設有選取、規劃 `{"from": "selection"}` 引用，服務層只能回「請先勾選」。現在無選取時明確告知「目前沒有選取，selection 引用不可用，請改用 search/list_items 找出項目」。同理，兩段式規劃的 selection 早退條件也改為**只有真的有選取時**才成立——沒有選取的 selection 引用本來就跑不了，那正是最需要偵察的情況。

### 8.95.8 模型輸出殘骸不得進到使用者資料（2026-07-29）

真實症狀：請助理建一個叫 `AgentFolder_23f4b9ba` 的資料夾，**資料夾真的被建出來，名字卻是**

```
AgentFolder_23f4b9ba'}}]}<tool_call|>> {
```

成因：模型在**字串值內部**開始輸出聊天模板 token（或乾脆把 JSON 收掉改講白話），而受限解碼只保證**結構**合法——外層 JSON 解析得乾乾淨淨，髒東西全在字串裡面。整合測試 `test_chat_create_folder_pending_confirm_creates_real_item` 抓到，重現率 4/5。

範圍已量測：同樣的提示（中英文、有無引號皆試）對**遠端 OpenAI 相容 gateway** 2/3～4/5 會發生，對**本機 Ollama（gemma4:12b）0/3**。所以這是該 gateway 的解碼路徑，不是模型家族的問題——但產品不能假設對接的端點乾淨。

**做法（`planner._strip_decoding_artifacts`）**：解析成功後，把每個字串值在下列任一特徵處截斷，並清掉緊鄰的 JSON 標點：

| 特徵 | 例子 |
|---|---|
| 聊天模板 token | `<tool_call`、`<end_of_turn>`、`<start_of_turn>`，以及小於號接豎線的前綴 |
| 引號後接連續收括號 | `'}}]}` — 模型收完物件又繼續寫（`…'}}]}of course! Here is your plan:{`，這個變體完全沒有模板 token） |

**截斷而非退回重規劃**：截斷點之前就是使用者要的值，之後全是殘骸。退回重規劃會讓一個講得清清楚楚的請求得到「我做不到」，而且同一個 gateway 很可能再吐一次同樣的東西。截斷會寫 WARNING log 留痕。只有真的帶上述特徵的字串會被動到——`report [2026] {final}` 這種正常名稱不受影響（有測試釘住）。

**驗證**：同一請求對 gateway 連跑 10 次，**10/10 名稱乾淨**；整合測試 51/51 通過（原本 50/51）。

**未涵蓋**：codegen 產生的程式碼字串走的是另一條路徑（`subagent.py`），本次未處理；若在生成的程式碼裡看到同類殘骸要另外補。

### 8.95.9 生成的技能要先跑過再提出（2026-07-29）

`author()` 只做靜態驗證（AST 安全掃描＋manifest schema），從不執行程式碼。2026-07-29 全量評測量到**100 個生成技能有 18 個第一次呼叫就丟例外**——`NameError: name 'outputode_dir' is not defined`（識別字被 token 化弄壞）、正則的 `bad escape`、把 `str` 當 `Path` 用。全部語法合法、全部逃過靜態掃描，而使用者是在**核可安裝之後點下去**才發現。

做法：`CodegenSubAgent.author(request, smoke=...)` 多一個可選的試跑鉤子。驗證通過後，把程式碼丟進**正式環境同一個沙箱**跑一次（每個宣告的 item_type 各一次），失敗就把錯誤當成 repair problem 丟回既有的修補迴圈——與 manifest 錯誤走同一條路，不新增流程。`AssistantSkillService` 在有沙箱時自動接上；沒有沙箱時行為完全不變。

**只有「程式碼壞了」才觸發重寫**（`skills/smoke.py` 的 `_CODE_DEFECT_MARKERS`：NameError／SyntaxError／AttributeError／TypeError／re.error…）。輸入格式不合（PNG 技能拿到純文字 fixture）**不算**——評測 harness 正是在這裡摔過：99 個 M4 失敗有 48 個其實是 fixture 不匹配，對著幻覺問題修只會更糟。試跑用的 fixture 刻意是最小的純文字檔／資料夾，不從技能名稱猜格式。

**已知限制**：純文字 fixture 對影像／PDF／壓縮類技能只能驗到「程式碼跑得起來」，驗不到「做對了」。要更進一步得讓使用者選一個真實檔案當試跑輸入，或依 manifest 推斷格式——後者就是評測那邊踩過的坑，暫不做。

### 8.95.10 模型把數字寫壞（已知問題，未修，2026-07-29）

除了 §8.95.8 的結構殘骸之外，還有一種**字元層級**的損壞：要求把檔案改名為 `報告_2026`，實際建出 `報告_20<0xA0>26`（byte-fallback token 以字面形式外洩）或 `報告_2006`（數字直接寫錯）。

三臂實測（同 20 案、同程式碼、只換端點與模型）：

| 端點 / 模型 | 通過 | 名稱損壞 |
|---|---|---|
| 遠端 gateway，gemma4:26b | 4/20 | 10 |
| 本機 Ollama，gemma4:26b | 10/20 | 4 |
| 本機 Ollama，gemma4:12b | 20/20（兩輪 40/40） | 0 |

結論：**主因是 26B 這個模型**（兩台完全不同的機器出現同一種故障，排除硬體），遠端 gateway 讓它更嚴重。§8.95.8 的截斷救不了這一類——`報告_20<0xA0>26` 截掉只會變成更錯的 `報告_20`。

可行的修法是把 `<0xNN>` 這種不可能出現在使用者資料裡的標記視為無效計畫、走修補迴圈重規劃；`報告_2006` 這種純寫錯則只能靠換模型。**本次刻意不修，先記錄**（alfred 指示）。

### 8.9 資料模型（新增表，Alembic migration）

- `assistant_sessions(id, user_id, title, created_at, updated_at)`
- `assistant_messages(id, session_id, role, content, tool_calls JSONB, created_at)`
- `assistant_skills(id, user_id, name, description, manifest JSONB, code TEXT, status, created_at, updated_at)`
- `assistant_workflows(id, user_id, session_id, name, source_nl, steps JSONB, status, created_at, updated_at)`
- `assistant_workflow_runs(id, workflow_id, user_id, source_nl, status, step_results JSONB, created_at, finished_at)`

全部依 `user_id` 隔離。`assistant_workflows.session_id` 記錄發起該計畫的對話 session，但**刻意不設外鍵**：workflow 是可審核、可保存重跑的執行計畫，session 只是 UI 對話脈絡，兩者生命週期不同。不綁 FK 是為了在刪除或清理 session 時，不連帶破壞已保存的 workflow 與稽核紀錄；session 被刪後 `session_id` 成為孤立 UUID，workflow 仍可用 `user_id`／`status`／`name` 查詢與重跑。實際執行歷史改由 `assistant_workflow_runs.workflow_id` 承載，並以 `ON DELETE SET NULL` 確保 workflow 被刪時仍保留 run 紀錄。詳見[附錄 A](./appendix-a-decisions.md) DEC-027。

### 8.10 安全總結

- 每個 skill/步驟綁 `user_id`，只能碰自己有權限的項目（重用 PermissionService）。
- 破壞性步驟需確認；技能安裝與執行生成程式碼需核可 + 沙箱 + 稽核。
- 計畫先顯示再執行（階段 6-7），不先斬後奏。
- 本地模型，資料不外流，無雲端 key。
- 所有步驟與結果可追溯（activity_logs + workflow_runs）。

### 8.11 測試策略

- **後端單元** `tests/assistant/`：
  - `test_router.py`（mock 服務 + 認證）、`test_loop.py`（迴圈/上限/錯誤）、`test_dispatch.py`（路由+user_id）、`test_context.py`（裁切）。
  - `test_planner.py`：NL → 候選 workflow 結構化輸出與驗證（mock LLM）。
  - `test_workflow.py`：步驟相依、錯誤策略、唯讀 fast-path vs 需確認。
  - `test_authoring.py`：生成停在 pending_approval，不自動執行。
  - `test_sandbox.py`：逾時/路徑/網路限制。
  - `test_hooks.py`：權限閘擋破壞性/安裝。
- **LLM 一律 mock**。
- **前端**：MSW mock；測計畫顯示與確認、技能核可、依 manifest 動態右鍵選單、改檔後 query 失效。

### 8.12 環境變數

```
# 本地預設執行器
# LLM_PROVIDER: "ollama"（原生 /api/chat）| "openai_compatible"（走 /v1/chat/completions，
# 由 _build_local_client 建 ExternalLLMClient；用於指向 OpenAI 相容 gateway，後端可為 gemma4:26b）
LLM_PROVIDER=ollama
LLM_BASE_URL=http://192.168.10.75:11434
# 可選：主要端點連不上時改試的 Ollama fallback（空字串＝不啟用）
LLM_FALLBACK_BASE_URL=
LLM_API_KEY=ollama-local
ASSISTANT_MODEL=gemma4:26b
LLM_NUM_CTX=65536
LLM_TIMEOUT_SECONDS=300
LLM_KEEP_ALIVE=15m
ASSISTANT_ENABLED=true
ASSISTANT_MAX_TOOL_ITERATIONS=8
ASSISTANT_SANDBOX_TIMEOUT_SEC=30

# 反迴圈與取樣（DEC-031）：生成 token 上限（0＝不限）、結構化請求的溫度；
# codegen 需要完整取樣，另以較高溫度覆蓋（DEC-032）
LLM_NUM_PREDICT=2048
LLM_STRUCTURED_TEMPERATURE=0.2
LLM_CODEGEN_TEMPERATURE=0.8

# Thinking 開關（DEC-033 / E8）：
# LLM_PLANNER_DISABLE_THINKING＝planner 每次呼叫預設關 thinking（cured 迴圈、latency ~10x，
#   codegen 不連動）；LLM_DISABLE_THINKING＝client-wide 全域 E8 knob，對所有本地呼叫送
#   think:false（預設 false），per-call 的 planner 值優先於它
LLM_PLANNER_DISABLE_THINKING=true
LLM_DISABLE_THINKING=false

# 對話記憶：回讀進 planner 的最近訊息數（user+assistant），0＝關閉（單輪）；
# ContextManager.trim 仍以 num_ctx 為硬上限（§8.14）
ASSISTANT_HISTORY_MAX_MESSAGES=12

# 兩段式規劃（§8.95.6）：先執行唯讀偵察、看到實際結果再規劃其餘步驟，兩段合併為同一份計畫。
# 預設關閉——一般案例不需要偵察，多一次 LLM 呼叫的延遲與詞元沒有回報。開啟時系統提示會
# 一併切換（教了不會被兌現的規則比不教更糟，該回歸已量測：0/20 vs 20/20）。
ASSISTANT_TWO_PHASE_PLANNING=false

# 失敗升級到外部大型模型（1.3）
EXTERNAL_LLM_ENABLED=false        # 全域開關；false 則永不外送
MAX_LOCAL_ATTEMPTS=3              # 本地連續失敗幾次才評估升級
EXTERNAL_LLM_BASE_URL=
EXTERNAL_MODEL=
EXTERNAL_LLM_API_KEY=
PRIVACY_DEFAULT=sensitive         # 預設保守：使用者檔案內容視為隱私，需去識別化才可外送
```

### 8.121 驗證與評分

助理的功能正確性由獨立的**驗證／評分 harness** 持續把關：自動餵 prompt、可選跑瀏覽器（API / Browser 模式）、對結果做確定性斷言與可選 LLM 評審、並以多維度加權評分與 baseline 回歸比較。詳見 §10。

### 8.13 里程碑

1. **M1 引擎骨架（HARNESS 01/02/05/07）**：AgentLoop + LLMClient(Gemma) + context + prompt + 唯讀內建技能 + 測試。
2. **M2 Workflow 管線（planner/workflow + 08/09）**：NL→候選 workflow→技能檢查→權限→顯示計畫→確認→執行→記錄；唯讀 fast-path。前端聊天面板 + 計畫確認 UI。
3. **M3 技能框架與持久化（03/05/06）**：registry + manifest + 寫入/批次內建技能 + sessions/skills/workflows 持久化（migration）+ 工作流程重用。
4. **M4 自我撰寫 + 安全（04/03/08/09）**：sub-agent codegen + 生成子流程 + 核可閘 + sandbox。完成 7zip 範例端到端。
5. **M5 動態 UI**：依 manifest 渲染右鍵選單、技能核可/程式碼審查介面、已存工作流程一鍵重跑、側欄 Skills 管理頁（檢視/編輯/刪除，見 5.3）、使用者訊息複製鈕（前端全域 `user-select:none`，故以按鈕程式複製）。

### 8.14 對話記憶（多輪 context 回讀）

助理在**同一 session** 內回讀最近數輪對話，讓使用者能以指涉／省略延續操作（先列檔、下一句「把第一個改名為 X」）。設計原則是「把既有資料接上去」——對話本來就有存（`session_repo.add_message`），只是規劃時沒回讀；本功能把歷史接進 planner，不重建儲存。

- **模組**：`app/assistant/memory.py` 提供 `summarise_results`（把 StepResults 壓成精簡文字）／`append_result_summary`（接到 assistant 訊息尾）／`history_to_messages`（DB 訊息 → `LLMMessage`，取最後 N 則）。
- **管線接點**：`WorkflowPlanner.plan()` 新增 `history` 參數，組訊息序為 `[system,（選檔提示）, *history, 當前 user]` 後再 `context.trim()`；`WorkflowService.chat()`（含 replan）透傳。
- **歷史載入點**：router 的 `/chat` handler（已持有 `session_repo`、已負責寫入）在呼叫 `service.chat()` **之前** `list_messages` → 取最後 N 則傳入；因當前 user 訊息在 `chat()` **之後**才寫入，載入的歷史天然不含本輪（讀寫同層、service 維持純度）。
- **工具結果的承載（真模型 A/B 定案，零 migration）**：工具實際結果在 `results`(StepResult)、不在訊息文字裡。以 **assistant 文字**承載結果摘要——真模型（gemma4）A/B 測得放 `tool` 角色 0/4、放 assistant 文字 4/4（chat template 不消化孤立 tool 訊息）。做法：router 持久化 assistant 訊息時把 `append_result_summary(reply, results)` 接到 `content` 尾（僅在有結果時）；live 回應 `response.message` 維持乾淨（`plan.reply`），僅**持久化**內容多摘要（reload 泡泡因此更完整）。
- **設定**：`assistant_history_max_messages=12`（≈6 輪；`0`=關閉、退回單輪）。硬上限仍由既有 `ContextManager.trim`（`num_ctx=65536`≈26 萬字元，留最近丟最舊）保護。
- **範圍**：v1 只接 planner 路徑；codegen（技能生成）為單輪任務、不吃歷史。隱私上歷史與當前訊息走**同一** privacy gate（`_call_external` 對整包 messages 分類），摘要化不引入新外送面。
- **摘要保真兩個必要修正**（回歸守門，見附錄 A 相關 DEC 與 eval `multiturn-recall-listed-names`）：① `_optional_uuid` 接受根目錄哨兵（`root/null/none//` → None），否則列根目錄崩「Invalid UUID」→ 記憶無檔名；② `summarise_results` 對集合型輸出萃取檔名呈「N items: name1, …」、不 dump UUID，否則 200 字預算被 UUID 佔滿而截斷丟名。
- **已知限制（v1 刻意做小）**：只記最近 ~6 輪（更早直接丟棄、非壓縮）；工具結果每步只留前 ~200 字；單一 session 內、不跨對話、無長期畫像；靠「最近」非「相關」（無語意檢索）；屬「重讀逐字稿」非「學習」。v2 方向依序：調參 → 舊對話摘要壓縮 → 語意檢索（複用 pgvector）→ 跨 session／使用者畫像。

## 9. In-App AI Assistant 前端聊天切片

Assistant 的使用入口位於登入後 CloudDrive shell，而不是 Swagger/API docs。`AppShell` 會掛載 `AssistantPanel`，因此 `/drive`、`/recent`、`/starred`、`/shared`、`/trash`、`/search`、`/settings` 等受保護頁面都能開啟同一個浮動對話面板。

主要檔案：

| 檔案 | 職責 |
| --- | --- |
| `src/api/assistantApi.ts` | 呼叫 chat、list skills、approve skill、execute skill。 |
| `src/api/types.ts` | `AssistantChatRequest`、`AssistantChatResponse`、tool call/result、skill manifest/approval/execute 型別。 |
| `src/hooks/useAssistant.ts` | `useAssistantChatMutation`、`useAssistantSkills`、`useApproveAssistantSkill`、`useExecuteAssistantSkill`。 |
| `src/components/assistant/AssistantPanel.tsx` | 登入後浮動聊天面板；保存當前 `session_id`，送出訊息、顯示錯誤與技能核可卡。 |
| `src/components/assistant/MessageBubble.tsx` | 使用者/助理訊息視覺呈現。 |
| `src/components/assistant/SkillApprovalCard.tsx` | 顯示 generated manifest 摘要並執行核可/略過。 |
| `src/components/assistant/AssistantSkillResultDialog.tsx` | 顯示右鍵技能執行結果。 |
| `src/components/drive/FileContextMenu.tsx` | 接收 manifest 轉出的 assistant actions，動態插入單檔右鍵選單。 |
| `src/pages/DrivePage.tsx` | 讀取已安裝技能、依 `item_type` 過濾 `ui.context_menu`、執行技能並顯示結果。 |
| `src/components/layout/AppShell.tsx` | 在受保護 CloudDrive shell 掛載 assistant 入口。 |
| `src/components/assistant/WorkflowPlanCard.tsx` | 顯示 pending 計畫（步驟/permission tier/需核可）並確認/取消/儲存。 |
| `src/components/assistant/SkillApprovalDialog.tsx` | 顯示生成技能的完整程式碼供 code review，核可/拒絕。 |
| `src/components/assistant/SavedWorkflowsPanel.tsx` | 列出已存工作流程並一鍵重跑。 |
| `src/pages/SkillsPage.tsx` + `src/components/assistant/SkillEditDialog.tsx` | 側欄 `/skills` 技能管理頁：顯示已安裝技能數、列表、刪除確認、編輯描述/程式碼。 |
| `src/hooks/useAssistant.ts` | 另含 `useUpdateAssistantSkill`/`useDeleteAssistantSkill`/`useSavedWorkflows`/`useSaveWorkflow`/`useRerunWorkflow`。 |

前端 assistant 功能已完整：直接 chat、計畫確認卡、技能核可與 code review、manifest 驅動右鍵選單、已存工作流程一鍵重跑，以及側欄 Skills 管理頁（列表/編輯/刪除）。測試涵蓋 `AssistantPanel`、`SkillApprovalDialog`、`SavedWorkflowsPanel`、`SkillsPage` 等。

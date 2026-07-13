## 3. 整體架構

### 3.1 模組拆分原則與依賴方向

整體系統依下列原則拆分模組，確保各模組職責清楚、相互低耦合、可獨立開發與測試：

1. 每個模組只處理自己的核心責任。
2. Router 不直接操作資料庫。
3. Service 負責商業邏輯與跨 repository 協調。
4. Repository 只負責資料存取。
5. StorageProvider 只負責檔案本體讀寫，不負責資料庫。
6. 權限檢查集中在 PermissionService，不分散在各 router。
7. 容量檢查集中在 QuotaService。
8. 前端 server state 由 TanStack Query 管理。
9. 前端 UI state 由 Zustand 管理。
10. 每個模組都要能用 mock repository 或 mock storage 獨立測試。

模組依賴方向（單向，不可逆）：

```text
Router
  -> Service
    -> Repository
    -> StorageProvider
    -> PermissionService
    -> QuotaService

Repository
  -> PostgreSQL

StorageProvider
  -> Local file system
```

Repository 不可呼叫 Service；StorageProvider 不可呼叫 Repository；前端元件不可直接呼叫 `fetch`，必須透過 api client 或 hook。後端的分層落地細節見 §6 後端核心設計。

### 3.2 後端架構

```text
FastAPI app
  core
    config
    security
    dependencies
    exceptions
  routers
    auth
    users
    drive
    upload
    download
    preview
    search
    share
    trash
  services
    auth
    user
    drive
    permission
    quota
    storage
    upload
    download
    preview
    search
    share
    version
    activity_log
  repositories
    user
    token
    drive_item
    file_version
    share
    share_link
    activity_log
  storage
    base
    local
  models
  schemas
```

### 3.3 前端架構

```text
React app
  app
    router
    providers
  api
    client
    authApi
    driveApi
    uploadApi
    shareApi
    searchApi
  pages
    LoginPage
    RegisterPage
    DrivePage
    SharedWithMePage
    RecentPage
    StarredPage
    TrashPage
  components
    layout
    drive
    upload
    preview
    share
    common
  hooks
    useAuth
    useDriveItems
    useUploadQueue
    useShare
  stores
    authStore
    uploadStore
    uiStore
  types
  utils
```

### 3.4 系統架構圖

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
graph TD
  U["使用者瀏覽器"] -->|HTTPS| NX["nginx：靜態 SPA + /api 反代"]
  NX -->|"靜態資源"| SPA["React SPA"]
  NX -->|"/api/v1"| BE["FastAPI 後端"]
  BE -->|"SQLAlchemy async / asyncpg"| PG[("PostgreSQL 16 + pgvector")]
  BE -->|"Storage Provider 介面"| ST["檔案儲存層 local／物件儲存"]
  BE -->|"HARNESS 引擎"| AS["AI 助理"]
  AS -->|"預設本地"| OL["Ollama Gemma"]
  AS -.->|"反覆失敗升級"| EX["外部 GPT-5.5"]
```

> metadata 經 PostgreSQL、檔案 binary 經 Storage Provider，兩者分離（見 §7.9）。

### 3.5 部署圖

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
graph LR
  subgraph DEV["本機開發（docker compose）"]
    F1["frontend :8088"] --> B1["backend :8000"]
    B1 --> P1[("postgres :5432")]
    B1 --> SV["storage_data volume"]
    P1 --> PV["postgres_data volume"]
  end
  subgraph PROD["正式環境"]
    NET["公網"] -->|"80/443"| NX2["nginx 唯一入口"]
    NX2 -->|"內網 /api"| BE2["backend（不對公網）"]
    BE2 -->|"內網"| PG2[("postgres（不對公網）")]
    BE2 --> ST2["storage"]
  end
```

> 本機映射 `8000/5432` 僅供開發；正式環境僅 nginx 對外（見 DEC-028）。

### 3.6 核心流程時序圖

**登入後 silent refresh**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
sequenceDiagram
  participant U as 瀏覽器
  participant FE as AuthInitializer
  participant BE as FastAPI /auth
  U->>FE: 載入頁面
  FE->>BE: POST /auth/refresh（HttpOnly cookie）
  alt refresh 有效
    BE-->>FE: 新 access token（存記憶體）
    FE-->>U: 維持登入
  else 無效
    BE-->>FE: 401
    FE-->>U: 導向登入
  end
```

**檔案上傳（補償式一致性）**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
sequenceDiagram
  participant C as 前端
  participant S as UploadService
  participant ST as Storage
  participant DB as PostgreSQL
  C->>S: 上傳檔案
  S->>ST: save(blob)
  S->>DB: 建 drive_item / file_version / quota
  alt DB 成功
    DB-->>S: ok
    S-->>C: 201
  else DB 失敗
    S->>ST: delete(blob)（補償回滾）
    S-->>C: error
  end
```

**分享給指定使用者**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
sequenceDiagram
  participant O as 擁有者
  participant SH as ShareService
  participant DB as PostgreSQL
  participant R as 受分享者
  O->>SH: 分享 item 給 user（viewer/downloader/editor）
  SH->>DB: 建立 shares 紀錄
  R->>SH: GET /share/shared-with-me
  SH->>DB: 查 shares
  DB-->>R: 顯示分享項目
```

**AI 助理執行 workflow**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
sequenceDiagram
  participant U as 使用者
  participant A as Assistant（HARNESS）
  participant L as LLM
  participant SVC as Drive/Skill Service
  U->>A: 自然語言指令
  A->>L: 解析意圖
  L-->>A: 計畫（步驟／權限層級）
  A-->>U: 顯示計畫
  alt 破壞性操作
    U->>A: 確認後才執行
  end
  A->>SVC: 一律經 service 層執行
  SVC-->>A: 結果
  A-->>U: 回填結果
```

**時光機還原**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
sequenceDiagram
  participant U as 使用者
  participant TM as SnapshotService
  participant DB as PostgreSQL
  participant ST as Storage
  U->>TM: 選時間點還原
  TM->>TM: 先建「還原前保命快照」
  TM->>DB: 套用快照 metadata（覆蓋現況）
  TM->>ST: 還原 blob 引用
  TM-->>U: 還原完成（可再倒回）
```

### 3.7 輔助流程圖

**權限判斷（繼承）**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
flowchart TD
  A["存取 item"] --> B{"是 owner?"}
  B -->|是| O["owner：全部操作"]
  B -->|否| C{"shares 有分享?"}
  C -->|是| P["依 shares.permission"]
  C -->|否| D{"share_link 存取?"}
  D -->|是| Q["依 link.permission"]
  D -->|否| E{"父資料夾被分享?"}
  E -->|是| F["繼承資料夾權限"]
  E -->|否| X["拒絕存取"]
```

**AI workflow 狀態機**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
flowchart TD
  S((開始)) -->|收到指令| planning["planning：規劃中"]
  planning -->|產生計畫| pending_confirm["pending_confirm：待確認"]
  pending_confirm -->|使用者確認| executing["executing：執行中"]
  pending_confirm -->|取消| cancelled["cancelled：已取消"]
  executing -->|成功| completed["completed：完成"]
  executing -->|失敗| failed["failed：失敗"]
  completed --> E((結束))
```

**upload session 狀態機**

```mermaid
%%{init: {'theme':'default','themeVariables':{'fontFamily':'Trebuchet MS, Helvetica, Arial, sans-serif','fontSize':'14px','actorFontSize':'14px','messageFontSize':'14px','noteFontSize':'13px'}}}%%
flowchart TD
  S((開始)) --> pending["pending：待處理"]
  pending -->|上傳分片| uploading["uploading：上傳中"]
  uploading -->|合併成功| completed["completed：完成"]
  uploading -->|失敗| failed["failed：失敗"]
  uploading -->|取消| cancelled["cancelled：已取消"]
  completed --> E((結束))
```

### 3.8 Harness 架構歸類：六核心元件 ↔ 九實作模組（概念架構，報告/簡報用）

> 參考視角，不改變任何實作與介面；工程事實來源為 [§8.7](./08-assistant-engine.md)（HARNESS 九大組件）與 [§10](./10-assistant-eval.md)（驗證/評分 harness）。關聯 DEC-016～023、026、029。

agent harness 文獻（survey）將 harness 定義為六元組 `H = (E, T, C, S, L, V)`：Execution Loop、Tool Registry、Context Manager、State Store、Lifecycle Hooks、Evaluation Interface。本專案在**程式碼層**拆成九個實作模組（§8.7 的 01–09），粒度是為了**可測試性**（各模組 test 獨立、LLM 一律 mock）；但九模組不在同一抽象層級（有主元件、子元件、也有橫切關注點）。因此對外採**二層說法**：**Workflow Pipeline**（描述「要做什麼」：NL → 候選 workflow → 技能檢查 → 權限/安全 → 確認 → 執行 → 記錄）＋ **Agent Harness Runtime**（描述「怎麼可靠地跑」：對齊 survey 六元件）。**一句話：程式碼九層（實作模組），報告六層（概念架構）。**

**六元件 ↔ 九模組對照**

| Survey 元件 | 對應九模組 | 主要檔案 | 說明 |
|---|---|---|---|
| **E** Execution Loop | 01 while loop、04 sub-agents、workflow 執行器 | `service.py`、`workflow.py`、`subagent.py`、`llm/router.py` | 主迴圈驅動「送訊息→解析→執行→回填」；workflow 執行器負責步驟相依/錯誤策略（DEC-029/030）；可派生 bounded sub-agent；**model interface（ModelRouter）也歸此** |
| **T** Tool / Skill Registry | 03 skills & tools、05 built-in skills | `skills/registry.py`、`skills/manifest.py`、`skills/authoring.py`、`skills/builtin/` | 內建／自建／現場生成技能都是 registry 的技能來源；manifest 定義 schema/權限標記/handler dispatch |
| **C** Context Manager | 02 context management、07 system prompt assembly | `context.py`、`planner.py`、`subagent.py` | token 預算、裁切/摘要、工具輸出瘦身、技能清單注入、prompt 組裝；07 無獨立 `prompt.py`，內嵌於各 agent |
| **S** State Store | 06 session persistence | `repository.py`（+ migration：sessions/messages/skills/workflows/workflow_runs） | 全部依 `user_id` 隔離（DEC-020） |
| **L** Lifecycle Hooks | 08 lifecycle hooks、09 permissions & safety | `hooks.py`、`permissions.py`、`skills/codeguard.py`、`skills/sandbox.py` | hooks 是**攔截點**（治理層）；permissions/codeguard/sandbox 是它強制執行的機制。分層權限：唯讀自動／破壞性確認／生成碼核可+沙箱+稽核（DEC-019） |
| **V** Evaluation Interface | §10 驗證/評分 harness | `backend/eval/` | 確定性斷言 + LLM judge + baseline 回歸；API / browser / exec 三模式 |

**呈現三注意**：① **V 不在請求路徑上**——eval 是 `backend/eval/` 的離線開發者工具，從外部打 `/assistant/chat`，架構圖畫在 runtime **旁側**（箭頭指入）；② **sub-agent 現況誠實**——`subagent.py` 目前唯一實例是 CodegenSubAgent，說法為「主迴圈可派生 bounded sub-agent，目前實例化為 codegen 子代理」；③ **L 的合併**——`sandbox.py`/`codeguard.py` 嚴格說是執行基礎設施而非 hook，正確說法「Lifecycle Hooks 是治理層，permissions/codeguard/sandbox 是它在各攔截點強制執行的機制」。

**模型路由的歸位（本專案特色）**：survey 把 LLM 當黑盒，但本專案模型策略是明確賣點，歸入 **E 的 model interface 子元件、受 L 的隱私閘治理**——使用者每則訊息自選來源（本機 Ollama / 具名外部連線，見 [§12 模型選擇/具名連線](../proposal.md)、[§11](./11-external-model.md)），選定即唯一執行器、無自動 fallback、失敗快速且回可區分錯誤；隱私閘永遠在（DEC-023 第 2 條）。原「連續失敗自動升級」已被手動選擇取代，僅保留於 `ModelRouter` 的 `target=None` 相容路徑（有 eval `model-escalation` 覆蓋）。

**報告用架構圖（V 在旁側）**

```
使用者自然語言需求
        ↓
┌─ Workflow Pipeline ────────────────────────────┐
│ 需求解析 → 規劃 → 技能檢查 → 權限/安全 → 確認 → 執行 → 記錄 │
└────────────────────────────────────────────────┘
        ↓
┌─ Agent Harness Runtime（六元件） ───────────────┐      ┌─ V Evaluation Interface ─┐
│ E Execution Loop（while/workflow/子代理/模型介面）│ ◄─── │ 離線開發者工具            │
│ T Tool/Skill Registry（內建/自建/現場生成+manifest）│ 評測 │ deterministic assertion  │
│ C Context Manager（裁切/prompt 組裝/技能清單注入） │ 請求 │ API/browser/exec         │
│ S State Store（sessions/messages/skills/workflows）│      │ LLM judge / baseline     │
│ L Lifecycle Hooks（治理層：權限/核可/codeguard/    │      └───────────────────────────┘
│   sandbox/audit —— 含外送隱私閘）                  │
└─────────────────────────────────────────────────┘
        ↓  CloudDrive Service Layer（DEC-017）→ PostgreSQL + Storage Provider
```

**文獻筆記（答辯用）**：StraTA（arXiv 2605.06642）為 Agentic RL 框架（先生成精簡策略再指導行動，分層聯訓），解的是同類長程規劃可靠度問題，設計哲學與本專案「計畫→確認→執行」及 validator+repair 同構；但它是**訓練期** RL、需微調凍結的 gemma4:26b（超出範圍），故本專案改採 **harness 層推理期補強**（約束解碼 DEC-031/032、驗證重試、確認閘）——這正是 harness 作為「LLM 與外部世界間可靠性基礎設施」的價值主張。

## 4. 已確認設計決策

| 項目 | 決策 |
| --- | --- |
| 文件覆蓋範圍 | MVP + 第二階段功能 |
| 第三階段功能 | 不納入主詳細設計，只保留擴充介面 |
| 前端狀態管理 | Zustand + TanStack Query |
| UI / 樣式 | shadcn/ui + Tailwind CSS |
| JWT 函式庫 | PyJWT |
| 密碼雜湊 | pwdlib[argon2] |
| 檔案儲存 | StorageProvider 抽象介面 + LocalStorageProvider 第一版實作 |
| 下載接口 | MVP 使用 FastAPI StreamingResponse |
| 大檔案分片上傳 | 不納入核心 detailed design，只保留 UploadSession 擴充點 |
| 分享功能 | 納入分層設計；指定使用者分享先做；公開連結、密碼、到期時間作為第二階段可選 |
| 檔案版本紀錄 | 納入資料表與 service 設計；MVP 可只存 v1 |
| 管理員後台 | 不納入主文件，只保留 role 欄位 |
| 文件語言 | 繁體中文 |

> 上述決策的延伸說明（欄位型別與長度、星號權威來源、metadata/storage 一致性、暴露面與 secret 管理等）已敘述於對應章節（§7.0、§7.3.1、§7.9、§8.9、§21）並彙整於[附錄 A](./appendix-a-decisions.md)（DEC-027、DEC-028），不另立問答清單。

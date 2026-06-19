# 專案自主決策紀錄

## DEC-001：Python 執行環境

- 日期：2026-06-13
- 狀態：Accepted
- 背景：系統 Python 為 3.9.6，但專案要求 Python 3.12 以上，且已指定使用 uv。
- 決策：由 uv 管理並鎖定 Python 3.12，不依賴系統 Python。
- 理由：符合已確認技術決策，且避免修改系統 Python。
- 影響範圍：`pyproject.toml`、`.python-version`、後端安裝與測試指令。

## DEC-002：Docker 尚不可用

- 日期：2026-06-13
- 狀態：Superseded by DEC-006
- 背景：目前環境找不到 `docker` 與 `docker compose` 命令。
- 決策：先完成 Dockerfile、Compose 設定與不依賴 Docker 的開發工作；在 PostgreSQL 整合測試前再次檢查並依授權安裝或啟用 Docker。
- 理由：Docker 缺失不影響專案骨架、單元測試與大部分模組開發，不應提前阻塞整體流程。
- 影響範圍：Stage 0 啟動驗證、Database 整合測試、Stage 11 E2E。

## DEC-003：Refresh Token 傳輸

- 日期：2026-06-13
- 狀態：Accepted
- 背景：需求確認 refresh token 必須使用 HttpOnly、Secure、SameSite cookie。
- 決策：登入與 refresh API 只在 JSON 回傳 access token；refresh token 透過 HttpOnly、SameSite=Lax cookie 設定。staging/production 必須加上 Secure；本機 development/test 的 HTTP 環境不加 Secure。登出撤銷 token 並清除 cookie。
- 理由：避免 JavaScript 直接存取 refresh token，降低 XSS 造成的憑證外洩風險。
- 影響範圍：Auth API、CORS、Axios client、前端登入狀態。

## DEC-004：星號個人化

- 日期：2026-06-13
- 狀態：Accepted
- 背景：共享檔案的星號狀態必須依使用者獨立。
- 決策：新增 `user_item_preferences`，以 `(user_id, item_id)` 唯一識別，星號狀態不使用共用的 `drive_items.is_starred`。
- 理由：避免一位使用者修改星號時影響其他使用者。
- 影響範圍：Database、DriveItem、Search、前端 Drive。

## DEC-005：最近項目來源

- 日期：2026-06-13
- 狀態：Accepted
- 背景：「最近」需依每位使用者的實際活動，而非只依檔案更新時間。
- 決策：由 `activity_logs` 聚合使用者對 item 的最後活動時間，並排除垃圾桶、已永久刪除及已失去權限的項目。
- 理由：符合已確認的產品行為，且不污染 DriveItem 的核心中繼資料。
- 影響範圍：ActivityLog、DriveItem recent query、前端 RecentPage。

## DEC-007：JWT Refresh Token 加入 jti claim

- 日期：2026-06-13
- 狀態：Accepted
- 背景：若兩個 refresh token 在同一秒內發行給同一使用者，JWT payload 相同（iat/exp 相同），導致 token hash 衝突，無法在資料庫中同時存在。
- 決策：在 `_create_token` 加入 `jti`（UUID4），確保每個 token 唯一。
- 理由：符合 RFC 7519 標準，且避免 hash 衝突導致的輪替失敗。
- 影響範圍：`app/core/security.py`、refresh_tokens 資料表中的 token_hash 唯一性。

## DEC-008：StorageProvider 使用 Protocol 而非 ABC

- 日期：2026-06-13
- 狀態：Accepted
- 背景：prompt.md 要求定義 StorageProvider 抽象介面，Protocol 與 ABC 均可。
- 決策：使用 `typing.Protocol`（加上 `@runtime_checkable`）定義介面，LocalStorageProvider 不繼承 Protocol，但滿足其結構。
- 理由：Protocol 是結構型子型別，不需要顯式繼承，更符合 Python duck typing 風格，且 runtime_checkable 允許 isinstance 驗證。
- 影響範圍：`app/storage/base.py`、`app/storage/local.py`、factory 測試。

## DEC-009：Refresh Token 輪替使用 JWT + DB Hash 雙重驗證

- 日期：2026-06-13
- 狀態：Accepted
- 背景：refresh token 需要支援撤銷（logout），且 prompt.md 要求只在 DB 儲存 hash。
- 決策：refresh token 為 JWT（含 jti），每次發行時將 SHA-256 hash 存入 refresh_tokens 表；refresh 時先驗證 JWT 合法性，再查 DB 確認未撤銷，發行新 token 後撤銷舊 token。
- 理由：JWT 提供無需 DB 查詢的快速過期檢查；DB hash 提供真正的撤銷能力。login/logout 路徑 refresh token 不出現在 JSON body（只在 cookie 中）。
- 影響範圍：auth service、router、security.py。

## DEC-010：ActivityLogService 失敗靜默吞噬

- 日期：2026-06-13
- 狀態：Accepted
- 背景：活動記錄是輔助功能，不應因記錄失敗而影響主要業務流程（建立資料夾、重命名等）。
- 決策：`ActivityLogService.log()` 捕捉所有例外，失敗時記錄 warning 並回傳 `None`，不重新拋出。
- 理由：活動記錄缺失不構成核心功能失敗；可以在事後透過稽核補救。
- 影響範圍：ActivityLog service、DriveService._log()、所有呼叫 log() 的服務。

## DEC-011：SQL Repository 使用 `# pragma: no cover`

- 日期：2026-06-13
- 狀態：Accepted
- 背景：SQL repository 實作需要真實的 PostgreSQL 連線，無法在單元測試中覆蓋；每個模組的 Abstract repository 由假實作（MemRepo/MockRepo）覆蓋測試。
- 決策：所有 `SQL*Repository` 類別加上 `# pragma: no cover`，排除在覆蓋率計算之外；並分別建立 Integration Test 套件在真實 DB 上驗證。
- 理由：避免因無法單元測試的 DB 層程式碼拖累整體覆蓋率門檻，同時維持邏輯層（service/router）的高覆蓋率。
- 影響範圍：所有後端模組的 repository.py。

## DEC-012：DriveService 依賴注入 ActivityLogService（可選）

- 日期：2026-06-13
- 狀態：Accepted
- 背景：DriveService 需要寫入活動記錄，但測試時不需要 activity service。
- 決策：`DriveService.__init__` 中 `activity_svc` 為可選（`ActivityLogService | None = None`），`_log()` 先檢查 `self._activity is not None`。
- 理由：測試可用簡單 in-memory fake repo 建立 DriveService，不需要帶入 activity service 依賴；生產路徑由 router 的 `_drive_service` 工廠注入完整依賴。
- 影響範圍：drive/service.py、drive/router.py、drive 測試。

## DEC-013：PermissionService 走訪父鏈繼承權限

- 日期：2026-06-13
- 狀態：Accepted
- 背景：分享時可以分享資料夾，子項目應自動繼承父資料夾的分享權限。
- 決策：`PermissionService.get_permission()` 從當前 item 開始，沿 parent_id 鏈向上走訪。每層先檢查 owner（立即回傳 OWNER），再查 shares 表；取所有層最高權限（most permissive）作為有效權限。
- 理由：一次性迭代走訪，避免遞迴深度問題；seen set 防止 parent 環路。
- 影響範圍：PermissionService、所有需要權限判斷的 service（FileVersion、Upload、Download、Share）。

## DEC-014：FileVersionService 不儲存 storage_key 在 Response

- 日期：2026-06-13
- 狀態：Accepted
- 背景：storage_key 是內部路徑，不應暴露給前端。
- 決策：`FileVersionResponse` 不包含 `storage_key` 欄位，僅包含 version_no、size_bytes、checksum_sha256 等前端需要的欄位。
- 理由：避免洩漏儲存層實作細節（S3 key 前綴、路徑結構等）。
- 影響範圍：FileVersionResponse schema、list versions endpoint。

## DEC-006：本機容器執行環境

- 日期：2026-06-13
- 狀態：Accepted
- 背景：主機原先沒有 Docker CLI 或 runtime，但完整驗收需要 PostgreSQL 與 Docker Compose。
- 決策：使用 Homebrew 安裝 Docker CLI、Docker Compose 與 Colima，並以 Colima 提供本機 Docker runtime。
- 理由：可在不依賴桌面 GUI 的情況下自動啟動 PostgreSQL 與執行整合測試。
- 影響範圍：Project Setup、Database、Integration Testing、Docker Compose 驗收。

## DEC-015：忘記密碼採「隨機臨時密碼 + 防枚舉 + 強制改密碼」

- 日期：2026-06-15
- 狀態：Accepted
- 背景：需要在登入頁提供忘記密碼功能，由使用者郵箱收到還原密碼，登入後提醒改密碼。
- 決策：
  1. `POST /auth/forgot-password` 直接將密碼重設為系統產生的隨機 10 碼（`generate_random_password`），透過 email 寄出，而非寄送一次性 reset token 連結。
  2. 防枚舉：查無 email 或帳號停用時靜默結束，端點對任何輸入都回傳相同訊息；SMTP 寄送失敗亦吞下並記錄。
  3. 以 `users.must_change_password` 旗標標記被重設的帳號，登入後前端顯示提醒 banner；使用者改密碼時清除旗標。
  4. Email 寄送做成 `EmailProvider` 抽象層（Console 預設 / SMTP 可選），仿照 `StorageProvider`。
- 理由：符合需求描述（隨機密碼寄出）且最小化基礎設施；抽象層讓 SMTP 與 console 可切換、無 SMTP 設定也能運作。
- 已知取捨：任何知道他人 email 者皆可觸發重設造成帳號臨時鎖定（DoS 向量）。可接受於本專案範圍；未來如需更嚴謹可改為一次性 token 連結 + 速率限制。
- 影響範圍：AuthService、UserRepository、User model、Alembic 0004、`app/email/`、CurrentUserResponse、前端 ForgotPasswordPage 與 ChangePasswordReminder。

## DEC-016：不採用 OpenClaw，改自建 In-App AI Assistant

- 日期：2026-06-16
- 狀態：Accepted
- 背景：原需求為「接入 openclaw」。評估後，OpenClaw 是 Node.js/TypeScript 的個人 AI 助理 daemon，主打跨通訊平台、語音、單人 local-first，與 CloudDrive（Python、多使用者 web）技術棧與使用模型皆不符。實際需求僅為「在網頁內用對話操作檔案」。
- 決策：不使用 OpenClaw。自建 In-App Assistant：後端 `/api/v1/assistant/chat` endpoint 內跑 Claude tool-use 迴圈，工具呼叫既有 service 層；前端提供聊天面板。
- 理由：OpenClaw 的核心價值（跨通訊平台、單人 daemon）在本專案用不到；扛一整個 Node daemon 並處理單人 vs 多人錯配不划算。自建在自家技術棧內、天然多租戶、工作量更小。
- 已知取捨：放棄 OpenClaw 既有的多通訊平台與技能生態；若未來需要從 Telegram/語音等管道操作，需另議。
- 影響範圍：新增 `app/assistant/` 模組、前端 assistant 元件；詳見 assistant-design.md。
- 註：本決策當時假設以 Claude/`anthropic` 實作；模型選擇後由 DEC-018/DEC-023 取代為本地 Gemma + 條件式外部升級。OpenClaw 不採用之結論不變。

## DEC-017：助理一律經 service 層，不直接操作 DB／檔案

- 日期：2026-06-16
- 狀態：Accepted
- 背景：「讓助理直接操作資料庫／檔案」（類比個人電腦直接裝 AI 助理操作本機檔案）會繞過 CloudDrive 的配額、權限、命名衝突、軟刪除、活動紀錄、分享 token 雜湊等業務邏輯。
- 決策：助理的每個工具都呼叫既有 service（DriveService、SearchService、TrashService…），並一律帶入當前 JWT 的 `user_id`；不直接讀寫 Postgres 或 storage 目錄。v1 在 agent loop 內直接定義工具，暫不抽成 MCP server。
- 理由：CloudDrive 的關鍵不變量全在 service 層，直接操作 DB 等於用另一語言重寫並承擔資料失同步風險。經 service 層可完整重用且天然多租戶安全。穩定介面是 service／REST，而非底層資料表。
- 已知取捨：多一層呼叫（可忽略）；工具與 service 介面耦合（同 repo、可控）。未來若要讓同套工具被多個 AI 客戶端共用，再抽成後端內建 MCP server（路線 B）。
- 影響範圍：AssistantService、ToolDispatcher、各既有 service 的注入。

## DEC-018：助理採本地 Gemma 4 26B，不用雲端 API

- 日期：2026-06-16
- 狀態：Amended by DEC-023（預設仍為本地 Gemma，但新增條件式外部升級）
- 背景：助理需自訂、可離線、資料不外流，且為使用者本地掌控的模型。
- 決策：使用本地執行的 Gemma 4 26B；預設經 Ollama（`/api/chat`，支援 tools），亦可指向任何 OpenAI 相容端點。後端以 `LLMClient` 抽象封裝，只用 httpx，不引入雲端 LLM SDK（不使用 anthropic/openai 雲端服務）。
- 理由：本地模型符合自訂與隱私需求；抽象層讓推論後端可替換。
- 已知取捨：26B 本地模型的 function-calling 可靠度低於前沿雲端模型，需靠 harness 的穩健迴圈、輸出解析/修復、驗證與重試補強；推論延遲與品質受本機硬體限制。
- 影響範圍：`app/assistant/llm/`、config（LLM_PROVIDER/LLM_BASE_URL/ASSISTANT_MODEL/LLM_NUM_CTX）、prompt 與迴圈設計。

## DEC-019：允許 agent 自我撰寫技能，但須「核可 → 沙箱 → 稽核」

- 日期：2026-06-16
- 狀態：Accepted
- 背景：核心價值是讓使用者請 agent 現場製作新功能（如 7zip 解壓縮並掛右鍵選單），這代表 agent 會生成並執行程式碼。
- 決策：技能撰寫由子代理 codegen 產生 handler+manifest，狀態停在 `pending_approval`；經使用者明確核可後，於受限子行程沙箱（CPU/記憶體/逾時上限、檔案存取限該使用者 storage、無對外網路、參數化呼叫）執行；所有動作寫入 activity_logs。絕不自動執行未審核程式碼。
- 理由：自我擴充是主要價值，但執行生成程式碼是最大安全面，必須以核可閘 + 沙箱 + 稽核三道關卡控管。
- 已知取捨：每個新功能需人工核可一次（非全自動）；沙箱限制可能擋掉部分進階功能；維護沙箱有額外成本。對安全而言可接受。
- 影響範圍：`skills/authoring.py`、`skills/sandbox.py`、`hooks.py`、`permissions.py`、`assistant_skills` 資料表、前端核可介面與動態右鍵選單。

## DEC-020：助理 session 與技能持久化到 DB（取代記憶體 only）

- 日期：2026-06-16
- 狀態：Accepted（取代早期設計草案中「v1 不持久化」的暫定）
- 背景：HARNESS 含 session persistence；且已安裝的自訂技能必須跨 session 留存才有意義。
- 決策：新增 `assistant_sessions` / `assistant_messages` / `assistant_skills` 資料表；對話可續接，使用者自訂技能依 `user_id` 隔離並於啟動時載入。
- 理由：技能與對話留存是功能可用性的前提。
- 影響範圍：Alembic migration、`app/assistant/repository.py`、models。

## DEC-021：助理執行模型採「Workflow 管線 + 計畫確認」

- 日期：2026-06-16
- 狀態：Accepted
- 背景：助理需涵蓋各類檔案/資料夾日常操作並能現場生成新功能；自由放任 tool 迴圈不利於可控性與安全。
- 決策：採需求流程圖的管線 —— 使用者 NL → LLM 解析 → 轉成候選 Workflow（結構化步驟）→ 檢查可用 Skill（缺則走生成子流程）→ 權限與安全檢查 → 顯示執行計畫 → 使用者確認（是→執行，否→修改/取消）→ 執行 Workflow → 記錄操作與結果。Workflow 為有序 skill 步驟，可儲存重用；唯讀且非破壞工作流程可依權限自動確認 fast-path。此管線疊在 HARNESS 引擎之上，各階段對應 HARNESS 組件（見 assistant-design.md 第 3 節）。
- 理由：先計畫後執行 + 使用者確認，兼顧通用性、可檢視性與安全；workflow 化讓多步操作與生成功能可重用、可稽核。
- 已知取捨：每次（非 fast-path）需一次確認互動；規劃階段增加一次 LLM 結構化輸出成本；需維護 workflow schema 與執行器。
- 影響範圍：`app/assistant/planner.py`、`workflow.py`、`assistant_workflows`/`assistant_workflow_runs` 表、前端計畫確認 UI。

## DEC-022：助理功能以「驗證／評分 Harness」持續把關

- 日期：2026-06-16
- 狀態：Accepted
- 背景：助理用本地非決定性模型、會生成技能與跑沙箱，需可重複的方式驗證「功能是否正常」並量化品質。
- 決策：建立獨立 eval harness —— 以 YAML 測試案例自動餵 prompt，支援 API 與 Browser 兩種模式（`--mode` 即「是否跑瀏覽器」開關，共用同一份案例）；驗證採確定性斷言（workflow/state/safety）為主、LLM 評審為輔；評分為多維度加權 + 通過門檻 + 多次執行通過率/變異 + baseline 回歸；受測 LLM 可 mock（CI 必跑、決定性）或 real（量測品質）。
- 理由：非決定性模型需以狀態斷言為主、judge 為輔，並以通過率/變異描述穩定度；雙模式兼顧 CI 速度與真實端到端；baseline 比較可擋回歸。
- 已知取捨：維護案例與 harness 有成本；real LLM eval 較慢且分數會浮動，故 CI 主跑 mock 確定性案例。
- 影響範圍：`backend/eval/`、`frontend/e2e/assistant/`、CI 設定；詳見 assistant-eval-design.md。

## DEC-023：模型策略 —— 預設本地，反覆失敗時條件式升級外部 API

- 日期：2026-06-16
- 狀態：Accepted（修訂 DEC-018）
- 背景：本地 Gemma 4 26B 對部分複雜任務可能反覆做不出可接受結果；需有退路，但不能犧牲隱私。依「建議模型策略」流程圖納入隱私閘、複雜度路由與失敗升級。
- 決策：
  1. 預設執行器為本地 Gemma；能用非 LLM 規則/小模型解的簡單任務優先省成本。
  2. 隱私閘：涉私資料的任務限本地；若要外部須先去識別化，去識別化失敗則禁止外送。
  3. 失敗升級：追蹤該工作的 `local_attempts`，當本地連續達 `MAX_LOCAL_ATTEMPTS` 次仍不可接受（結構化輸出/工作流程驗證反覆失敗、無進展、或驗證器判定未達需求）且符合資格（`EXTERNAL_LLM_ENABLED` 且非隱私敏感或已去識別化）時，經 `LLMClient` 外部執行器重試。
  4. 外部回來的計畫/結果仍走原本權限、安全、沙箱、確認閘；升級事件寫稽核；使用者可全面禁用外部。
  5. 不符資格（隱私鎖定或外部停用）時不外送任何資料，於本地失敗回報。
- 理由：兼顧本地隱私優先與「真的做不出來時有退路」；隱私永遠優先於升級。
- 已知取捨：啟用外部時部分資料可能（經去識別化後）外送，需使用者明確開啟並信任外部端點；維護隱私分類/去識別化有成本且非完美，故預設保守（檔案內容預設視為隱私）、外部預設關閉。
- 影響範圍：`app/assistant/llm/{router,external,privacy}.py`、config（EXTERNAL_LLM_*/MAX_LOCAL_ATTEMPTS/PRIVACY_DEFAULT）、hooks 稽核、eval 的 `model-escalation` 案例。

## DEC-024：新增「時光機（Snapshots）」整碟時間點還原

- 日期：2026-06-17
- 狀態：Accepted（已實作 S1-S5；仍有非阻擋限制：還原時硬配額檢查待補強）
- 背景：使用者希望有類 Apple Time Machine 的能力——把整個雲端硬碟倒帶到過去某時間點瀏覽與還原。既有 `file_versions` 只記每檔版本，無法表達「整碟在時間 T 的狀態」（哪些檔存在、名稱、位置、是否被刪）。
- 決策：
  1. 新增 `snapshots` / `snapshot_entries` 兩表記錄整碟時間點；**內容層引用既有 `file_versions` 並以 `checksum_sha256` 去重**，不重複存 blob（增量、省空間）。
  2. 快照三種觸發：**自動排程（預設開啟、每小時，可設定/關閉）**、**手動**、以及**助理寫入/破壞性 workflow 或生成式 skill 執行前自動建快照**（`trigger=assistant`，**每個 workflow / 每次 skill 一個**），讓使用者能一鍵回到助理操作前。
  3. 還原採**就地覆蓋**現況；還原前一律自動先建 `pre_restore` 保命快照（pinned），走 service 層套配額/權限檢查、寫稽核。資料夾子樹/整碟還原時，對「快照當時無、現在才有」的項目由**使用者每次還原選 `keep_new`（保留新增）或 `exact_mirror`（精確鏡像）**。
  4. 保留策略為**保留最近 N 個**（預設 50，可設），`pinned` 與 `pre_restore` 豁免；超量刪最舊。
  5. 快照空間**不計入檔案配額**，另設**獨立快照配額**（per-user，可設；**預設為檔案配額的一半**，15GB → 7.5GB）。
  6. 刪快照採 **blob 背景 GC**（依引用計數回收，不阻塞刪除）。
  7. 分享/協作項目**僅擁有者可還原**（viewer/editor 不可）。前端路由 `/time-machine`。
  8. 排程建立條件為使用者設定開啟、距最近一筆快照已達間隔、且 drive 目前至少有一個 item；空碟不建立排程快照。
  9. 前端時間軸**依日期分組**；還原以**多選勾選 + 「還原選取項」/「還原整個快照」**。
- 理由：以新模型表達整碟狀態才能還原刪除/改名/搬移；重用 file_versions + checksum 讓快照便宜；就地還原貼近 Time Machine 行為，pre_restore 快照消除「誤覆蓋無法回頭」風險；獨立快照配額避免快照吃爆使用者檔案空間又能各自控管；保留 N 比 Apple thinning 簡單且足夠；背景 GC 讓刪除操作輕快。
- 已知取捨：就地還原具破壞性（以 pre_restore + 二次確認緩解）；自動排程與引用計數回收有背景成本；協作/分享項目的還原暫限擁有者。
- 影響範圍：新增 `app/snapshot/`（router/service/repository/schemas）、`snapshots`/`snapshot_entries` migration、背景排程任務、`app/assistant/`（workflow/skill 執行前建快照串接）、前端時光機頁與 API/hooks、`tests/snapshot/`。詳見 [time-machine-design.md](./time-machine-design.md)。

## DEC-025：部署規範 —— 一行啟動、前端同源反向代理、選用功能可關閉

- 日期：2026-06-18
- 狀態：Accepted
- 背景：要求「把 code 拉下來、填最少環境參數、一行指令就能跑」，且部署到任何主機都不該手動調設定。原本前端把 API 網址編譯時寫死 `localhost:8000`，換主機即失效；缺根層 `.env.example`；compose 帶未使用的 redis、LLM 預設指向私有 IP。
- 決策：
  1. **一行啟動**：`scripts/start.sh` 首次由 `.env.example` 建 `.env` 並產生隨機 `JWT_SECRET_KEY`，偵測 `docker compose`/`docker-compose`，`up --build -d`。後端容器啟動自動 `alembic upgrade head`。
  2. **前端同源 + nginx 反代 `/api` → backend**：前端建置預設 `VITE_API_BASE_URL=/api/v1`（相對）。部署到任何主機免重建前端、無 CORS。
  3. **選用功能可關閉、不阻擋核心**：AI 助理與語意搜尋皆可用環境變數關閉；關閉時檔案/分享/搜尋/時光機照常。`EMBEDDING_ENABLED` 預設 false；`ASSISTANT_ENABLED` 在開發 compose 可預設開啟以便展示，沒有 Ollama 時設為 false。`SNAPSHOT_SCHEDULER_ENABLED` 在 compose（單 worker）預設開。
  4. **根層 `.env.example`** 列出所有 compose 變數 + 安全預設 + 註解；`.env` 不進版控。
  5. **清理**：移除未使用的 redis 服務與 `REDIS_URL`；LLM 預設改 `host.docker.internal:11434` + `extra_hosts: host-gateway` 以連主機 Ollama。
  6. postgres 採 `pgvector/pgvector:pg16`（語意搜尋需要 `vector` 擴充）。
- 理由：同源反代是讓「部署到任意主機零設定」最省事且最穩的做法；選用功能可關閉，確保沒有 Ollama/embedding 模型的人仍能一行跑起核心。
- 已知取捨：in-process 排程器假設單一 worker（多副本須關閉並改用外部 cron）；同源反代下 dev 直連模式仍靠 CORS 白名單。
- 影響範圍：`scripts/start.sh`、根 `.env.example`、`docker-compose.yml`、`frontend/{Dockerfile,nginx.conf}`、`README.md`。詳見 [deployment.md](./deployment.md)。

## DEC-026：外部模型接入（Codex 訂閱制 / OpenAI API）——執行升級與 eval 考官

- 日期：2026-06-19
- 狀態：Accepted（設計階段，尚未實作）
- 背景：本地 Gemma 4 對部分任務反覆做不出可接受結果時，希望能切換到 GPT-5.5；同時希望 eval harness 的考官可選用更強模型評斷 skill 的正確性與效果。使用者需在 profile 綁定自己的外部模型憑證才可使用。延伸自 DEC-023。
- 決策：
  1. **兩條認證路徑，訂閱制優先、API key 備援**：路徑 A = Codex 訂閱制（優先）；路徑 B = OpenAI API key（穩定備援）。provider 抽象成同一介面；訂閱制不可用時自動退回 API key，功能不中斷。
  2. **訂閱制管道參考 openclaw 的做法**：不自己刻 ChatGPT OAuth，而是**橋接官方 Codex CLI**（`@zed-industries/codex-acp`，讀 `CODEX_HOME/auth.json`；見 external-model-integration.md §2.1）。仍屬非官方整合層，故 API key（路徑 B）為穩定保證。**部署模式已定：(b) 多使用者集中式、各自帳號**——使用者自行 `codex login` 後把 `auth.json` token 交 server 加密存 profile；呼叫時以 per-request 隔離 `CODEX_HOME` + codex-acp、用畢即焚；token refresh 由 server 自理（openclaw 靠常駐 CLI refresh，我們無常駐故自理）。實作前須實機驗證 token 能否跨機使用 + refresh endpoint。
  3. **per-user 憑證、加密 at rest**：新表 `user_external_credentials`，對稱加密（`CREDENTIAL_ENCRYPTION_KEY`）儲存 token/key，API 只回遮罩、永不回明文；**絕不存明文密碼**，OAuth 路徑只存可撤銷 token。
  4. **執行升級延用 DEC-023**：`MAX_LOCAL_ATTEMPTS` 連續本地失敗才升級；隱私閘、權限/沙箱/確認閘、稽核全部沿用；external client 改依使用者 profile 憑證動態建立。
  5. **eval 考官預設 Gemma 4、可切 Codex/GPT**：考官憑證走開發者 env/CLI（非終端使用者）；評斷涵蓋「生成正確性」+「效果符合使用者期待」；考官與被考者分離。
- 理由：尊重「訂閱制優先」的成本考量，同時以 API key 備援與介面抽象確保不被非官方管道綁死；per-user 加密憑證兼顧「自帶額度」與安全；考官用更強模型更接近人類判斷。
- 可行性驗證（2026-06-19；原始碼 + 官方文件，見 external-model-integration.md §9）：Codex 訂閱採 **Agent Identity**，但 **agent 私鑰預設就在 `auth.json` 內**；官方文件明確把 auth.json 當密碼、**允許跨機複製**、未提機器綁定。**判定修正：跨機技術上可行**（先前「技術脆弱不可行」過度悲觀，予以更正）；例外是開啟 `SecretAuthStorage`（私鑰進 keyring）則不可搬。多使用者集中式的**剩餘問題為風險權衡而非技術硬傷**：集中保管多人憑證的安全責任、多人同 server IP 的風控灰區、代呼叫合規。已備一鍵雙機 demo（`experiments/codex-cross-machine-demo/`）供實證；最終由使用者跑 demo 100% 確認。
- 已知取捨：訂閱制管道穩定性不可控（以備援與抽象化緩解）；儲存可解密憑證有風險（以加密 at rest、遮罩、不入 log 緩解）；外部升級涉資料外送（沿用 DEC-023 隱私閘、預設關閉、使用者明確啟用）。
- 影響範圍：新 `user_external_credentials` 表 + profile 端點、`app/assistant/llm/`（router/external 依 per-user 憑證）、`backend/eval/judge.py`（OpenAI/Codex 考官 + provider 選項）、config（`CREDENTIAL_ENCRYPTION_KEY` 等）。詳見 [external-model-integration.md](./external-model-integration.md)。

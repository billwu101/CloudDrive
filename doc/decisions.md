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
- 影響範圍：新增 `app/assistant/` 模組、`anthropic` 依賴、前端 assistant 元件；詳見 assistant-design.md。

## DEC-017：助理一律經 service 層，不直接操作 DB／檔案

- 日期：2026-06-16
- 狀態：Accepted
- 背景：「讓助理直接操作資料庫／檔案」（類比個人電腦直接裝 AI 助理操作本機檔案）會繞過 CloudDrive 的配額、權限、命名衝突、軟刪除、活動紀錄、分享 token 雜湊等業務邏輯。
- 決策：助理的每個工具都呼叫既有 service（DriveService、SearchService、TrashService…），並一律帶入當前 JWT 的 `user_id`；不直接讀寫 Postgres 或 storage 目錄。v1 在 agent loop 內直接定義工具，暫不抽成 MCP server。
- 理由：CloudDrive 的關鍵不變量全在 service 層，直接操作 DB 等於用另一語言重寫並承擔資料失同步風險。經 service 層可完整重用且天然多租戶安全。穩定介面是 service／REST，而非底層資料表。
- 已知取捨：多一層呼叫（可忽略）；工具與 service 介面耦合（同 repo、可控）。未來若要讓同套工具被多個 AI 客戶端共用，再抽成後端內建 MCP server（路線 B）。
- 影響範圍：AssistantService、ToolDispatcher、各既有 service 的注入。

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
- 決策：登入與 refresh API 只在 JSON 回傳 access token；refresh token 透過 cookie 設定。登出撤銷 token 並清除 cookie。
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

## DEC-006：本機容器執行環境

- 日期：2026-06-13
- 狀態：Accepted
- 背景：主機原先沒有 Docker CLI 或 runtime，但完整驗收需要 PostgreSQL 與 Docker Compose。
- 決策：使用 Homebrew 安裝 Docker CLI、Docker Compose 與 Colima，並以 Colima 提供本機 Docker runtime。
- 理由：可在不依賴桌面 GUI 的情況下自動啟動 PostgreSQL 與執行整合測試。
- 影響範圍：Project Setup、Database、Integration Testing、Docker Compose 驗收。

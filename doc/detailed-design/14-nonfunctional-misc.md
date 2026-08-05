## 14. 非功能設計

### 14.1 安全

1. 所有檔案操作都必須由後端檢查權限。
2. 前端隱藏按鈕不代表授權。
3. 密碼使用 Argon2 hash。
4. JWT secret 必須由環境變數提供。
5. refresh token 資料庫只保存 hash。
6. share token 資料庫只保存 hash。
7. LocalStorageProvider 必須防止路徑穿越。
8. 上傳檔案大小限制由環境變數提供。
9. CORS origins 由環境變數提供。

### 14.2 效能

1. 檔案列表分頁。
2. 搜尋使用 pg_trgm。
3. 下載使用 StreamingResponse，避免一次讀入記憶體。
4. 前端搜尋 debounce。
5. 前端列表可在資料量增加時改為虛擬滾動。

### 14.3 可維護性

1. StorageProvider 可替換。
2. PermissionService 集中權限邏輯。
3. QuotaService 集中容量邏輯。
4. Service 層可用 mock repository 單元測試。
5. 前端 API 呼叫集中在 api module。

## 15. 錯誤碼設計

| 錯誤碼 | HTTP 狀態 | 說明 |
| --- | --- | --- |
> **本表為 `app/core/error_codes.py` 的 `ErrorCode` 實際成員**（2026-08-05 校正）。
> 原表列的 `ITEM_NOT_FOUND`／`DUPLICATE_NAME`／`INVALID_ITEM_TYPE`／`INVALID_PARENT`／
> `CANNOT_MOVE_TO_DESCENDANT`／`INVALID_FILE_NAME`／`SHARE_TARGET_NOT_FOUND`／
> `SHARE_LINK_EXPIRED`／`SHARE_LINK_DISABLED`／`INVALID_SHARE_PASSWORD` **在程式中並不存在**，
> 是設計階段的草稿；實作把它們分別收斂成 `NOT_FOUND`、`NAME_CONFLICT`、`INVALID_OPERATION`
> 與 `SHARE_LINK_INVALID`。狀態碼由 `app/core/exceptions.py` 的例外子類別決定。

| Code | HTTP | 情境 | 拋出方式 |
| --- | --- | --- | --- |
| `UNAUTHORIZED` | 401 | 未登入或 token 無效 | `UnauthorizedError` |
| `INVALID_CREDENTIALS` | 401 | 帳號或密碼錯誤 | `AppError(status_code=401)` |
| `REFRESH_TOKEN_REVOKED` | 401 | refresh token 已撤銷或過期 | `AppError(status_code=401)` |
| `SHARE_LINK_INVALID` | 401 | 分享連結 token 不存在／密碼錯誤／停用／過期（**刻意合併，見下**） | `AppError(status_code=401)` |
| `SHARE_LINK_PASSWORD_REQUIRED` | 401 | 有密碼的連結未帶密碼（正常流程的第一次請求） | `AppError(status_code=401)` |
| `FORBIDDEN` | 403 | 權限不足 | `ForbiddenError` |
| `USER_INACTIVE` | 403 | 帳號停用 | `AppError(status_code=403)` |
| `NOT_FOUND` | 404 | item 或資源不存在 | `NotFoundError` |
| `ITEM_CONTENT_NOT_FOUND` | 404 | 檔案本體不存在（中繼資料還在） | `AppError(status_code=404)` |
| `NAME_CONFLICT` | 409 | 同層名稱重複 | `NameConflictError` |
| `EMAIL_ALREADY_EXISTS` | 409 | email 已存在 | `AppError(status_code=409)` |
| `QUOTA_EXCEEDED` | **413** | 容量不足 | `QuotaExceededError` |
| `FILE_TOO_LARGE` | 413 | 單檔超過上限 | `FileTooLargeError` |
| `INVALID_OPERATION` | **400 或 422** | 操作不合法（**兩種狀態碼並存，見下**） | `AppError`（400）／`InvalidOperationError`（422） |
| `ASSISTANT_UNAVAILABLE` | 503 | 助理的模型連線不可用 | `AppError(status_code=503)` |
| `VALIDATION_ERROR` | — | **目前無任何 raise 點**（enum 成員未使用） | — |
| `INTERNAL_ERROR` | — | **目前無任何 raise 點**（enum 成員未使用） | — |

**`QUOTA_EXCEEDED` 為何是 413 而非 409**：與 `FILE_TOO_LARGE` 同碼，讓「送太多位元組上來」的兩種原因共用一個狀態類別。代價是前端無法只看狀態碼分辨兩者，因此 §27.2 第 6 點要求的錯誤分類**以 `code` 優先於狀態碼**（`frontend/src/lib/uploadLimits.ts`）；僅在無可辨識 `code` 時（例如被 nginx 直接擋下）才以 413 判為檔案過大。

**`SHARE_LINK_INVALID` 為何不分 expired／disabled／wrong-password**：§28.3 第 1 點要求驗證失敗不可區分，否則回應差異本身就能用來確認某個 token 曾經存在。原表的 410／403 分流會洩漏這件事，故合併為單一碼與單一狀態碼。

**`INVALID_OPERATION` 的 400／422 並存**：以 `AppError(ErrorCode.INVALID_OPERATION, ...)` 直接拋出者取 `AppError` 預設的 400（58 處，含上傳檔名驗證與助理技能路徑）；以 `InvalidOperationError` 拋出者為 422（5 處，含 §6.10 分片上傳的缺片與終態情境）。同一個 `code` 對外呈現兩種狀態碼是**實作不一致，待決定統一方向**——前端目前依 `code` 分支，故此不一致尚未造成可見錯誤。

## 16. 模組獨立測試策略

### 16.1 後端單元測試

每個 service 使用 mock repository、mock storage 測試，不依賴真實 PostgreSQL 或檔案系統。

| 模組 | 測試方式 |
| --- | --- |
| AuthService | mock UserRepository、RefreshTokenRepository |
| DriveService | mock DriveItemRepository、PermissionService |
| UploadService | mock StorageProvider、QuotaService、DriveItemRepository |
| DownloadService | mock StorageProvider、PermissionService |
| TrashService | mock DriveItemRepository、StorageProvider、QuotaService |
| ShareService | mock ShareRepository、UserRepository、PermissionService |
| SearchService | mock SearchRepository |
| FileVersionService | mock FileVersionRepository、PermissionService |

### 16.2 後端整合測試

使用測試 PostgreSQL 或 testcontainers。LocalStorageProvider 使用 temporary directory。

整合測試重點：

1. migration 可成功執行。
2. 註冊登入流程。
3. 上傳檔案後資料庫與本機檔案一致。
4. 下載回來內容與上傳內容一致。
5. 分享權限生效。
6. 垃圾桶永久刪除會清理檔案。

### 16.3 前端單元測試

使用 Vitest + React Testing Library。

1. 表單驗證。
2. Zustand store 行為。
3. 元件 loading、empty、error 狀態。
4. context menu 顯示邏輯。
5. dialog 開關。

### 16.4 前端整合測試

使用 MSW mock API。

1. DrivePage 載入檔案列表。
2. 建立資料夾後列表刷新。
3. 上傳成功後列表刷新。
4. 分享彈窗送出成功。
5. 垃圾桶還原成功。

### 16.5 E2E 測試

使用 Playwright。

1. 使用者註冊與登入。
2. 建立資料夾。
3. 上傳檔案。
4. 預覽檔案。
5. 下載檔案。
6. 分享給另一位使用者。
7. 另一位使用者在「與我分享」看到檔案。
8. 刪除並還原檔案。

## 17. 開發順序建議

1. 建立後端專案與 core config。
2. 建立 PostgreSQL migration：users、refresh_tokens、drive_items、file_versions。
3. 實作 AuthService 與 auth API。
4. 實作 DriveService：列表、建立資料夾、重新命名、移動。
5. 實作 StorageProvider 與 LocalStorageProvider。
6. 實作 UploadService 一般上傳。
7. 實作 DownloadService StreamingResponse。
8. 實作 TrashService。
9. 實作 SearchService。
10. 實作 ShareService 指定使用者分享。
11. 實作 PreviewService 基本預覽。
12. 建立 React app shell、登入、我的硬碟頁。
13. 建立 upload queue、preview dialog、share dialog。
14. 補齊後端單元測試與整合測試。
15. 補齊前端元件測試與 E2E 測試。

## 18. 驗收對應

| 需求 | 主要模組 |
| --- | --- |
| 註冊、登入、登出 | Auth |
| JWT 與 refresh token | Core Security、Auth |
| 檔案上傳 | Upload、Storage、Quota、Version |
| 檔案下載 | Download、Storage、Permission |
| 建立資料夾 | Drive |
| 檔案與資料夾列表 | Drive |
| 重新命名 | Drive |
| 移動 | Drive |
| 垃圾桶 | Trash |
| 搜尋 | Search |
| 星號 | Drive |
| 最近檔案 | Drive、ActivityLog |
| 基本預覽 | Preview |
| 私人檔案權限檢查 | Permission |
| 容量統計 | Quota |
| 指定使用者分享 | Share、Permission |
| 公開分享連結 | ShareLink |
| 檔案版本 | FileVersion |

## 19. 第三階段擴充點

第三階段不納入主詳細設計，但保留以下擴充方向：

| 功能 | 擴充方式 |
| --- | --- |
| 管理員後台 | 使用 `users.is_admin`，另開 admin routers/pages |
| OAuth 登入 | AuthService 增加 OAuth provider，users 增加 provider identity 表 |
| WebSocket 通知 | 增加 NotificationService 與 websocket router |
| 搜尋升級 | 在現有全文（PostgreSQL `tsvector`／`ILIKE`）＋語意（pgvector）之上，未來可換 OpenSearch／專用向量庫以提升規模與相關性 |
| 防毒掃描 | UploadService 上傳後送 background task |
| 檔案加密 | StorageProvider 寫入前加密、讀取後解密 |
| 團隊空間 | 增加 workspaces、workspace_members、workspace_drive_items |
| 桌面同步 | 另開 sync API 與 client，不影響現有 DriveService |

## 20. 未固定參數

以下值在需求文件中未明確指定，因此本設計不硬編，由環境變數或後續需求決定：

1. access token 有效分鐘數。
2. refresh token 有效天數。
3. 單一檔案大小上限。
4. 使用者預設容量。
5. 垃圾桶自動清除天數。
6. CORS allowed origins。
7. 本機儲存根目錄。
8. 是否啟用公開分享連結密碼。
9. 是否啟用公開分享連結到期時間。

## 22. 結論


本詳細設計將系統拆分為 Auth、User/Quota、DriveItem、Permission、Storage、Upload、Download、Preview、Trash、Search、Share、FileVersion、ActivityLog 與前端對應模組。模組之間透過明確接口互動，避免彼此直接耦合。

MVP 可以先完成一般檔案上傳、下載、資料夾管理、垃圾桶、搜尋、星號與基本預覽。第二階段再補強指定使用者分享、公開連結、版本紀錄顯示、圖片縮圖與 PDF 預覽。第三階段功能只保留擴充點，不放入主開發範圍。

---

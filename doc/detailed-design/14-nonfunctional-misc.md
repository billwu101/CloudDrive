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
| `UNAUTHORIZED` | 401 | 未登入或 token 無效 |
| `FORBIDDEN` | 403 | 權限不足 |
| `EMAIL_ALREADY_EXISTS` | 409 | email 已存在 |
| `INVALID_CREDENTIALS` | 401 | 帳號或密碼錯誤 |
| `USER_INACTIVE` | 403 | 使用者停用 |
| `ITEM_NOT_FOUND` | 404 | item 不存在 |
| `ITEM_CONTENT_NOT_FOUND` | 404 | 檔案本體不存在 |
| `DUPLICATE_NAME` | 409 | 同層名稱重複 |
| `INVALID_ITEM_TYPE` | 400 | item type 不符合操作 |
| `INVALID_PARENT` | 400 | parent 不存在或不是 folder |
| `CANNOT_MOVE_TO_DESCENDANT` | 400 | 不可移動到自己的子孫資料夾 |
| `QUOTA_EXCEEDED` | 409 | 容量不足 |
| `FILE_TOO_LARGE` | 413 | 檔案過大 |
| `INVALID_FILE_NAME` | 400 | 檔名不合法 |
| `SHARE_TARGET_NOT_FOUND` | 404 | 分享對象不存在 |
| `SHARE_LINK_EXPIRED` | 410 | 分享連結過期 |
| `SHARE_LINK_DISABLED` | 410 | 分享連結停用 |
| `INVALID_SHARE_PASSWORD` | 403 | 分享密碼錯誤 |

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

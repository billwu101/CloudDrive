# 雲端硬碟系統開發文件

## 1. 文件目的

本文件描述一個參考 Google Drive 與 OneDrive 的雲端硬碟系統開發方案。系統前端使用 React，後端使用 FastAPI，資料庫使用 PostgreSQL。文件內容涵蓋需求範圍、系統架構、資料庫設計、API 規格、前端頁面規劃、權限模型、安全性、部署方式與開發里程碑。

本文件可作為後續開發、分工、估時與驗收的基準。

## 2. 初版假設

以下是假設條件，若專案需求不同，後續可再調整：

1. 系統是一個多人使用的雲端硬碟，不是單機檔案管理器。
2. 使用者需要登入後才能管理自己的檔案。
3. PostgreSQL 只儲存使用者、檔案中繼資料、權限、分享紀錄、版本紀錄等資料，不直接儲存大型檔案二進位內容。
4. 檔案本體建議儲存在本機檔案系統、MinIO、AWS S3、Azure Blob Storage 或其他物件儲存服務中。
5. 初版可先使用本機儲存或 MinIO，之後再替換成正式雲端物件儲存。
6. 系統優先支援網頁版，不包含桌面同步程式與手機 App。
7. 初版使用帳號密碼登入，之後可擴充 Google、Microsoft OAuth 登入。
8. 初版支援檔案上傳、下載、預覽、資料夾、搜尋、分享連結、垃圾桶、星號標記與近期檔案。

## 3. 待確認問題

在正式開發前，建議先確認下列問題：

1. 使用者來源是否只有本系統帳號，或需要支援 Google、Microsoft、學校 SSO？
2. 檔案儲存位置要使用本機硬碟、MinIO、AWS S3、Azure Blob Storage，還是其他服務？
3. 是否需要多人協作編輯文件，或只需要檔案分享與下載？
4. 是否需要即時通知，例如他人分享檔案給我時跳出通知？
5. 是否需要管理員後台，用於查看使用者、容量、檔案統計與系統紀錄？
6. 單一檔案大小上限是多少？
7. 每位使用者容量上限是多少？
8. 是否需要防毒掃描、敏感檔案封鎖或內容審核？
9. 是否需要支援公開分享連結的密碼與到期時間？
10. 是否需要保留檔案版本紀錄？若需要，最多保留幾版？

## 4. 專案目標

### 4.1 核心目標

建立一個可上傳、分類、搜尋、分享與下載檔案的雲端硬碟系統。使用者可以像使用 Google Drive 或 OneDrive 一樣，透過資料夾階層管理自己的檔案，並能將檔案或資料夾分享給其他使用者或產生公開連結。

### 4.2 使用者目標

使用者可以：

1. 註冊與登入帳號。
2. 上傳檔案。
3. 建立、重新命名、移動、複製、刪除資料夾與檔案。
4. 透過列表或格狀檢視瀏覽檔案。
5. 透過關鍵字搜尋檔名與檔案資訊。
6. 預覽圖片、PDF、文字檔與常見文件格式。
7. 將檔案標記星號。
8. 查看最近開啟或最近修改的檔案。
9. 把檔案移到垃圾桶，並可還原或永久刪除。
10. 分享檔案或資料夾給指定使用者。
11. 建立公開分享連結。
12. 查看自己的容量使用狀況。

### 4.3 系統目標

系統需要：

1. 保護使用者檔案與權限。
2. 支援大型檔案上傳。
3. 支援可中斷續傳的上傳流程。
4. 維護檔案版本與操作紀錄。
5. 保持清楚的前後端分層。
6. 提供可擴充的儲存層抽象，讓本機儲存能在未來替換成物件儲存。
7. 具備可部署到 Docker 環境的架構。

## 5. 功能範圍

### 5.1 MVP 必做功能

MVP 指第一版可展示與可使用的核心版本。

1. 使用者註冊、登入、登出。
2. JWT 存取權杖與刷新權杖。
3. 檔案上傳。
4. 檔案下載。
5. 建立資料夾。
6. 檔案與資料夾列表。
7. 檔案與資料夾重新命名。
8. 檔案與資料夾移動。
9. 檔案與資料夾刪除到垃圾桶。
10. 垃圾桶還原與永久刪除。
11. 檔案搜尋。
12. 檔案星號標記。
13. 最近檔案列表。
14. 檔案基本預覽。
15. 私人檔案權限檢查。
16. 容量統計。
17. 帳號設定：修改顯示名稱、登入 Email 與密碼。

### 5.2 第二階段功能

1. 分享給指定使用者。
2. 分享權限分級：可檢視、可下載、可編輯。
3. 公開分享連結。
4. 分享連結密碼。
5. 分享連結到期時間。
6. 檔案版本紀錄。
7. 上傳進度列表。
8. 大檔案分片上傳。
9. 上傳失敗後續傳。
10. 圖片縮圖。
11. PDF 預覽。
12. 操作紀錄。

### 5.3 第三階段功能

1. 管理員後台。
2. 使用者容量配額管理。
3. 團隊空間。
4. 共同資料夾。
5. 檔案留言。
6. 檔案標籤。
7. 全文檢索。
8. 防毒掃描。
9. 檔案加密。
10. OAuth 登入。
11. WebSocket 即時通知。
12. 桌面或手機同步客戶端。

### 5.4 暫不包含功能

初版不包含：

1. 線上 Office 文件共同編輯。
2. 桌面同步程式。
3. 手機 App。
4. 複雜企業組織權限。
5. 端對端加密。

### 5.5 擴充功能：In-App AI Assistant

核心 28 模組之後新增的對話式 AI 助理（自然語言操作檔案、計畫確認、現場生成技能、技能管理、工作流程重用）。完整規格見 **§33**。

## 6. 使用者角色

### 6.1 一般使用者

一般使用者可以管理自己的檔案與資料夾，並使用分享功能。

### 6.2 管理員

管理員可以查看系統統計、使用者列表、容量使用狀況與違規檔案處理紀錄。管理員功能可放在第二或第三階段開發。

## 7. 使用情境

### 7.1 上傳檔案

1. 使用者進入「我的硬碟」。
2. 使用者點擊上傳按鈕或拖曳檔案到頁面。
3. 前端顯示上傳進度。
4. 後端驗證使用者權限與容量限制。
5. 後端將檔案寫入儲存服務。
6. 後端將檔案中繼資料寫入 PostgreSQL。
7. 前端更新檔案列表。

### 7.2 建立資料夾

1. 使用者點擊新增資料夾。
2. 輸入資料夾名稱。
3. 後端檢查同層是否有重名項目。
4. 建立資料夾紀錄。
5. 前端刷新列表。

### 7.3 分享檔案

1. 使用者選取檔案。
2. 點擊分享。
3. 選擇分享給指定使用者或建立公開連結。
4. 設定權限。
5. 後端建立權限或分享連結紀錄。
6. 收到分享的使用者可以在「與我分享」頁面看到檔案。

### 7.4 框選檔案與資料夾

1. 使用者在「我的硬碟」檔案區空白處按住滑鼠左鍵。
2. 使用者拖曳出選取矩形，所有與矩形相交的檔案與資料夾即時進入選取狀態。
3. 框選只需要按住滑鼠左鍵拖曳，不需要搭配鍵盤按鍵；新的框選範圍會取代既有選取。
4. 在空白處單擊可清除目前選取，從檔案卡片或按鈕開始拖曳不會誤觸框選。

### 7.5 刪除與還原

1. 使用者刪除檔案或資料夾。
2. 系統不立即永久刪除，而是標記為已刪除並移入垃圾桶。
3. 使用者可從垃圾桶還原。
4. 使用者可永久刪除。
5. 系統可定期清除超過保留期限的垃圾桶項目。

### 7.6 管理帳號設定

1. 使用者從個人選單進入帳號設定頁。
2. 使用者可修改顯示名稱與登入 Email。
3. Email 必須是有效格式且不可與其他帳號重複。
4. 使用者輸入目前密碼後，可設定至少 8 個字元的新密碼。
5. 更新成功後，頁面與個人選單立即顯示最新資料。

## 8. 系統架構

### 8.1 架構總覽

系統採用前後端分離架構：

```text
React Frontend
  |
  | HTTPS REST API
  v
FastAPI Backend
  |
  | SQLAlchemy / asyncpg
  v
PostgreSQL

FastAPI Backend
  |
  | Storage Adapter
  v
Local Storage / MinIO / S3 / Azure Blob
```

### 8.2 前端技術

建議使用：

1. React
2. TypeScript
3. Vite
4. React Router
5. TanStack Query
6. Zustand 或 Redux Toolkit
7. React Hook Form
8. Zod
9. Axios 或 Fetch API wrapper
10. Tailwind CSS 或 Material UI

若要更接近 Google Drive 與 OneDrive，可使用 Material UI 或 shadcn/ui 來快速建立一致的操作介面。

### 8.3 後端技術

建議使用：

1. FastAPI
2. Python 3.12 以上
3. SQLAlchemy 2.x
4. Alembic
5. Pydantic
6. asyncpg
7. python-jose 或 PyJWT
8. passlib 或 pwdlib
9. Uvicorn
10. Celery 或 RQ
11. Redis

### 8.4 資料庫

使用 PostgreSQL 儲存：

1. 使用者帳號。
2. 檔案與資料夾中繼資料。
3. 權限設定。
4. 分享連結。
5. 檔案版本。
6. 上傳工作狀態。
7. 操作紀錄。
8. 容量統計。

### 8.5 儲存層

檔案本體不建議直接存在 PostgreSQL。建議抽象成 Storage Provider：

```text
StorageProvider
  - save(file_stream, storage_key)
  - read(storage_key)
  - delete(storage_key)
  - exists(storage_key)
  - generate_download_url(storage_key)
```

可實作：

1. LocalStorageProvider
2. MinIOStorageProvider
3. S3StorageProvider
4. AzureBlobStorageProvider

## 9. 後端目錄建議

```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      dependencies.py
      exceptions.py
    db/
      session.py
      base.py
      migrations/
    models/
      user.py
      drive_item.py
      file_version.py
      share.py
      upload_session.py
      activity_log.py
    schemas/
      auth.py
      user.py
      drive_item.py
      share.py
      upload.py
    routers/
      auth.py
      users.py
      drive.py
      upload.py
      share.py
      search.py
      trash.py
    services/
      auth_service.py
      drive_service.py
      storage_service.py
      share_service.py
      search_service.py
      quota_service.py
    repositories/
      user_repository.py
      drive_repository.py
      share_repository.py
    storage/
      base.py
      local.py
      minio.py
      s3.py
    tasks/
      thumbnails.py
      cleanup.py
      virus_scan.py
    tests/
  alembic.ini
  pyproject.toml
  Dockerfile
```

## 10. 前端目錄建議

```text
frontend/
  src/
    app/
      router.tsx
      providers.tsx
    api/
      client.ts
      authApi.ts
      driveApi.ts
      shareApi.ts
      uploadApi.ts
    components/
      layout/
      drive/
      upload/
      preview/
      share/
      common/
    pages/
      LoginPage.tsx
      RegisterPage.tsx
      DrivePage.tsx
      SharedWithMePage.tsx
      RecentPage.tsx
      StarredPage.tsx
      TrashPage.tsx
      SettingsPage.tsx
    hooks/
      useAuth.ts
      useDriveItems.ts
      useUploadQueue.ts
    stores/
      authStore.ts
      uploadStore.ts
      uiStore.ts
    types/
      auth.ts
      drive.ts
      share.ts
    utils/
      fileIcons.ts
      formatBytes.ts
      mime.ts
    styles/
      globals.css
  package.json
  vite.config.ts
  Dockerfile
```

## 11. 資料庫設計

### 11.1 users

儲存使用者資料。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| email | varchar | 登入信箱，唯一 |
| username | varchar | 顯示名稱 |
| password_hash | varchar | 密碼雜湊 |
| avatar_url | text | 頭像網址 |
| quota_bytes | bigint | 使用者容量上限 |
| used_bytes | bigint | 已使用容量 |
| is_active | boolean | 是否啟用 |
| is_admin | boolean | 是否為管理員 |
| created_at | timestamptz | 建立時間 |
| updated_at | timestamptz | 更新時間 |

### 11.2 drive_items

統一儲存檔案與資料夾。使用 item_type 區分 file 與 folder。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| owner_id | uuid | 擁有者 |
| parent_id | uuid | 上層資料夾，根目錄為 null |
| item_type | varchar | file 或 folder |
| name | varchar | 檔案或資料夾名稱 |
| mime_type | varchar | MIME type，資料夾可為 null |
| extension | varchar | 副檔名 |
| size_bytes | bigint | 檔案大小 |
| storage_key | text | 儲存服務中的檔案 key |
| checksum_sha256 | varchar | 檔案 checksum |
| is_starred | boolean | 是否加星號 |
| is_deleted | boolean | 是否在垃圾桶 |
| deleted_at | timestamptz | 刪除時間 |
| created_by | uuid | 建立者 |
| updated_by | uuid | 最後修改者 |
| created_at | timestamptz | 建立時間 |
| updated_at | timestamptz | 更新時間 |

建議索引：

```sql
CREATE INDEX idx_drive_items_owner_parent ON drive_items(owner_id, parent_id);
CREATE INDEX idx_drive_items_owner_deleted ON drive_items(owner_id, is_deleted);
CREATE INDEX idx_drive_items_name_trgm ON drive_items USING gin (name gin_trgm_ops);
CREATE UNIQUE INDEX uq_drive_items_same_folder_name
ON drive_items(owner_id, parent_id, lower(name))
WHERE is_deleted = false;
```

若要支援更高效的資料夾樹查詢，可考慮 PostgreSQL ltree 或 closure table。

### 11.3 file_versions

儲存檔案版本。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| file_id | uuid | 對應 drive_items.id |
| version_no | integer | 版本號 |
| storage_key | text | 版本檔案儲存 key |
| size_bytes | bigint | 檔案大小 |
| checksum_sha256 | varchar | checksum |
| created_by | uuid | 建立者 |
| created_at | timestamptz | 建立時間 |

### 11.4 shares

儲存指定使用者分享權限。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| item_id | uuid | 被分享的檔案或資料夾 |
| owner_id | uuid | 分享者 |
| target_user_id | uuid | 被分享者 |
| permission | varchar | viewer、downloader、editor |
| created_at | timestamptz | 建立時間 |
| updated_at | timestamptz | 更新時間 |

### 11.5 share_links

儲存公開分享連結。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| item_id | uuid | 被分享項目 |
| token_hash | varchar | 分享 token 雜湊 |
| permission | varchar | viewer、downloader |
| password_hash | varchar | 分享密碼雜湊，可為 null |
| expires_at | timestamptz | 到期時間，可為 null |
| is_active | boolean | 是否啟用 |
| created_by | uuid | 建立者 |
| created_at | timestamptz | 建立時間 |

注意：資料庫不要直接存明文分享 token。建立分享連結時回傳明文 token 給前端，資料庫只保存 hash。

### 11.6 upload_sessions

支援大型檔案分片上傳。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| user_id | uuid | 上傳者 |
| parent_id | uuid | 目標資料夾 |
| file_name | varchar | 檔名 |
| mime_type | varchar | MIME type |
| total_size_bytes | bigint | 檔案總大小 |
| chunk_size_bytes | integer | 每片大小 |
| total_chunks | integer | 總分片數 |
| uploaded_chunks | integer | 已上傳分片數 |
| status | varchar | pending、uploading、completed、failed、cancelled |
| final_item_id | uuid | 完成後建立的 drive_item |
| created_at | timestamptz | 建立時間 |
| updated_at | timestamptz | 更新時間 |

### 11.7 upload_chunks

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| upload_session_id | uuid | 對應 upload_sessions |
| chunk_index | integer | 分片編號 |
| storage_key | text | 暫存位置 |
| size_bytes | integer | 分片大小 |
| checksum_sha256 | varchar | 分片 checksum |
| created_at | timestamptz | 建立時間 |

### 11.8 activity_logs

記錄使用者操作。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| actor_id | uuid | 操作者 |
| item_id | uuid | 操作對象 |
| action | varchar | upload、download、rename、move、delete、restore、share |
| metadata | jsonb | 附加資訊 |
| ip_address | inet | IP |
| user_agent | text | 瀏覽器資訊 |
| created_at | timestamptz | 建立時間 |

## 12. 權限模型

### 12.1 權限類型

| 權限 | 說明 |
| --- | --- |
| owner | 擁有者，可執行所有操作 |
| editor | 可重新命名、移動、上傳新版本 |
| viewer | 可檢視與預覽 |
| downloader | 可檢視與下載 |

### 12.2 權限判斷順序

1. 若 user_id 等於 item.owner_id，擁有 owner 權限。
2. 若 item 透過 shares 分享給該使用者，依 shares.permission 判斷。
3. 若透過 share_links 存取，依 link.permission 判斷。
4. 若資料夾被分享，子項目應繼承資料夾權限。
5. 若以上皆不符合，拒絕存取。

### 12.3 權限注意事項

1. 後端每個檔案操作都必須檢查權限。
2. 前端隱藏按鈕只是使用者體驗，不能取代後端權限檢查。
3. 分享連結 token 不應直接儲存明文。
4. 資料夾權限繼承要避免查詢過慢，必要時可以建立 permission cache。

## 13. API 設計

API base path 建議為：

```text
/api/v1
```

### 13.1 Auth API

#### POST /auth/register

註冊使用者。

Request:

```json
{
  "email": "user@example.com",
  "username": "User",
  "password": "password"
}
```

Response:

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "User"
}
```

#### POST /auth/login

登入。

Request:

```json
{
  "email": "user@example.com",
  "password": "password"
}
```

Response:

```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer"
}
```

#### POST /auth/refresh

刷新 access token。

#### POST /auth/logout

登出並使 refresh token 失效。

#### GET /auth/me

取得目前登入使用者。

### 13.2 Drive API

#### GET /drive/items

取得指定資料夾底下的檔案與資料夾。

Query:

| 參數 | 說明 |
| --- | --- |
| parent_id | 上層資料夾 id，根目錄可省略 |
| sort | name、updated_at、size |
| order | asc、desc |
| page | 頁碼 |
| page_size | 每頁筆數 |

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "report.pdf",
      "item_type": "file",
      "mime_type": "application/pdf",
      "size_bytes": 102400,
      "is_starred": false,
      "updated_at": "2026-06-11T14:00:00Z"
    }
  ],
  "total": 1
}
```

#### POST /drive/folders

建立資料夾。

Request:

```json
{
  "parent_id": "uuid-or-null",
  "name": "New Folder"
}
```

#### PATCH /drive/items/{item_id}/rename

重新命名。

Request:

```json
{
  "name": "new-name.pdf"
}
```

#### PATCH /drive/items/{item_id}/move

移動檔案或資料夾。

Request:

```json
{
  "target_parent_id": "uuid-or-null"
}
```

#### PATCH /drive/items/{item_id}/star

設定星號。

Request:

```json
{
  "is_starred": true
}
```

#### GET /drive/items/{item_id}/download

下載檔案。可直接串流回應，或回傳短效下載 URL。

#### GET /drive/items/{item_id}/preview

取得預覽資訊。

Response:

```json
{
  "preview_type": "pdf",
  "url": "https://example.com/preview/temporary-url",
  "expires_in": 300
}
```

### 13.3 Upload API

#### POST /upload/simple

小檔案直接上傳。適用於初版或小於指定大小的檔案。

Form data:

| 欄位 | 說明 |
| --- | --- |
| parent_id | 上層資料夾 |
| file | 檔案 |

#### POST /upload/sessions

建立分片上傳工作。

Request:

```json
{
  "parent_id": "uuid-or-null",
  "file_name": "video.mp4",
  "mime_type": "video/mp4",
  "total_size_bytes": 104857600,
  "chunk_size_bytes": 5242880
}
```

#### PUT /upload/sessions/{session_id}/chunks/{chunk_index}

上傳單一分片。

#### POST /upload/sessions/{session_id}/complete

合併分片並建立檔案紀錄。

#### DELETE /upload/sessions/{session_id}

取消上傳。

### 13.4 Search API

#### GET /search

搜尋檔案。

Query:

| 參數 | 說明 |
| --- | --- |
| q | 關鍵字 |
| type | file、folder、all |
| mime_type | MIME type |
| page | 頁碼 |
| page_size | 每頁筆數 |

### 13.5 Trash API

#### GET /trash

取得垃圾桶項目。

#### PATCH /trash/{item_id}/restore

還原項目。

#### DELETE /trash/{item_id}

永久刪除項目。

#### DELETE /trash

清空垃圾桶。

### 13.6 Share API

#### POST /share/items/{item_id}/users

分享給指定使用者。

Request:

```json
{
  "target_email": "friend@example.com",
  "permission": "viewer"
}
```

#### GET /share/shared-with-me

取得與我分享的檔案。

#### POST /share/items/{item_id}/links

建立公開分享連結。

Request:

```json
{
  "permission": "viewer",
  "password": "optional-password",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

Response:

```json
{
  "url": "https://drive.example.com/s/share-token"
}
```

#### DELETE /share/links/{link_id}

停用分享連結。

## 14. 前端頁面規劃

### 14.1 登入頁

功能：

1. Email 輸入。
2. 密碼輸入。
3. 登入按鈕。
4. 註冊入口。
5. 錯誤訊息顯示。

### 14.2 註冊頁

功能：

1. 使用者名稱輸入。
2. Email 輸入。
3. 密碼輸入。
4. 確認密碼。
5. 表單驗證。

### 14.3 主版面

主版面類似 Google Drive 與 OneDrive：

1. 左側導覽列。
2. 上方搜尋列。
3. 右上角使用者選單。
4. 中央檔案區。
5. 右側詳細資訊面板，可選擇是否開啟。

左側導覽列包含：

1. 我的硬碟。
2. 與我分享。
3. 最近。
4. 星號。
5. 垃圾桶。
6. 儲存空間。

### 14.4 我的硬碟頁

功能：

1. 麵包屑導航。
2. 新增按鈕。
3. 上傳檔案。
4. 上傳資料夾。
5. 建立資料夾。
6. 列表檢視。
7. 格狀檢視。
8. 排序。
9. 多選。
10. 右鍵選單。
11. 拖曳檔案上傳。

### 14.5 檔案項目元件

每個檔案或資料夾顯示：

1. 圖示或縮圖。
2. 名稱。
3. 擁有者。
4. 最近修改時間。
5. 檔案大小。
6. 星號狀態。
7. 更多操作按鈕。

### 14.6 檔案操作選單

操作包含：

1. 開啟。
2. 預覽。
3. 下載。
4. 重新命名。
5. 移動。
6. 複製。
7. 加入星號。
8. 分享。
9. 查看詳細資訊。
10. 移至垃圾桶。

### 14.7 上傳佇列

上傳佇列顯示：

1. 檔名。
2. 進度條。
3. 上傳速度。
4. 剩餘時間。
5. 暫停。
6. 繼續。
7. 取消。
8. 失敗重試。

### 14.8 預覽視窗

支援：

1. 圖片預覽。
2. PDF 預覽。
3. 文字檔預覽。
4. 影片播放。
5. 音訊播放。

不支援預覽時，顯示下載按鈕。

### 14.9 分享彈窗

功能：

1. 搜尋使用者 email。
2. 設定權限。
3. 建立分享連結。
4. 設定連結到期時間。
5. 設定連結密碼。
6. 複製連結。
7. 移除分享對象。

## 15. 前端狀態管理

建議狀態分工：

1. Auth state：登入狀態、token、目前使用者。
2. Drive query state：目前資料夾、排序、分頁、搜尋條件。
3. Upload state：上傳佇列與進度。
4. UI state：側邊欄、預覽窗、分享彈窗、右鍵選單。

建議：

1. 伺服器資料使用 TanStack Query。
2. UI 狀態使用 Zustand。
3. 表單使用 React Hook Form。
4. schema 驗證使用 Zod。

## 16. 關鍵流程設計

### 16.1 小檔案上傳流程

```text
User selects file
  -> Frontend sends multipart/form-data
  -> Backend checks auth
  -> Backend checks quota
  -> Backend saves file to storage
  -> Backend creates drive_items row
  -> Backend updates used_bytes
  -> Frontend refreshes file list
```

### 16.2 分片上傳流程

```text
User selects large file
  -> Frontend creates upload session
  -> Frontend splits file into chunks
  -> Frontend uploads chunks concurrently
  -> Backend records uploaded chunks
  -> Frontend calls complete
  -> Backend merges chunks or completes multipart upload
  -> Backend creates drive_items row
  -> Backend updates used_bytes
```

### 16.3 下載流程

```text
User clicks download
  -> Backend checks permission
  -> Backend logs download activity
  -> Backend streams file or returns temporary signed URL
  -> Browser downloads file
```

### 16.4 搜尋流程

```text
User enters keyword
  -> Frontend debounces input
  -> Frontend calls /search
  -> Backend filters accessible files
  -> PostgreSQL searches names and metadata
  -> Backend returns paginated result
```

### 16.5 垃圾桶流程

```text
Delete item
  -> Mark is_deleted = true
  -> Set deleted_at
  -> Hide from normal file list
  -> Show in trash

Restore item
  -> Check parent still exists
  -> Resolve naming conflict if needed
  -> Mark is_deleted = false

Permanent delete
  -> Delete file from storage
  -> Delete metadata or mark as purged
  -> Update quota
```

## 17. 檔案命名與衝突處理

同一資料夾下不允許出現相同名稱的未刪除項目。

當使用者上傳同名檔案時，可提供三種策略：

1. 取代原檔案並建立新版本。
2. 保留兩者，新檔案自動命名為 `filename (1).ext`。
3. 由使用者在前端選擇。

MVP 建議先採用第 2 種，第二階段再加入版本管理。

## 18. 安全性需求

### 18.1 身分驗證

1. 使用 access token 與 refresh token。
2. access token 有效時間建議 15 到 30 分鐘。
3. refresh token 有效時間建議 7 到 30 天。
4. refresh token 需可撤銷。
5. 密碼使用 bcrypt 或 argon2 雜湊。

### 18.2 權限安全

1. 所有檔案操作必須在後端檢查權限。
2. 使用者不得透過猜測 UUID 存取他人檔案。
3. 分享連結 token 需足夠長且不可預測。
4. 分享連結可設定失效。

### 18.3 上傳安全

1. 限制單檔大小。
2. 限制使用者總容量。
3. 檢查 MIME type。
4. 檢查副檔名。
5. 避免使用原始檔名作為 storage_key。
6. 對可疑檔案執行防毒掃描。
7. 禁止路徑穿越，例如 `../../secret.txt`。

### 18.4 API 安全

1. 啟用 CORS 白名單。
2. 限制登入嘗試頻率。
3. 對上傳 API 加上 rate limit。
4. 使用 HTTPS。
5. 避免在錯誤訊息洩漏內部路徑。
6. API response 不回傳 password_hash、token_hash 等敏感欄位。

## 19. 效能需求

### 19.1 前端效能

1. 檔案列表使用分頁或虛擬滾動。
2. 搜尋輸入使用 debounce。
3. 大量檔案上傳時避免造成 UI 卡頓。
4. 縮圖使用 lazy loading。
5. 預覽視窗按需載入。

### 19.2 後端效能

1. 檔案下載使用 streaming response 或 signed URL。
2. 大檔案使用分片上傳。
3. 搜尋欄位建立索引。
4. 熱門查詢可使用 Redis cache。
5. 縮圖產生放入背景任務。

### 19.3 資料庫效能

1. drive_items 依 owner_id、parent_id 建索引。
2. 搜尋名稱使用 pg_trgm。
3. activity_logs 可依時間分區。
4. 大型 JSON metadata 避免過度查詢。
5. 列表查詢只取必要欄位。

## 20. 錯誤處理

建議定義標準錯誤格式：

```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Storage quota exceeded",
    "details": {}
  }
}
```

常見錯誤碼：

| code | 說明 |
| --- | --- |
| UNAUTHORIZED | 未登入 |
| FORBIDDEN | 權限不足 |
| ITEM_NOT_FOUND | 檔案或資料夾不存在 |
| DUPLICATE_NAME | 同層已有相同名稱 |
| QUOTA_EXCEEDED | 容量不足 |
| FILE_TOO_LARGE | 檔案超過限制 |
| INVALID_FILE_TYPE | 不允許的檔案類型 |
| UPLOAD_SESSION_NOT_FOUND | 上傳工作不存在 |
| SHARE_LINK_EXPIRED | 分享連結已過期 |

## 21. 背景任務

可透過 Celery 或 RQ 處理：

1. 產生圖片縮圖。
2. 產生 PDF 預覽。
3. 清理失敗或過期的上傳分片。
4. 清理垃圾桶過期項目。
5. 統計使用者容量。
6. 防毒掃描。
7. 寄送分享通知 email。

## 22. Docker 開發環境

建議使用 docker-compose 管理本機開發環境。

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://drive:drive@postgres:5432/drive
      REDIS_URL: redis://redis:6379/0
      STORAGE_DRIVER: local
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: drive
      POSTGRES_PASSWORD: drive
      POSTGRES_DB: drive
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

正式環境不建議使用 compose 裡的簡易密碼，應改用環境變數或 secret manager。

## 23. 環境變數

後端建議環境變數：

| 名稱 | 說明 |
| --- | --- |
| APP_ENV | development、staging、production |
| DATABASE_URL | PostgreSQL 連線字串 |
| REDIS_URL | Redis 連線字串 |
| JWT_SECRET_KEY | JWT 簽章密鑰 |
| JWT_ALGORITHM | JWT 演算法 |
| ACCESS_TOKEN_EXPIRE_MINUTES | access token 有效時間 |
| REFRESH_TOKEN_EXPIRE_DAYS | refresh token 有效天數 |
| STORAGE_DRIVER | local、minio、s3、azure |
| LOCAL_STORAGE_PATH | 本機檔案儲存路徑 |
| MAX_UPLOAD_SIZE_BYTES | 單檔上限 |
| DEFAULT_USER_QUOTA_BYTES | 預設使用者容量 |
| CORS_ORIGINS | 前端允許來源 |

前端建議環境變數：

| 名稱 | 說明 |
| --- | --- |
| VITE_API_BASE_URL | 後端 API 位置 |
| VITE_APP_NAME | 應用名稱 |

## 24. 測試計畫

### 24.1 後端測試

使用 pytest。

測試項目：

1. 註冊與登入。
2. JWT 驗證。
3. 建立資料夾。
4. 上傳檔案。
5. 下載檔案。
6. 權限拒絕。
7. 分享權限。
8. 搜尋。
9. 垃圾桶還原。
10. 容量限制。
11. 分片上傳。

### 24.2 前端測試

使用 Vitest 與 React Testing Library。

測試項目：

1. 登入表單驗證。
2. 檔案列表渲染。
3. 上傳進度顯示。
4. 右鍵選單。
5. 分享彈窗。
6. 搜尋輸入 debounce。
7. 錯誤訊息顯示。

### 24.3 E2E 測試

使用 Playwright。

測試情境：

1. 使用者登入。
2. 建立資料夾。
3. 上傳檔案。
4. 搜尋檔案。
5. 分享檔案。
6. 另一位使用者開啟分享檔案。
7. 刪除檔案並從垃圾桶還原。

### 24.4 回歸防護測試（補充，2026-06-14）

根據測試空白分析，以下三個區域缺乏保護，新增功能時容易造成無聲回歸，已補充對應測試：

#### 後端 Router 層 HTTP 狀態碼轉換

Service 層已有單元測試驗證商業邏輯，但 Router 層負責將 Service 拋出的例外轉換為正確 HTTP 狀態碼。若 Router 漏接例外或錯誤使用 `status_code`，單元測試不會捕捉到。

補充項目：

| 檔案 | 端點覆蓋 |
| --- | --- |
| `tests/upload/test_router.py` | POST /upload/simple 201、未驗證 403、parent 不存在 404、quota 超出 413、parent_id 傳遞 |
| `tests/trash/test_router.py` | 移到垃圾桶 200、列表 200、還原 200、永久刪除 204、清空 204，各端點未驗證 403 |
| `tests/search/test_router.py` | 搜尋成功 200、空結果 200、未驗證 403、缺少 q 422、過濾參數傳遞 |
| `tests/share/test_router.py` | 分享 201/403/404、移除分享 204/403、shared-with-me 200/403、建立連結 201/403、驗證連結 200/404、停用連結 204/403 |

#### 後端整合：版本紀錄不變式

每次上傳必須自動建立版本記錄（`file_versions.version_no = 1`）。若 upload service 的版本建立邏輯被重構，整合測試才能抓到回歸。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `tests/integration/test_file_version_flow.py` | 上傳自動產生 v1、size_bytes 正確記錄、未驗證 403、非擁有者無分享不能列版本、viewer 可列版本、兩次上傳同名各自有獨立 v1 |

#### 前端 Store 安全不變式

`authStore` 持有 access token，但沒有測試確保 token 只在記憶體中。若未來有人誤加了 `localStorage.setItem`，現有測試不會報錯。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `src/stores/authStore.test.ts` | 初始狀態 null、setToken/clearToken/clearAuth/setUser 狀態轉換、setToken 不寫入 localStorage 或 sessionStorage |

#### 前端元件行為

DriveToolbar 與 FileTable 是核心互動元件，但沒有對應元件測試。若 props 介面變更或條件渲染邏輯改變，目前沒有任何測試能捕捉。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `src/components/drive/DriveToolbar.test.tsx` | New Folder 永遠可見、Trash 按鈕僅在 selectedCount > 0 時出現、顯示正確數量、click handler 呼叫 |
| `src/components/drive/FileTable.test.tsx` | 渲染所有項目名稱、空陣列不渲染資料列、onItemClick/onItemDoubleClick 傳入正確項目 |

#### 前端 E2E 分享完整流程

目前 E2E 完全沒有覆蓋分享功能。分享涉及兩個使用者帳號、跨頁面操作，是最容易在前後端整合時出問題的流程。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `e2e/share.spec.ts` | 分享後對方在 shared-with-me 看到、移除分享後對方看不到、建立公開連結後連結出現在對話框 |

## 25. 開發里程碑

### 25.1 第一週：專案基礎

1. 建立 frontend 與 backend 專案。
2. 設定 Docker Compose。
3. 設定 PostgreSQL、Redis。
4. 建立 FastAPI 基礎架構。
5. 建立 React 基礎版面。
6. 設定 lint、format、測試工具。

### 25.2 第二週：帳號與檔案基礎

1. 使用者註冊。
2. 使用者登入。
3. JWT 驗證。
4. drive_items 資料表。
5. 建立資料夾 API。
6. 檔案列表 API。
7. 前端我的硬碟頁。

### 25.3 第三週：上傳下載

1. 小檔案上傳。
2. 檔案下載。
3. 容量檢查。
4. 上傳進度 UI。
5. 檔案圖示與 MIME type 顯示。
6. 操作紀錄。

### 25.4 第四週：檔案管理

1. 重新命名。
2. 移動。
3. 星號。
4. 最近檔案。
5. 垃圾桶。
6. 搜尋。
7. 右鍵選單。

### 25.5 第五週：分享與預覽

1. 指定使用者分享。
2. 分享連結。
3. 與我分享頁面。
4. 圖片預覽。
5. PDF 預覽。
6. 文字預覽。

### 25.6 第六週：強化與驗收

1. 分片上傳。
2. 測試補齊。
3. 錯誤處理優化。
4. 權限測試。
5. 效能優化。
6. 部署文件。
7. Demo 準備。

## 26. 驗收標準

MVP 完成時需符合：

1. 使用者可以註冊、登入、登出。
2. 使用者只能看到自己的檔案。
3. 使用者可以建立資料夾。
4. 使用者可以上傳與下載檔案。
5. 使用者可以重新命名與移動檔案。
6. 使用者可以刪除檔案到垃圾桶。
7. 使用者可以從垃圾桶還原檔案。
8. 使用者可以搜尋檔案。
9. 使用者可以將檔案加星號。
10. 使用者可以查看容量使用量。
11. API 對未授權操作回傳正確錯誤。
12. 前端能清楚顯示 loading、empty、error 狀態。
13. Docker 開發環境可以一鍵啟動。

## 27. UI 設計方向

### 27.1 整體風格

介面應以實用、清楚、可快速操作為主。雲端硬碟屬於高頻工作型產品，不適合過度裝飾。建議風格：

1. 淺色背景。
2. 左側固定導覽。
3. 上方全域搜尋。
4. 清楚的檔案列表。
5. 足夠的留白。
6. 操作按鈕使用圖示搭配 tooltip。
7. 重要操作，例如刪除與永久刪除，需要確認。

### 27.2 主要元件

1. Sidebar
2. TopSearchBar
3. Breadcrumbs
4. FileToolbar
5. FileTable
6. FileGrid
7. ContextMenu
8. UploadDropzone
9. UploadQueue
10. PreviewDialog
11. ShareDialog
12. ConfirmDialog
13. StorageUsageBar

### 27.3 狀態設計

每個頁面都要設計：

1. Loading state。
2. Empty state。
3. Error state。
4. Permission denied state。
5. Offline or retry state。

## 28. 後端服務分層

### 28.1 Router

負責：

1. 接收 HTTP request。
2. 驗證 request schema。
3. 呼叫 service。
4. 回傳 response。

### 28.2 Service

負責：

1. 商業邏輯。
2. 權限判斷。
3. 容量判斷。
4. 呼叫 repository。
5. 呼叫 storage provider。

### 28.3 Repository

負責：

1. 資料庫查詢。
2. transaction 管理。
3. 封裝 SQLAlchemy 操作。

### 28.4 Storage Provider

負責：

1. 儲存檔案。
2. 讀取檔案。
3. 刪除檔案。
4. 建立短效下載 URL。

## 29. 推薦資料型別

### 29.1 TypeScript

```ts
export type DriveItemType = "file" | "folder";

export interface DriveItem {
  id: string;
  ownerId: string;
  parentId: string | null;
  itemType: DriveItemType;
  name: string;
  mimeType?: string;
  extension?: string;
  sizeBytes: number;
  isStarred: boolean;
  isDeleted: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface UploadTask {
  id: string;
  file: File;
  parentId: string | null;
  progress: number;
  status: "pending" | "uploading" | "paused" | "completed" | "failed";
  errorMessage?: string;
}
```

### 29.2 Pydantic Schema

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class DriveItemResponse(BaseModel):
    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    item_type: str
    name: str
    mime_type: str | None = None
    extension: str | None = None
    size_bytes: int
    is_starred: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
```

## 30. 風險與對策

| 風險 | 影響 | 對策 |
| --- | --- | --- |
| 大檔案上傳失敗 | 使用體驗差 | 分片上傳與續傳 |
| 權限判斷錯誤 | 資料外洩 | 後端集中權限檢查與測試 |
| 檔案名稱衝突 | 使用者困惑 | 明確衝突策略 |
| 資料夾樹查詢慢 | 列表載入慢 | 索引、ltree 或 closure table |
| 儲存成本上升 | 維運成本高 | 容量限制、垃圾桶清理 |
| 預覽生成耗時 | 使用者等待 | 背景任務與快取 |
| 分享連結外流 | 資料風險 | 密碼、到期時間、撤銷機制 |

## 31. 建議開發順序

1. 後端專案初始化。
2. 前端專案初始化。
3. Docker Compose。
4. 使用者註冊與登入。
5. drive_items 資料表與 migration。
6. 我的硬碟列表。
7. 建立資料夾。
8. 小檔案上傳。
9. 下載檔案。
10. 重新命名、移動、刪除。
11. 垃圾桶。
12. 搜尋。
13. 星號與最近。
14. 分享功能。
15. 預覽功能。
16. 分片上傳。
17. 測試與部署。

## 32. 頁面重新整理後維持登入狀態（Silent Refresh）

### 32.1 問題背景

Access token 依安全規範只存在前端記憶體（Zustand store），不寫入 localStorage 或 sessionStorage。使用者重新整理瀏覽器後，Zustand 狀態歸零，`RequireAuth` 發現 `accessToken === null` 就立刻重導至 `/login`，即使 refresh token cookie 仍然有效。

### 32.2 解法：App 啟動時執行 Silent Refresh

在 React tree 的最頂層加入 `AuthInitializer` 元件，app 掛載時呼叫 `POST /auth/refresh` 一次：

- 成功 → 將新 access token 寫入 Zustand store → router 看到已認證狀態 → 直接渲染目標頁面
- 失敗（cookie 不存在或已過期）→ 不做任何事 → router 將使用者導向 `/login`（正常登出或 session 過期行為）
- 等待期間 → `AuthInitializer` 回傳 `null`（空白畫面），不讓 `RequireAuth` 在 refresh 結束前搶先重導

### 32.3 實作要點

| 項目 | 說明 |
|---|---|
| 使用 `refreshClient` | Silent refresh 必須使用不帶攔截器的獨立 Axios instance，避免 401 → refresh → 401 的無窮迴圈 |
| Refresh 單例化 | `AuthInitializer` 與 401 interceptor 共用同一個 pending refresh promise，避免 React StrictMode 或同時多個 401 重複輪替一次性 token |
| 元件位置 | `<AuthInitializer>` 包住 `<RouterProvider>`，在 `<QueryClientProvider>` 內（可使用 React Query） |
| 等待行為 | `ready` 狀態預設 `false`，`.finally()` 後設為 `true`，確保無論成功或失敗都解除阻擋 |
| 安全不變式 | Access token 仍只存在記憶體，silent refresh 不改變 refresh token 的儲存位置（HttpOnly cookie） |
| Cookie 環境 | development/test 可在本機 HTTP 使用 cookie；staging/production 強制 `Secure` |

### 32.4 登出與 Session 過期

- 明確登出：呼叫 `POST /auth/logout` → 後端撤銷 refresh token 並清除 cookie → 下次 silent refresh 失敗 → 導向 `/login`
- Session 過期（refresh token TTL 到期）：cookie 已失效 → silent refresh 返回 401 → 導向 `/login`
- 這兩種情境均不需前端額外處理，已由現有流程覆蓋

### 32.5 相關檔案

| 檔案 | 變更 |
|---|---|
| `frontend/src/app/AuthInitializer.tsx` | 新增；執行 silent refresh，阻擋 router 至 refresh 完成 |
| `frontend/src/App.tsx` | 用 `<AuthInitializer>` 包住 `<RouterProvider>` |
| `frontend/src/api/authApi.ts` | 新增 `authApi.refresh()` 使用 `refreshClient` |
| `frontend/src/api/client.ts` | 將 `refreshClient` 改為具名匯出（`export const`） |

## 33. 擴充功能：In-App AI Assistant（28 模組之後新增）

原 28 模組完成後，於網頁應用內新增一個**可對話、可自我擴充的 AI 助理**。使用者用自然語言描述需求，助理把需求轉成**可檢視、可確認、可執行、可記錄的 Workflow**，以既有或現場生成的技能完成檔案／資料夾操作。完整設計見 [assistant-design.md](./assistant-design.md)，評測見 [assistant-eval-design.md](./assistant-eval-design.md)，決策見 [decisions.md](./decisions.md) 的 DEC-016～023。

### 33.1 功能範圍

- **對話操作**：登入後 CloudDrive shell 內的浮動聊天面板，用自然語言列檔／搜尋／整理／改名／移動／分享／壓縮解壓等。
- **計畫確認**：寫入/破壞性操作先產生計畫（步驟、權限層級、是否需確認），唯讀操作可 fast-path 自動執行；使用者確認後才執行，破壞性操作**絕不自動執行**。
- **現場生成新技能**：缺少的能力由助理現場生成（例如「做一個 7zip 解壓縮功能」），經 **codegen → 靜態驗證（codeguard）→ 使用者核可 → 受限沙箱執行**，產出檔案寫回 drive。
- **技能管理**：側欄 **Skills 頁（`/skills`）**檢視已安裝技能數量、編輯（描述/程式碼，改碼重跑 codeguard）、刪除。
- **工作流程重用**：計畫可命名儲存，之後一鍵重跑。
- **動態 UI**：已安裝技能依 manifest 動態掛到檔案右鍵選單；使用者訊息列提供複製鈕（前端全域禁止反白，故以按鈕程式複製）。
- **模型策略**：預設本地 Gemma（Ollama），達失敗上限且符合隱私條件時才條件式升級外部模型；隱私敏感且無法去識別化則不外送。

### 33.2 後端目錄（補充 §9）

```
app/assistant/
  router.py service.py repository.py context.py prompt.py hooks.py
  planner.py workflow.py permissions.py subagent.py
  llm/      client.py ollama.py external.py router.py privacy.py
  skills/   registry.py manifest.py authoring.py sandbox.py codeguard.py builtin/
backend/eval/   schema.py runner.py inproc.py runner_browser.py verifier.py
                judge.py scoring.py baseline.py report.py state.py run.py cases/
```

### 33.3 前端目錄（補充 §10）

```
src/components/assistant/  AssistantPanel MessageBubble WorkflowPlanCard
                           SkillApprovalCard SkillApprovalDialog SkillEditDialog
                           SavedWorkflowsPanel AssistantSkillResultDialog StepResultList
src/pages/SkillsPage.tsx           # 側欄 Skills 管理頁（/skills）
src/api/assistantApi.ts  src/hooks/useAssistant.ts
frontend/e2e/assistant/assistant-eval.spec.ts  frontend/playwright.eval.config.ts
```

### 33.4 API（補充 §13，前綴 `/api/v1`）

| Method | Path | 用途 |
|---|---|---|
| POST | `/assistant/chat` | 對話；回計畫或技能提案；記錄 session/訊息 |
| GET | `/assistant/sessions`、`/assistant/sessions/{id}/messages` | 對話歷史 |
| POST | `/assistant/workflows/{id}/confirm` · `/cancel` | 確認/取消 pending 計畫 |
| POST | `/assistant/workflows/save`、GET `/workflows/saved`、POST `/workflows/saved/{id}/rerun` | 命名儲存與一鍵重跑 |
| GET | `/assistant/skills?status=installed` | 列出已安裝技能 |
| POST | `/assistant/skills/{id}/approve` · `/execute` | 核可安裝 / 執行（生成技能於沙箱執行並寫回 drive） |
| PATCH | `/assistant/skills/{id}` | 編輯描述/程式碼（改碼重跑 codeguard） |
| DELETE | `/assistant/skills/{id}` | 刪除技能（連同右鍵動作）；回 204 |

### 33.5 前端頁面（補充 §14）

- **聊天面板**：浮動於各受保護頁；訊息泡泡、計畫確認卡、技能核可/程式碼審查、已存工作流程清單、使用者訊息複製鈕。
- **Skills 管理頁（`/skills`）**：已安裝技能列表（數量、描述、右鍵動作、更新時間）+ 編輯/刪除。

### 33.6 環境變數（補充 §23）

`ASSISTANT_ENABLED`、`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`ASSISTANT_MODEL`、`LLM_NUM_CTX`、`LLM_TIMEOUT_SECONDS`、`LLM_KEEP_ALIVE`、`ASSISTANT_MAX_TOOL_ITERATIONS`、`ASSISTANT_SANDBOX_TIMEOUT_SEC`、`EXTERNAL_LLM_ENABLED`、`MAX_LOCAL_ATTEMPTS`、`EXTERNAL_LLM_BASE_URL`/`EXTERNAL_MODEL`/`EXTERNAL_LLM_API_KEY`、`PRIVACY_DEFAULT`。Docker 預設接本地 Gemma（`gemma4:26b`）。

### 33.7 安全（補充 §18）

- 生成程式碼**絕不自動執行**：經 codeguard AST 靜態掃描（拒禁用 import/`eval`/dunder/錯誤簽章）→ 使用者核可 → 受限子行程沙箱（`python -I`、CPU/檔案 rlimit、`addaudithook` 封鎖網路/spawn/越界寫入）。編輯既有技能同樣重跑 codeguard。
- 沙箱檔案存取限該使用者 storage；所有動作可記入 activity_logs。詳見 DEC-019。

### 33.8 測試與評測（補充 §24）

- 後端 `tests/assistant/`、前端 `components/assistant/*.test.tsx`。
- 獨立評測 harness `backend/eval/`：YAML 案例 + 確定性斷言（workflow/state/safety）+ 可選 LLM judge；多次執行通過率/變異；baseline 回歸；三種 runner（in-process mock〔CI 預設、決定性〕、API〔`--llm real`〕、Browser〔Playwright〕）。

## 34. 結論

本專案的核心不是只做「檔案上傳」，而是要建立完整的檔案管理系統。因此設計上需同時考慮檔案本體儲存、資料庫中繼資料、權限、分享、搜尋、垃圾桶、容量限制與使用者體驗。

建議第一版先完成穩定的 MVP：登入、我的硬碟、資料夾、上傳、下載、搜尋、垃圾桶與容量統計。待核心流程穩定後，再加入分享連結、檔案版本、分片上傳、預覽、背景任務與管理後台。其後再以「In-App AI Assistant」（§33）擴充對話式操作與自我撰寫技能能力。

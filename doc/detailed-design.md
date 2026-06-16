# 雲端硬碟系統詳細設計文件

## 1. 文件目的

本文根據 [proposal.md](./proposal.md) 產生，描述雲端硬碟系統的詳細設計。系統前端使用 React，後端使用 FastAPI，資料庫使用 PostgreSQL。

本文目標是把需求文件中的功能拆成可開發、可測試、可替換的模組。每個模組都應盡量維持低耦合，透過明確的 service、repository、API schema 與 storage interface 溝通。

## 2. 已確認設計決策

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

## 3. 本文件範圍

### 3.1 納入範圍

1. 使用者註冊、登入、登出。
2. JWT access token 與 refresh token。
3. 使用者資料與容量統計。
4. 檔案與資料夾中繼資料管理。
5. 一般檔案上傳。
6. 後端串流下載。
7. 檔案基本預覽。
8. 資料夾列表、建立、重新命名、移動。
9. 檔案重新命名、移動、星號、最近列表。
10. 垃圾桶刪除、還原、永久刪除。
11. 搜尋檔案與資料夾名稱。
12. 指定使用者分享。
13. 公開分享連結的擴充設計。
14. 檔案版本資料模型與 service 介面。
15. 操作紀錄。
16. 前端頁面、元件、hook、store、API client 設計。
17. 模組級測試策略。

### 3.2 不納入範圍

1. 管理員後台 UI。
2. OAuth 登入。
3. WebSocket 即時通知。
4. 全文檢索。
5. 防毒掃描實作。
6. 端對端加密。
7. 線上 Office 文件共同編輯。
8. 桌面同步程式。
9. 手機 App。
10. 大檔案分片上傳核心流程實作。

上述項目可保留資料表欄位或抽象接口，但不在本文件中展開成完整實作。

## 4. 模組拆分原則

### 4.1 基本原則

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

### 4.2 模組依賴方向

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

Repository 不可呼叫 Service。StorageProvider 不可呼叫 Repository。前端元件不可直接呼叫 fetch，必須透過 api client 或 hook。

## 5. 整體架構

### 5.1 後端架構

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

### 5.2 前端架構

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

## 6. 後端核心設計

### 6.1 Core 模組

### 6.1.1 責任

Core 模組提供全系統共用能力：

1. 讀取環境變數。
2. 建立資料庫 session dependency。
3. JWT encode/decode。
4. 密碼雜湊與驗證。
5. 統一錯誤格式。
6. 取得目前登入使用者。
7. CORS、API prefix、app startup 設定。

### 6.1.2 主要檔案

```text
backend/app/core/config.py
backend/app/core/security.py
backend/app/core/dependencies.py
backend/app/core/exceptions.py
backend/app/core/error_codes.py
```

### 6.1.3 Config 設計

未在需求中明確指定的值都由環境變數提供，不在程式碼中硬編固定值。

```python
class Settings(BaseSettings):
    app_env: str
    api_v1_prefix: str
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    cors_origins: list[str]
    storage_driver: str
    local_storage_path: str
    max_upload_size_bytes: int
    default_user_quota_bytes: int
```

### 6.1.4 Security 設計

密碼：

1. 使用 `pwdlib[argon2]`。
2. 註冊時只儲存 `password_hash`。
3. 登入時使用 verify。

JWT：

1. 使用 PyJWT。
2. access token 用於 API 驗證。
3. refresh token 用於取得新的 access token。
4. token payload 至少包含 `sub`、`type`、`exp`、`iat`。

```json
{
  "sub": "user_uuid",
  "type": "access",
  "exp": 1780000000,
  "iat": 1779990000
}
```

### 6.1.5 可獨立測試項

1. `hash_password` 產生的結果不可等於原密碼。
2. `verify_password` 對正確密碼回傳 true。
3. `verify_password` 對錯誤密碼回傳 false。
4. access token decode 後可取得 user id。
5. refresh token 不可被當成 access token 使用。
6. 過期 token 會回傳 `UNAUTHORIZED`。

### 6.2 Auth 模組

### 6.2.1 責任

Auth 模組負責：

1. 使用者註冊。
2. 使用者登入。
3. access token 與 refresh token 簽發。
4. refresh token 輪替或撤銷。
5. 登出。
6. 取得目前使用者。
7. 忘記密碼：重設為隨機臨時密碼並寄送 email。

Auth 模組不負責檔案權限，也不處理檔案資料。

### 6.2.2 對外 API

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 註冊 |
| POST | `/api/v1/auth/login` | 登入 |
| POST | `/api/v1/auth/forgot-password` | 忘記密碼：寄送隨機臨時密碼（防枚舉，恆回傳相同訊息） |
| POST | `/api/v1/auth/refresh` | 刷新 access token |
| POST | `/api/v1/auth/logout` | 登出 |
| GET | `/api/v1/auth/me` | 目前使用者 |

### 6.2.3 Service 介面

```python
class AuthService:
    async def register(self, data: RegisterRequest) -> User
    async def login(self, email: str, password: str) -> TokenPair
    async def forgot_password(self, *, email: str, email_provider: EmailProvider) -> None
    async def refresh(self, refresh_token: str) -> TokenPair
    async def logout(self, refresh_token: str) -> None
    async def get_current_user(self, access_token: str) -> User
```

### 6.2.5 忘記密碼流程

1. 前端 `/forgot-password` 頁送出 email 至 `POST /auth/forgot-password`。
2. `forgot_password()` 正規化 email 後查詢使用者；查無或帳號停用時**靜默結束**（防枚舉）。
3. 否則以 `generate_random_password(10)` 產生隨機 10 碼密碼，呼叫 `UserRepository.reset_password()` 更新 hash 並設定 `users.must_change_password = True`。
4. 透過 `EmailProvider` 寄出含臨時密碼的 email。端點無論結果都回傳相同訊息。
5. 使用者以臨時密碼登入；`CurrentUserResponse.must_change_password=True` 觸發前端提醒 banner。
6. 使用者於帳號設定改密碼時，`UserService.change_password()` → `update_password()` 一併清除 `must_change_password`。

**Email 抽象層（`app/email/`）**：仿照 `StorageProvider` 模式。`EmailProvider` protocol（`send(to, subject, body)`），`ConsoleEmailProvider`（記錄至 log，預設）與 `SMTPEmailProvider`（aiosmtplib，Gmail 等）。`get_email_provider()` factory 依 `EMAIL_PROVIDER` 設定選擇；`smtp` 但未設 `SMTP_HOST` 時 fallback 回 console。SMTP 寄送失敗會被吞下並記錄，以維持端點不可枚舉。

### 6.2.4 Repository 依賴

1. UserRepository
2. RefreshTokenRepository

### 6.2.5 Refresh Token 儲存設計

需求文件提到 refresh token 與登出撤銷，因此需要儲存 refresh token 狀態。

建議資料表：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | uuid | 主鍵 |
| user_id | uuid | 使用者 |
| token_hash | varchar | refresh token hash |
| expires_at | timestamptz | 到期時間 |
| revoked_at | timestamptz | 撤銷時間 |
| created_at | timestamptz | 建立時間 |

資料庫只保存 refresh token hash，不保存明文 refresh token。

### 6.2.6 錯誤碼

| 情境 | 錯誤碼 |
| --- | --- |
| email 已存在 | `EMAIL_ALREADY_EXISTS` |
| 帳號或密碼錯誤 | `INVALID_CREDENTIALS` |
| token 過期 | `UNAUTHORIZED` |
| refresh token 已撤銷 | `REFRESH_TOKEN_REVOKED` |
| 使用者停用 | `USER_INACTIVE` |

### 6.2.7 可獨立測試項

1. 註冊成功會建立 user。
2. 重複 email 註冊會失敗。
3. 正確帳密登入會回傳 token pair。
4. 錯誤密碼登入會失敗。
5. refresh token 可換取新 access token。
6. logout 後 refresh token 不可再使用。
7. 停用使用者不可登入。

### 6.3 User 與 Quota 模組

### 6.3.1 責任

User 模組負責使用者基本資料。Quota 模組負責容量檢查與統計。

兩者分開是為了讓容量邏輯可被 Upload、Trash、Version 模組共用。

### 6.3.2 UserService 介面

```python
class UserService:
    async def get_by_id(self, user_id: UUID) -> User
    async def get_by_email(self, email: str) -> User | None
    async def update_username(self, user_id: UUID, username: str) -> User
    async def update_email(self, user_id: UUID, email: str) -> User
    async def change_password(self, user_id: UUID, current_password: str, new_password: str) -> None
```

#### 帳號設定 API

| Method | Path | 說明 |
| --- | --- | --- |
| PATCH | `/api/v1/users/me` | 更改 username |
| PATCH | `/api/v1/users/me/email` | 更改 email（已被使用回 409）|
| PATCH | `/api/v1/users/me/password` | 更改密碼（驗證舊密碼，成功回 204）|

### 6.3.3 QuotaService 介面

```python
class QuotaService:
    async def assert_has_space(self, user_id: UUID, size_delta: int) -> None
    async def increase_used_bytes(self, user_id: UUID, size_delta: int) -> None
    async def decrease_used_bytes(self, user_id: UUID, size_delta: int) -> None
    async def recalculate_used_bytes(self, user_id: UUID) -> int
```

### 6.3.4 容量統計規則

1. 一般檔案上傳成功後增加 `used_bytes`。
2. 檔案移入垃圾桶時不立即釋放容量。
3. 永久刪除檔案後釋放容量。
4. 版本紀錄若保存多版，每一版都計入容量。
5. 資料夾本身大小為 0。
6. 容量上限值由 `users.quota_bytes` 決定。

### 6.3.5 可獨立測試項

1. 剩餘容量足夠時 `assert_has_space` 成功。
2. 剩餘容量不足時回傳 `QUOTA_EXCEEDED`。
3. 上傳檔案後 used_bytes 增加。
4. 永久刪除檔案後 used_bytes 減少。
5. 資料夾不影響容量。

### 6.4 DriveItem 模組

### 6.4.1 責任

DriveItem 模組管理檔案與資料夾的中繼資料：

1. 建立資料夾。
2. 列出資料夾內容。
3. 重新命名。
4. 移動。
5. 複製的擴充點。
6. 星號標記。
7. 最近檔案列表。
8. 查詢 item 詳細資訊。

DriveItem 模組不直接處理檔案內容讀寫，檔案本體由 Storage 模組處理。

### 6.4.2 Service 介面

```python
class DriveService:
    async def list_items(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        sort: str,
        order: str,
        page: int,
        page_size: int,
    ) -> Page[DriveItem]

    async def create_folder(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        name: str,
    ) -> DriveItem

    async def rename_item(
        self,
        user_id: UUID,
        item_id: UUID,
        name: str,
    ) -> DriveItem

    async def move_item(
        self,
        user_id: UUID,
        item_id: UUID,
        target_parent_id: UUID | None,
    ) -> DriveItem

    async def set_starred(
        self,
        user_id: UUID,
        item_id: UUID,
        is_starred: bool,
    ) -> DriveItem

    async def get_recent_items(
        self,
        user_id: UUID,
        page: int,
        page_size: int,
    ) -> Page[DriveItem]

    async def get_ancestors(
        self,
        user_id: UUID,
        item_id: UUID,
    ) -> list[DriveItemResponse]
    # Returns ordered [root_folder, ..., direct_parent]; current item excluded.
    # Walks parent_id chain upward; cycle-safe via seen-set guard.
    # Endpoint: GET /api/v1/drive/items/{item_id}/ancestors
```

### 6.4.3 Repository 介面

```python
class DriveItemRepository:
    async def get_by_id(self, item_id: UUID) -> DriveItem | None
    async def list_children(self, owner_id: UUID, parent_id: UUID | None, paging: Paging) -> Page[DriveItem]
    async def create(self, item: DriveItemCreate) -> DriveItem
    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem
    async def update_parent(self, item_id: UUID, parent_id: UUID | None, updated_by: UUID) -> DriveItem
    async def update_starred(self, item_id: UUID, is_starred: bool) -> DriveItem
    async def exists_name_in_parent(self, owner_id: UUID, parent_id: UUID | None, name: str) -> bool
```

### 6.4.4 驗證規則

1. 名稱不可為空。
2. 名稱不可包含路徑分隔符。
3. 同一 owner、同一 parent、未刪除項目不可同名。
4. 移動資料夾時不可移到自己的子孫資料夾。
5. 根目錄以 `parent_id = null` 表示。
6. 使用者只能列出自己有權限存取的項目。

### 6.4.5 權限要求

| 操作 | 最低權限 |
| --- | --- |
| list | viewer |
| get detail | viewer |
| create folder | owner 或 editor |
| rename | owner 或 editor |
| move | owner 或 editor |
| set starred | viewer，但星號狀態屬於使用者個人化時需另建表 |
| delete to trash | owner 或 editor |

目前 `drive_items.is_starred` 是 item 欄位，表示星號不區分使用者。若未來分享檔案也要讓每位使用者有自己的星號狀態，需拆出 `user_item_preferences`。

### 6.4.6 可獨立測試項

1. 建立根目錄資料夾成功。
2. 建立子資料夾成功。
3. 同層重名失敗。
4. 不同資料夾可有相同名稱。
5. 重新命名後 updated_at 更新。
6. 移動到不存在資料夾失敗。
7. 移動資料夾到自己的子資料夾失敗。
8. 無權限使用者不可 rename。

### 6.5 Permission 模組

### 6.5.1 責任

Permission 模組負責統一判斷使用者對某個 item 的權限。

此模組是 Drive、Upload、Download、Preview、Trash、Share、Version 的共同依賴。

### 6.5.2 權限層級

| 權限 | 值 | 能力 |
| --- | --- | --- |
| owner | 4 | 所有操作 |
| editor | 3 | 修改、移動、上傳新版本 |
| downloader | 2 | 檢視與下載 |
| viewer | 1 | 檢視與預覽 |
| none | 0 | 不可存取 |

### 6.5.3 Service 介面

```python
class PermissionService:
    async def get_permission(self, user_id: UUID, item_id: UUID) -> Permission
    async def assert_can_view(self, user_id: UUID, item_id: UUID) -> None
    async def assert_can_download(self, user_id: UUID, item_id: UUID) -> None
    async def assert_can_edit(self, user_id: UUID, item_id: UUID) -> None
    async def assert_is_owner(self, user_id: UUID, item_id: UUID) -> None
```

### 6.5.4 權限判斷流程

```text
get item
  -> item.owner_id == user_id ?
      yes: owner
      no:
        check direct share
          -> found: share.permission
          -> not found:
             check inherited folder share
               -> found: inherited permission
               -> not found: none
```

公開連結權限由 ShareLinkService 驗證，不混入一般 user permission 判斷。

### 6.5.5 資料夾繼承策略

MVP + 第二階段採用查詢祖先資料夾的方式判斷繼承權限。若資料量變大，可擴充 closure table 或 permission cache。

本文件不指定 ltree 或 closure table，因為需求尚未要求大規模資料夾樹效能優化。

### 6.5.6 可獨立測試項

1. owner 取得 owner 權限。
2. 指定分享 viewer 取得 viewer 權限。
3. 未分享使用者取得 none。
4. 子項目繼承父資料夾權限。
5. editor 可編輯但不等於 owner。
6. viewer 不可下載時，依實際 permission 設計拒絕下載。

### 6.6 Storage 模組

### 6.6.1 責任

Storage 模組負責檔案本體的儲存、讀取與刪除。第一版實作 LocalStorageProvider，未來可替換 MinIO、S3 或 Azure Blob。

Storage 模組不負責：

1. 使用者認證。
2. 權限判斷。
3. 容量判斷。
4. drive_items 建立。
5. 分享邏輯。

### 6.6.2 StorageProvider 介面

```python
from typing import BinaryIO, Protocol


class StorageProvider(Protocol):
    async def save(self, file_stream: BinaryIO, storage_key: str) -> int:
        ...

    async def open_read(self, storage_key: str) -> BinaryIO:
        ...

    async def delete(self, storage_key: str) -> None:
        ...

    async def exists(self, storage_key: str) -> bool:
        ...

    async def get_size(self, storage_key: str) -> int:
        ...
```

`generate_download_url` 暫不作為 MVP 必要接口，因為已確認 MVP 使用 StreamingResponse。未來物件儲存可加回 signed URL。

### 6.6.3 LocalStorageProvider 設計

本機儲存路徑：

```text
{LOCAL_STORAGE_PATH}/{user_id}/{item_id}/{version_no}/{safe_file_name}
```

`storage_key` 不直接使用使用者上傳的原始檔名產生。原始檔名只存在資料庫 `drive_items.name`。

### 6.6.4 安全規則

1. `storage_key` 由後端產生。
2. 禁止 `../` 路徑穿越。
3. LocalStorageProvider 只能讀寫 `LOCAL_STORAGE_PATH` 之下的檔案。
4. 寫入前先寫到 temporary path，成功後再 move 到正式位置。
5. 刪除檔案時只刪除 storage_key 指向的檔案。

### 6.6.5 可獨立測試項

1. save 後 exists 為 true。
2. save 回傳寫入 bytes。
3. open_read 可讀回同樣內容。
4. delete 後 exists 為 false。
5. 非法 storage_key 會被拒絕。
6. 寫入失敗不留下正式檔案。

### 6.7 Upload 模組

### 6.7.1 責任

Upload 模組負責一般檔案上傳流程：

1. 接收 multipart file。
2. 驗證 parent folder。
3. 驗證權限。
4. 檢查容量。
5. 儲存檔案本體。
6. 建立 drive_items。
7. 建立 file_versions v1。
8. 更新容量。
9. 寫入 activity log。

大檔案分片上傳不納入核心 detailed design，只保留 `UploadSession` 擴充點。

### 6.7.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/api/v1/upload/simple` | 一般檔案上傳 |

Form data：

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| parent_id | 否 | 目標資料夾，根目錄可空 |
| file | 是 | 上傳檔案 |

### 6.7.3 Service 介面

```python
class UploadService:
    async def upload_simple(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        upload_file: UploadFile,
    ) -> DriveItem
```

### 6.7.4 上傳流程

```text
receive request
  -> authenticate user
  -> validate file name and size
  -> validate parent folder exists if parent_id is not null
  -> PermissionService.assert_can_edit(parent_id) if parent exists
  -> QuotaService.assert_has_space(user_id, file_size)
  -> create DriveItem row with pending storage_key
  -> create storage_key
  -> StorageProvider.save(file, storage_key)
  -> update DriveItem storage fields
  -> create FileVersion v1
  -> QuotaService.increase_used_bytes
  -> ActivityLogService.log(upload)
  -> return DriveItemResponse
```

### 6.7.5 Transaction 設計

上傳同時涉及資料庫與檔案系統，無法靠單一 DB transaction 完全保證原子性。

處理策略：

1. 先檢查容量與權限。
2. 建立 `drive_items` 時可使用 `status = pending` 擴充欄位，或在儲存成功後再建立資料列。
3. 第一版建議儲存成功後再建立資料列，降低資料庫殘留。
4. 若資料列建立失敗，呼叫 StorageProvider.delete 清理檔案。
5. 若檔案儲存失敗，不建立資料列。

`proposal.md` 尚未定義 status 欄位，因此本詳細設計不強制新增 status。

### 6.7.6 檔名衝突策略

已確認詳細設計不新增未決策略。根據 `proposal.md`，MVP 建議保留兩者並自動命名為 `filename (1).ext`。

UploadService 需呼叫 DriveService 或 DriveItemRepository 取得可用名稱：

```python
async def resolve_available_name(owner_id: UUID, parent_id: UUID | None, original_name: str) -> str
```

### 6.7.7 UploadSession 擴充點

保留資料表與 service interface，但不實作核心流程。

```python
class UploadSessionService:
    async def create_session(...)
    async def upload_chunk(...)
    async def complete_session(...)
    async def cancel_session(...)
```

MVP 中 router 可以不暴露這些 endpoint。

### 6.7.8 可獨立測試項

1. 上傳成功會建立 drive_item。
2. 上傳成功會建立 file_version v1。
3. 上傳成功會增加 used_bytes。
4. 容量不足時上傳失敗。
5. parent_id 不存在時失敗。
6. 無權限上傳到分享資料夾時失敗。
7. 同名檔案會產生可用新名稱。
8. storage 寫入失敗時不建立 drive_item。
9. drive_item 建立失敗時會清理已寫入檔案。

### 6.8 Download 模組

### 6.8.1 責任

Download 模組負責檔案下載：

1. 驗證使用者權限。
2. 驗證 item 是 file。
3. 從 StorageProvider 讀取檔案。
4. 使用 StreamingResponse 回傳。
5. 寫入下載操作紀錄。

### 6.8.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/drive/items/{item_id}/download` | 下載檔案 |

### 6.8.3 Service 介面

```python
class DownloadService:
    async def prepare_download(
        self,
        user_id: UUID,
        item_id: UUID,
    ) -> DownloadFileResult
```

```python
class DownloadFileResult(BaseModel):
    file_name: str
    mime_type: str
    size_bytes: int
    stream: BinaryIO
```

### 6.8.4 Router 回應設計

Router 使用：

```python
return StreamingResponse(
    result.stream,
    media_type=result.mime_type,
    headers={
        "Content-Disposition": f'attachment; filename="{encoded_file_name}"'
    },
)
```

### 6.8.5 可獨立測試項

1. owner 可下載。
2. downloader 可下載。
3. viewer 是否可下載依權限設計拒絕或允許；本文件採用 downloader 才可下載。
4. folder 不可下載為檔案。
5. storage_key 不存在時回傳 `ITEM_CONTENT_NOT_FOUND`。
6. 成功下載會寫入 activity log。

### 6.9 Preview 模組

### 6.9.1 責任

Preview 模組負責根據檔案 MIME type 回傳預覽資訊。

MVP 基本預覽：

1. 圖片：回傳可被前端載入的預覽 endpoint。
2. PDF：回傳可被前端 PDF viewer 載入的 endpoint。
3. 文字檔：回傳文字內容或文字預覽 endpoint。
4. 不支援的類型：回傳 `unsupported`。

圖片縮圖與 PDF 預覽生成屬第二階段，可透過 background task 擴充。

### 6.9.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/drive/items/{item_id}/preview` | 取得預覽資訊 |
| GET | `/api/v1/drive/items/{item_id}/preview/content` | 取得預覽內容串流 |

### 6.9.3 Service 介面

```python
class PreviewService:
    async def get_preview_info(self, user_id: UUID, item_id: UUID) -> PreviewInfo
    async def open_preview_content(self, user_id: UUID, item_id: UUID) -> PreviewContent
```

### 6.9.4 PreviewInfo

```json
{
  "preview_type": "image | pdf | text | video | audio | unsupported",
  "content_url": "/api/v1/drive/items/{item_id}/preview/content",
  "mime_type": "application/pdf"
}
```

### 6.9.5 可獨立測試項

1. image MIME type 回傳 image preview。
2. pdf MIME type 回傳 pdf preview。
3. text MIME type 回傳 text preview。
4. 不支援 MIME type 回傳 unsupported。
5. 無權限使用者不可取得 preview。
6. folder 不可 preview。

### 6.10 Trash 模組

### 6.10.1 責任

Trash 模組負責軟刪除、還原與永久刪除。

### 6.10.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/trash` | 取得垃圾桶列表 |
| PATCH | `/api/v1/trash/{item_id}/restore` | 還原 |
| DELETE | `/api/v1/trash/{item_id}` | 永久刪除 |
| DELETE | `/api/v1/trash` | 清空垃圾桶 |
| PATCH | `/api/v1/drive/items/{item_id}/trash` | 移至垃圾桶 |

`proposal.md` 沒列出移至垃圾桶 endpoint，但刪除到垃圾桶是 MVP 功能，因此補入此 endpoint 作為 Drive/Trash 的入口。

### 6.10.3 Service 介面

```python
class TrashService:
    async def move_to_trash(self, user_id: UUID, item_id: UUID) -> DriveItem
    async def list_trash(self, user_id: UUID, page: int, page_size: int) -> Page[DriveItem]
    async def restore(self, user_id: UUID, item_id: UUID) -> DriveItem
    async def permanently_delete(self, user_id: UUID, item_id: UUID) -> None
    async def empty_trash(self, user_id: UUID) -> None
```

### 6.10.4 軟刪除規則

1. 移至垃圾桶時設定 `is_deleted = true`。
2. 設定 `deleted_at`。
3. 一般列表不顯示 `is_deleted = true` 的項目。
4. 資料夾移至垃圾桶時，其子項目不必逐一標記，但查詢時要因祖先刪除而隱藏。
5. 永久刪除資料夾時需遞迴刪除所有子項目檔案本體。

### 6.10.5 還原規則

1. 還原時檢查原 parent 是否仍存在且未刪除。
2. 若 parent 不存在，還原到根目錄。
3. 若同層名稱衝突，使用檔名衝突策略產生新名稱。
4. 還原後設定 `is_deleted = false`、`deleted_at = null`。

### 6.10.6 可獨立測試項

1. 移至垃圾桶後不出現在一般列表。
2. 移至垃圾桶後出現在垃圾桶列表。
3. 還原後回到一般列表。
4. parent 被刪除後還原到根目錄。
5. 還原時名稱衝突會自動改名。
6. 永久刪除會刪除 storage 檔案。
7. 永久刪除會扣回容量。
8. 無權限使用者不可永久刪除。

### 6.11 Search 模組

### 6.11.1 責任

Search 模組負責搜尋使用者可存取的檔案與資料夾。

MVP 搜尋範圍：

1. 檔案名稱。
2. 資料夾名稱。
3. MIME type 篩選。
4. item_type 篩選。

全文檢索不納入本文件主設計。

### 6.11.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/search` | 搜尋項目 |

Query：

| 參數 | 必填 | 說明 |
| --- | --- | --- |
| q | 是 | 關鍵字 |
| type | 否 | file、folder、all |
| mime_type | 否 | MIME type |
| page | 否 | 頁碼 |
| page_size | 否 | 每頁筆數 |

### 6.11.3 Service 介面

```python
class SearchService:
    async def search(
        self,
        user_id: UUID,
        query: str,
        item_type: str | None,
        mime_type: str | None,
        page: int,
        page_size: int,
    ) -> Page[DriveItem]
```

### 6.11.4 查詢設計

1. 排除 `is_deleted = true`。
2. 搜尋 owner 自己的檔案。
3. 搜尋被分享給自己的檔案。
4. 使用 PostgreSQL `pg_trgm` 提升模糊搜尋效能。
5. 第二階段若需要更完整的權限繼承搜尋，可加入 permission cache。

### 6.11.5 可獨立測試項

1. 搜尋可找到自己的檔案。
2. 搜尋可找到分享給自己的檔案。
3. 搜尋不可找到未分享的他人檔案。
4. 垃圾桶檔案不出現在搜尋結果。
5. type=file 只回傳檔案。
6. type=folder 只回傳資料夾。
7. MIME type 篩選有效。

### 6.12 Share 模組

### 6.12.1 責任

Share 模組負責分享檔案或資料夾。

第一優先實作：

1. 分享給指定使用者。
2. 設定權限：viewer、downloader、editor。
3. 移除指定使用者分享。
4. 取得與我分享列表。

第二階段可選：

1. 公開分享連結。
2. 分享連結密碼。
3. 分享連結到期時間。
4. 停用分享連結。

### 6.12.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/api/v1/share/items/{item_id}/users` | 分享給指定使用者 |
| PATCH | `/api/v1/share/items/{item_id}/users/{target_user_id}` | 更新分享權限 |
| DELETE | `/api/v1/share/items/{item_id}/users/{target_user_id}` | 移除指定分享 |
| GET | `/api/v1/share/shared-with-me` | 與我分享 |
| POST | `/api/v1/share/items/{item_id}/links` | 建立公開連結 |
| DELETE | `/api/v1/share/links/{link_id}` | 停用公開連結 |

### 6.12.3 Service 介面

```python
class ShareService:
    async def share_with_user(
        self,
        owner_id: UUID,
        item_id: UUID,
        target_email: str,
        permission: SharePermission,
    ) -> Share

    async def update_user_share(
        self,
        owner_id: UUID,
        item_id: UUID,
        target_user_id: UUID,
        permission: SharePermission,
    ) -> Share

    async def remove_user_share(
        self,
        owner_id: UUID,
        item_id: UUID,
        target_user_id: UUID,
    ) -> None

    async def list_shared_with_me(
        self,
        user_id: UUID,
        page: int,
        page_size: int,
    ) -> Page[DriveItem]
```

### 6.12.4 ShareLinkService 介面

```python
class ShareLinkService:
    async def create_link(
        self,
        user_id: UUID,
        item_id: UUID,
        permission: LinkPermission,
        password: str | None,
        expires_at: datetime | None,
    ) -> ShareLinkCreated

    async def disable_link(self, user_id: UUID, link_id: UUID) -> None
    async def validate_link(self, token: str, password: str | None) -> ShareLinkAccess
```

### 6.12.5 分享規則

1. 只有 owner 可以建立或移除分享。
2. 不可分享給自己。
3. 同一 item 對同一 target user 只保留一筆分享。
4. 重複分享時更新 permission。
5. 被分享者可在「與我分享」看到 item。
6. 資料夾分享權限可繼承到子項目。

### 6.12.6 分享連結安全規則

1. 明文 token 只在建立時回傳前端。
2. 資料庫只保存 token hash。
3. 有密碼時只保存 password hash。
4. 過期連結不可使用。
5. 停用連結不可使用。

### 6.12.7 可獨立測試項

1. owner 可分享檔案給指定使用者。
2. 非 owner 不可分享。
3. 分享給不存在 email 會失敗。
4. 重複分享會更新權限。
5. 移除分享後對方不可再存取。
6. 分享資料夾後子項目可被檢視。
7. 建立公開連結時資料庫不保存明文 token。
8. 到期連結不可使用。
9. 密碼錯誤不可使用分享連結。

### 6.13 FileVersion 模組

### 6.13.1 責任

FileVersion 模組負責檔案版本紀錄。MVP 可只建立 v1，但資料模型與 service 先設計好，避免之後重構。

### 6.13.2 Service 介面

```python
class FileVersionService:
    async def create_initial_version(
        self,
        file_id: UUID,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None,
        created_by: UUID,
    ) -> FileVersion

    async def create_new_version(
        self,
        user_id: UUID,
        file_id: UUID,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None,
    ) -> FileVersion

    async def list_versions(
        self,
        user_id: UUID,
        file_id: UUID,
    ) -> list[FileVersion]
```

### 6.13.3 版本規則

1. 上傳新檔案時建立 v1。
2. `version_no` 從 1 開始遞增。
3. 新版本必須對應 file item，不可對 folder 建版本。
4. 建立新版本需 editor 以上權限。
5. 每個版本都有自己的 storage_key。
6. 每個版本大小都計入使用者容量。

### 6.13.4 可獨立測試項

1. 新檔案上傳後建立 v1。
2. 第二版 version_no 為 2。
3. folder 不可建立版本。
4. viewer 不可建立新版本。
5. list_versions 依版本號排序。

### 6.14 ActivityLog 模組

### 6.14.1 責任

ActivityLog 模組負責記錄重要操作，供近期檔案、審計與未來管理功能使用。

### 6.14.2 Service 介面

```python
class ActivityLogService:
    async def log(
        self,
        actor_id: UUID,
        item_id: UUID | None,
        action: str,
        metadata: dict,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None
```

### 6.14.3 記錄操作

| action | 觸發時機 |
| --- | --- |
| upload | 檔案上傳成功 |
| download | 檔案下載成功 |
| preview | 預覽檔案 |
| rename | 重新命名 |
| move | 移動 |
| trash | 移至垃圾桶 |
| restore | 從垃圾桶還原 |
| permanent_delete | 永久刪除 |
| share | 建立分享 |
| unshare | 移除分享 |

### 6.14.4 可獨立測試項

1. log 可寫入 action。
2. metadata 以 jsonb 儲存。
3. item_id 可為 null。
4. ActivityLogService 失敗時不應破壞主要操作流程；是否阻擋主流程由 service 層決定。

## 7. 資料庫詳細設計

### 7.1 users

```text
id uuid primary key
email varchar unique not null
username varchar not null
password_hash varchar not null
avatar_url text null
quota_bytes bigint not null
used_bytes bigint not null default 0
is_active boolean not null default true
is_admin boolean not null default false
created_at timestamptz not null
updated_at timestamptz not null
```

索引：

```sql
CREATE UNIQUE INDEX uq_users_email ON users (lower(email));
```

### 7.2 refresh_tokens

```text
id uuid primary key
user_id uuid not null references users(id)
token_hash varchar not null unique
expires_at timestamptz not null
revoked_at timestamptz null
created_at timestamptz not null
```

索引：

```sql
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

### 7.3 drive_items

```text
id uuid primary key
owner_id uuid not null references users(id)
parent_id uuid null references drive_items(id)
item_type varchar not null
name varchar not null
mime_type varchar null
extension varchar null
size_bytes bigint not null default 0
storage_key text null
checksum_sha256 varchar null
is_starred boolean not null default false
is_deleted boolean not null default false
deleted_at timestamptz null
created_by uuid not null references users(id)
updated_by uuid null references users(id)
created_at timestamptz not null
updated_at timestamptz not null
```

約束：

```sql
ALTER TABLE drive_items
ADD CONSTRAINT ck_drive_items_item_type
CHECK (item_type IN ('file', 'folder'));
```

索引：

```sql
CREATE INDEX idx_drive_items_owner_parent ON drive_items(owner_id, parent_id);
CREATE INDEX idx_drive_items_owner_deleted ON drive_items(owner_id, is_deleted);
CREATE INDEX idx_drive_items_parent ON drive_items(parent_id);
CREATE INDEX idx_drive_items_updated_at ON drive_items(updated_at DESC);
CREATE INDEX idx_drive_items_name_trgm ON drive_items USING gin (name gin_trgm_ops);

CREATE UNIQUE INDEX uq_drive_items_same_folder_name
ON drive_items(owner_id, parent_id, lower(name))
WHERE is_deleted = false;
```

### 7.4 file_versions

```text
id uuid primary key
file_id uuid not null references drive_items(id)
version_no integer not null
storage_key text not null
size_bytes bigint not null
checksum_sha256 varchar null
created_by uuid not null references users(id)
created_at timestamptz not null
```

索引與約束：

```sql
CREATE UNIQUE INDEX uq_file_versions_file_version
ON file_versions(file_id, version_no);

CREATE INDEX idx_file_versions_file_id
ON file_versions(file_id);
```

### 7.5 shares

```text
id uuid primary key
item_id uuid not null references drive_items(id)
owner_id uuid not null references users(id)
target_user_id uuid not null references users(id)
permission varchar not null
created_at timestamptz not null
updated_at timestamptz not null
```

約束：

```sql
ALTER TABLE shares
ADD CONSTRAINT ck_shares_permission
CHECK (permission IN ('viewer', 'downloader', 'editor'));

CREATE UNIQUE INDEX uq_shares_item_target_user
ON shares(item_id, target_user_id);
```

### 7.6 share_links

```text
id uuid primary key
item_id uuid not null references drive_items(id)
token_hash varchar not null unique
permission varchar not null
password_hash varchar null
expires_at timestamptz null
is_active boolean not null default true
created_by uuid not null references users(id)
created_at timestamptz not null
```

約束：

```sql
ALTER TABLE share_links
ADD CONSTRAINT ck_share_links_permission
CHECK (permission IN ('viewer', 'downloader'));
```

### 7.7 upload_sessions 與 upload_chunks

保留作為未來分片上傳擴充點。MVP 不需要暴露 endpoint，也不要求前端實作分片流程。

資料表可先不 migration，等分片上傳進入開發時再加入；若希望先穩定 API contract，可先建立表但不啟用功能。

### 7.8 activity_logs

```text
id uuid primary key
actor_id uuid not null references users(id)
item_id uuid null references drive_items(id)
action varchar not null
metadata jsonb not null default '{}'
ip_address inet null
user_agent text null
created_at timestamptz not null
```

索引：

```sql
CREATE INDEX idx_activity_logs_actor_created
ON activity_logs(actor_id, created_at DESC);

CREATE INDEX idx_activity_logs_item_created
ON activity_logs(item_id, created_at DESC);
```

## 8. API 詳細設計

### 8.1 統一 Response 規則

成功時依 API 回傳資料。

錯誤時統一格式：

```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Storage quota exceeded",
    "details": {}
  }
}
```

### 8.2 分頁格式

列表 API 統一使用：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 50
}
```

### 8.3 DriveItemResponse

```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "parent_id": null,
  "item_type": "file",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "extension": "pdf",
  "size_bytes": 102400,
  "is_starred": false,
  "is_deleted": false,
  "created_at": "2026-06-11T14:00:00Z",
  "updated_at": "2026-06-11T14:00:00Z"
}
```

### 8.4 API 與模組對應

| API | Router | Service |
| --- | --- | --- |
| `/auth/*` | AuthRouter | AuthService |
| `/drive/items` | DriveRouter | DriveService |
| `/upload/simple` | UploadRouter | UploadService |
| `/drive/items/{id}/download` | DriveRouter | DownloadService |
| `/drive/items/{id}/preview` | DriveRouter | PreviewService |
| `/trash/*` | TrashRouter | TrashService |
| `/search` | SearchRouter | SearchService |
| `/share/*` | ShareRouter | ShareService / ShareLinkService |

## 9. 前端詳細設計

### 9.1 前端技術組合

1. React + TypeScript。
2. Vite。
3. React Router。
4. TanStack Query 管 server state。
5. Zustand 管 UI state。
6. shadcn/ui + Tailwind CSS。
7. React Hook Form + Zod。

### 9.2 Router 設計

```text
/login
/register
/drive
/drive/folders/:folderId
/shared
/recent
/starred
/trash
/s/:shareToken
```

受保護頁面需透過 `RequireAuth` 包裝。

### 9.2.1 AuthInitializer

App 啟動時（`App.tsx` 最外層）執行一次 silent refresh，解決頁面重載後 access token 因 in-memory 儲存而消失的問題。

責任：

1. 掛載時透過共用的 `refreshAccessToken()` 呼叫 `POST /auth/refresh`。
2. 成功 → 將 access token 寫入 `authStore`，繼續渲染 router。
3. 失敗（cookie 不存在或過期）→ 不做任何事，讓 `RequireAuth` 導向 `/login`。
4. 等待期間回傳 `null`，阻止 router 在結果未定前搶先重導。
5. `AuthInitializer` 與 Axios 401 interceptor 共用 pending promise，避免 StrictMode 或同時請求重複輪替 refresh token。
6. refresh cookie 在 development/test 不設定 `Secure` 以支援本機 HTTP；staging/production 必須設定 `Secure`。

```tsx
// src/app/AuthInitializer.tsx
export function AuthInitializer({ children }) {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let active = true
    refreshAccessToken().finally(() => {
      if (active) setReady(true)
    })
    return () => { active = false }
  }, [])
  if (!ready) return null
  return <>{children}</>
}
```

### 9.2.2 RequireAuth

責任：

1. 檢查 authStore 是否有 token（`AuthInitializer` 已確保此時結果已定）。
2. 若無 token，導向 `/login`（保留原始 location 供登入後還原）。
3. 若有 token，渲染子路由。
4. 若後續 API 請求收到 401，攔截器自動嘗試 refresh；refresh 失敗則 `clearToken` 並觸發下次路由守衛重導。

### 9.3 API Client 模組

### 9.3.1 責任

1. 統一 base URL。
2. 自動帶上 access token。
3. 處理 401 refresh。
4. 統一解析錯誤格式。
5. 封裝 auth、drive、upload、share、search API。

### 9.3.2 檔案

```text
src/api/client.ts
src/api/authApi.ts
src/api/driveApi.ts
src/api/uploadApi.ts
src/api/shareApi.ts
src/api/searchApi.ts
```

### 9.3.3 可獨立測試項

1. request 會帶 Authorization header。
2. 401 時會呼叫 refresh。
3. refresh 成功後重試原 request。
4. refresh 失敗會清除 authStore。
5. API error 會轉成前端可顯示的錯誤物件。

### 9.4 Auth 前端模組

### 9.4.1 頁面與元件

```text
LoginPage
RegisterPage
AuthForm
```

### 9.4.2 Zustand authStore

```ts
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: CurrentUser | null;
  setTokens(tokens: TokenPair): void;
  setUser(user: CurrentUser): void;
  clearAuth(): void;
}
```

### 9.4.3 TanStack Query

| Query/Mutation | 說明 |
| --- | --- |
| `useCurrentUserQuery` | 取得目前使用者 |
| `useLoginMutation` | 登入 |
| `useRegisterMutation` | 註冊 |
| `useLogoutMutation` | 登出 |

### 9.4.4 可獨立測試項

1. email 格式錯誤時表單阻擋送出。
2. 密碼空白時表單阻擋送出。
3. 登入成功後寫入 token。
4. 登出後清除 token。
5. 未登入使用者不可進入 `/drive`。

### 9.5 Layout 模組

### 9.5.1 責任

Layout 模組負責整體操作框架：

1. Sidebar。
2. TopSearchBar。
3. UserMenu。
4. MainContent。
5. DetailsPanel 擴充點。
6. UploadQueue 固定區塊。

### 9.5.2 元件

```text
AppShell
Sidebar
TopBar
TopSearchBar
UserMenu
StorageUsageBar
```

### 9.5.3 uiStore

```ts
interface UiState {
  sidebarCollapsed: boolean;
  viewMode: "list" | "grid";
  selectedItemIds: Set<string>;   // uses Set for O(1) membership checks
  previewItemId: string | null;
  shareItemId: string | null;
  contextMenu: ContextMenuState | null;
  // actions
  selectItem(id: string, multi?: boolean): void;  // multi=true → toggle without clearing
  selectAll(ids: string[]): void;
  clearSelection(): void;
}
```

### 9.5.4 可獨立測試項

1. Sidebar 可切換收合。
2. viewMode 切換後 DrivePage 顯示列表或格狀。
3. 選取檔案後 toolbar 顯示操作。
4. 關閉 preview dialog 後 previewItemId 清空。
5. 全域 CSS（`index.css`）對 `*` 設定 `user-select: none`，徹底禁止任何 UI 文字被滑鼠選取或複製；`input`、`textarea` 以 `user-select: text` 覆寫，保留表單欄位的正常選取能力。

### 9.6 Drive 前端模組

### 9.6.1 頁面

```text
DrivePage
RecentPage
StarredPage
```

### 9.6.2 元件

```text
DriveToolbar
Breadcrumbs
FileTable            — header checkbox (indeterminate) + onSelectAll
FileGrid
FileRow              — checkbox overlays icon on hover; always visible when selected
FileCard             — absolute-positioned checkbox top-left
FileIcon
FileContextMenu      — single-item right-click menu
MultiFileContextMenu — multi-item right-click menu (count label + trash only)
CreateFolderDialog
RenameDialog
MoveDialog
ConfirmTrashDialog   — supports itemNames: string[] for bulk confirmation
```

**多選行為：**
- Checkbox 點擊 (`onCheckboxClick`) 永遠以累積模式加選，不取代已選範圍。
- `useDragSelect` 監聽 `window` 上的 Pointer Events，超過 5 px 移動門檻後顯示 `position:fixed` 選取框。
- 框選可從 `<main>` 內任意空白處啟動（含檔案列表外的 padding 區域）；Sidebar 與 TopBar 不在 `<main>` 內，從那裡開始拖曳不會啟動選框（以 `closest('main')` 判斷）。
- 框選以 `[data-item-id]` 元素的 `getBoundingClientRect()` 判斷是否與選取框相交，因此格狀檔案卡與列表列都支援。
- 框選只使用滑鼠左鍵；新的框選範圍取代既有選取，不要求搭配 Ctrl/Cmd 等鍵盤按鍵。
- `pointerdown` 時取消原生預設行為並呼叫 `removeAllRanges()`；拖曳期間攔截 `selectstart` 防止文字反白。
- 空白處單擊清除選取；從檔案項目、checkbox、button、link 或其他互動控制開始拖曳時不啟動框選。
- 右鍵點擊已選取的多個項目之一 → 顯示 `MultiFileContextMenu`（僅「移至垃圾桶」）。
- 右鍵點擊未選或單選項目 → 顯示 `FileContextMenu`（完整單一操作）。
- `uiStore.selectAll(ids)` 提供 header checkbox 全選功能。
- 批次移至垃圾桶後自動 `clearSelection()`。

### 9.6.3 Hooks

```ts
useDriveItems(parentId, sort, order, page, pageSize)
useFolderItem(folderId)      // GET /drive/items/{id} — current folder's metadata
useFolderAncestors(folderId) // GET /drive/items/{id}/ancestors — ordered [root → parent]
useCreateFolder()
useRenameItem()
useMoveItem()
useSetStarred()
useMoveToTrash()
useRecentItems()
useDragSelect(containerRef, onSelectIds, onClear)
```

`useFolderItem` + `useFolderAncestors` 一起驅動 DrivePage 的 Breadcrumbs 元件，並提供 ArrowLeft 返回按鈕所需的 `parent_id`。

### 9.6.4 Query Key 設計

```ts
["drive", "items", parentId]         // folder contents
["drive", "item", id]                // single item metadata
["drive", "ancestors", id]           // ancestor chain for breadcrumbs
["drive", "recent"]
["drive", "starred"]
```

### 9.6.5 更新策略

1. 建立資料夾成功後 invalidate `drive-items`。
2. 重新命名成功後 invalidate 相關列表。
3. 移動成功後 invalidate 原資料夾與目標資料夾。
4. 星號成功後 invalidate starred 與目前列表。
5. 移至垃圾桶後 invalidate drive、trash、recent。

### 9.6.6 可獨立測試項

1. 空資料夾顯示 empty state。
2. loading 時顯示 skeleton。
3. API error 時顯示錯誤狀態。
4. 點擊資料夾會進入該 folder route。
5. 點擊檔案會開啟 preview。
6. 右鍵選單會根據 item_type 顯示可用操作。

### 9.7 Upload 前端模組

### 9.7.1 責任

1. 選擇檔案。
2. 拖曳上傳。
3. 呼叫 `/upload/simple`。
4. 顯示進度。
5. 顯示成功、失敗、取消狀態。

### 9.7.2 uploadStore

```ts
interface UploadTask {
  id: string;
  file: File;
  parentId: string | null;
  progress: number;
  status: "pending" | "uploading" | "completed" | "failed" | "cancelled";
  errorMessage?: string;
}

interface UploadState {
  tasks: UploadTask[];
  addTasks(files: File[], parentId: string | null): void;
  updateProgress(id: string, progress: number): void;
  markCompleted(id: string): void;
  markFailed(id: string, message: string): void;
  removeTask(id: string): void;
}
```

### 9.7.3 元件

```text
UploadButton
UploadDropzone
UploadQueue
UploadTaskItem
```

### 9.7.4 可獨立測試項

1. 選擇檔案後建立 UploadTask。
2. 拖曳檔案到螢幕任意位置（包含 Sidebar、TopBar）均會建立 UploadTask；`UploadDropzone` 使用 `window` 全域 drag 事件並以 `position:fixed` overlay 覆蓋整個視窗。
3. 上傳中顯示進度。
4. 上傳成功後檔案列表刷新。
5. 上傳失敗後顯示錯誤訊息。

### 9.8 Preview 前端模組

### 9.8.1 責任

1. 呼叫 preview API。
2. 根據 preview_type 渲染不同 viewer。
3. 不支援預覽時顯示下載操作。

### 9.8.2 元件

```text
PreviewDialog
ImagePreview
PdfPreview
TextPreview
VideoPreview
AudioPreview
UnsupportedPreview
```

### 9.8.3 可獨立測試項

1. image preview 使用 img 顯示。
2. pdf preview 使用 iframe 或 PDF viewer 顯示。
3. text preview 顯示文字內容。
4. unsupported preview 顯示下載按鈕。
5. preview API 錯誤時顯示錯誤狀態。

### 9.9 Share 前端模組

### 9.9.1 責任

1. 開啟分享彈窗。
2. 輸入 target email。
3. 選擇 permission。
4. 建立指定使用者分享。
5. 顯示與移除既有分享。
6. 第二階段支援公開連結、密碼、到期時間。

### 9.9.2 元件

```text
ShareDialog
UserShareForm
PermissionSelect
ShareMemberList
ShareLinkPanel
```

### 9.9.3 Hooks

```ts
useShareWithUser()
useUpdateUserShare()
useRemoveUserShare()
useSharedWithMe()
useCreateShareLink()
```

### 9.9.4 可獨立測試項

1. email 空白不可送出。
2. permission 必須是 viewer、downloader、editor 其中之一。
3. 分享成功後顯示成功狀態。
4. 移除分享後列表更新。
5. 建立公開連結後可複製 URL。

### 9.10 Trash 前端模組

### 9.10.1 頁面與元件

```text
TrashPage
TrashToolbar
RestoreConfirmDialog
PermanentDeleteConfirmDialog
EmptyTrashConfirmDialog
```

### 9.10.2 Hooks

```ts
useTrashItems()
useRestoreItem()
usePermanentDelete()
useEmptyTrash()
```

### 9.10.3 可獨立測試項

1. 垃圾桶列表可顯示已刪除項目。
2. 還原成功後 item 從垃圾桶消失。
3. 永久刪除前必須確認。
4. 清空垃圾桶前必須確認。

### 9.11 Search 前端模組

### 9.11.1 責任

1. 上方搜尋列輸入。
2. debounce。
3. 呼叫搜尋 API。
4. 顯示搜尋結果。
5. 支援檔案/資料夾類型篩選。

### 9.11.2 Hooks

```ts
useSearchItems(query, filters, page, pageSize)
```

### 9.11.3 導覽行為

- 從非 `/search` 頁進入搜尋時，將來源路徑存入 navigate state `{ from: pathname }`。
- 後續 replace 導航（每次 keystroke）攜帶同一份 state 向前傳遞。
- 清空搜尋欄時讀取 `state.from` 精準導回，避免 `navigate(-1)` 因中間 replace history 退到上一個搜尋狀態。

### 9.11.4 可獨立測試項

1. 輸入關鍵字後 debounce 呼叫 API。
2. 清空關鍵字後不查詢，並導回搜尋前頁面。
3. 搜尋結果可開啟 preview 或資料夾。
4. 搜尋錯誤時顯示錯誤狀態。

## 10. 模組獨立測試策略

### 10.1 後端單元測試

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

### 10.2 後端整合測試

使用測試 PostgreSQL 或 testcontainers。LocalStorageProvider 使用 temporary directory。

整合測試重點：

1. migration 可成功執行。
2. 註冊登入流程。
3. 上傳檔案後資料庫與本機檔案一致。
4. 下載回來內容與上傳內容一致。
5. 分享權限生效。
6. 垃圾桶永久刪除會清理檔案。

### 10.3 前端單元測試

使用 Vitest + React Testing Library。

1. 表單驗證。
2. Zustand store 行為。
3. 元件 loading、empty、error 狀態。
4. context menu 顯示邏輯。
5. dialog 開關。

### 10.4 前端整合測試

使用 MSW mock API。

1. DrivePage 載入檔案列表。
2. 建立資料夾後列表刷新。
3. 上傳成功後列表刷新。
4. 分享彈窗送出成功。
5. 垃圾桶還原成功。

### 10.5 E2E 測試

使用 Playwright。

1. 使用者註冊與登入。
2. 建立資料夾。
3. 上傳檔案。
4. 預覽檔案。
5. 下載檔案。
6. 分享給另一位使用者。
7. 另一位使用者在「與我分享」看到檔案。
8. 刪除並還原檔案。

## 11. 錯誤碼設計

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

## 12. 非功能設計

### 12.1 安全

1. 所有檔案操作都必須由後端檢查權限。
2. 前端隱藏按鈕不代表授權。
3. 密碼使用 Argon2 hash。
4. JWT secret 必須由環境變數提供。
5. refresh token 資料庫只保存 hash。
6. share token 資料庫只保存 hash。
7. LocalStorageProvider 必須防止路徑穿越。
8. 上傳檔案大小限制由環境變數提供。
9. CORS origins 由環境變數提供。

### 12.2 效能

1. 檔案列表分頁。
2. 搜尋使用 pg_trgm。
3. 下載使用 StreamingResponse，避免一次讀入記憶體。
4. 前端搜尋 debounce。
5. 前端列表可在資料量增加時改為虛擬滾動。

### 12.3 可維護性

1. StorageProvider 可替換。
2. PermissionService 集中權限邏輯。
3. QuotaService 集中容量邏輯。
4. Service 層可用 mock repository 單元測試。
5. 前端 API 呼叫集中在 api module。

## 13. 第三階段擴充點

第三階段不納入主詳細設計，但保留以下擴充方向：

| 功能 | 擴充方式 |
| --- | --- |
| 管理員後台 | 使用 `users.is_admin`，另開 admin routers/pages |
| OAuth 登入 | AuthService 增加 OAuth provider，users 增加 provider identity 表 |
| WebSocket 通知 | 增加 NotificationService 與 websocket router |
| 全文檢索 | SearchService 底層替換為 PostgreSQL full-text 或 OpenSearch |
| 防毒掃描 | UploadService 上傳後送 background task |
| 檔案加密 | StorageProvider 寫入前加密、讀取後解密 |
| 團隊空間 | 增加 workspaces、workspace_members、workspace_drive_items |
| 桌面同步 | 另開 sync API 與 client，不影響現有 DriveService |

## 14. 未固定參數

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

## 15. 開發順序建議

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

## 16. 驗收對應

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

## 17. In-App AI Assistant M1 後端骨架

Assistant 後端第一個可執行切片位於 `backend/app/assistant/`，目標是先建立可測、可替換、預設安全的 agent loop。此切片尚未啟用寫入型 workflow、生成技能安裝或 sandbox 執行碼；所有已註冊內建技能皆為唯讀，且一律透過既有 service 層帶入 `user_id`。

主要檔案：

| 檔案 | 職責 |
| --- | --- |
| `assistant/router.py` | `POST /api/v1/assistant/chat`，檢查 `ASSISTANT_ENABLED`，將 request 交給 `AgentService`。 |
| `assistant/service.py` | AgentLoop：組 prompt、呼叫模型、執行 tool calls、回填 tool result、以 iteration 上限防止無限迴圈。 |
| `assistant/context.py` | 依 `LLM_NUM_CTX` 估算字元預算，保留 system prompt 與最新對話。 |
| `assistant/prompt.py` | 組穩定 system prompt，列出 registry 中可用技能。 |
| `assistant/llm/client.py` | `LLMClient` protocol 與 `LLMMessage`/`LLMResponse`/`LLMToolCall` 結構。 |
| `assistant/llm/ollama.py` | 呼叫本地 Ollama `/api/chat`，解析 Ollama tool call 格式。 |
| `assistant/llm/external.py` | OpenAI-compatible `/chat/completions` 外部 fallback client。 |
| `assistant/llm/privacy.py` | 隱私分類與基本去識別化；預設 `PRIVACY_DEFAULT=sensitive` 時禁止外送。 |
| `assistant/llm/router.py` | 本地模型重試、可接受性驗證 hook、達 `MAX_LOCAL_ATTEMPTS` 後依隱私閘決定是否升級外部。 |
| `assistant/skills/registry.py` | 技能註冊、LLM tool schema 轉換、handler dispatch。 |
| `assistant/skills/builtin/read_only.py` | `list_items`、`get_info`、`search`、`recent`、`storage_quota`。 |

新增設定：

| 環境變數 | 預設 | 說明 |
| --- | --- | --- |
| `ASSISTANT_ENABLED` | `true` | 停用時 `/assistant/chat` 回 503。 |
| `LLM_PROVIDER` | `ollama` | 目前保留設定；M1 使用 Ollama-compatible local client。 |
| `LLM_BASE_URL` | `http://localhost:11434` | 本地模型 base URL。 |
| `ASSISTANT_MODEL` | `gemma-4-26b` | 本地模型名稱。 |
| `LLM_NUM_CTX` | `8192` | Context 裁切預算。 |
| `ASSISTANT_MAX_TOOL_ITERATIONS` | `8` | AgentLoop tool-call 上限。 |
| `ASSISTANT_SANDBOX_TIMEOUT_SEC` | `30` | 後續 sandbox 預留設定。 |
| `EXTERNAL_LLM_ENABLED` | `false` | 外部 fallback 全域開關。 |
| `MAX_LOCAL_ATTEMPTS` | `3` | 本地模型連續失敗幾次後才評估外部升級。 |
| `EXTERNAL_LLM_BASE_URL` / `EXTERNAL_MODEL` / `EXTERNAL_LLM_API_KEY` | 空 | 外部 OpenAI-compatible client 設定。 |
| `PRIVACY_DEFAULT` | `sensitive` | 預設保守，不可去識別化時不外送。 |

M1 測試位於 `backend/tests/assistant/`，包含 router dispatch/auth、agent loop tool 執行與迴圈上限、context 裁切，以及 model router 的外部升級與隱私阻擋。

## 18. 結論

本詳細設計將系統拆分為 Auth、User/Quota、DriveItem、Permission、Storage、Upload、Download、Preview、Trash、Search、Share、FileVersion、ActivityLog 與前端對應模組。模組之間透過明確接口互動，避免彼此直接耦合。

MVP 可以先完成一般檔案上傳、下載、資料夾管理、垃圾桶、搜尋、星號與基本預覽。第二階段再補強指定使用者分享、公開連結、版本紀錄顯示、圖片縮圖與 PDF 預覽。第三階段功能只保留擴充點，不放入主開發範圍。

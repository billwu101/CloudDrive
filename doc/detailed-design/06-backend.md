## 6. 後端核心設計

本章描述後端的**核心模組**，逐一說明各模組的職責、Service 介面、流程與測試項。各模組依 §3.1 的分層協作（router → service → repository／storage），模組間只透過 service 注入溝通、不互相引用內部實作。

核心模組一覽：

| 模組 | 章節 | 職責 | repo 套件 |
| --- | --- | --- | --- |
| Core | §6.1 | 設定、JWT、密碼雜湊、DB session、錯誤格式、CORS | `app/core` |
| Auth | §6.2 | 註冊／登入／登出／refresh、忘記密碼（含 Email provider 抽象 `app/email`） | `app/auth`、`app/email` |
| User／Quota | §6.3 | 個人資料、密碼變更、容量統計 | `app/users` |
| DriveItem | §6.4 | 檔案／資料夾 CRUD、移動、星號、最近 | `app/drive` |
| Permission | §6.5 | 權限判斷（owner／editor／downloader／viewer） | `app/permission` |
| Storage | §6.6 | 二進位儲存抽象（LocalStorageProvider） | `app/storage` |
| Upload | §6.7 | 上傳（同步建全文索引、選用 embedding） | `app/upload` |
| Download | §6.8 | 單檔串流下載 + 多選 zip 打包 | `app/download` |
| Preview | §6.9 | 圖片／PDF／文字／影音 + Office 轉 PDF + Markdown | `app/preview` |
| Trash | §6.10 | 垃圾桶軟刪除、還原、永久刪除 | `app/trash` |
| Search | §6.11 | 全文搜尋（檔名＋內容）+ 語意搜尋（選用） | `app/search` |
| Share | §6.12 | 指定使用者分享 + 公開連結管理 + Shared by me | `app/share` |
| PublicShare | §6.12.8 | 公開連結的**免認證**存取端（訪客） | `app/public_share` |
| FileVersion | §6.13 | 檔案版本資料模型與 service | `app/file_version` |
| ActivityLog | §6.14 | 操作紀錄（稽核 + 「最近」來源） | `app/activity_log` |

**進階／獨立模組另立專章**（不在本章，但屬同一後端）：

- **In-App AI Assistant**（`app/assistant`）：HARNESS 引擎與 Workflow 管線見 §8、前端聊天切片見 §9、驗證評分 Harness 見 §10。
- **外部模型接入**（`app/external_model`）：per-user 加密憑證、Codex／OpenAI 升級與失敗回退（`_FallbackClient`）見 §11。
- **時光機 Snapshots**（`app/snapshot`）：整碟快照、自動排程、blob GC 與還原見 §12。

### 6.1 Core 模組

### 6.1.1 責任

Core 模組提供全系統共用能力：

1. 讀取環境變數。
2. 建立資料庫 session dependency。
3. JWT encode/decode。
4. 密碼雜湊與驗證。
5. 統一錯誤格式。
6. 取得目前登入使用者。
7. CORS、API prefix、app startup 設定（CORS 以 `expose_headers` 暴露 `Content-Disposition`，讓前端跨來源時仍能讀取下載 zip 的檔名）。

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
        new_parent_id: UUID | None,
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
    async def name_exists_in_parent(self, name: str, parent_id: UUID | None, owner_id: UUID, *, exclude_id: UUID | None = None) -> bool

class UserItemPreferenceRepository:
    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None
    async def upsert_preference(self, user_id: UUID, item_id: UUID, *, is_starred: bool) -> UserItemPreference
    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]
    async def get_all_starred_item_ids(self, user_id: UUID, *, limit: int) -> list[UUID]
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
| set starred | viewer；星號屬於使用者個人偏好 |
| delete to trash | owner 或 editor |

正式星號狀態以 `user_item_preferences.is_starred` 為準；`drive_items.is_starred` 僅為初始 schema 遺留/相容欄位，不作為回應與查詢的權威來源。這樣共享檔案時，每位使用者可有自己的星號狀態，不會互相污染。

**星號清單為全域查詢（`GET /drive/starred`）**：以 `user_item_preferences`（`user_id` + `is_starred=true`）為來源取得 item id，再逐一取回項目並濾掉已刪除／非本人擁有者——**與資料夾階層無關**，因此位於任何子資料夾的檔案加星後都會出現。實作模式與 §6.4「最近項目」一致（先取 id 清單再補齊項目）。前端**不得**以「列根目錄再過濾 `is_starred`」代替，那會漏掉子資料夾內與分頁外的項目。

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

    # 非同步串流寫入：來源是 async 位元組串流（FastAPI 上傳串流、分片串流），
    # 逐塊寫入暫存檔後原子改名，回傳實際寫入位元組數。
    async def save_stream(self, storage_key: str, chunks: AsyncIterator[bytes]) -> int:
        ...

    async def open_read(self, storage_key: str) -> BinaryIO:
        ...

    async def delete(self, storage_key: str) -> None:
        ...

    async def exists(self, storage_key: str) -> bool:
        ...

    async def get_size(self, storage_key: str) -> int:
        ...

    # 分片上傳（proposal §27）：把多個已落地的分片依序串接成一個正式物件。
    # 實作須「邊讀邊寫」，記憶體用量與檔案大小無關（不得先組成 bytes 再寫入）。
    async def concat(self, source_keys: list[str], target_key: str) -> int:
        ...
```

**串流寫入要求**：寫入端一律不得先在記憶體組出完整內容。`save` 收同步 `BinaryIO`，以固定緩衝區複製；`save_stream` 收 async 位元組串流，逐塊寫入。既有 `upload_simple` 曾以 `chunks: list[bytes]` 累積整檔再 `b"".join(...)`，記憶體用量 ≈ 檔案大小 ×2（大檔會 OOM）；因上傳來源是 async 串流、無法交給同步 `save`，故新增 `save_stream`，由 `upload_simple` 邊收邊寫並同步累積 sha256（proposal §27.3）。

**全文索引與串流的取捨**：`upload_simple` 串流化後不再持有整檔位元組，但全文索引需要檔案內容。因 `extract_text` 本就對超過 `DEFAULT_MAX_BYTES`（5 MB）的檔案回傳 `None`（不索引），服務只保留**上限 5 MB + 1 byte 的檔頭**供索引使用：小檔內容完整、超限檔的檔頭必然觸發原有的「過大不索引」分支，索引行為與串流化前完全一致，而記憶體用量與檔案大小脫鉤。

`concat` 供分片合併使用；`LocalStorageProvider` 以固定大小緩衝區依序讀取各分片、附加寫入目標檔，回傳總位元組數；任一來源缺漏即拋 `StorageKeyNotFoundError` 且不留下半成品或暫存檔。未來替換為物件儲存時，可改以原生 multipart complete 實作同一介面。

`open_read` 亦為**惰性串流**：逐塊讀取後 yield，不先把整檔讀進記憶體。分片合併後計算 checksum 與大檔下載都依賴這點，否則 5 GB 檔可以上傳卻會在讀取時吃爆記憶體。

`list_objects` 除排除 `.tmp-*` 外，另**排除 `uploads/` 前綴**（`UPLOAD_TEMP_PREFIX`）——見 §6.7.7 第 6 點。

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

大檔案分片續傳上傳見 §6.7.7（proposal §27 已將其由「擴充點」提升為正式功能）。

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

### 6.7.7 分片續傳上傳（UploadSessionService）

實作 proposal §27。資料表與狀態機見 §7.7、端點見 §13.5、前端流程見 §5。參數：分片 **8 MB**、單檔上限 **5 GB**、未完成保留 **7 天**、單檔分片**序列**送出。

```python
class UploadSessionService:
    async def create_session(
        self, user_id: UUID, *, filename: str, total_size: int,
        parent_id: UUID | None, mime_type: str | None,
    ) -> UploadSession:
        """建立工作階段。預檢：total_size <= 5 GB、目標資料夾存在且屬本人、
        配額足夠（已用 + 本次 + 其他未完成工作階段的佔用）。回傳含 chunk_size /
        total_chunks，前端據此切片。"""

    async def get_session(self, user_id: UUID, session_id: UUID) -> UploadSessionStatus:
        """續傳用：回傳狀態與**已完成的 chunk_index 清單**，前端只補送缺的分片。"""

    async def upload_chunk(
        self, user_id: UUID, session_id: UUID, chunk_index: int, stream: AsyncIterator[bytes]
    ) -> None:
        """把單一分片**串流寫入** storage 暫存 key，寫入/覆寫 upload_chunks（冪等）。
        終態工作階段拒絕；index 超出 total_chunks 拒絕。首個分片時 pending → uploading。"""

    async def complete_session(self, user_id: UUID, session_id: UUID) -> DriveItemResponse:
        """驗證分片齊全 → storage.concat 合併為正式 blob → 計算 checksum 與實際大小 →
        解析同層可用檔名 → 建立 drive_items + file_versions v1 → 實扣配額 →
        寫 activity log → 刪除暫存分片 → 標記 completed。"""

    async def cancel_session(self, user_id: UUID, session_id: UUID) -> None:
        """標記 cancelled 並刪除所有暫存分片（不佔配額）。"""

    async def cleanup_expired(self) -> int:
        """清理 expires_at 已過的 pending/uploading 工作階段：刪暫存分片與紀錄。
        回傳清理筆數。"""
```

**流程與規則**

1. **授權**：所有方法都以 `user_id` 過濾；他人的工作階段一律 `NOT_FOUND`（不洩漏存在性）。
2. **記憶體**：`upload_chunk` 串流寫入、`complete_session` 以 `storage.concat` 邊讀邊寫，**記憶體用量與檔案大小無關**。checksum 於合併時逐塊累積計算。
3. **配額**：建立時預檢、完成時實扣；取消／過期不扣。預檢須計入該使用者其他未完成工作階段的 `total_size`，避免多個大檔同時開啟而超賣。
4. **一致性**（同 §7.9 補償式）：合併出的正式 blob 若在 DB 階段失敗，立即刪除該 blob；暫存分片一律在 `completed`／`cancelled`／到期時刪除。
5. **清理排程**：`cleanup_expired` 由 `app/upload/scheduler.py` 的 `UploadCleanupScheduler` 呼叫（與快照排程同機制但**獨立排程器**，避免 snapshot 模組承載 upload 邏輯），預設每 24 小時一次，由 `UPLOAD_CLEANUP_SCHEDULER_ENABLED` 開關（預設關）。單一 worker 部署可直接開啟；多 worker 須改外部 cron，避免重複執行。
6. **暫存分片與內容 GC 的分工**：分片暫存於 `uploads/{user_id}/{session_id}/{index}`。這些 blob 刻意尚未被任何 `drive_item` 引用，若讓內容 GC 掃到會被判為孤兒而刪除，等於把使用者暫停中的上傳清掉。因此 `list_objects` **排除 `uploads/` 前綴**（與既有排除 `.tmp-*` 同理），該命名空間改由 `cleanup_expired` 負責回收。
7. **缺片時不進終態**：`complete_session` 驗出缺片時回 `INVALID_OPERATION` 但**不改狀態**，工作階段維持 `uploading`，client 補送缺片後可再次 `complete`——否則「續傳」在最後一步失去意義。`failed` 保留給無法補救的情況。

### 6.7.8 錯誤碼對應

前端據此分類顯示（proposal §27.2 第 6 點），不再一律顯示 `Network error`：

| 情境 | 錯誤碼 | HTTP |
| --- | --- | --- |
| 檔案超過單檔上限（5 GB） | `FILE_TOO_LARGE` | 413 |
| 配額不足 | `QUOTA_EXCEEDED` | 413 |
| 工作階段不存在／非本人 | `NOT_FOUND` | 404 |
| 對終態工作階段送分片 | `INVALID_OPERATION` | 422 |
| 完成時分片缺漏 | `INVALID_OPERATION` | 422 |

### 6.7.9 可獨立測試項

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

1. 驗證使用者權限（每個檔案各自經 `assert_can_download`）。
2. **單檔下載**：驗證 item 是 file，從 StorageProvider 讀取，使用 `StreamingResponse` 回傳。
3. **多選打包下載**：接受多個 item id（可同時含檔案與資料夾）；資料夾遞迴展開並保留目錄結構，逐檔權限檢查後打包成單一 zip 串流回傳。zip 以 `SpooledTemporaryFile` 緩衝（小檔留記憶體、大檔落暫存）避免整包佔用 RAM；頂層同名項自動去重（`a.txt` → `a (1).txt`），blob 缺失的檔案略過而非整批失敗。
4. **zip 檔名**：取自選取內容而非固定 `download.zip`——單選用該項目名（資料夾用資料夾名、檔案去副檔名），多選用「第一項名 等 N 項」；以 `Content-Disposition` 回傳。前端為 blob 下載、blob URL 不帶檔名，故需從此標頭解析檔名設給 `a.download`；當前端與後端跨來源時，後端 CORS 必須以 `expose_headers` 暴露 `Content-Disposition`，否則瀏覽器讀不到（見 §6.1.1）。
5. 寫入下載操作紀錄。

### 6.8.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/download/{item_id}` | 下載單一檔案（串流） |
| POST | `/api/v1/download/archive` | 多選打包為 zip（body：`{ "item_ids": [...] }`；資料夾遞迴、保留結構） |

### 6.8.3 Service 介面

```python
class DownloadService:
    async def download(self, user_id: UUID, item_id: UUID) -> DownloadFileResult
    async def archive(self, user_id: UUID, item_ids: list[UUID]) -> ArchiveResult
```

```python
@dataclass
class DownloadFileResult:
    filename: str
    mime_type: str
    size_bytes: int
    stream: AsyncGenerator[bytes, None]

@dataclass
class ArchiveResult:           # 多選 zip 打包（含資料夾遞迴，見 §6.8.1）
    filename: str
    stream: AsyncGenerator[bytes, None]
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

Preview 模組負責根據檔案 MIME type 判定預覽型別，並回傳預覽資訊與內容。

支援的預覽型別（後端 `_resolve_preview_type` 依 MIME 判定）：

1. 圖片（`image/*`）、影片（`video/*`）、音訊（`audio/*`）：`content` endpoint 直接串流原檔。
2. PDF（`application/pdf`）：串流原檔給前端 PDF viewer。
3. 文字（`text/*`，排除 `text/markdown`）：回傳文字內容。
4. **Markdown**（`text/markdown`／`.md`）：型別 `markdown`，`content` 回原始 Markdown 文字，由前端 react-markdown 渲染。
5. **Office 文書**（`docx/xlsx/pptx`、舊版 `doc/xls/ppt`、`csv`）：型別 `document`，`content` endpoint 以 **LibreOffice headless** 將原檔轉成 PDF 後串流，前端重用 PdfPreview 顯示；轉換按需產生並快取（見 §6.9.5）。
6. 不支援的類型：回傳 `unsupported`，前端顯示下載。

圖片縮圖等可透過 background task 進一步擴充。

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
  "preview_type": "image | pdf | document | text | markdown | video | audio | unsupported",
  "content_url": "/api/v1/drive/items/{item_id}/preview/content",
  "mime_type": "application/pdf"
}
```

`document` 與 `markdown` 為本次新增：`document` 的 `content` 是 LibreOffice 轉出的 PDF（`mime_type` = `application/pdf`），`markdown` 的 `content` 是原始 Markdown 文字。

### 6.9.5 文書轉換與快取（LibreOffice）

- **轉換器**：對 `document` 型，以 `soffice --headless --convert-to pdf` 子程序把原檔（docx/xlsx/pptx、doc/xls/ppt、csv）轉成 PDF；設逾時，失敗則退回 `unsupported`（前端顯示下載）。
- **按需 + 快取**：首次預覽時才轉（不在上傳時做，避免拖慢上傳、也避免轉了沒人看），結果以原檔 `checksum_sha256` 為鍵存入 storage（如 `preview-cache/{checksum}.pdf`）；同檔再次預覽直接回快取，原檔變更（checksum 變）自然換新鍵。
- **依賴**：backend 映像需安裝 LibreOffice（見 §21 部署）；無 LibreOffice 的環境，`document` 自動退化為 `unsupported`，不影響其他預覽（功能可關閉）。
- **安全／效能**：只轉使用者有權限的檔（沿用權限檢查）；轉換子程序設逾時、不需網路；CPU/IO 密集，靠快取攤平重複成本。

### 6.9.6 可獨立測試項

1. image MIME type 回傳 image preview。
2. pdf MIME type 回傳 pdf preview。
3. text MIME type 回傳 text preview。
4. `text/markdown` 回傳 `markdown` 型。
5. Office MIME（docx/xlsx/pptx/csv）回傳 `document` 型，`content` 為轉換後 PDF。
6. 轉換結果第二次預覽命中快取（不重轉）。
7. 不支援 MIME type 回傳 unsupported。
8. 無權限使用者不可取得 preview。
9. folder 不可 preview。

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

Search 模組提供使用者可存取檔案／資料夾的搜尋，分兩種：

1. **全文搜尋（預設啟用）**：搜尋**檔名**與**檔案內容**。上傳時自動抽取文字建索引（`file_search_index`），查詢時比對檔名與索引內容。
2. **語意搜尋（選用）**：以 embedding 向量做語意相近檢索（`file_embeddings` + pgvector），由 `EMBEDDING_ENABLED` 控制、預設關閉；未啟用時相關端點回 `503`。

兩者都只在使用者**有權限**（owner 或被分享）的範圍內搜尋，並排除垃圾桶。資料表見 §7.10／§7.11。

### 6.11.2 內容索引（全文）

- **建立時機**：上傳時於 `SearchIndexService.index_file` 同步建立——以 `extract_text` 抽取純文字後 upsert `file_search_index`（一檔一列，`item_id` 為 PK）。
- **可抽取型別**：純文字類（`txt/md/markdown/csv/tsv/json/log/xml/yaml/yml/html/htm/rst`，以及 `text/*`、`application/json`）與 **PDF**（pypdf，最多 50 頁）。其餘型別不索引內容，但仍可用檔名搜到。
- **保護上限**：單檔超過 5 MiB 不在上傳路徑同步抽取；內容截斷至 20 萬字，避免索引列膨脹。
- **失敗非致命**：抽取失敗或不支援只代表「不可內容搜尋」，不影響上傳；既有索引列會被清除。

### 6.11.3 API

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/v1/search` | 全文搜尋（檔名 + 內容），支援 `type`／`mime_type` 篩選與分頁 |
| GET | `/api/v1/search/semantic` | 語意搜尋（選用，未啟用回 `503`） |
| POST | `/api/v1/search/embeddings/backfill` | 為語意搜尋啟用前已存在的檔案補建 embedding（選用，未啟用回 `503`） |

`GET /search` Query：`q`（必填）、`type`（file／folder／all）、`mime_type`、`page`、`page_size`。

### 6.11.4 Service 介面

```python
class SearchService:                      # 全文搜尋
    async def search(self, user_id, query, *, item_type, mime_type, page, page_size) -> Page[DriveItemResponse]

class SearchIndexService:                 # 上傳時建索引（全文 + 選用 embedding）
    async def index_file(self, *, item_id, data, mime_type, extension) -> bool

class SemanticSearchService:              # 語意查詢（選用）
    async def search(self, *, user_id, query, limit) -> list[SemanticHit]   # SemanticHit(item, score, snippet)

class EmbeddingBackfillService:           # 舊檔補建 embedding（選用）
    async def run(self, *, user_id, batch_size) -> BackfillResult           # (indexed, remaining)
```

由 `app/search/factory.py` 依 `EMBEDDING_ENABLED` 組裝：未啟用時 `build_semantic_search_service`／`build_embedding_backfill_service` 回 `None`，router 轉 `503`。Embedding 經 `OllamaEmbeddingClient`（`EMBEDDING_BASE_URL` 預設沿用 `LLM_BASE_URL`）。

### 6.11.5 查詢設計

**全文（`SQLSearchRepository.search`）**：

1. 比對 `DriveItem.name ILIKE %q%` OR `FileSearchIndex.content ILIKE %q%`（子字串，涵蓋 CJK）OR `to_tsvector('english', content) @@ plainto_tsquery(q)`（英文詞幹）。
2. LEFT JOIN 索引表，讓「無內容索引的檔案」仍可用檔名命中。
3. 排除 `is_deleted = true`；限 owner 自己或被分享給自己的項目；支援 `type`／`mime_type` 篩選與分頁。

**語意（`SQLFileEmbeddingRepository.semantic_search`）**：

1. 長文於建索引時切塊（每塊 1000 字、重疊 100、最多 50 塊），逐塊 embedding 存 `file_embeddings`（best-effort，失敗不擋上傳）。
2. 查詢時將 query embedding 成向量，以 pgvector `cosine_distance` 找最近塊；每檔以 `DISTINCT ON (item_id)` 取其最相近塊後再排序。
3. 權限過濾（owner 或被分享、排除垃圾桶）；回 `SemanticHit(item, score = 1 − distance, snippet)`，snippet 為最相近塊的預覽文字。

### 6.11.6 可獨立測試項

1. 全文：可用檔名找到自己的檔案。
2. 全文：可用**檔案內容**找到自己的檔案（內容已索引）。
3. 全文：可找到分享給自己的檔案；找不到未分享的他人檔案。
4. 全文：垃圾桶檔案不出現；`type`／`mime_type` 篩選有效。
5. 索引：上傳支援型別會建 `file_search_index`；不支援型別不建、仍可檔名搜。
6. 語意：未啟用時 `/search/semantic`、`/embeddings/backfill` 回 `503`。
7. 語意：啟用時依相似度排序、含 score 與 snippet（需 embedding 服務）。

### 6.12 Share 模組

### 6.12.1 責任

Share 模組負責分享檔案或資料夾，含三條互相獨立的路徑：

**A. 指定使用者分享（需登入）**

1. 分享給指定使用者。
2. 設定權限：viewer、downloader、editor。
3. 移除指定使用者分享。
4. 取得與我分享列表。
5. 取得**我分享出去的**列表（§6.12.12，proposal §29）。

**B. 公開連結的管理端（需登入，由分享者操作）**

1. 建立公開分享連結。
2. 分享連結密碼（選填）。
3. 分享連結到期時間（選填）。
4. 停用分享連結。

**C. 公開連結的存取端（不需登入，由收到連結的訪客操作）**

由 `app/public_share`（§6.12.8–§6.12.11，proposal §28）負責。這是系統中**唯一對外免認證**的路徑，與 A/B 分開成獨立套件，避免免認證邏輯與需登入的 router 混在同一檔而誤用 `CurrentUserId`。

### 6.12.2 API

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/api/v1/share/items/{item_id}/users` | 分享給指定使用者 |
| PATCH | `/api/v1/share/items/{item_id}/users/{target_user_id}` | 更新分享權限 |
| DELETE | `/api/v1/share/items/{item_id}/users/{target_user_id}` | 移除指定分享 |
| GET | `/api/v1/share/shared-with-me` | 與我分享 |
| GET | `/api/v1/share/shared-by-me` | 我分享出去的項目（§6.12.12） |
| POST | `/api/v1/share/items/{item_id}/links` | 建立公開連結 |
| DELETE | `/api/v1/share/links/{link_id}` | 停用公開連結（保留記錄） |
| DELETE | `/api/v1/share/links/{link_id}/record` | 刪除已失效的連結記錄（§6.12.12 第 5 點） |

免認證的訪客存取端點另見 §6.12.9（`/api/v1/public/*`）。

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
6.1 **非 owner 不可停用他人的公開連結**（`deactivate_link` 必須自行驗證擁有權——舊註解宣稱由 router 把關，實際上沒有）。
7. 建立公開連結時資料庫不保存明文 token。
8. 到期連結不可使用。
9. 密碼錯誤不可使用分享連結。

### 6.12.8 PublicShare 模組（免認證存取端）

對應 proposal §28。套件 `app/public_share/`，掛在 `/api/v1/public`，**整個 router 不依賴 `CurrentUserId`**。

實作 proposal §28.7 決策 1：訪客先用 token（必要時加密碼）換一張**短效存取憑證**，之後的預覽／下載都帶憑證，不再重送密碼。

#### 存取憑證（share access token）

沿用 `app/core/security.py` 的 JWT 機制，但以 `type` claim 區隔：

```text
type = "share_access"      # 不是 "access"，故無法冒充使用者權杖
sub  = str(share_link_id)  # 授權來源是連結，不是使用者
itm  = str(root_item_id)   # 授權子樹的根
prm  = "viewer" | "downloader"
exp  = 簽發時間 + SHARE_ACCESS_TOKEN_EXPIRE_MINUTES（預設 15 分鐘）
iss_at_chain = 首次簽發時間（續發時原樣沿用，用於封頂總時長）
```

`_decode_token` 已在 `type` 不符時丟 `UnauthorizedError`，因此 `decode_access_token` 不會接受 share access token，`get_current_user_id` 也不會（**這是本設計免於權限提升的關鍵，需有測試守住**）。反向亦然：使用者的 access token 不能當 share access token 用。

**續發**：`POST /public/links/{token}/session/refresh` 以未過期的舊憑證換新，總時長上限 `SHARE_ACCESS_TOKEN_MAX_LIFETIME_MINUTES`（預設 240 分鐘）。設計理由：憑證若做長效，等同把密碼保護降級為一次性關卡；若做短效又不能續發，前端就得把密碼留在 `sessionStorage` 才能無縫續看，違反 proposal §28.3 第 3 點。續發只延長「已通過驗證」的狀態，不重新授權。

**憑證不取代 DB 檢查**：proposal §28.3 第 5 點要求每次存取都驗證。因此每個內容請求除了驗簽，都必須重查 `share_links` 確認 `is_active` 且未過期——分享者按下停用後，尚未過期的憑證必須立刻失效。

#### 6.12.9 API

| Method | Path | 說明 | 認證 |
| --- | --- | --- | --- |
| POST | `/api/v1/public/links/{token}/session` | 驗證 token（+密碼）→ 發存取憑證 | 🔓 |
| POST | `/api/v1/public/links/{token}/session/refresh` | 以未過期憑證續發 | 🎫 |
| GET | `/api/v1/public/items` | 連結根項目中繼資料 | 🎫 |
| GET | `/api/v1/public/items/{item_id}/children` | 瀏覽資料夾子樹（唯讀、分頁） | 🎫 |
| GET | `/api/v1/public/items/{item_id}/preview` | 線上預覽 | 🎫 |
| GET | `/api/v1/public/items/{item_id}/download` | 下載原檔 | 🎫 + downloader |
| GET | `/api/v1/public/archive` | 子樹整包 zip | 🎫 + downloader |

🎫 = `Authorization: Bearer <share access token>`。

`POST .../session` 的回應同時帶回根項目中繼資料，讓「未設密碼的連結」只需一次往返即可顯示內容（proposal §28.7 末段：未設密碼不出現密碼輸入步驟）。

`/public/items/{id}/preview` 直接串流內容（Office 轉 PDF、文字截斷等邏輯由 `PreviewService.content_for_item()` 提供——該方法由既有 `get_content()` 抽出，接收「呼叫端已授權的 item」，避免在公開路徑重寫一份）。前端要選哪個檢視器，看 `/public/items` 回傳的 `preview_type`。

`/public/archive` 重用 §6.8.1 既有的 zip 打包能力（proposal §28.7 決策 3），差別只在項目來源是憑證授權的子樹而非使用者選取，且**不做 owner 權限檢查**（改由憑證的子樹邊界把關）。

#### 6.12.10 Service 介面

```python
class PublicShareService:
    async def open_session(
        self, token: str, password: str | None
    ) -> PublicSessionResult          # 憑證 + 根項目中繼資料

    async def refresh_session(self, access_token: str) -> PublicSessionResult

    async def get_item(self, access_token: str, item_id: UUID | None) -> DriveItem
    async def list_children(
        self, access_token: str, item_id: UUID, page: int, page_size: int
    ) -> Page[DriveItem]
    async def open_content(self, access_token: str, item_id: UUID) -> ContentStream
    async def build_archive(self, access_token: str) -> ArchiveResult
```

#### 6.12.11 安全規則（proposal §28.3 的實作對應）

1. **不可枚舉、不可區分**：token 不存在、連結已停用、已過期、密碼錯誤——**四者一律回同一個 `404 SHARE_LINK_INVALID`**，訊息相同。token 查無此筆時仍執行一次 dummy `verify_password`，讓「不存在」與「密碼錯」的回應時間落在同一量級（`pwdlib` 的雜湊成本是此處主要時間來源）。

   **唯一的例外**是「連結有效、有設密碼、但呼叫端沒帶密碼」——即 §28.4 流程圖的第一次請求。這回 `401 SHARE_LINK_PASSWORD_REQUIRED`，否則前端無從決定要不要顯示密碼欄。此回應確實透露「此 token 存在且有密碼」，但不透露密碼是否正確，也不讓「密碼錯」與「token 不存在」變得可區分；token 有 256 bits 亂度，靠這點差異枚舉不可行。**此探測不計入速率限制**（未驗證任何憑證），否則使用者光是打開頁面就先耗掉一次額度。
2. **不洩漏存在性**：驗證通過前不回傳任何項目欄位。故根項目中繼資料只出現在 `session` 的**成功**回應中，`GET /public/items` 也一律要求憑證。
3. **密碼傳遞與儲存**：密碼只走 `POST` body，不得進 URL／query／log；例外處理不得把 body 寫入日誌。儲存改用 `core.security.hash_password`（`pwdlib`，加鹽、常數時間比對），不再沿用 token 用的裸 SHA-256——高亂度 token 用 SHA-256 沒問題，使用者自選的密碼不行。**既有連結的密碼會因此失效**；因為本章之前根本沒有存取端點，這些密碼從未被成功驗證過，無實際影響。
4. **最小授權（子樹邊界）**：每次帶 `item_id` 的請求都必須驗證該項目位於憑證 `itm` 的子樹內（含自身），以遞迴 CTE 上溯 `parent_id` 比對；不在子樹內回 `404`（非 403，避免確認該 id 存在）。已在垃圾桶的項目視同不存在。
5. **權限不被提升**：權限一律取自連結的 `prm`，**絕不查詢 `created_by` 是否為 owner**。`viewer` 呼叫 download／archive 回 `403 FORBIDDEN`。
6. **速率限制**：每個連結每分鐘最多 5 次 `session` 嘗試（proposal §28.7 決策 2），超過鎖定 5 分鐘，鎖定期間一律回同一則錯誤。計數狀態存在 `share_links` 資料列上（§7.6），**不放記憶體**——本專案為多 worker 部署，行程內計數會讓限制隨 worker 數放大。成功驗證不重置計數窗，只有窗過期才重置；`refresh` 不計入（它需要已簽發的憑證，不是猜測管道）。

設定項：

| 環境變數 | 預設 | 用途 |
| --- | --- | --- |
| `SHARE_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | 存取憑證有效期 |
| `SHARE_ACCESS_TOKEN_MAX_LIFETIME_MINUTES` | `240` | 續發總時長上限 |
| `SHARE_LINK_ATTEMPT_LIMIT` | `5` | 每分鐘驗證嘗試上限 |
| `SHARE_LINK_LOCKOUT_MINUTES` | `5` | 超限後鎖定時間 |

#### 可獨立測試項

1. 未設密碼的連結可直接換到憑證，回應含根項目中繼資料。
2. 有密碼的連結，密碼錯誤與 token 不存在的回應狀態碼、錯誤碼、訊息完全相同。
3. 憑證無法被 `get_current_user_id` 接受（不可冒充使用者）。
4. 使用者 access token 無法存取 `/public/*`。
5. `viewer` 憑證下載原檔回 403；`downloader` 成功。
6. 以憑證存取子樹以外的 item id 回 404。
7. 分享者停用連結後，尚未過期的憑證立即失效。
8. 第 6 次驗證嘗試被鎖定；鎖定期滿後恢復。
9. 續發不能突破總時長上限。
10. `downloader` 的資料夾連結可取得 zip，且 zip 內不含子樹以外項目。

### 6.12.12 Shared by me（我分享出去的項目）

對應 proposal §29。屬需登入路徑，放在既有 ShareService。

```python
class ShareService:
    async def list_shared_by_me(
        self, user_id: UUID, page: int, page_size: int
    ) -> Page[SharedByMeEntry]
```

```python
@dataclass
class SharedByMeUserShare:
    target_user_id: UUID
    email: str
    display_name: str | None
    permission: str
    created_at: datetime

@dataclass
class SharedByMeLink:
    link_id: UUID
    permission: str
    has_password: bool          # 只回布林，不回 hash
    expires_at: datetime | None
    is_active: bool             # 已停用或已過期皆為 False
    created_at: datetime

@dataclass
class SharedByMeEntry:
    item: DriveItem
    user_shares: list[SharedByMeUserShare]
    links: list[SharedByMeLink]
```

規則：

1. **一項目一列**（proposal §29.5 決策 1）：以 `item_id` 聚合 `shares` 與 `share_links`，同一項目的多筆分享收在同一個 entry 的兩個清單裡。
2. **排除垃圾桶**：`drive_items.is_deleted = true` 的項目不列出（proposal §29.2 第 6 點）。
3. **已停用／過期的連結仍列出**，以 `is_active=false` 呈現，讓使用者知道那條連結曾經存在；`shares` 移除後即消失（無軟刪除）。
4. **無批次收回**（proposal §29.5 決策 3）：本端點唯讀，移除／停用沿用既有 `DELETE /share/items/{id}/users/{uid}` 與 `DELETE /share/links/{link_id}`。
5. **移除連結**：`DELETE /api/v1/share/links/{link_id}/record` 把整筆 `share_links` 刪掉，**仍有效的連結也接受**（proposal §29.5 決策 4，2026-07-27 翻案）。刪除該列即是撤銷：`open_session` 以 token hash 查該列、`_authorize` 以 link id 查該列，列不存在一律回 `404 SHARE_LINK_INVALID`。與所有分享管理端點一樣要驗證擁有權。
   - `DELETE /api/v1/share/links/{link_id}`（停用、保留記錄）仍保留於 API，但前端不再使用；連結顯示為「已失效」因此只剩「已過期」一種來源。
5. 查詢以 `item_id IN (...)` 批次撈取，避免 N+1。

#### My Drive 標記

proposal §29.2 第 5 點要求在檔案列表標示已分享項目。`DriveItemResponse` 新增兩個布林欄位：

| 欄位 | 說明 |
| --- | --- |
| `is_shared_with_users` | 該項目有至少一筆 `shares` |
| `has_active_public_link` | 該項目有至少一條**仍有效**的公開連結（`is_active` 且未過期） |

兩者分開而非合併成單一 `is_shared`，因為前端要用兩種圖示分別呈現（proposal §29.5 決策 2）。由 `DriveService.list_items` 在組回應時以**一次**批次查詢填入（對當頁的 item id 做 `IN` 查詢），不逐列查。非 owner 檢視他人分享來的項目時兩者皆為 `false`——這是分享者自己的狀態，不對被分享者揭露。

#### 可獨立測試項

1. 分享給使用者後該項目出現在 `shared-by-me`，含對象與權限。
2. 建立公開連結後該項目出現，且 `has_password` 正確、不回傳 hash。
3. 同一項目分享給 3 人 + 1 條連結 → 只回 1 個 entry，`user_shares` 長度 3。
4. 項目丟垃圾桶後不再列出。
5. 連結停用後仍列出但 `is_active=false`。
6. `list_items` 回傳的兩個標記欄位正確，且不隨列數增加而增加查詢次數。
7. 已停用的連結記錄可被刪除，刪除後不再出現在 `shared-by-me`。
8. 仍有效的連結可直接移除，且移除後訪客端立即失效；非 owner 不可移除他人的連結。

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

### 6.15 Repository 介面（全模組完整方法）

各模組資料存取層 `AbstractXxxRepository` 的完整方法。auth／drive 另見 §6.2.4／§6.4.3 的就地說明；進階模組 assistant／external_model／snapshot 的 repository 也一併集中於此以便對照 code。下列方法**皆為 `async`**，為精簡省略 `self`／`async def`，格式為 `方法(參數) -> 回傳`。

```python
# auth（app/auth）
UserRepository:
    get_by_email(email) -> User | None
    get_by_id(user_id) -> User | None
    create(*, email, username, password_hash, quota_bytes) -> User
    reset_password(user_id, password_hash) -> None
RefreshTokenRepository:
    create(*, user_id, token_hash, expires_at) -> RefreshToken
    get_by_hash(token_hash) -> RefreshToken | None
    revoke(token_id) -> None

# users（app/users）
UserRepository:
    get_by_id(user_id) -> User | None
    get_by_email(email) -> User | None
    update_username(user_id, username) -> User
    update_email(user_id, email) -> User
    update_password(user_id, password_hash) -> User
    add_used_bytes(user_id, delta) -> None
    subtract_used_bytes(user_id, delta) -> None
    recalculate_used_bytes(user_id) -> int
    list_all_ids() -> list[UUID]

# permission（app/permission；操作 share 表判斷權限）
ShareRepository:
    get_by_item_and_user(item_id, user_id) -> Share | None
    delete_by_item(item_id) -> None

# drive（app/drive；見 §6.4.3）
DriveItemRepository:
    get_by_id(item_id) -> DriveItem | None
    list_children(parent_id, owner_id, *, sort_by, order, offset, limit) -> tuple[list[DriveItem], int]
    create(*, owner_id, parent_id, item_type, name, created_by) -> DriveItem
    update_name(item_id, name, updated_by) -> DriveItem
    update_parent(item_id, parent_id, updated_by) -> DriveItem
    name_exists_in_parent(name, parent_id, owner_id, *, exclude_id) -> bool
    get_preference(user_id, item_id) -> UserItemPreference | None
    upsert_preference(user_id, item_id, *, is_starred) -> UserItemPreference
    get_starred_ids(user_id, item_ids) -> set[UUID]
    get_all_starred_item_ids(user_id, *, limit) -> list[UUID]

# file_version（app/file_version）
FileVersionRepository:
    create(*, file_id, version_no, storage_key, size_bytes, checksum_sha256, created_by) -> FileVersion
    get_max_version_no(file_id) -> int
    list_by_file(file_id) -> list[FileVersion]
    delete_by_file(file_id) -> None

# search（app/search；內容索引/語意 repo 見 §6.11）
SearchRepository:
    search(user_id, query, *, item_type, mime_type, offset, limit) -> tuple[list[DriveItem], int]

# share（app/share）
ShareRepository:
    create(*, item_id, owner_id, target_user_id, permission) -> Share
    get_by_item_and_user(item_id, user_id) -> Share | None
    update_permission(share_id, permission) -> Share
    delete(share_id) -> None
    delete_by_item(item_id) -> None
    list_shared_with_me(user_id, *, offset, limit) -> tuple[list[Share], int]
ShareLinkRepository:
    create(*, item_id, token_hash, permission, password_hash, expires_at, created_by) -> ShareLink
    get_by_token_hash(token_hash) -> ShareLink | None
    deactivate(link_id) -> None

# trash（app/trash）
TrashRepository:
    mark_deleted(item_id, deleted_at) -> DriveItem
    mark_restored(item_id) -> DriveItem
    list_deleted(owner_id, *, offset, limit) -> tuple[list[DriveItem], int]
    get_all_deleted(owner_id) -> list[DriveItem]
    hard_delete(item_id) -> None
    get_children_recursive(item_id) -> list[DriveItem]

# activity_log（app/activity_log）
ActivityLogRepository:
    create(*, actor_id, item_id, action, metadata, ip_address, user_agent) -> ActivityLog
    list_by_actor(actor_id, *, limit) -> list[ActivityLog]
    list_by_item(item_id, *, limit) -> list[ActivityLog]
    get_recent_item_ids(actor_id, *, limit, exclude_item_ids) -> list[UUID]

# assistant（app/assistant；skills/sessions/messages/workflows 共用一個 repo，見 §8）
AssistantRepository:
    get_by_id(*, user_id, skill_id) -> AssistantSkill | None
    get_by_name(*, user_id, name) -> AssistantSkill | None
    list_by_status(*, user_id, status) -> list[AssistantSkill]
    create_or_replace_pending(*, user_id, name, description, manifest, code) -> AssistantSkill
    approve(*, user_id, skill_id) -> AssistantSkill | None
    update(*, user_id, skill_id, description, manifest, code) -> AssistantSkill | None
    delete(*, user_id, skill_id) -> bool
    ensure_session(*, user_id, session_id, title) -> AssistantSession
    add_message(*, session_id, role, content, tool_calls) -> AssistantMessage
    list_sessions(*, user_id) -> list[AssistantSession]
    list_messages(*, user_id, session_id) -> list[AssistantMessage]
    create_pending(*, user_id, session_id, source_nl, steps) -> AssistantWorkflow
    get_pending(*, user_id, workflow_id) -> AssistantWorkflow | None
    set_status(*, workflow, status) -> None
    record_run(*, user_id, workflow_id, source_nl, status, step_results) -> AssistantWorkflowRun
    save_named(*, user_id, name, source_nl, steps) -> AssistantWorkflow
    list_saved(*, user_id) -> list[AssistantWorkflow]
    get_saved(*, user_id, workflow_id) -> AssistantWorkflow | None

# external_model（app/external_model；見 §11）
ExternalCredentialRepository:
    list_by_user(user_id) -> list[UserExternalCredential]
    get(user_id, provider) -> UserExternalCredential | None
    upsert(*, user_id, provider, auth_type, secret_encrypted, masked_hint, updated_at) -> None
    delete(user_id, provider) -> None
    set_status(user_id, provider, status) -> None

# snapshot（app/snapshot；見 §12）
SnapshotRepository:
    list_owner_items(owner_id) -> list[DriveItem]
    list_all_items(owner_id) -> list[DriveItem]
    create_snapshot(*, user_id, trigger, label, pinned, item_count, total_bytes, entries) -> Snapshot
    list_snapshots(user_id) -> list[Snapshot]
    get_snapshot(*, user_id, snapshot_id) -> Snapshot | None
    list_entries(*, snapshot_id, parent_item_id) -> list[SnapshotEntry]
    list_all_entries(snapshot_id) -> list[SnapshotEntry]
    upsert_item(*, owner_id, entry) -> None
    set_deleted(*, item_id, deleted) -> None
    delete_snapshot(snapshot_id) -> None
    get_settings(user_id) -> SnapshotSettings | None
    upsert_settings(*, user_id, retention_n, schedule_enabled, schedule_interval_minutes, quota_bytes) -> SnapshotSettings
    get_user_quota_bytes(user_id) -> int
    used_snapshot_bytes(user_id) -> int
    referenced_storage_keys() -> set[str]
    is_referenced_by_snapshot(storage_key) -> bool
```

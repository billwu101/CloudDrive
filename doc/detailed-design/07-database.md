## 7. 資料庫詳細設計

### 7.0 欄位型別與長度原則

資料庫欄位使用 `varchar` 或 `text` 的原則如下：

| 類型 | 建議型別 | 依據 |
| --- | --- | --- |
| 枚舉狀態、短代碼 | `varchar(20~100)` | 例如 `status`、`permission`、`item_type`，長度有限且常用於索引或檢查 |
| Email、username、hash、token hash | `varchar(255)` | 255 是常見帳號識別欄位上限，可避免異常長字串 |
| 檔名 | `varchar(512)` | 檔案系統與瀏覽器上傳可能出現較長名稱，仍需上限防止濫用 |
| checksum | `varchar(64)` | SHA-256 hex 固定 64 字元 |
| MIME type | `varchar(255)` | MIME type 字串長度有限 |
| 使用者輸入長文、manifest code、storage key、URL、加密 secret | `text` | 長度不固定，不適合硬切；由 service 層與欄位用途控制 |
| 結構化流程、metadata | `jsonb` | 方便保存 workflow steps、activity metadata、manifest 等半結構化資料 |

長度選擇不是任意值：`50` 多用於狀態/類型，`100~200` 用於技能或 workflow 名稱，`255` 用於帳號、hash 或外部識別字，`512` 用於檔名。各表欄位依此原則，並結合「業務意義 + 防止不受控輸入 + 索引效率」決定。

### 7.1 users

```text
id uuid primary key
email varchar(255) unique not null
username varchar(255) not null
password_hash varchar(255) not null
avatar_url text null
quota_bytes bigint not null
used_bytes bigint not null default 0
is_active boolean not null default true
is_admin boolean not null default false
created_at timestamptz not null
updated_at timestamptz not null
```

型別/長度依據（通用原則見 §7.0；需求見 proposal §16）：
- `email` / `username` / `password_hash` → `varchar(255)`：帳號識別與雜湊欄位上限 255 字元（避免異常長字串、利於索引）。
- `avatar_url` → `text`：URL 長度不定，不硬切。
- `quota_bytes` / `used_bytes` → `bigint`：以位元組計的容量需大整數範圍。

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
is_starred boolean not null default false -- legacy compatibility; canonical source is user_item_preferences
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

### 7.3.1 user_item_preferences

```text
id uuid primary key
user_id uuid not null references users(id) on delete cascade
item_id uuid not null references drive_items(id) on delete cascade
is_starred boolean not null default false
created_at timestamptz not null
updated_at timestamptz not null
unique(user_id, item_id)
```

此表是星號狀態的 canonical source。Drive/Search 回應中的 `is_starred` 需依目前使用者查詢此表後填入。

`drive_items.is_starred` 為初始 schema 的**遺留／相容欄位**，不作為回應與查詢的權威來源；保留它只為相容，新邏輯一律以本表為準。星號之所以每使用者獨立，是為了讓**分享檔案時各使用者的星號互不影響**（避免一人加星污染他人看到的狀態）。見[附錄 A](./appendix-a-decisions.md) DEC-004、DEC-027。

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

-- 讓擁有者事後仍能取回原網址（proposal §29.2 第 7 點、§29.2.1）
-- Fernet 密文，金鑰為 CREDENTIAL_ENCRYPTION_KEY，不存於 DB。
-- 可為 null：本欄位加入之前建立的連結沒有可還原的值。
token_encrypted varchar null

-- 驗證嘗試速率限制（proposal §28.7 決策 2、設計 §6.12.11 第 6 點）
attempt_window_start timestamptz null
attempt_count int not null default 0
locked_until timestamptz null
```

約束：

```sql
ALTER TABLE share_links
ADD CONSTRAINT ck_share_links_permission
CHECK (permission IN ('viewer', 'downloader', 'editor'));
```

速率限制計數存在資料列上而非行程記憶體：正式部署為多 worker，行程內計數會讓「每分鐘 5 次」實際變成「每分鐘 5 × worker 數」。三個欄位由 `PublicShareService.open_session` 在同一個交易內讀取並更新。

### 7.7 upload_sessions 與 upload_chunks

大檔案分片續傳上傳（proposal §27）。工作階段存於 DB、分片本體存於 storage，因此**關閉瀏覽器後仍可續傳**（proposal §27.2）。參數依 §27.7：分片 **8 MB**、單檔上限 **5 GB**、未完成保留 **7 天**。

```text
upload_sessions
id uuid primary key
user_id uuid not null references users(id)
parent_id uuid null references drive_items(id)      -- 目標資料夾；null = 根目錄
filename varchar not null                            -- 使用者原始檔名（完成時才做同層去重）
mime_type varchar null
total_size bigint not null                           -- 客戶端宣告大小，建立時據此預檢配額與上限
chunk_size integer not null                          -- 本工作階段固定的分片大小
total_chunks integer not null
status varchar not null                              -- pending | uploading | completed | failed | cancelled
checksum_sha256 varchar null                         -- 合併完成後計算，寫入 drive_items/file_versions
drive_item_id uuid null references drive_items(id)   -- 完成後對應的檔案
error_code varchar null                              -- 失敗原因（對應 §15 錯誤碼）
created_at timestamptz not null
updated_at timestamptz not null
expires_at timestamptz not null                      -- created_at + 7 天；到期由清理任務回收
```

```text
upload_chunks
id uuid primary key
session_id uuid not null references upload_sessions(id) on delete cascade
chunk_index integer not null                         -- 0-based
size integer not null
checksum_sha256 varchar null
storage_key varchar not null                         -- 暫存分片在 storage 的 key
created_at timestamptz not null
```

索引與約束：

```sql
-- 續傳查詢與清單
CREATE INDEX idx_upload_sessions_user_status
ON upload_sessions(user_id, status, created_at DESC);

-- 到期清理掃描
CREATE INDEX idx_upload_sessions_expires
ON upload_sessions(expires_at)
WHERE status IN ('pending', 'uploading');

-- 同一分片只能有一筆，重送同 index 視為冪等覆寫
CREATE UNIQUE INDEX uq_upload_chunks_session_index
ON upload_chunks(session_id, chunk_index);
```

**狀態機**

```text
pending ──(收到第一個分片)──> uploading ──(complete 成功)──> completed
   │                              │
   └──────────────┬───────────────┘
                  ├──(使用者取消)──> cancelled
                  ├──(complete 驗證失敗 / 逾時)──> failed
                  └──(超過 expires_at)──> 由清理任務刪除（連同暫存分片）
```

`completed`／`cancelled`／`failed` 為終態；終態的工作階段不接受再上傳分片。**暫停**不是狀態——前端停止送分片即可，伺服器端仍是 `uploading`，續傳時直接接著送未完成的 index。

**設計要點**

- **續傳依據**：查詢工作階段時回傳「已存在的 `chunk_index` 清單」，前端據此**只送缺的分片**（§13 端點）。
- **冪等**：重送同一 `chunk_index` 覆寫該分片（`ON CONFLICT` 更新），使重試安全。
- **配額**：建立工作階段時以 `total_size` **預檢**（含既有未完成工作階段的佔用量），避免傳完才發現超額；`completed` 時才實扣 `used_bytes`。
- **一致性**：合併成正式 blob 後才建立 `drive_items`／`file_versions`；DB 階段失敗則刪除已合併 blob（補償回滾，同 §7.9）。取消與到期清理都必須刪除暫存分片，避免孤兒檔。
- **同層檔名衝突**：於 `complete` 階段才做自動改名（`name (1)` 等），與 simple upload 一致——建立工作階段時的檔名僅供顯示。

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

### 7.9 metadata 與 storage 一致性

DB metadata 與實體 blob 分屬 PostgreSQL 與檔案系統，**檔案操作不在 DB transaction 內**，因此採**補償式一致性**（非分散式交易）：

- **上傳**：先寫 blob 到 storage，再建立 `drive_items`／`file_versions`／配額 metadata；若 DB 階段失敗，service 立即刪除剛寫入的 blob（補償回滾），避免「有檔案、無紀錄」的孤兒 blob。
- **刪除**：永久刪除時先移除 metadata 與配額，再依快照引用判斷 blob 是否可刪；若 blob 仍被快照引用、或無法證明可安全刪除，則**保留交由背景 GC**（依 checksum 引用計數回收），優先避免誤刪仍可還原的內容。
- **殘留風險與補強**：極端中斷仍可能留下孤兒 blob 或缺失 blob，故正式環境可加**定期 storage audit** 產生孤兒／缺失報告；`activity_logs` 為輔助稽核、不阻塞主流程。

見[附錄 A](./appendix-a-decisions.md) DEC-027。

### 7.10 file_search_index

```text
item_id uuid primary key references drive_items(id) on delete cascade
content text not null default ''
updated_at timestamptz not null
```

檔案抽取出的純文字內容，供全文搜尋（§6.11）。一檔一列、隨 drive item 一併 cascade 刪除；`content` 同時供 `ILIKE` 子字串比對（涵蓋 CJK）與 `to_tsvector('english', …)` 英文全文檢索。

### 7.11 file_embeddings

```text
id uuid primary key
item_id uuid not null references drive_items(id) on delete cascade
chunk_index integer not null default 0
snippet text not null default ''
embedding vector(768) not null
model varchar(100) not null default ''
updated_at timestamptz not null
```

語意搜尋（選用）用的向量表：長文切塊後**一塊一列**（`chunk_index`）。`embedding` 為 pgvector `vector(768)`（須與 `EMBEDDING_MODEL` 輸出維度一致，預設 `nomic-embed-text` = 768）；`snippet` 為該塊預覽文字（搜尋結果顯示用）。查詢以 `cosine_distance` 取每檔最近塊。需 `CREATE EXTENSION vector`（migration 0012）。

索引：

```sql
CREATE INDEX idx_file_embeddings_item_id ON file_embeddings(item_id);
```

### 7.12 Schema 演進（Migrations）

資料庫 schema 由 Alembic 管理（`backend/alembic/versions/`），為**單一連續 revision 鏈、無分支**，head 為 `0019`（`0020` 為本次規劃、尚未實作）。下表為完整演進（亦可作為「migration → 對應文件章節」的覆蓋對照）：

| Rev | 變更 | 對應章節 |
| --- | --- | --- |
| 0001 | 初始 schema：建 8 張核心表（`users`、`refresh_tokens`、`drive_items`、`file_versions`、`shares`、`share_links`、`activity_logs`、`user_item_preferences`） | §7.1–7.8、7.3.1 |
| 0002 | `activity_logs.ip_address` 由 `INET` 改 `varchar(45)` | §7.8 |
| 0003 | `item_type` 值大寫化（`file`/`folder` → `FILE`/`FOLDER`，資料修正） | §7.3 |
| 0004 | `users` 加 `must_change_password` 旗標 | §7.1 |
| 0005 | `assistant_skills` | §8.9 |
| 0006 | `assistant_workflows` + `assistant_workflow_runs` | §8.9 |
| 0007 | `assistant_sessions` + `assistant_messages` | §8.9 |
| 0008 | `assistant_workflows` 加 `name`（saved workflows） | §8.9 |
| 0009 | `snapshots` + `snapshot_entries`（時光機） | §12.7 |
| 0010 | `snapshot_settings`（保留數／排程／快照配額） | §12.7 |
| 0011 | `file_search_index`（全文內容索引） | §7.10 |
| 0012 | `file_embeddings` + `CREATE EXTENSION vector`（pgvector 語意） | §7.11 |
| 0013 | `file_embeddings` 改一檔多向量（chunk）+ snippet | §7.11 |
| 0014 | `user_external_credentials`（外部模型 per-user 憑證，DEC-026） | §11.3 |
| 0015 | `assistant_skills` 加 `chat_enabled` | §8.9 |
| 0016 | `external_model_connections` | §11.3 |
| 0017 | `upload_sessions` + `upload_chunks`（分片續傳，DEC-036） | §7.7 |
| 0018 | 永久刪除所需的 FK ON DELETE：`activity_logs.item_id` → SET NULL、`user_item_preferences.item_id` → CASCADE | §7.8、§6.10 |
| 0019 | `upload_sessions.parent_id` / `drive_item_id` → SET NULL（同上，清空垃圾桶用） | §7.7 |
| 0020 | `share_links` 加 `attempt_window_start` / `attempt_count` / `locked_until`（公開連結速率限制） | §7.6、§6.12.11 |
| 0021 | `ck_share_links_permission` 放寬納入 `editor`（訪客寫入，proposal §33） | §7.6、§6.12.11b |

> 部署時 `alembic upgrade head` 套用全鏈（見 §21）。**新增 migration 必須接在鏈尾並回填本表**，維持文件與 schema 同步。

# Backend Upload 模組任務

## 完成定義

- 一般 multipart 上傳可完成檔案儲存、中繼資料、v1 版本與容量更新。
- 失敗流程不留下無效資料或孤兒檔案。
- ~~分片上傳只保留接口，不實作核心流程。~~ → **分片續傳上傳已納入正式範圍**（proposal §27、detailed-design §6.7.7／§7.7／§13.5、DEC-035）：可續傳、記憶體用量與檔案大小無關、逾期自動清理。

## 最小可執行任務

- [x] 建立 upload schemas。
- [x] 建立 `UploadService`。
- [x] 驗證 UploadFile 檔名。
- [x] 驗證 UploadFile 大小。
- [x] 驗證 parent folder 存在。
- [x] 驗證 parent item type 是 folder。
- [x] 呼叫 PermissionService 檢查寫入權限。
- [x] 呼叫 QuotaService 檢查容量。
- [x] 產生安全 storage key。
- [x] 實作同名檔案自動改名。
- [x] 呼叫 StorageProvider 儲存檔案。
- [x] 建立 file 類型 DriveItem。
- [x] 寫入 MIME type。
- [x] 寫入 extension。
- [x] 寫入 size bytes。
- [x] 計算並寫入 SHA-256 checksum。
- [x] 建立 FileVersion v1。
- [x] 增加使用者 used bytes。
- [x] 寫入 upload activity log。
- [x] 實作 DB 失敗時刪除已寫入檔案。
- [x] 建立 upload router。
- [x] 實作 `POST /upload/simple`。
- [x] 回傳 DriveItemResponse。
- [x] 定義 UploadSessionService interface。
- [x] ~~不啟用分片上傳 endpoint。~~（改由下方分片續傳任務實作）

## 分片續傳上傳（proposal §27 / detailed-design §6.7.7 / DEC-035）

> 參數：單檔上限 **5 GB**、分片 **8 MB**、未完成保留 **7 天**、單檔分片**序列**。
> 依賴順序：儲存層 → 資料層 → 服務 → 端點 → 清理。前三組完成前不要開始端點。

### 前置：修既有缺陷（與分片獨立，可先做）

- [ ] `upload_simple` 改**串流寫入**：移除 `chunks: list[bytes]` + `b"".join` 的整檔累積，改邊收邊寫並同步累積 sha256（修記憶體 ≈ 檔案大小 ×2 的 OOM 風險）。
- [ ] 測試：上傳後 checksum／size 與串流前一致；以大於緩衝區的資料驗證不會整檔進記憶體。

### 儲存層

- [ ] `StorageProvider` 新增 `concat(source_keys, target_key) -> int`（依序串接為單一物件）。
- [ ] `LocalStorageProvider.concat` 以固定緩衝區**邊讀邊寫**實作，回傳總位元組數。
- [ ] 測試：多分片合併後內容與大小正確；記憶體用量不隨來源大小成長。

### 資料層

- [ ] 新增 `UploadSession`／`UploadChunk` ORM model（欄位見 §7.7）。
- [ ] Alembic migration：建表 + 3 個索引（`user_id,status,created_at`、`expires_at` 部分索引、`(session_id, chunk_index)` unique）。
- [ ] `UploadSessionRepository`：建立、依 id+user 取得、列已完成 chunk_index、upsert chunk、更新狀態、列出過期工作階段、刪除。
- [ ] 測試：repository 各方法；同 `chunk_index` 重送為冪等覆寫。

### 服務

- [ ] `create_session`：驗 `total_size <= 5 GB`、parent 存在且屬本人、配額預檢（**含其他未完成工作階段的佔用量**），回 `chunk_size`/`total_chunks`。
- [ ] `get_session`：回狀態 + **已完成 chunk_index 清單**（續傳依據）；非本人回 `NOT_FOUND`。
- [ ] `upload_chunk`：串流寫入暫存 key、upsert chunk、首片時 `pending → uploading`；終態拒收、index 越界拒收。
- [ ] `complete_session`：驗分片齊全 → `storage.concat` → 算 checksum/size → 解析同層可用檔名 → 建 DriveItem + FileVersion v1 → **實扣配額** → activity log → 刪暫存分片 → `completed`；DB 失敗則刪已合併 blob（補償回滾）。
- [ ] `cancel_session`：標 `cancelled` 並刪暫存分片（不扣配額）。
- [ ] `cleanup_expired`：刪除 `expires_at` 已過的 pending/uploading 工作階段與其暫存分片，回傳筆數。
- [ ] 測試：授權隔離（他人一律 NOT_FOUND）、配額預檢含未完成佔用、缺片時 complete 失敗、取消/過期清乾淨分片、完成後配額正確、合併後 checksum 正確。

### 端點（§13.5）

- [ ] `POST /upload/sessions`
- [ ] `GET /upload/sessions/{id}`
- [ ] `PUT /upload/sessions/{id}/chunks/{index}`
- [ ] `POST /upload/sessions/{id}/complete`
- [ ] `DELETE /upload/sessions/{id}`
- [ ] 錯誤碼對應（§6.7.8）：`FILE_TOO_LARGE`／`QUOTA_EXCEEDED` 413、`NOT_FOUND` 404、`INVALID_OPERATION` 422。
- [ ] 測試：各端點成功路徑 + 上述錯誤碼；未登入 401。

### 清理排程與設定

- [ ] 背景排程呼叫 `cleanup_expired`（沿用快照排程機制，預設每日一次；多 worker 須關閉並改外部 cron）。
- [ ] 新增設定：分片大小、單檔上限、保留天數、simple/分片切換門檻，並補進 `.env.example` 與 detailed-design §8.12 風格的環境變數說明。
- [ ] 測試：過期工作階段會被清理且不影響未過期者。

## 測試任務

- [x] 測試上傳成功。
- [x] 測試建立 DriveItem。
- [x] 測試建立 FileVersion v1。
- [x] 測試增加容量。
- [x] 測試容量不足。
- [x] 測試 parent 不存在。
- [x] 測試 parent 不是 folder。
- [x] 測試無權限上傳。
- [x] 測試同名檔案自動改名。
- [x] 測試 storage 失敗不建立 DB 資料。
- [x] 測試 DB 失敗清除 storage 檔案。


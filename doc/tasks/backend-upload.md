# Backend Upload 模組任務

## 完成定義

- 一般 multipart 上傳可完成檔案儲存、中繼資料、v1 版本與容量更新。
- 失敗流程不留下無效資料或孤兒檔案。
- 分片上傳只保留接口，不實作核心流程。

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
- [x] 不啟用分片上傳 endpoint。

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


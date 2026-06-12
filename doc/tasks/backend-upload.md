# Backend Upload 模組任務

## 完成定義

- 一般 multipart 上傳可完成檔案儲存、中繼資料、v1 版本與容量更新。
- 失敗流程不留下無效資料或孤兒檔案。
- 分片上傳只保留接口，不實作核心流程。

## 最小可執行任務

- [ ] 建立 upload schemas。
- [ ] 建立 `UploadService`。
- [ ] 驗證 UploadFile 檔名。
- [ ] 驗證 UploadFile 大小。
- [ ] 驗證 parent folder 存在。
- [ ] 驗證 parent item type 是 folder。
- [ ] 呼叫 PermissionService 檢查寫入權限。
- [ ] 呼叫 QuotaService 檢查容量。
- [ ] 產生安全 storage key。
- [ ] 實作同名檔案自動改名。
- [ ] 呼叫 StorageProvider 儲存檔案。
- [ ] 建立 file 類型 DriveItem。
- [ ] 寫入 MIME type。
- [ ] 寫入 extension。
- [ ] 寫入 size bytes。
- [ ] 計算並寫入 SHA-256 checksum。
- [ ] 建立 FileVersion v1。
- [ ] 增加使用者 used bytes。
- [ ] 寫入 upload activity log。
- [ ] 實作 DB 失敗時刪除已寫入檔案。
- [ ] 建立 upload router。
- [ ] 實作 `POST /upload/simple`。
- [ ] 回傳 DriveItemResponse。
- [ ] 定義 UploadSessionService interface。
- [ ] 不啟用分片上傳 endpoint。

## 測試任務

- [ ] 測試上傳成功。
- [ ] 測試建立 DriveItem。
- [ ] 測試建立 FileVersion v1。
- [ ] 測試增加容量。
- [ ] 測試容量不足。
- [ ] 測試 parent 不存在。
- [ ] 測試 parent 不是 folder。
- [ ] 測試無權限上傳。
- [ ] 測試同名檔案自動改名。
- [ ] 測試 storage 失敗不建立 DB 資料。
- [ ] 測試 DB 失敗清除 storage 檔案。


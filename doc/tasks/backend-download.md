# Backend Download 模組任務

## 完成定義

- 有權限使用者可透過 StreamingResponse 下載檔案。
- 下載不會一次把完整檔案載入記憶體。
- 無權限、資料夾或內容不存在時回傳正確錯誤。

## 最小可執行任務

- [x] 建立 `DownloadFileResult`。
- [x] 建立 `DownloadService`。
- [x] 查詢 DriveItem。
- [x] 驗證 item 存在。
- [x] 驗證 item type 是 file。
- [x] 呼叫 PermissionService 檢查 download 權限。
- [x] 驗證 storage key 存在。
- [x] 呼叫 StorageProvider.open_read。
- [x] 回傳檔名、MIME type、大小與 stream。
- [x] 建立下載 endpoint。
- [x] 使用 FastAPI StreamingResponse。
- [x] 設定 `Content-Disposition`。
- [x] 正確編碼非 ASCII 檔名。
- [x] 設定 `Content-Length`。
- [x] 寫入 download activity log。
- [x] 定義 `ITEM_CONTENT_NOT_FOUND`。

## 測試任務

- [x] 測試 owner 可下載。
- [x] 測試 downloader 可下載。
- [x] 測試 viewer 不可下載。
- [x] 測試 folder 不可下載。
- [x] 測試內容不存在。
- [x] 測試下載內容與原始檔一致。
- [x] 測試成功下載寫入 activity log。


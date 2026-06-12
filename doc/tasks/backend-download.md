# Backend Download 模組任務

## 完成定義

- 有權限使用者可透過 StreamingResponse 下載檔案。
- 下載不會一次把完整檔案載入記憶體。
- 無權限、資料夾或內容不存在時回傳正確錯誤。

## 最小可執行任務

- [ ] 建立 `DownloadFileResult`。
- [ ] 建立 `DownloadService`。
- [ ] 查詢 DriveItem。
- [ ] 驗證 item 存在。
- [ ] 驗證 item type 是 file。
- [ ] 呼叫 PermissionService 檢查 download 權限。
- [ ] 驗證 storage key 存在。
- [ ] 呼叫 StorageProvider.open_read。
- [ ] 回傳檔名、MIME type、大小與 stream。
- [ ] 建立下載 endpoint。
- [ ] 使用 FastAPI StreamingResponse。
- [ ] 設定 `Content-Disposition`。
- [ ] 正確編碼非 ASCII 檔名。
- [ ] 設定 `Content-Length`。
- [ ] 寫入 download activity log。
- [ ] 定義 `ITEM_CONTENT_NOT_FOUND`。

## 測試任務

- [ ] 測試 owner 可下載。
- [ ] 測試 downloader 可下載。
- [ ] 測試 viewer 不可下載。
- [ ] 測試 folder 不可下載。
- [ ] 測試內容不存在。
- [ ] 測試下載內容與原始檔一致。
- [ ] 測試成功下載寫入 activity log。


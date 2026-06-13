# Backend Permission 模組任務

## 完成定義

- 所有檔案操作可透過單一 PermissionService 判斷權限。
- 支援 owner、editor、downloader、viewer 與資料夾權限繼承。
- 模組不依賴 router，可獨立測試。

## 最小可執行任務

- [x] 定義 `Permission` enum。
- [x] 定義權限等級比較規則。
- [x] 建立 `PermissionService`。
- [x] 實作 owner 判斷。
- [x] 實作 direct share 權限查詢。
- [x] 實作父資料夾分享權限查詢。
- [x] 實作 `get_permission`。
- [x] 實作 `assert_can_view`。
- [x] 實作 `assert_can_download`。
- [x] 實作 `assert_can_edit`。
- [x] 實作 `assert_is_owner`。
- [x] 定義無權限時的 `FORBIDDEN` 錯誤。
- [x] 確保 PermissionService 不直接依賴 HTTP request。
- [x] 將權限檢查接口提供給 Drive 模組。
- [x] 將權限檢查接口提供給 Upload 模組。
- [x] 將權限檢查接口提供給 Download 模組。
- [x] 將權限檢查接口提供給 Trash 模組。
- [x] 將權限檢查接口提供給 Share 模組。
- [x] 將權限檢查接口提供給 FileVersion 模組。

## 測試任務

- [x] 測試 owner 權限。
- [x] 測試 direct viewer share。
- [x] 測試 direct downloader share。
- [x] 測試 direct editor share。
- [x] 測試未分享使用者取得 none。
- [x] 測試子項目繼承父資料夾權限。
- [x] 測試 viewer 不可編輯。
- [x] 測試 downloader 可下載。
- [x] 測試 editor 可重新命名。


# Backend Permission 模組任務

## 完成定義

- 所有檔案操作可透過單一 PermissionService 判斷權限。
- 支援 owner、editor、downloader、viewer 與資料夾權限繼承。
- 模組不依賴 router，可獨立測試。

## 最小可執行任務

- [ ] 定義 `Permission` enum。
- [ ] 定義權限等級比較規則。
- [ ] 建立 `PermissionService`。
- [ ] 實作 owner 判斷。
- [ ] 實作 direct share 權限查詢。
- [ ] 實作父資料夾分享權限查詢。
- [ ] 實作 `get_permission`。
- [ ] 實作 `assert_can_view`。
- [ ] 實作 `assert_can_download`。
- [ ] 實作 `assert_can_edit`。
- [ ] 實作 `assert_is_owner`。
- [ ] 定義無權限時的 `FORBIDDEN` 錯誤。
- [ ] 確保 PermissionService 不直接依賴 HTTP request。
- [ ] 將權限檢查接口提供給 Drive 模組。
- [ ] 將權限檢查接口提供給 Upload 模組。
- [ ] 將權限檢查接口提供給 Download 模組。
- [ ] 將權限檢查接口提供給 Trash 模組。
- [ ] 將權限檢查接口提供給 Share 模組。
- [ ] 將權限檢查接口提供給 FileVersion 模組。

## 測試任務

- [ ] 測試 owner 權限。
- [ ] 測試 direct viewer share。
- [ ] 測試 direct downloader share。
- [ ] 測試 direct editor share。
- [ ] 測試未分享使用者取得 none。
- [ ] 測試子項目繼承父資料夾權限。
- [ ] 測試 viewer 不可編輯。
- [ ] 測試 downloader 可下載。
- [ ] 測試 editor 可重新命名。


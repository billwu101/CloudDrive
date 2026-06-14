# Backend User 與 Quota 模組任務

## 完成定義

- 可查詢目前使用者資料與容量。
- 上傳、永久刪除及版本操作可透過 QuotaService 更新容量。
- QuotaService 可獨立測試。

## 最小可執行任務

- [x] 建立 user response schema。
- [x] 建立 user profile update schema。
- [x] 建立 `UserService`。
- [x] 實作依 id 取得使用者。
- [x] 實作依 email 取得使用者。
- [x] 實作更新使用者顯示名稱。
- [x] 實作更新登入 email，包含正規化、格式與唯一性檢查。
- [x] 實作驗證目前密碼後更新密碼雜湊。
- [x] 建立 `QuotaService`。
- [x] 實作取得 quota 與 used bytes。
- [x] 實作計算剩餘容量。
- [x] 實作 `assert_has_space`。
- [x] 實作原子增加 `used_bytes`。
- [x] 實作原子減少 `used_bytes`。
- [x] 防止 `used_bytes` 變成負數。
- [x] 實作依 file_versions 重算 used bytes。
- [x] 建立使用者資料 API。
- [x] 建立 email 與密碼更新 API。
- [x] 建立容量統計 API。
- [x] 定義 `QUOTA_EXCEEDED` 錯誤。

## 測試任務

- [x] 測試容量足夠時允許上傳。
- [x] 測試容量不足時回傳錯誤。
- [x] 測試增加容量。
- [x] 測試減少容量。
- [x] 測試資料夾不計容量。
- [x] 測試永久刪除檔案後容量減少。
- [x] 測試重新計算容量結果。
- [x] 測試顯示名稱、email 與密碼更新。
- [x] 測試重複 email、錯誤目前密碼與輸入驗證。

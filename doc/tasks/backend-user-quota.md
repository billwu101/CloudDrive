# Backend User 與 Quota 模組任務

## 完成定義

- 可查詢目前使用者資料與容量。
- 上傳、永久刪除及版本操作可透過 QuotaService 更新容量。
- QuotaService 可獨立測試。

## 最小可執行任務

- [ ] 建立 user response schema。
- [ ] 建立 user profile update schema。
- [ ] 建立 `UserService`。
- [ ] 實作依 id 取得使用者。
- [ ] 實作依 email 取得使用者。
- [ ] 實作更新使用者顯示名稱。
- [ ] 建立 `QuotaService`。
- [ ] 實作取得 quota 與 used bytes。
- [ ] 實作計算剩餘容量。
- [ ] 實作 `assert_has_space`。
- [ ] 實作原子增加 `used_bytes`。
- [ ] 實作原子減少 `used_bytes`。
- [ ] 防止 `used_bytes` 變成負數。
- [ ] 實作依 file_versions 重算 used bytes。
- [ ] 建立使用者資料 API。
- [ ] 建立容量統計 API。
- [ ] 定義 `QUOTA_EXCEEDED` 錯誤。

## 測試任務

- [ ] 測試容量足夠時允許上傳。
- [ ] 測試容量不足時回傳錯誤。
- [ ] 測試增加容量。
- [ ] 測試減少容量。
- [ ] 測試資料夾不計容量。
- [ ] 測試永久刪除檔案後容量減少。
- [ ] 測試重新計算容量結果。


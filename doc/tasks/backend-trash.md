# Backend Trash 模組任務

## 完成定義

- 檔案與資料夾可移入垃圾桶、列出、還原及永久刪除。
- 永久刪除會清理版本檔案與容量。
- TrashService 可獨立測試。

## 最小可執行任務

- [ ] 建立 `TrashService`。
- [ ] 實作移至垃圾桶。
- [ ] 設定 `is_deleted = true`。
- [ ] 設定 `deleted_at`。
- [ ] 實作垃圾桶分頁列表。
- [ ] 實作還原 item。
- [ ] 還原時檢查原 parent。
- [ ] 原 parent 不存在時還原到根目錄。
- [ ] 還原時處理名稱衝突。
- [ ] 實作永久刪除 file。
- [ ] 實作遞迴永久刪除 folder。
- [ ] 刪除所有 file_versions storage objects。
- [ ] 刪除 item 的 share records。
- [ ] 更新 used bytes。
- [ ] 寫入 trash activity log。
- [ ] 寫入 restore activity log。
- [ ] 寫入 permanent_delete activity log。
- [ ] 建立 trash router。
- [ ] 實作 move-to-trash endpoint。
- [ ] 實作 `GET /trash`。
- [ ] 實作 restore endpoint。
- [ ] 實作 permanent delete endpoint。
- [ ] 實作 empty trash endpoint。

## 測試任務

- [ ] 測試移至垃圾桶。
- [ ] 測試一般列表隱藏垃圾桶項目。
- [ ] 測試垃圾桶列表。
- [ ] 測試還原。
- [ ] 測試 parent 不存在時還原到根目錄。
- [ ] 測試還原名稱衝突。
- [ ] 測試永久刪除 storage 檔案。
- [ ] 測試永久刪除扣除容量。
- [ ] 測試遞迴刪除資料夾。


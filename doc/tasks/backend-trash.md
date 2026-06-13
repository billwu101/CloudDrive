# Backend Trash 模組任務

## 完成定義

- 檔案與資料夾可移入垃圾桶、列出、還原及永久刪除。
- 永久刪除會清理版本檔案與容量。
- TrashService 可獨立測試。

## 最小可執行任務

- [x] 建立 `TrashService`。
- [x] 實作移至垃圾桶。
- [x] 設定 `is_deleted = true`。
- [x] 設定 `deleted_at`。
- [x] 實作垃圾桶分頁列表。
- [x] 實作還原 item。
- [x] 還原時檢查原 parent。
- [x] 原 parent 不存在時還原到根目錄。
- [x] 還原時處理名稱衝突。
- [x] 實作永久刪除 file。
- [x] 實作遞迴永久刪除 folder。
- [x] 刪除所有 file_versions storage objects。
- [x] 刪除 item 的 share records。
- [x] 更新 used bytes。
- [x] 寫入 trash activity log。
- [x] 寫入 restore activity log。
- [x] 寫入 permanent_delete activity log。
- [x] 建立 trash router。
- [x] 實作 move-to-trash endpoint。
- [x] 實作 `GET /trash`。
- [x] 實作 restore endpoint。
- [x] 實作 permanent delete endpoint。
- [x] 實作 empty trash endpoint。

## 測試任務

- [x] 測試移至垃圾桶。
- [x] 測試一般列表隱藏垃圾桶項目。
- [x] 測試垃圾桶列表。
- [x] 測試還原。
- [x] 測試 parent 不存在時還原到根目錄。
- [x] 測試還原名稱衝突。
- [x] 測試永久刪除 storage 檔案。
- [x] 測試永久刪除扣除容量。
- [x] 測試遞迴刪除資料夾。


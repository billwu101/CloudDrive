# Frontend Trash 模組任務

## 完成定義

- 垃圾桶頁可列出、還原、永久刪除及清空。
- 破壞性操作都有確認。

## 最小可執行任務

- [x] 建立 TrashPage。
- [x] 建立 `useTrashItems` query。
- [x] 建立 `useRestoreItem` mutation。
- [x] 建立 `usePermanentDelete` mutation。
- [x] 建立 `useEmptyTrash` mutation。
- [x] 建立 TrashToolbar。
- [x] 建立 RestoreConfirmDialog。
- [x] 建立 PermanentDeleteConfirmDialog。
- [x] 建立 EmptyTrashConfirmDialog。
- [x] 還原成功後 invalidate trash 與 drive。
- [x] 永久刪除後 invalidate trash 與 storage usage。
- [x] 清空垃圾桶後 invalidate trash 與 storage usage。
- [x] 建立 loading state。
- [x] 建立 empty state。
- [x] 建立 error state。
- [x] 停用重複送出的破壞性操作。

## 測試任務

- [x] 測試垃圾桶列表。
- [x] 測試還原。
- [x] 測試永久刪除確認。
- [x] 測試清空垃圾桶確認。
- [x] 測試 loading/empty/error 狀態。


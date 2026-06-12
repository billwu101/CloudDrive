# Frontend Trash 模組任務

## 完成定義

- 垃圾桶頁可列出、還原、永久刪除及清空。
- 破壞性操作都有確認。

## 最小可執行任務

- [ ] 建立 TrashPage。
- [ ] 建立 `useTrashItems` query。
- [ ] 建立 `useRestoreItem` mutation。
- [ ] 建立 `usePermanentDelete` mutation。
- [ ] 建立 `useEmptyTrash` mutation。
- [ ] 建立 TrashToolbar。
- [ ] 建立 RestoreConfirmDialog。
- [ ] 建立 PermanentDeleteConfirmDialog。
- [ ] 建立 EmptyTrashConfirmDialog。
- [ ] 還原成功後 invalidate trash 與 drive。
- [ ] 永久刪除後 invalidate trash 與 storage usage。
- [ ] 清空垃圾桶後 invalidate trash 與 storage usage。
- [ ] 建立 loading state。
- [ ] 建立 empty state。
- [ ] 建立 error state。
- [ ] 停用重複送出的破壞性操作。

## 測試任務

- [ ] 測試垃圾桶列表。
- [ ] 測試還原。
- [ ] 測試永久刪除確認。
- [ ] 測試清空垃圾桶確認。
- [ ] 測試 loading/empty/error 狀態。


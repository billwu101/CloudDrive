# Frontend Drive 模組任務

## Breadcrumb 路徑導覽與返回按鈕

- [x] 新增 `driveApi.getItem(item_id)` 及 `driveApi.getAncestors(item_id)`。
- [x] 新增 `useFolderItem(folderId)` 和 `useFolderAncestors(folderId)` hooks。
- [x] DrivePage 用以上 hooks 讓 `Breadcrumbs` 顯示真實 pwd 路徑，各層名稱可點擊跳轉。
- [x] 進入子資料夾時顯示 ArrowLeft 返回按鈕，點擊返回直接父層（或根目錄）。

## 完成定義

- 可瀏覽根目錄與子資料夾。
- 支援列表/格狀、排序、建立資料夾、重新命名、移動、星號與移至垃圾桶。
- loading、empty、error 狀態完整。

## 最小可執行任務

- [x] 建立 DriveItem TypeScript type。
- [x] 建立 DrivePage。
- [x] 建立 RecentPage。
- [x] 建立 StarredPage。
- [x] 建立 `useDriveItems` query。
- [x] 建立 `useRecentItems` query。
- [x] 建立 `useStarredItems` query。
- [x] 建立 `useCreateFolder` mutation。
- [x] 建立 `useRenameItem` mutation。
- [x] 建立 `useMoveItem` mutation。
- [x] 建立 `useSetStarred` mutation。
- [x] 建立 `useMoveToTrash` mutation。
- [x] 建立 `DriveToolbar`。
- [x] 建立 Breadcrumbs。
- [x] 建立 FileTable。
- [x] 建立 FileGrid。
- [x] 建立 FileRow。
- [x] 建立 FileCard。
- [x] 建立 FileIcon MIME mapping。
- [x] 建立 FileContextMenu。
- [x] 建立 CreateFolderDialog。
- [x] 建立 RenameDialog。
- [x] 建立 MoveDialog。
- [x] 建立 ConfirmTrashDialog。
- [x] 點擊資料夾時切換 route。
- [x] 點擊檔案時開啟 preview。
- [x] 實作列表排序控制。
- [x] 實作列表/格狀切換。
- [x] 實作單選與多選。
- [x] 操作成功後 invalidate 正確 query。
- [x] 建立 loading skeleton。
- [x] 建立 empty state。
- [x] 建立 error state 與 retry。

## 測試任務

- [x] 測試根目錄載入。
- [x] 測試子資料夾載入。
- [x] 測試建立資料夾。
- [x] 測試重新命名。
- [x] 測試移動。
- [x] 測試星號。
- [x] 測試移至垃圾桶。
- [x] 測試列表與格狀切換。
- [x] 測試 loading/empty/error 狀態。


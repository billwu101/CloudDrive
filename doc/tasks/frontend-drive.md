# Frontend Drive 模組任務

## Breadcrumb 路徑導覽與返回按鈕

- [x] 新增 `driveApi.getItem(item_id)` 及 `driveApi.getAncestors(item_id)`。
- [x] 新增 `useFolderItem(folderId)` 和 `useFolderAncestors(folderId)` hooks。
- [x] DrivePage 用以上 hooks 讓 `Breadcrumbs` 顯示真實 pwd 路徑，各層名稱可點擊跳轉。
- [x] 進入子資料夾時顯示 ArrowLeft 返回按鈕，點擊返回直接父層（或根目錄）。

## 多選與批次操作

- [x] FileRow / FileCard：滑鼠懸停顯示 checkbox（覆蓋 icon），已選取時 checkbox 常駐顯示。
- [x] FileTable header checkbox 支援全選（indeterminate 半選狀態）。
- [x] 右鍵多選項目 → 顯示 MultiFileContextMenu（僅「移至垃圾桶」）。
- [x] 右鍵單選/未選項目 → 顯示既有 FileContextMenu。
- [x] Checkbox 點擊永遠以多選模式累積（不取代選取範圍）。
- [x] DrivePage / RecentPage / StarredPage / SearchPage 均通過 onCheckboxClick 與 onSelectAll。
- [x] 批次移至垃圾桶（逐一 mutate）後清除選取狀態。
- [x] DrivePage 支援從空白處拖曳矩形框選檔案與資料夾。
- [x] 框選只需按住滑鼠左鍵拖曳，不需要搭配鍵盤按鍵。
- [x] 框選具有 5 px 移動門檻，且不會攔截檔案卡片與互動控制的拖曳起點。
- [x] 框選可從 `<main>` 內任意空白處啟動（含檔案列表外 padding 區域）；以 `closest('main')` 排除 Sidebar 與 TopBar。

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
- [ ] **修 bug**：`useStarredItems` 改打新的 `GET /drive/starred`（`driveApi.listStarred`），移除「列根目錄再前端 `filter(is_starred)`」——舊寫法看不到子資料夾內與分頁外的星號項目。
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
- [ ] 測試 `useStarredItems` 打 `/drive/starred`，且**子資料夾內**的星號項目會出現（回歸本次 bug）。
- [x] 測試移至垃圾桶。
- [x] 測試列表與格狀切換。
- [x] 測試 loading/empty/error 狀態。
- [x] 測試框選命中、取代選取、空白點擊清除及無效拖曳起點。

---

## 追加：拖曳移動到資料夾（proposal §30）

**目標**：不必開對話框，直接把項目拖到看得見的資料夾上完成移動。
**不含範圍**：拖到麵包屑／側邊欄、跨分頁拖曳、拖曳排序、拖曳複製（proposal §30.4）。
**後端**：無需改動——`PATCH /drive/items/{id}/parent` 既有的驗證（目的地須為資料夾、不可移入自身子樹、同名衝突）已足夠。
**設計依據**：§5.6.2「拖曳移動到資料夾」。

### 子任務

- [x] `src/hooks/useDragMove.ts`：自訂 MIME `application/x-clouddrive-items`；管理 `draggingIds` / `dropTargetId`；逐一送出移動、收集部分失敗。
- [x] `src/components/drive/FileCard.tsx`：`draggable` + drag/drop handlers + 放置態樣式。
- [x] `src/components/drive/FileRow.tsx`：同上。
- [x] `src/components/drive/FileGrid.tsx` / `FileTable.tsx`：把 handlers 往下傳。
- [x] `src/pages/DrivePage.tsx`：接上 `useDragMove`，顯示移動失敗訊息。
- [x] `src/components/upload/UploadDropzone.tsx`：`drop` 監聽補上 `types.includes('Files')` 判斷（`dragenter`/`dragover` 已有）。

### 測試任務

- [x] 拖曳單一項目到資料夾會呼叫移動，帶正確的目的地 id。
- [x] 拖曳選取範圍內的項目 → 整批移動。
- [x] 拖曳未選取的項目 → 只移動它，且既有選取不變。
- [x] 放到檔案上不觸發移動。
- [x] 放到被拖曳項目自身不觸發移動。
- [x] 部分失敗時其餘照常完成，並列出失敗項目。
- [x] 內部拖曳不會叫出上傳覆蓋層。

### 驗收條件

proposal §30.3 全部 9 項通過；`lint` / `typecheck` / `vitest` 全綠。

### 驗證結果（2026-07-27）

- 單元測試 8 項（`src/hooks/useDragMove.test.tsx`）：單一／整批／選取外、放到檔案、放到自身、外部拖曳、放置標示、部分失敗。前端全套 **318 passed**；`lint` / `typecheck` 全綠。
- Chrome 實機驗證（dev server）：`draggable=true`、`dragstart` 寫入自訂 MIME payload、資料夾 `dragover` 接受而檔案不接受、放置標示與來源淡化都正確套用。
- **未做**：真正的原生 OS 拖放。CDP 的合成滑鼠事件不會啟動 HTML5 drag，且真的放開會搬動使用者的實際檔案，故止於 `dragover`，由使用者手動確認最後一哩。

---

## 修正：選取狀態沒有跟著資料夾切換清掉（2026-07-27 使用者回報）

**症狀**：進入資料夾後工具列仍顯示 `Download (1)` / `Trash (1)`。因為雙擊資料夾的第一下會先選取它，第二下才導航，結果你站在資料夾裡、而那個資料夾自己是被選取的狀態。

**風險**：`Trash (N)` 會刪掉畫面上根本看不到的項目；`handleDownloadSelected` 當時用的是未過濾的 `selectedIds`，會下載到不在此資料夾的檔案。

- [x] `src/pages/DrivePage.tsx`：`useEffect` 依 `folderId` 清空選取（同時涵蓋麵包屑、返回鍵、瀏覽器上一頁、直接輸入網址）。
- [x] `src/pages/DrivePage.tsx`：新增 `visibleSelected`（選取 ∩ 當前列表），工具列數字、下載、垃圾桶一律改用它——即使 store 裡殘留舊 id 也無法被操作。
- [x] `src/pages/DrivePage.selection.test.tsx`：進資料夾後按鈕消失且 store 已清空；殘留的幽靈 id 不計入數量。

---

## 調整：公開連結到期日預設 7 天（2026-07-27 使用者要求）

- [x] `src/components/share/ShareLinkPanel.tsx`：`DEFAULT_EXPIRY_DAYS = 7`，欄位預填 7 天後的本地時間（`datetime-local` 需要本地時間字串，不能直接用 ISO/UTC，否則會偏移時區）。
- [x] 欄位 aria-label 由「Link expiry (optional)」改為「Link expiry」——已有預設值，不再是選填。
- [x] `ShareDialog.test.tsx`：驗證預設值落在 7 天 ±0.1 天。

---

## 追加：快照用量可見性（proposal §30）

**背景**：實測本機帳號現存檔案 34 MB、快照歷史 3.5 GB，介面完全沒有呈現，且快照配額滿了會自動刪除最舊快照而使用者無從得知。
**後端**：零改動——`GET /snapshots/settings` 已回傳 `used_bytes`（依 checksum 去重）與 `effective_quota_bytes`。

- [x] `src/components/snapshot/SnapshotUsagePanel.tsx`：用量條、80% 警告、最大前 5 個快照（含時間，因為排程快照標籤全是「Scheduled」）、去重說明。
- [x] `src/pages/TimeMachinePage.tsx`：掛上面板，接 `useSnapshotSettings()`。
- [x] `src/components/layout/StorageUsageBar.tsx`：抽出 `Meter`，檔案與快照各一條獨立量表（§30.4 決策 1）。
- [x] 測試 9 項：`SnapshotUsagePanel.test.tsx` 6 項 + `StorageUsageBar.test.tsx` 3 項。

### 驗證結果（2026-07-27）

前端 **330 passed**；`lint` / `typecheck` 全綠。Chrome 實機確認：時光機頁顯示「3.5 GB of 7.5 GB」、最大快照 3.0 GB、側邊欄兩條量表（33.4 MB / 15.0 GB 與 3.5 GB / 7.5 GB）。

### 修正（同日）：面板顯示的是「涵蓋量」而非「可回收量」

使用者追問「這些檔案不是都一樣嗎，為什麼還要一直存 1.3 GB」——問題不在儲存，在**我顯示的數字**。`total_bytes` 是該快照涵蓋的內容大小，不是刪掉它能省的空間。五列各寫 1.3 GB，讀起來就是每個各佔 1.3 GB。

實測：涵蓋 3063 MB 的快照與 6 個各 1358 MB 的快照，後者刪掉全部釋放 **0 bytes**（彼此共用同一份 blob）。

- [x] `backend/app/snapshot/repository.py`：`reclaimable_bytes_by_snapshot()`——以 `storage_key` 計算「僅此快照持有」的 blob（其他快照、drive_items、file_versions 皆無引用）。
- [x] `backend/app/snapshot/service.py` / `schemas.py` / `router.py`：`SnapshotResponse.reclaimable_bytes`；列表端點每頁一次查詢。
- [x] 面板改為「Worth deleting」，依可回收量排序、0 的不列出、全為 0 時顯示說明。
- [x] 測試：後端單元 + router + integration（共用 blob 的快照回報 0）；前端排序與空狀態。

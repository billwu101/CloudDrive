# Frontend Upload 模組任務

## 完成定義

- 使用者可選擇或拖曳檔案上傳。
- 上傳佇列顯示進度、成功與失敗狀態。
- 上傳成功後檔案列表刷新。
- **大檔走分片續傳**：可暫停／繼續／取消，關閉瀏覽器後仍可續傳；佇列並行受限；錯誤訊息分類明確（proposal §27、detailed-design §5.7.4、DEC-036）。

## 最小可執行任務

- [x] 建立 UploadTask type。
- [x] 建立 `uploadStore.ts`。
- [x] 實作 addTasks。
- [x] 實作 updateProgress。
- [x] 實作 markCompleted。
- [x] 實作 markFailed。
- [x] 實作 cancel task state。
- [x] 實作 removeTask。
- [x] 建立 `UploadButton`。
- [x] 建立 `UploadDropzone`（全域：使用 `window` drag 事件，drop 螢幕任意位置均有效，overlay 為 `position:fixed`）。
- [x] 建立 `UploadQueue`。
- [x] 建立 `UploadTaskItem`。
- [x] 建立 multipart/form-data request。
- [x] 取得目前 parentId。
- [x] 顯示上傳百分比。
- [x] 顯示檔名。
- [x] 顯示完成狀態。
- [x] 顯示錯誤訊息。
- [x] 實作失敗重試。
- [x] 實作取消尚未完成的 request。
- [x] 上傳成功後 invalidate drive-items。
- [x] 上傳多檔時逐一建立 task。
- [x] 不實作分片上傳。

## 測試任務

- [x] 測試選擇檔案建立 task。
- [x] 測試拖曳檔案建立 task。
- [x] 測試進度更新。
- [x] 測試成功狀態。
- [x] 測試失敗狀態。
- [x] 測試重試。
- [x] 測試成功後刷新列表。

## 分片續傳上傳（proposal §27 / detailed-design §5.7.4 / DEC-036）

> 參數：單檔上限 **5 GB**、分片 **8 MB**、檔案之間並行 **3**、單檔分片**序列**。
> 依賴：後端端點（`doc/tasks/backend-upload.md` 的服務與端點兩組）完成後才能整合測試；store/佇列可先做。

### 前置：修既有缺陷（不需等後端）

- [x] **送出前預檢**：以 `file.size` 比對單檔上限與剩餘配額，超過者直接標失敗且**不發出請求**（避免注定失敗的大檔佔住連線、拖垮同批其他檔）。
- [x] **並行上限**：以佇列取代 `Promise.allSettled` 全並行，同時最多 **3** 個檔案，其餘 `queued`。
- [x] **錯誤分類**：依 `errorCode` 顯示「檔案過大／配額不足／連線中斷」，取代一律 `Network error`。
- [x] 測試：超限檔案未發請求即失敗；超過 3 個時其餘為 `queued` 並依序遞補；三類錯誤訊息正確。

### API 與型別

- [x] `uploadApi` 新增 `createSession`／`getSession`／`putChunk`／`completeSession`／`cancelSession`。
- [x] `UploadTask` 擴充 `sessionId`／`uploadedChunks`／`totalChunks`／`errorCode`；`status` 增加 `queued`／`paused`。
- [x] 測試：各 API 呼叫正確路徑與參數。

### 分片流程

- [x] 依門檻決定走 `/upload/simple` 或分片流程。
- [x] 建立工作階段 → 依 `chunk_index` 以 `file.slice()` **序列**送片 → 全數完成後 `complete`。
- [x] 進度 = 已完成片數 ÷ 總片數。
- [x] 單片失敗自動重試（有限次數），仍失敗則整體標失敗但**保留工作階段**供續傳。
- [x] 測試：切片數與 `chunk_index` 正確、進度隨片數更新、單片失敗重試後可完成。

### 續傳與控制

- [x] 持久化未完成任務的 `{ sessionId, fileName, size, parentId }`（`File` 無法持久化，恢復時需使用者重新選同一檔案——UI 要明確說明）。
- [x] 續傳：先 `getSession` 取已完成 index，**只補送缺片**。
- [x] 暫停（停止送後續分片，不呼叫後端）／繼續（從缺片接續）／取消（`DELETE` 並移除任務）。
- [x] `UploadTaskItem` 增加暫停／繼續／取消控制與 `queued`／`paused` 狀態顯示。
- [x] 測試：續傳只送缺片、暫停後停止送出、繼續可接續、取消會呼叫 DELETE。


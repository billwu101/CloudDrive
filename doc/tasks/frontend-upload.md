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

## 上傳佇列自動收斂（proposal §27.8 / detailed-design §5.7.5）

> 一輪 = 一次 `addTasks()` 呼叫回傳的那組任務；一輪結束後**延遲 3 秒**移除該輪的 `completed`，其餘狀態一律留著。
> 涵蓋四個上傳入口，含訪客頁的兩個（`usePublicDrive.ts` 一併在本節處理，見 `doc/tasks/frontend-share.md` 交叉註記）。

### 子任務

- [x] `src/stores/uploadStore.ts`：新增 `SETTLE_DELAY_MS = 3000` 與 `settleBatch(ids: string[])`；移除條件為「id 在該批 **且** 當下 `status === 'completed'`」。
- [x] `src/hooks/useUpload.ts`：`useUploadFiles`／`useUploadFolders` 於 `await runWithConcurrency(...)` 之後呼叫 `settleBatch`。
- [x] `src/hooks/usePublicDrive.ts`：`useGuestUploadFiles`／`useGuestUploadFolders` 同上。
- [x] `src/components/upload/UploadQueue.tsx`：轉發 `onRetry` 時一併 `removeTask(task.id)`（放在佇列本身，不放在 `DriveExplorer` 等呼叫端）。

### 測試任務

- [x] `settleBatch` 在 3 秒前不動任何項目，3 秒後只移除該批的 `completed`。
- [x] `failed`／`canceled`／`paused`／`needs_file` 不被移除。
- [x] 只移除**該批**的成功項：另一批的 `completed` 不受影響。
- [x] 排程後該 id 已被 `removeTask` 移除時，計時器到期不報錯。
- [x] `useUploadFiles` 一輪結束後會呼叫 `settleBatch`（含全成功與混合兩種結果）。
- [x] 重試時原失敗項被移除（`UploadQueue.test.tsx`，本模組新增的測試檔）。

### 驗證結果（2026-08-01）

單元測試 **361 passed**（51 檔，較先前 +10）；`npm run lint` / `npm run typecheck` 全綠。

**瀏覽器實測（dev，於拋棄式資料夾 `_settle-test` 內進行，未觸碰任何既有檔案）**

面板在單次 tool 往返之間就會收斂完畢，只看前後狀態會誤判，因此改成**單一腳本內按時間取樣**面板文字，記錄整段轉場：

| 情境 | 觀察 |
| --- | --- |
| 全部成功（2 檔，My Drive） | `t=556ms` 起面板顯示 `settle-c.txt \| Uploaded \| settle-d.txt \| Uploaded`，**持續到 t=2501ms 仍在**，`t=3201ms` 面板整個消失 |
| 有成功有失敗（My Drive） | `t=602ms` 兩列並存；`t=3402ms` 起只剩 `settle-huge.bin \| File is too large (max 5.0 GB)`，**5 秒後仍在** |
| 新一輪不清舊失敗 | 上一輪的失敗列仍在時再傳一檔：`Uploads (2)` → 3.6 秒後 `Uploads (1)`，留下的正是**上一輪那筆失敗** |
| 重試 | 按下 Retry 後列數維持 **1**（不是 2）；以 DOM node identity 驗證該列是**新節點**（舊節點已移除、`data-probe` 標記不再存在），確認是「舊列被換掉」而非「舊列沒動」 |
| 訪客 editor 頁（`useGuestUploadFiles`） | 建 editor 連結（密碼＋到期）→ 訪客開啟 → 上傳 2 檔：`t=701ms` 兩列 Uploaded，`t=3602ms` 面板消失，檔案確實出現在資料夾中 |
| 資料夾上傳（`useUploadFolders` / `useGuestUploadFolders`） | 兩端各傳一組含子目錄的資料夾，皆為 Uploaded → 延遲後消失；目錄結構正確重建 |

四個上傳入口全部實際跑過。兩個分頁 console 全程無錯誤。

**環境限制（誠實記錄）**：訪客端的**失敗**保留未能單獨實測——訪客路徑沒有前端預檢，而後端對同名上傳會自動改名（實測 `guest-g1.txt` → `guest-g1 (1).txt`）而非回錯，手上沒有不需破壞性操作就能觸發的失敗。該分支與 My Drive 共用同一個 `settleBatch`，已由 store 單元測試與 My Drive 端實測覆蓋。

**收尾**：測試用的 editor 連結已 Remove（訪客頁隨即顯示「Link unavailable」），`_settle-test` 資料夾已移入垃圾桶。


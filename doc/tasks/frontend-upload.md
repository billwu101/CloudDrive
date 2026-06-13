# Frontend Upload 模組任務

## 完成定義

- 使用者可選擇或拖曳檔案上傳。
- 上傳佇列顯示進度、成功與失敗狀態。
- 上傳成功後檔案列表刷新。

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
- [x] 建立 `UploadDropzone`。
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


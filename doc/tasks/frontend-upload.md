# Frontend Upload 模組任務

## 完成定義

- 使用者可選擇或拖曳檔案上傳。
- 上傳佇列顯示進度、成功與失敗狀態。
- 上傳成功後檔案列表刷新。

## 最小可執行任務

- [ ] 建立 UploadTask type。
- [ ] 建立 `uploadStore.ts`。
- [ ] 實作 addTasks。
- [ ] 實作 updateProgress。
- [ ] 實作 markCompleted。
- [ ] 實作 markFailed。
- [ ] 實作 cancel task state。
- [ ] 實作 removeTask。
- [ ] 建立 `UploadButton`。
- [ ] 建立 `UploadDropzone`。
- [ ] 建立 `UploadQueue`。
- [ ] 建立 `UploadTaskItem`。
- [ ] 建立 multipart/form-data request。
- [ ] 取得目前 parentId。
- [ ] 顯示上傳百分比。
- [ ] 顯示檔名。
- [ ] 顯示完成狀態。
- [ ] 顯示錯誤訊息。
- [ ] 實作失敗重試。
- [ ] 實作取消尚未完成的 request。
- [ ] 上傳成功後 invalidate drive-items。
- [ ] 上傳多檔時逐一建立 task。
- [ ] 不實作分片上傳。

## 測試任務

- [ ] 測試選擇檔案建立 task。
- [ ] 測試拖曳檔案建立 task。
- [ ] 測試進度更新。
- [ ] 測試成功狀態。
- [ ] 測試失敗狀態。
- [ ] 測試重試。
- [ ] 測試成功後刷新列表。


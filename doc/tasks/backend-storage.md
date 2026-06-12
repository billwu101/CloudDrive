# Backend Storage 模組任務

## 完成定義

- StorageProvider 抽象介面完成。
- LocalStorageProvider 可安全地儲存、讀取、檢查與刪除檔案。
- 可使用 temporary directory 獨立測試。

## 最小可執行任務

- [ ] 建立 `backend/app/storage/base.py`。
- [ ] 定義 `StorageProvider` protocol。
- [ ] 定義 `save` 方法。
- [ ] 定義 `open_read` 方法。
- [ ] 定義 `delete` 方法。
- [ ] 定義 `exists` 方法。
- [ ] 定義 `get_size` 方法。
- [ ] 建立 `LocalStorageProvider`。
- [ ] 從 Settings 取得 storage root。
- [ ] 實作 storage key 正規化。
- [ ] 實作路徑穿越防護。
- [ ] 實作 temporary file 寫入。
- [ ] 實作原子 move 到正式路徑。
- [ ] 實作檔案讀取。
- [ ] 實作檔案存在檢查。
- [ ] 實作檔案大小查詢。
- [ ] 實作檔案刪除。
- [ ] 實作空目錄清理。
- [ ] 建立 StorageProvider dependency factory。
- [ ] 根據 `STORAGE_DRIVER` 回傳 provider。
- [ ] 為未來 MinIO/S3 provider 保留實作位置。

## 測試任務

- [ ] 測試儲存後檔案存在。
- [ ] 測試讀回內容相同。
- [ ] 測試 get_size。
- [ ] 測試刪除。
- [ ] 測試刪除不存在檔案的行為。
- [ ] 測試拒絕 `../` storage key。
- [ ] 測試寫入失敗不留下正式檔案。


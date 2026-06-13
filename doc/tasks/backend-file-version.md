# Backend FileVersion 模組任務

## 完成定義

- 新檔案上傳會建立 v1。
- 模組支援建立新版本及列出版本的 service contract。
- 每個版本使用獨立 storage key 並納入容量計算。

## 最小可執行任務

- [x] 建立 `FileVersion` SQLAlchemy model。
- [x] 建立唯一 `(file_id, version_no)` constraint。
- [x] 建立 FileVersion schemas。
- [x] 建立 `FileVersionRepository`。
- [x] 實作建立版本。
- [x] 實作取得最大 version number。
- [x] 實作列出 file versions。
- [x] 建立 `FileVersionService`。
- [x] 實作建立 initial v1。
- [x] 驗證只有 file 可建立版本。
- [x] 實作下一版 version number。
- [x] 實作 editor 以上權限檢查。
- [x] 實作新版本 storage key。
- [x] 實作版本容量增加。
- [x] 實作版本列表排序。
- [x] 建立版本列表 endpoint。
- [x] 為上傳新版本 endpoint 保留 router contract。

## 測試任務

- [x] 測試建立 v1。
- [x] 測試第二版為 v2。
- [x] 測試 folder 不可建立版本。
- [x] 測試 viewer 不可建立版本。
- [x] 測試 editor 可建立版本。
- [x] 測試版本列表排序。
- [x] 測試版本容量計算。


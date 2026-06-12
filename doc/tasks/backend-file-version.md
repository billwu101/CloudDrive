# Backend FileVersion 模組任務

## 完成定義

- 新檔案上傳會建立 v1。
- 模組支援建立新版本及列出版本的 service contract。
- 每個版本使用獨立 storage key 並納入容量計算。

## 最小可執行任務

- [ ] 建立 `FileVersion` SQLAlchemy model。
- [ ] 建立唯一 `(file_id, version_no)` constraint。
- [ ] 建立 FileVersion schemas。
- [ ] 建立 `FileVersionRepository`。
- [ ] 實作建立版本。
- [ ] 實作取得最大 version number。
- [ ] 實作列出 file versions。
- [ ] 建立 `FileVersionService`。
- [ ] 實作建立 initial v1。
- [ ] 驗證只有 file 可建立版本。
- [ ] 實作下一版 version number。
- [ ] 實作 editor 以上權限檢查。
- [ ] 實作新版本 storage key。
- [ ] 實作版本容量增加。
- [ ] 實作版本列表排序。
- [ ] 建立版本列表 endpoint。
- [ ] 為上傳新版本 endpoint 保留 router contract。

## 測試任務

- [ ] 測試建立 v1。
- [ ] 測試第二版為 v2。
- [ ] 測試 folder 不可建立版本。
- [ ] 測試 viewer 不可建立版本。
- [ ] 測試 editor 可建立版本。
- [ ] 測試版本列表排序。
- [ ] 測試版本容量計算。


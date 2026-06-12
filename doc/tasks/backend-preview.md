# Backend Preview 模組任務

## 完成定義

- 可判斷圖片、PDF、文字、影音與不支援格式。
- 有權限使用者可取得預覽資訊及內容串流。
- 預覽邏輯可獨立測試。

## 最小可執行任務

- [ ] 建立 PreviewInfo schema。
- [ ] 建立 PreviewContent result。
- [ ] 建立 `PreviewService`。
- [ ] 建立 MIME type 到 preview type 的 mapping。
- [ ] 實作 image preview type。
- [ ] 實作 PDF preview type。
- [ ] 實作 text preview type。
- [ ] 實作 video preview type。
- [ ] 實作 audio preview type。
- [ ] 實作 unsupported preview type。
- [ ] 驗證 item 存在。
- [ ] 驗證 item type 是 file。
- [ ] 呼叫 PermissionService 檢查 view 權限。
- [ ] 實作 preview info endpoint。
- [ ] 實作 preview content endpoint。
- [ ] 文字預覽限制最大讀取量。
- [ ] 設定預覽 response MIME type。
- [ ] 寫入 preview activity log。
- [ ] 為未來縮圖 background task 保留接口。

## 測試任務

- [ ] 測試圖片預覽。
- [ ] 測試 PDF 預覽。
- [ ] 測試文字預覽。
- [ ] 測試不支援格式。
- [ ] 測試 folder 不可預覽。
- [ ] 測試無權限不可預覽。
- [ ] 測試文字預覽不讀取超過限制。


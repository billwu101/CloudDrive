# Backend Preview 模組任務

## 完成定義

- 可判斷圖片、PDF、文字、影音與不支援格式。
- 有權限使用者可取得預覽資訊及內容串流。
- 預覽邏輯可獨立測試。

## 最小可執行任務

- [x] 建立 PreviewInfo schema。
- [x] 建立 PreviewContent result。
- [x] 建立 `PreviewService`。
- [x] 建立 MIME type 到 preview type 的 mapping。
- [x] 實作 image preview type。
- [x] 實作 PDF preview type。
- [x] 實作 text preview type。
- [x] 實作 video preview type。
- [x] 實作 audio preview type。
- [x] 實作 unsupported preview type。
- [x] 驗證 item 存在。
- [x] 驗證 item type 是 file。
- [x] 呼叫 PermissionService 檢查 view 權限。
- [x] 實作 preview info endpoint。
- [x] 實作 preview content endpoint。
- [x] 文字預覽限制最大讀取量。
- [x] 設定預覽 response MIME type。
- [x] 寫入 preview activity log。
- [x] 為未來縮圖 background task 保留接口。

## 測試任務

- [x] 測試圖片預覽。
- [x] 測試 PDF 預覽。
- [x] 測試文字預覽。
- [x] 測試不支援格式。
- [x] 測試 folder 不可預覽。
- [x] 測試無權限不可預覽。
- [x] 測試文字預覽不讀取超過限制。


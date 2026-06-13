# Integration、E2E 與驗收任務

## 完成定義

- 關鍵使用者流程具備後端整合測試與 Playwright E2E。
- 測試可在乾淨環境重複執行。
- 驗收項目可對照 proposal.md。

## 後端整合測試

- [x] 建立測試 PostgreSQL。
- [x] 建立測試 DB migration fixture。
- [x] 建立 temporary LocalStorageProvider fixture。
- [x] 建立 FastAPI test client。
- [x] 建立測試使用者 factory。
- [x] 測試完整註冊登入。
- [x] 測試建立資料夾。
- [x] 測試上傳後 DB 與 storage 一致。
- [x] 測試下載內容一致。
- [x] 測試重新命名與移動。
- [x] 測試搜尋。
- [x] 測試垃圾桶還原。
- [x] 測試永久刪除清理 storage。
- [x] 測試指定使用者分享。
- [x] 測試權限隔離。

## 前端整合測試

- [x] 設定 MSW。
- [x] 建立 auth API handlers。
- [x] 建立 drive API handlers。
- [x] 建立 upload API handlers。
- [x] 建立 share API handlers。
- [x] 建立 trash API handlers。
- [x] 測試登入後載入 DrivePage。
- [x] 測試建立資料夾後刷新列表。
- [x] 測試上傳後刷新列表。
- [x] 測試分享操作。
- [x] 測試垃圾桶操作。

## Playwright E2E

- [x] 建立 E2E 測試環境啟動指令。
- [x] 測試使用者註冊。
- [x] 測試使用者登入。
- [x] 測試建立資料夾。
- [x] 測試上傳檔案。
- [x] 測試預覽檔案。
- [x] 測試下載檔案。
- [x] 測試搜尋檔案。
- [x] 測試分享給第二位使用者。
- [x] 測試第二位使用者看到分享項目。
- [x] 測試刪除與還原。
- [x] 測試登出。

## 驗收

- [x] 對照 proposal.md MVP 驗收標準逐項檢查。
- [x] 對照 detailed-design.md 模組完成定義逐項檢查。
- [x] 確認無使用者可存取未授權檔案。
- [x] 確認 Docker 開發環境可從零啟動。
- [x] 確認 README 啟動步驟可重現。


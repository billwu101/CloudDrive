# Integration、E2E 與驗收任務

## 完成定義

- 關鍵使用者流程具備後端整合測試與 Playwright E2E。
- 測試可在乾淨環境重複執行。
- 驗收項目可對照 proposal.md。

## 後端整合測試

- [ ] 建立測試 PostgreSQL。
- [ ] 建立測試 DB migration fixture。
- [ ] 建立 temporary LocalStorageProvider fixture。
- [ ] 建立 FastAPI test client。
- [ ] 建立測試使用者 factory。
- [ ] 測試完整註冊登入。
- [ ] 測試建立資料夾。
- [ ] 測試上傳後 DB 與 storage 一致。
- [ ] 測試下載內容一致。
- [ ] 測試重新命名與移動。
- [ ] 測試搜尋。
- [ ] 測試垃圾桶還原。
- [ ] 測試永久刪除清理 storage。
- [ ] 測試指定使用者分享。
- [ ] 測試權限隔離。

## 前端整合測試

- [ ] 設定 MSW。
- [ ] 建立 auth API handlers。
- [ ] 建立 drive API handlers。
- [ ] 建立 upload API handlers。
- [ ] 建立 share API handlers。
- [ ] 建立 trash API handlers。
- [ ] 測試登入後載入 DrivePage。
- [ ] 測試建立資料夾後刷新列表。
- [ ] 測試上傳後刷新列表。
- [ ] 測試分享操作。
- [ ] 測試垃圾桶操作。

## Playwright E2E

- [ ] 建立 E2E 測試環境啟動指令。
- [ ] 測試使用者註冊。
- [ ] 測試使用者登入。
- [ ] 測試建立資料夾。
- [ ] 測試上傳檔案。
- [ ] 測試預覽檔案。
- [ ] 測試下載檔案。
- [ ] 測試搜尋檔案。
- [ ] 測試分享給第二位使用者。
- [ ] 測試第二位使用者看到分享項目。
- [ ] 測試刪除與還原。
- [ ] 測試登出。

## 驗收

- [ ] 對照 proposal.md MVP 驗收標準逐項檢查。
- [ ] 對照 detailed-design.md 模組完成定義逐項檢查。
- [ ] 確認無使用者可存取未授權檔案。
- [ ] 確認 Docker 開發環境可從零啟動。
- [ ] 確認 README 啟動步驟可重現。


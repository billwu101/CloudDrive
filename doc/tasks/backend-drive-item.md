# Backend DriveItem 模組任務

## 完成定義

- 可建立資料夾、列出項目、重新命名、移動、標記星號與取得近期項目。
- 同層名稱衝突與循環移動會被阻止。
- Service 與 Repository 可獨立測試。

## 最小可執行任務

- [ ] 建立 `DriveItem` SQLAlchemy model。
- [ ] 定義 file/folder item type enum。
- [ ] 建立 DriveItem request/response schemas。
- [ ] 建立統一分頁 schema。
- [ ] 建立 `DriveItemRepository` interface。
- [ ] 實作依 id 查詢 item。
- [ ] 實作列出 parent children。
- [ ] 實作建立資料夾。
- [ ] 實作更新名稱。
- [ ] 實作更新 parent。
- [ ] 實作更新星號。
- [ ] 實作同層名稱存在查詢。
- [ ] 建立 `DriveService`。
- [ ] 實作檔名與資料夾名稱驗證。
- [ ] 實作同層重名檢查。
- [ ] 實作建立根目錄資料夾。
- [ ] 實作建立子資料夾。
- [ ] 實作列表排序。
- [ ] 實作列表分頁。
- [ ] 實作重新命名。
- [ ] 實作移動檔案。
- [ ] 實作移動資料夾。
- [ ] 實作禁止移動到自己的子孫資料夾。
- [ ] 實作星號更新。
- [ ] 實作近期項目查詢。
- [ ] 建立 drive router。
- [ ] 實作 `GET /drive/items`。
- [ ] 實作 `POST /drive/folders`。
- [ ] 實作 rename endpoint。
- [ ] 實作 move endpoint。
- [ ] 實作 star endpoint。

## 測試任務

- [ ] 測試建立根資料夾。
- [ ] 測試建立子資料夾。
- [ ] 測試同層重名失敗。
- [ ] 測試不同 parent 可同名。
- [ ] 測試重新命名。
- [ ] 測試移動到不存在 parent 失敗。
- [ ] 測試移動到自己的子資料夾失敗。
- [ ] 測試無權限修改失敗。
- [ ] 測試排序與分頁。


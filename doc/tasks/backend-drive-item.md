# Backend DriveItem 模組任務

## 完成定義

- 可建立資料夾、列出項目、重新命名、移動、標記星號與取得近期項目。
- 同層名稱衝突與循環移動會被阻止。
- Service 與 Repository 可獨立測試。

## 最小可執行任務

- [x] 建立 `DriveItem` SQLAlchemy model。
- [x] 定義 file/folder item type enum。
- [x] 建立 DriveItem request/response schemas。
- [x] 建立統一分頁 schema。
- [x] 建立 `DriveItemRepository` interface。
- [x] 實作依 id 查詢 item。
- [x] 實作列出 parent children。
- [x] 實作建立資料夾。
- [x] 實作更新名稱。
- [x] 實作更新 parent。
- [x] 實作更新星號。
- [x] 實作同層名稱存在查詢。
- [x] 建立 `DriveService`。
- [x] 實作檔名與資料夾名稱驗證。
- [x] 實作同層重名檢查。
- [x] 實作建立根目錄資料夾。
- [x] 實作建立子資料夾。
- [x] 實作列表排序。
- [x] 實作列表分頁。
- [x] 實作重新命名。
- [x] 實作移動檔案。
- [x] 實作移動資料夾。
- [x] 實作禁止移動到自己的子孫資料夾。
- [x] 實作星號更新。
- [x] 實作近期項目查詢。
- [x] 建立 drive router。
- [x] 實作 `GET /drive/items`。
- [x] 實作 `POST /drive/folders`。
- [x] 實作 rename endpoint。
- [x] 實作 move endpoint。
- [x] 實作 star endpoint。

## 測試任務

- [x] 測試建立根資料夾。
- [x] 測試建立子資料夾。
- [x] 測試同層重名失敗。
- [x] 測試不同 parent 可同名。
- [x] 測試重新命名。
- [x] 測試移動到不存在 parent 失敗。
- [x] 測試移動到自己的子資料夾失敗。
- [x] 測試無權限修改失敗。
- [x] 測試排序與分頁。


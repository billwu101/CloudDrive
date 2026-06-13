# Backend Search 模組任務

## 完成定義

- 可搜尋使用者擁有或被分享的未刪除檔案與資料夾。
- 支援 type、MIME type 與分頁篩選。
- 未授權檔案不會出現在結果中。

## 最小可執行任務

- [x] 啟用 PostgreSQL `pg_trgm` extension migration。
- [x] 建立檔名 trigram index migration。
- [x] 建立 search request schema。
- [x] 建立 `SearchRepository`。
- [x] 實作 owner item 名稱搜尋。
- [x] 實作 direct shared item 搜尋。
- [x] 實作排除垃圾桶項目。
- [x] 實作 item type 篩選。
- [x] 實作 MIME type 篩選。
- [x] 實作搜尋結果分頁。
- [x] 實作搜尋結果排序。
- [x] 建立 `SearchService`。
- [x] 正規化空白與搜尋字串。
- [x] 拒絕空搜尋字串。
- [x] 建立 search router。
- [x] 實作 `GET /search`。
- [x] 回傳統一 Page schema。

## 測試任務

- [x] 測試搜尋自己的檔案。
- [x] 測試搜尋被分享檔案。
- [x] 測試不回傳未分享檔案。
- [x] 測試不回傳垃圾桶檔案。
- [x] 測試 file type 篩選。
- [x] 測試 folder type 篩選。
- [x] 測試 MIME type 篩選。
- [x] 測試分頁。


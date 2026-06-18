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


## 延伸：全文內容搜尋（第一階段，2026-06-18）

- [x] `app/search/extract.py`：純函式文字抽取（text/*、json、csv… 以 MIME/副檔名判斷 + PDF 用 pypdf），大小上限 5MB、輸出截斷 200k 字、壞檔不丟例外回 None。
- [x] `file_search_index` 表（model + Alembic 0011）：`item_id`(PK, FK CASCADE)、`content`、`updated_at`；建 GIN index `to_tsvector('english', content)`。隨 drive_item 刪除而 cascade。
- [x] `app/search/indexer.py`：`SearchIndexService.index_file()` 抽取並 upsert（pg insert on conflict）；抽不到內容則清掉舊索引列。
- [x] 上傳整合：`UploadService` 注入 `search_indexer`，上傳成功後就地索引（已有 bytes，不必回讀 storage）。兩個 router（upload、assistant）皆注入。
- [x] 搜尋查詢改寫：`SQLSearchRepository` LEFT JOIN `file_search_index`，比對「檔名 ILIKE OR 內容 ILIKE（涵蓋 CJK）OR 英文 tsvector @@ plainto_tsquery」。
- [x] 測試：extract 各型別/截斷/壞檔、indexer upsert/清舊、整合測試「檔名不含關鍵字、僅內容含」可搜到（Postgres）。
- 註：第二階段（語意/embedding 向量搜尋）待辦——抽取 pipeline 已可共用。舊檔 backfill 與搜尋結果命中片段高亮亦待後續。

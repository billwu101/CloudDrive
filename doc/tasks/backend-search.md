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

## 延伸：語意搜尋（第二階段，2026-06-18）

- [x] `app/search/embedding.py`：`EmbeddingClient` 協定 + `OllamaEmbeddingClient`（POST `/api/embeddings`，httpx transport 可注入、逾時、auth）；失敗丟 `EmbeddingError`。
- [x] `file_embeddings` 表（model + Alembic 0012）：`item_id`(PK, FK CASCADE)、`embedding vector(768)`、`model`、`updated_at`；`CREATE EXTENSION vector` + hnsw cosine index。隨 drive_item cascade。新依賴 `pgvector`（mypy override 忽略缺 stub）。
- [x] `app/search/semantic.py`：`SQLFileEmbeddingRepository`（upsert / delete / `semantic_search` 用 `embedding.cosine_distance(query)` 排序）+ `SemanticSearchService`（embed query → 最近鄰 → score = 1 − cosine 距離）。
- [x] 索引整合：`SearchIndexService` 注入選用 embedding client/repo，上傳抽文字後**同時**寫全文 + embedding（截斷 8000 字）；embedding 失敗不影響全文與上傳；不支援型別連同 embedding 一起清掉。
- [x] `app/search/factory.py`：依 `embedding_enabled` 建 client / index service / semantic service（關閉時 semantic 為 None）。upload + assistant router 共用。
- [x] `GET /search/semantic?q=&limit=`：回傳 `[{item, score}]`；功能關閉或 embedding 服務不可用回 503。
- [x] 設定：`embedding_enabled`(預設 False)、`embedding_model`(nomic-embed-text)、`embedding_base_url`(空則用 llm_base_url)、`embedding_dim`(768)。docker-compose 換 `pgvector/pgvector:pg16` + `EMBEDDING_*` env。
- [x] 測試：embedding client（MockTransport 解析/錯誤）、SemanticSearchService（距離→分數、空 query 不 embed）、SearchIndexService（同寫 embedding、失敗容錯、清舊）、router（關閉 503 / 命中 / 服務掛 503）。**真 pgvector 驗證**：臨時 pgvector 容器跑 migration 0001→0012 成功、cosine `<=>` 排序正確。
- [x] 前端「語意搜尋」切換 UI：SearchPage 加 Keyword／Semantic 模式切換（`useSemanticSearch` → `GET /search/semantic`），語意模式依相關度排序、隱藏類型過濾/分頁，503 顯示「未啟用」提示。測試：searchApi semantic 端點 + 503、SearchPage 模式切換/語意結果/503 提示。
- [x] 舊檔 backfill：`app/search/backfill.py`（`EmbeddingBackfillService` + `SQLEmbeddingBackfillRepository` 找「有全文索引、無 embedding」的檔）；`POST /search/embeddings/backfill?batch_size=`（**per-user**、分批、回 `{indexed, remaining}`、可重複呼叫至 0；embedding 服務掛 503）。測試：service 分批/一次跑完/服務掛 fail-fast、router 關閉 503/回數/服務掛 503；真 pgvector 驗證 join 查詢可執行。
- [x] chunking：長文件切成重疊 chunks（每塊 1000 字、重疊 100、上限 50 塊），每塊一向量；`file_embeddings` 改 multi-row（`id` PK、`chunk_index`、`snippet` 欄）+ migration 0013；`semantic_search` 以 `DISTINCT ON (item_id)` 取每檔最近 chunk。indexer/backfill 改用 `embed_chunks` + `replace_chunks`。真 pgvector 驗證 DISTINCT ON 取最近 chunk + 回對應 snippet。
- [x] 命中片段 + 相似度分數：`/search/semantic` 回 `{item, score, snippet}`（snippet = 最近 chunk 文字）；前端語意結果用 `SemanticResultList` 顯示分數 badge（% match）+ snippet（query 詞高亮）。
- [x] 前端 backfill 觸發入口：語意模式「Index older files」按鈕（`useBackfillEmbeddings`），顯示 indexed/remaining，可重複點到補完。
- 待後續：backfill 背景自動化（目前手動觸發）。

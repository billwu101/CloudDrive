# Frontend Search 模組任務

## 完成定義

- 使用者可從 TopSearchBar 搜尋項目。
- 搜尋具有 debounce、篩選、分頁與狀態顯示。
- 搜尋結果可開啟資料夾或預覽檔案。

## 最小可執行任務

- [x] 建立 SearchFilters type。
- [x] 建立 SearchResultPage 或搜尋結果區。
- [x] 建立 `useSearchItems` query。
- [x] 建立 debounce hook。
- [x] 將搜尋字串同步到 URL query。
- [x] 清空搜尋字串時停止 query，並導回搜尋前頁面（`state.from` 記錄來源路徑，fallback `/drive`）。
- [x] 建立 item type 篩選。
- [x] 建立 MIME type 篩選。
- [x] 建立搜尋結果列表。
- [x] 建立搜尋分頁控制。
- [x] 點擊資料夾時進入資料夾。
- [x] 點擊檔案時開啟 preview。
- [x] 建立 loading state。
- [x] 建立無結果 state。
- [x] 建立 error state。
- [x] 加入 retry。

## 測試任務

- [x] 測試 debounce。
- [x] 測試空字串不查詢，且導回搜尋前頁面（非歷史 -1）。
- [x] 測試 type 篩選。
- [x] 測試 MIME type 篩選。
- [x] 測試搜尋結果開啟資料夾。
- [x] 測試搜尋結果開啟預覽。
- [x] 測試無結果狀態。


## 延伸：語意搜尋 UI（2026-06-18）

- [x] `searchApi.semanticSearch` + `useSemanticSearch` hook（`GET /search/semantic`，retry:false 避免 503 重試）。
- [x] SearchPage 加 Keyword／Semantic 模式切換 pills；語意模式依相關度排序（標示「Sorted by relevance」）、隱藏類型過濾與分頁。
- [x] 語意搜尋未啟用（503）顯示引導訊息，而非一般錯誤。
- [x] 測試：searchApi 語意端點 + 503 傳遞；SearchPage 預設關鍵字結果、切換語意顯示結果、503 提示。

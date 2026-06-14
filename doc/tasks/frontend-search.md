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


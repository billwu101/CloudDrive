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

### 星號清單（全域查詢，修 bug：子資料夾內的星號項目看不到）

> 舊行為只有「列根目錄再前端過濾」，漏掉子資料夾與分頁外的項目。設計見 detailed-design §6.4 星號說明與 §13.5 `GET /drive/starred`。

- [ ] `UserItemPreferenceRepository` 加 `get_all_starred_item_ids(user_id, *, limit)`（查該使用者所有 `is_starred=true`，與資料夾階層無關）。
- [ ] `DriveService` 加 `get_starred(user_id, *, limit)`：取 id → 取回項目 → 濾掉已刪除／非本人擁有者 → 組回應（模式同 `get_recent`）。
- [ ] drive router 實作 `GET /drive/starred`。

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
- [ ] 測試 `GET /drive/starred` 回傳**子資料夾內**的星號項目（回歸本次 bug）。
- [ ] 測試星號清單濾掉已刪除項目與非本人擁有者。


---

## 修正（2026-07-27）：型別欄位為空時預覽誤判為「不支援」

**症狀**：使用者回報一個 PDF 顯示「Preview not available for this file type」，但同資料夾的其他 10 個 PDF 都正常。

**根因**：`_resolve_preview_type` 只看 `mime_type`（markdown 與 Office 才會參考 `extension`）。該檔案的 `mime_type` 與 `extension` 兩欄皆空，於是落到 UNSUPPORTED。實測全庫 95 個檔案中 38 個沒有 mime，其中 31 個有副檔名——這 31 個一律無法預覽。

- [x] `app/preview/service.py`：新增 `_EXT_MIME` 對照表；判定改為 `mime_type` → `extension` → 從 `name` 解析副檔名（`_effective_extension`）。以檔名為最終依據也順帶蓋掉「改名換副檔名但欄位沒更新」的情況。
- [x] `app/preview/service.py`：新增 `resolve_mime()`，`get_info` 與 `content_for_item` 一併改用——否則型別判對了、Content-Type 仍是 `octet-stream`，瀏覽器只會下載。
- [x] 測試 5 項：兩欄皆空的 .pdf、只缺 mime、mp4/png 以檔名判定、未知副檔名仍為 unsupported、輸出 mime 由檔名補上。
- [x] Chrome 實機驗證：該檔案現在開得出 PDF 檢視器，不再顯示「Preview not available」。

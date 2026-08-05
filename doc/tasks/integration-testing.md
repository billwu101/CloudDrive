# Integration、E2E 與驗收任務

> **測試案例總表在 `doc/test-cases.md`**——跑 API 測試與 Playwright 時以該文件為依據，
> 內含驗證強度分級（L0–L4）與各模組的判定準則。本文件只管任務進度，不重複列案例。

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

### 依 `doc/test-cases.md` 第一部補齊（2026-08-05）

現有 71 條約覆蓋四成案例，補上 **69 條**，共 142 條。全部達 A2 以上（寫入後改由查詢端點讀回驗證）。

- [x] `test_api_contract_flow.py`（7）— API-X-01~06。含**前端呼叫路徑逐條比對後端註冊路由**（7a35bb0 防線，目前全數對得上）、錯誤信封、全端點匿名掃描、他人 UUID 掃描。
- [x] `test_star_recent_flow.py`（7）— API-STAR-01~04、API-RECENT-01。含 db5b2b7 兩個回歸點（子資料夾、超過第一頁）。
- [x] `test_preview_flow.py`（8）— API-PREV-01~05。含 31c8b67（驗實際 bytes 與 Content-Type，不驗元素存在）與 edd8314（空 mime 以副檔名 fallback）。
- [x] `test_upload_validation_flow.py`（12）— API-UP-04~15。配額精確增減、拒絕後磁碟零殘留、storage_key 不含原檔名（走檔案系統驗證）、危險檔名 5 種。
- [x] `test_permission_matrix_flow.py`（9）— API-SHR-02~09。viewer/downloader/editor 全矩陣、資料夾繼承、子樹邊界、即時撤銷。
- [x] `test_account_flow.py`（15）— API-USER-01~08、API-AUTH-05~08。含 refresh 續期、登出後重放 refresh token、密碼雜湊（直接查表）。
- [x] `test_hierarchy_flow.py`（11）— API-MV／REN／DIR／LIST／DL。移動兩端都驗、不可移入自身子樹、分頁無重複無遺漏、zip 只含選取項。

**執行結果**：`uv run pytest tests/integration` → **141 passed, 1 failed**。
唯一失敗為 `test_assistant_flow.py::test_chat_second_turn_carries_history_and_result_summary`，
需連得到本機 Ollama（未啟動時回 503），屬環境限制；此條在補測試前的基準即已失敗，非本次造成。
`ruff check` / `ruff format --check` / `mypy` 全通過。

**過程中確認的既有行為（非本次改動，測試已釘住）**：

| 項目 | 實際行為 | 說明 |
|---|---|---|
| 匿名存取受保護端點 | 全端點一致 **401** | 與 §19 相符；既有 `test_unauthenticated_endpoint_returns_403` 寫成 `in (401, 403)`，名稱誤導 |
| 容量不足 | **413** `QUOTA_EXCEEDED` | §19 對照表寫 409，**文件與程式不一致**，待確認以何者為準 |
| 不合法操作 | **422**（`InvalidOperationError`）或 400（直接 `AppError`） | §19 寫 400，同上待確認 |
| 星號清單 | 只列 `owner_id == 自己` 的項目 | 被分享項目加星後不出現在任何人清單；per-user 隔離本身正確 |
| editor 分享的上傳 | 新項目 `owner_id` 為上傳者 | 資料夾擁有者的清單看不到（`list_children` 依 owner 過濾）；與 §33.3-6 公開連結 editor 的歸屬決策相反 |
| editor 權限範圍 | 不含丟垃圾桶 | 與 §14.1 相符（只有改名／移動／上傳新版本） |

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
- [x] 補 headed／UI 執行方式（`test:e2e:headed`、`test:e2e:ui`，`SLOWMO` 可調節奏）。
      實測：headed 的 chromium 行程參數無 `--headless`，確認開出視窗；對照組
      `test:e2e` 仍為 `--headless=old`，CI 不受影響。
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
- [x] 對照 detailed-design/ 模組完成定義逐項檢查。
- [x] 確認無使用者可存取未授權檔案。
- [x] 確認 Docker 開發環境可從零啟動。
- [x] 確認 README 啟動步驟可重現。


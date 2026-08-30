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

### 第二輪：補齊零覆蓋頁面（2026-08-28）

盤點發現 74 個端點中仍有 6 塊完全沒被整合測試碰過，補上 **88 條**，整合測試共 230 條。

- [x] `test_assistant_skills_flow.py`（17）— Skills 頁原本**整頁零覆蓋**。技能清單多租戶隔離、
      核可狀態機、**codeguard 擋下 `import subprocess`／`eval`／dunder／缺 `run()`** 四種情形
      且不覆寫既有程式碼、未核可不得執行（且不留檔案、不建快照）、manifest 型別閘、
      chat_enabled 開關持久化、非擁有者不得編輯／核可／執行／刪除。
- [x] `test_snapshot_usage_flow.py`（15）— §30 快照用量整章。含 `d69851c` 回歸點：
      **可回收空間 != 涵蓋量**（造出兩快照共用內容的情境驗證），以及 §30.4-3 的
      **以 storage_key 而非 checksum 計算共用**（上傳兩份位元組相同但 key 不同的檔案，
      可回收為 8192 而非 4096，直接把兩種去重鍵釘死）。
- [x] `test_model_connection_flow.py`（14）— 外部模型連線。憑證只回遮罩、
      **DB 內為 Fernet 密文（直接查表驗證）**、多租戶隔離、更新與刪除後重新查詢確認。
- [x] `test_semantic_search_flow.py`（13）— 語意搜尋。重點是 **`EMBEDDING_ENABLED` 關閉時
      優雅降級不炸**（那才是 CI 與多數環境的實際狀態）；需要真模型的部分 skip 並說明。
- [x] `test_auth_gaps_flow.py`（15）— 認證缺口。**帳號停用 → 403 `USER_INACTIVE`**（原本零測試）、
      `GET /auth/me` 與 `GET /users/me` 不漂移、忘記密碼對未知與已知 email 回應不可區分。
- [x] `test_public_session_refresh_flow.py`（14）— 公開連結短效憑證續發（§28.7）。
      連結移除／過期後續發必須失敗（§28.3-5 每次存取都重新驗證）、續發不得提升權限。

**執行結果（2026-08-28）**：`225 passed, 5 skipped, 0 failed`（整合）／
`1180 passed, 5 skipped`（後端全套）。`ruff check`／`ruff format --check`／`mypy` 全通過。

**過程中修正的問題**：

1. **`backend/.env` 與根目錄 `.env` 是兩份不同的檔案**，且 `config.py` 的 `env_file=".env"`
   相對於行程工作目錄——Docker 讀根目錄那份，pytest 讀 `backend/` 那份。`backend/.env`
   殘留舊的 LLM token，導致 5 條 assistant 測試以 `ExternalAuthError` 失敗。同步後全過。
   **先前把這條失敗歸因為「需要本機 Ollama 的環境限制」是錯的。**
2. 移除 4 處**恆為真的無效斷言**（型別檢查、schema 保證的欄位存在、已被前一行釘死的 `!=`），
   改為對實際數值斷言。
3. 強化 `conftest.register_and_login`：原本**完全不檢查註冊回應**，若 username 撞唯一鍵而
   靜默 409，呼叫端會拿到前一個使用者的 token 並以錯誤的方式通過。現在檢查註冊狀態碼，
   並以 `GET /users/me` 確認 token 確實屬於所要求的 email。

**發現但未處理（待決定）**：

| 項目 | 說明 |
|---|---|
| `GET /assistant/skills` 無法查詢全部狀態 | 參數為 `status: str \| None = "installed"`，HTTP 上永遠送不出 `None`；`?status=` 會過濾 `== ""` 回空陣列。repository 的 `status is None` 分支從 API 無法到達，且 `?status=bogus` 回空陣列而非 400 |
| 型別閘不對稱 | `_execute_generated` 檢查 manifest 的 `item_types`（DEC-035），`_execute_inspect` 完全不檢查。目前無害（內建 manifest 兩種型別都宣告），但兩條執行路徑只有一條有閘 |
| `update_skill` 依名稱跳過 codeguard | `inspect_item_details` 這個名字會跳過靜態掃描（存的是虛擬碼非沙箱碼，屬刻意）。目前無改名端點所以不可達，若日後新增改名功能會成為破口 |
| 登入頻率限制（§17.4-2） | **後端完全沒有實作**，不是沒測 |

**第一輪執行結果**：`141 passed, 1 failed`。當時把唯一失敗歸因為「需連得到本機 Ollama 的
環境限制」——**這個判斷是錯的**，真正原因是 `backend/.env` 的舊 LLM token（見第二輪第 1 點），
同步後該條即通過。

**過程中確認的既有行為（非本次改動，測試已釘住）**：

| 項目 | 實際行為 | 說明 |
|---|---|---|
| 匿名存取受保護端點 | 全端點一致 **401** | 與 §19 相符；既有 `test_unauthenticated_endpoint_returns_403` 寫成 `in (401, 403)`，名稱誤導 |
| 容量不足 | **413** `QUOTA_EXCEEDED` | §19 原寫 409；已於 `e462fc1` 依實作校正文件 |
| 不合法操作 | **400** | 原本 400／422 並存；已於 `4fcb7f4` 統一為 400，422 讓給 FastAPI 自身的請求驗證 |
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

### 助理模型切換 E2E（2026-08-30）

- [x] `frontend/e2e/assistant-model-switch.spec.ts`（4 條，全通過）
      —— 清單內容、移除連線後消失、**選定後送出訊息帶回工具結果**、中途換模型。
      需要模型的兩條以 `E2E_LLM_BASE_URL` / `E2E_LLM_API_KEY` 控制，未設定即 skip。
      預設打 Docker 堆疊（8088 / 8001），可用 `E2E_BASE` / `E2E_API` 覆寫。
      實測：`4 passed (1.1m)`，其中真實模型呼叫 19.4s 與 43.4s。

**過程中修掉四個「測試綠燈但功能不能用」的設定缺口**（全都是同一個模式：
設定散在多處，而缺漏的那處不會產生任何可辨識的錯誤）：

| 缺口 | 症狀 | 修法 |
|---|---|---|
| `CREDENTIAL_ENCRYPTION_KEY` 只在 `backend/.env`，根目錄 `.env` 沒有 | pytest 的模型連線測試全過，但**執行中的 app 建不了任何連線**（500） | 同步到根目錄 `.env` |
| `docker-compose.yml` 未傳遞 `PRIVACY_DEFAULT` | 改 `.env` 對 Docker 完全無效 | compose 補上該變數 |
| `privacy_default` 預設 `"sensitive"` | **所有具名連線一律拒送**，下拉列得出來但每個都回「連不上模型」 | 本專案的連線指向自架 gateway，設為 `non_sensitive` |
| `docker-compose.yml` 未傳遞 `LLM_NUM_PREDICT` | 輸出上限只能用程式預設，無法調整 | compose 補上該變數 |

## 驗收

- [x] 對照 proposal.md MVP 驗收標準逐項檢查。
- [x] 對照 detailed-design/ 模組完成定義逐項檢查。
- [x] 確認無使用者可存取未授權檔案。
- [x] 確認 Docker 開發環境可從零啟動。
- [x] 確認 README 啟動步驟可重現。


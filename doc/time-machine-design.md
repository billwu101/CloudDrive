# 時光機（Snapshots）設計文件

> 狀態：**設計階段（尚未實作）**。本文件先定義要做什麼與如何整合既有模組；實作前可再調整。
> 參考：Apple Time Machine（<https://support.apple.com/en-us/104984>）的「時間軸瀏覽 + 還原」體驗。

## 1. 目的

讓使用者把整個雲端硬碟「倒帶」到過去某個時間點：瀏覽當時的檔案/資料夾狀態，並把單一檔案、資料夾子樹、或整個硬碟**就地還原**回那個時間點——包含救回被刪的檔案、回復改名與搬移。對應 Apple Time Machine 的核心價值，但落在多使用者的 Web 雲端硬碟情境。

## 2. 與既有模組的關係（重用，不重造）

專案已具備時光機所需的底層元件，時光機是它們之上的「整碟時間點」層：

| 既有元件 | 時光機如何使用 |
|---|---|
| `file_versions`（每檔版本史 + `checksum_sha256`） | 快照的**內容層**：快照項目指向某個 file version，不複製 blob。 |
| `drive_items`（`is_deleted`/`deleted_at`/`parent_id`/`name`/`updated_at`） | 快照記錄當下的名稱、父層、型別，使「改名/搬移/刪除」可被還原。 |
| Trash（軟刪除 + 還原） | 互補：Trash 是短期回收筒；時光機可從快照重建**早已永久刪除**的檔案，不受 Trash 保留期限制。 |
| `activity_logs` | 建立快照與還原都寫稽核紀錄。 |
| Storage（內容定址，checksum dedup） | 未變更的檔案在快照間共用同一 blob → 快照很省空間（增量）。 |
| 背景任務（Celery/RQ + Redis，proposal §21/§8.3） | 跑自動排程快照與保留縮減。 |
| Assistant（workflow executor / skill execute） | 寫入/破壞性操作前自動建快照（見 §4.3）。 |

**設計決策**：不只靠 `file_versions`——它是 per-file，無法表達「整碟在時間 T 的狀態」（哪些檔存在、名稱、位置、刪除與否）。因此新增 `snapshots` / `snapshot_entries` 兩表，內容層引用 `file_versions` 並用 checksum 去重。（記為 DEC-024。）

## 3. 核心概念

- **Snapshot（快照）**：某使用者的整個 drive 在某時間點的狀態，等於一組 entries 的集合。增量儲存：未變更檔案共用既有 version/blob。
- **Snapshot entry（快照項目）**：快照當下「一個檔案或資料夾存在且其狀態」的紀錄——名稱、父層、型別；檔案另指向內容（file version / storage_key / checksum）。
- **Timeline（時間軸）**：依時間排列的快照清單，可點任一快照「進入時光機」唯讀瀏覽當時的 drive。
- **Restore（還原）**：把選定範圍（單檔 / 資料夾子樹 / 整碟）就地還原到所選快照——**覆蓋現況**。
- **Pre-restore snapshot（還原前保命快照）**：每次還原前自動先建一個 `pre_restore` 快照，誤覆蓋也能再倒回來。
- **Pinned（釘選）**：標記為保留的快照，不被自動縮減刪除。

## 4. 快照觸發來源（三種）

### 4.1 自動排程
**預設開啟，每小時**一次（間隔可在設定調整或關閉）建 `trigger=scheduled` 快照，由背景任務驅動。**無變更則跳過**：以 `activity_logs` 判定——若上一個快照之後沒有任何寫入類 activity（建立/上傳/改名/搬移/刪除/還原等），就跳過該次排程快照，避免冗餘與浪費配額。（手動與 assistant 快照不受此跳過影響。）

### 4.2 手動
使用者於時光機頁按「立即建立快照」，建 `trigger=manual`，可加標籤（label）。

### 4.3 AI agent / skill 操作前自動快照（本專案特有）
助理執行**寫入/破壞性 workflow** 或執行**生成式 skill（會寫回 drive）**前，自動建一個 `trigger=assistant` 快照，label 標註來源（例如「執行前：organize_by_type」）。讓使用者對助理的批次操作能一鍵回到操作前狀態。
- **粒度：每個 workflow / 每次 skill 執行前建一個**（一個 workflow 不論內含幾步，只在第一個非唯讀步驟前建一個；單次 skill 執行前建一個）——不是每個寫入步驟各建。
- 串接點：`workflow.py` 的 executor 在第一個非唯讀步驟前、`skills/authoring.py` 的 `_execute_generated` 寫回前，呼叫 `SnapshotService.create(trigger="assistant", label=...)`。
- 唯讀操作不建（無副作用）。

## 5. 還原語意（就地覆蓋）

- **範圍**：
  - 單一檔案 → 還原其內容/名稱/位置到快照當下。
  - 資料夾子樹 → 還原整個子樹。對「快照當時無、現在才新增」的項目，**由使用者在每次還原時選擇模式**：
    - `keep_new`（保留新增物）：只把快照裡有的還原回來，現在多出來的不動。
    - `exact_mirror`（精確鏡像）：完全還原成快照當時樣子，現在多出來的移到垃圾桶。
    - 還原 API 帶 `subtree_mode` 參數，前端還原對話框讓使用者選（預設提示 `keep_new` 較安全）。
  - 整個 drive → 還原全部（同樣可選 `subtree_mode`）。
- **覆蓋規則**：以快照狀態為準覆蓋現況；被刪檔重建、改名/搬移回復、內容回到當時 version。
- **保命**：還原前自動建 `pre_restore` 快照（pinned，不被自動刪）。
- **配額**：還原走 service 層並套配額檢查；若還原會超過（檔案）配額則拒絕並提示。
- **稽核**：還原寫 `activity_logs`（action=`snapshot_restore`，記快照 id 與範圍）。

## 6. 保留策略與配額

- **保留最近 N 個**：每次建快照後執行 prune，依時間保留最近 **N** 個（預設 **N=50**，可設定），超過刪最舊。
- **豁免**：`pinned=true` 與 `trigger=pre_restore` 的快照不計入自動刪除（避免把保命點刪掉）。
- **獨立快照配額**：快照佔用的空間**不計入使用者的檔案配額**，而是另設一個**獨立的快照配額**（per-user 上限，可設）。判斷「快照吃多少空間」以去重後（checksum reference count）實際新增的 blob 計。建快照若會超過快照配額 → 先 prune 最舊的非豁免快照騰空間；仍不夠則該次排程快照跳過並提示（手動建快照則回錯誤）。
  - **預設快照配額 = 使用者檔案配額的一半**（檔案配額目前 15GB → 快照配額預設 7.5GB），可在設定調整。
- **Blob 回收採背景 GC**：刪快照（prune 或手動）時只移除 metadata（snapshot/entries）；實際不再被任何快照或現役檔案引用的 blob，由**背景任務依 checksum 引用計數定期回收**，不阻塞刪除操作。

## 7. 資料模型（新增表，Alembic migration）

### 7.1 `snapshots`
| 欄位 | 型別 | 說明 |
|---|---|---|
| id | uuid | 主鍵 |
| user_id | uuid | 擁有者（FK users，scope 隔離） |
| trigger | varchar | `scheduled` / `manual` / `assistant` / `pre_restore` |
| label | text | 顯示標籤（手動或 assistant 來源說明） |
| item_count | integer | 快照含項目數 |
| total_bytes | bigint | 快照內容總大小（去重後估計） |
| pinned | boolean | 釘選，不被自動縮減 |
| created_at | timestamptz | 建立時間 |

### 7.2 `snapshot_entries`
| 欄位 | 型別 | 說明 |
|---|---|---|
| id | uuid | 主鍵 |
| snapshot_id | uuid | FK snapshots（ON DELETE CASCADE） |
| item_id | uuid | 原 `drive_items.id`（追蹤同一邏輯項目跨快照） |
| parent_item_id | uuid \| null | 快照當下的父層（還原位置用） |
| name | text | 快照當下的名稱 |
| item_type | varchar | FILE / FOLDER |
| version_id | uuid \| null | 指向 `file_versions.id`（檔案內容；資料夾為 null） |
| checksum_sha256 | varchar \| null | 內容定址，便於去重與引用計數 |

> 索引：`(snapshot_id, parent_item_id)` 供瀏覽分頁；`(checksum_sha256)` 供引用計數回收。

## 8. API（設計，前綴 `/api/v1`）

| Method | Path | 用途 |
|---|---|---|
| POST | `/snapshots` | 手動建立快照（body 可帶 label） |
| GET | `/snapshots` | 列出快照（時間軸；含 trigger/label/大小/pinned） |
| GET | `/snapshots/{id}/items?parent_id=` | 瀏覽某快照中某資料夾的內容（唯讀，分頁） |
| POST | `/snapshots/{id}/restore` | 就地還原（body: `scope = whole` 或 `item_ids[]`、`subtree_mode = keep_new`\|`exact_mirror`；自動先建 pre_restore） |
| PATCH | `/snapshots/{id}` | pin/unpin、改 label |
| DELETE | `/snapshots/{id}` | 刪除快照（pre_restore 可選擇性保護；blob 由背景 GC 回收） |
| GET/PUT | `/snapshots/settings` | 保留數 N（預設 50）、自動排程開關（預設開）與間隔（預設每小時）、獨立快照配額上限（per-user 設定） |

## 9. 前端（設計）

- **側欄入口「時光機」**，路由 **`/time-machine`**。
- **時間軸**：快照清單**依日期分組折疊 + 分頁/捲動載入**（像 Time Machine 依日/月分組，因應釘選與保命快照累積）；每項顯示時間、來源標籤、大小、pinned 標記；「立即建立快照」按鈕；保留 N / 排程開關與間隔 / 快照配額用量設定。
- **進入快照**：選一個快照 → 唯讀檔案瀏覽器，呈現當時的 drive（沿用既有 FileGrid/FileTable，資料源換成 snapshot items）。
- **還原流程**：在快照瀏覽器以**多選勾選**檔案/資料夾 → 按「還原選取項」；另有「**還原整個快照**」按鈕。確認對話框明示「**會覆蓋目前內容；已自動建立還原前快照，可再倒回**」，並讓使用者選 `subtree_mode`（保留新增 / 精確鏡像）→ 執行 → 完成後 invalidate `['drive']`。
- 對應元件（建議）：`pages/TimeMachinePage.tsx`、`components/timeline/SnapshotList.tsx`、`SnapshotBrowser.tsx`、`RestoreConfirmDialog.tsx`；`api/snapshotApi.ts`、`hooks/useSnapshots.ts`。

## 10. 後端模組（設計，沿用四件式結構）

```
app/snapshot/
  router.py      # 上述 endpoints
  service.py     # SnapshotService：create(trigger,label) / list / browse / restore / prune
  repository.py  # snapshots / snapshot_entries 查詢
  schemas.py     # I/O schema
alembic/versions/00XX_add_snapshots.py
tests/snapshot/
```
- `SnapshotService.create`：列出使用者現役 drive_items → 為有新內容的檔案確保 file_version → 寫 snapshot + entries（dedup by checksum）→ prune。
- `SnapshotService.restore`：先 `create(trigger="pre_restore", pinned=True)` → 依 scope 比對快照與現況 → 套用差異（重建/改名/搬移/回復內容）→ 配額檢查 → 寫 activity log。

## 11. 安全與權限

- 單使用者 scope：快照只含自己擁有的項目；所有查詢/還原帶 `user_id`。
- 還原一律走 service 層（不直接碰 storage），套配額與權限檢查。
- 還原為破壞性操作 → 前端需明確二次確認；後端強制先建 pre_restore 快照。
- 分享/協作項目的還原僅限擁有者；viewer/editor 不可對他人項目發動還原（後續若有協作快照再議）。

## 12. 里程碑（建議）

1. **S1 資料層**：`snapshots`/`snapshot_entries` model + migration + repository + `SnapshotService.create`（手動）+ 測試。
2. **S2 瀏覽 + 還原**：list / browse / restore（含 pre_restore + `subtree_mode` keep_new/exact_mirror + 配額）+ API + 測試。
3. **S3 保留與排程**：prune（保留 N=50、pinned 豁免）+ 獨立快照配額 + blob 背景 GC + 背景排程自動快照（預設開、每小時）+ 設定 endpoint。
4. **S4 Assistant 整合**：workflow / skill 執行前自動 `assistant` 快照（每個 workflow/skill 一個）。
5. **S5 前端**：`/time-machine` 頁、快照瀏覽、還原流程（含 subtree_mode 選擇）、設定 UI。

## 13. 決策與待確認

### 13.1 已決定（2026-06-17，記入 DEC-024）

| 項目 | 決定 |
|---|---|
| 快照配額 | **獨立快照配額**，不計入使用者檔案配額（§6） |
| 自動排程 | **預設開啟，每小時**（可設定/關閉，§4.1） |
| 保留數 N | **預設 50**（可設定，§6） |
| 子樹還原模式 | **還原時讓使用者選** `keep_new` / `exact_mirror`（§5） |
| Blob 回收 | **背景 GC**（依引用計數，不阻塞刪除，§6） |
| 助理快照粒度 | **每個 workflow / 每次 skill 執行前一個**（§4.3） |
| 協作/分享還原 | **僅擁有者可還原**（§11） |
| 前端路由 | **`/time-machine`**（§9） |
| 快照配額預設值 | **檔案配額的一半**（15GB → 7.5GB，可設，§6） |
| 「無變更則跳過」判定 | **用 `activity_logs`**（上次快照後無寫入類 activity 就跳過，§4.1） |
| 時間軸顯示 | **依日期分組折疊 + 分頁**（§9） |
| 還原選取互動 | **多選勾選 + 「還原選取項」/「還原整個快照」**（§9） |

### 13.2 仍待確認

- 設計層級已無未決項。實作時的細節（分組折疊的捲動載入頁大小、activity「寫入類」動作的確切清單、配額用量的即時估算方式）於對應里程碑（S3/S5）落地時定，不影響資料模型與整體設計。

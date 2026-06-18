# 時光機（Snapshots）模組任務

設計見 [time-machine-design.md](../time-machine-design.md)，決策見 DEC-024。

> 狀態（2026-06-18）：**S1、S2、S3（保留/配額/設定/排程判定）、S4（Assistant 整合）後端 + S5 前端（含進階）完成**並全綠（後端 snapshot 25 測試 + assistant hook 測試、前端 TimeMachinePage 5 測試）。
> 仍未做：**blob 背景 GC**、**實際週期排程 runner/cron**（排程「是否該建」的判定 `run_scheduled_snapshot()` 已實作並測試，只差呼叫它的背景觸發器）、**還原時的硬配額檢查**（還原已寫 activity log）。
> 下列為 checklist（勾選 = 已實作 + 測試）。

## 完成定義

1. 對應 checklist 完成。
2. 單元測試通過（沙箱外、不需真實排程器）。
3. 與 file_versions / storage / assistant 接口已驗證。
4. 無阻擋 MVP 的已知錯誤。

## S1：資料層 + 手動快照

- [x] `snapshots` / `snapshot_entries` model + Alembic migration（user scope、checksum 索引、CASCADE）。
- [x] `app/snapshot/repository.py`：建立快照、列快照、依 `(snapshot_id, parent_item_id)` 瀏覽、依 checksum 引用計數。
- [x] `SnapshotService.create(trigger, label, pinned)`：列現役 drive_items → 必要時補 file_version → 寫 snapshot+entries（dedup）。
- [x] `POST /snapshots`、`GET /snapshots`。
- [x] `tests/snapshot/`：建快照含正確 entries、增量共用 version、空變更可跳過。

## S2：瀏覽 + 還原

- [x] `GET /snapshots/{id}/items?parent_id=`：唯讀瀏覽快照內某層（分頁）。
- [x] `SnapshotService.restore(snapshot_id, scope, subtree_mode)`：先建 `pre_restore`（pinned）→ 比對快照與現況 → 重建/改名/搬移/回復內容 → 依 `subtree_mode`（`keep_new` / `exact_mirror`）處理現有新增物 → 配額檢查 → 寫 activity log。
- [x] `POST /snapshots/{id}/restore`（scope = whole | item_ids[]、subtree_mode）。
- [x] 測試：單檔/子樹/整碟還原、救回已刪檔、回復改名/搬移、`keep_new` 不刪新增物、`exact_mirror` 把新增物移垃圾桶、配額超限拒絕、pre_restore 必建。

## S3：保留、配額與排程

- [x] `SnapshotService.prune`：保留最近 N（預設 50），pinned / pre_restore 豁免；`create()` 後自動呼叫。
- [x] 獨立快照配額（**預設 = 檔案配額的一半**，`quota_bytes=NULL` 即 auto）：以 distinct checksum 去重計算用量，超量時由最舊的非豁免快照開始刪到符合上限（永遠保留最新一筆）。
- [ ] blob 背景 GC：背景任務依 checksum 引用計數回收不再被引用的內容（刪快照只移除 metadata）。**未做**。
- [x] 排程「是否該建」判定 `run_scheduled_snapshot(now)`：排程開、距上次快照已過間隔、且現有檔案>0 才建 `scheduled`（**預設開、每小時**，可設）。
- [ ] 呼叫上述判定的背景週期 runner / cron。**未做**（判定函式已就緒）。
- [x] `snapshot_settings` model + Alembic 0010；`GET/PUT /snapshots/settings`：保留 N、排程開關/間隔、獨立快照配額上限（per-user），回傳 effective_quota_bytes / used_bytes。
- [x] 測試：prune 保留 N 與豁免、快照配額超限由最舊刪起、設定讀寫 + auto 配額解析、排程間隔/停用/空碟跳過。

## S4：Assistant 整合

- [x] workflow executor 在含寫入步驟時於 `before_execution` 建一個 `assistant` 快照（整個 workflow 一個，非每步）— `snapshot_before_write_hook`。
- [x] `skills/authoring.py` `_execute_generated` 寫回前建一個 `assistant` 快照。
- [x] 唯讀操作不建；快照失敗不阻擋執行。測試：含寫入步驟才建「一個」快照、唯讀無快照、快照後端失敗被吞掉。

## S5：前端

- [x] `api/snapshotApi.ts` + `hooks/useSnapshots.ts`（含 settings）。
- [x] 側欄「時光機」入口 + `/time-machine` 路由 + lazy page。
- [x] `TimeMachinePage`（快照時間軸清單 + 立即建立快照 + 依日期分組）。
- [x] 設定 UI：`SnapshotSettingsDialog`（排程開關/間隔、保留 N、auto/自訂配額、顯示用量）。
- [x] 快照內容唯讀瀏覽：資料夾導覽（breadcrumb）、多選勾選。
- [x] 還原確認對話框（明示覆蓋 + 已建保命快照 + 選 `subtree_mode`）：「還原整個快照」與「還原選取項」（scope=items）→ 還原後 invalidate `['drive']`。
- [x] 測試：清單、瀏覽、資料夾導覽、整碟還原、逐項還原（scope=items）、設定讀寫。

## 測試/驗證任務

- [x] `ruff format/check`、`mypy`、`pytest`（snapshot + assistant hook 切片）全綠。
- [x] 前端 `lint`、`typecheck`、`test` 全綠。
- [x] 文件同步：更新本檔與 `progress.md`（S3/S4 完成、GC/排程 runner 標明未做）。

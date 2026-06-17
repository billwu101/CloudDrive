# 時光機（Snapshots）模組任務

設計見 [time-machine-design.md](../time-machine-design.md)，決策見 DEC-024。

> 狀態：**設計完成，尚未實作**。下列為實作時的 checklist（勾選 = 已實作 + 測試）。

## 完成定義

1. 對應 checklist 完成。
2. 單元測試通過（沙箱外、不需真實排程器）。
3. 與 file_versions / storage / assistant 接口已驗證。
4. 無阻擋 MVP 的已知錯誤。

## S1：資料層 + 手動快照

- [ ] `snapshots` / `snapshot_entries` model + Alembic migration（user scope、checksum 索引、CASCADE）。
- [ ] `app/snapshot/repository.py`：建立快照、列快照、依 `(snapshot_id, parent_item_id)` 瀏覽、依 checksum 引用計數。
- [ ] `SnapshotService.create(trigger, label, pinned)`：列現役 drive_items → 必要時補 file_version → 寫 snapshot+entries（dedup）。
- [ ] `POST /snapshots`、`GET /snapshots`。
- [ ] `tests/snapshot/`：建快照含正確 entries、增量共用 version、空變更可跳過。

## S2：瀏覽 + 還原

- [ ] `GET /snapshots/{id}/items?parent_id=`：唯讀瀏覽快照內某層（分頁）。
- [ ] `SnapshotService.restore(snapshot_id, scope, subtree_mode)`：先建 `pre_restore`（pinned）→ 比對快照與現況 → 重建/改名/搬移/回復內容 → 依 `subtree_mode`（`keep_new` / `exact_mirror`）處理現有新增物 → 配額檢查 → 寫 activity log。
- [ ] `POST /snapshots/{id}/restore`（scope = whole | item_ids[]、subtree_mode）。
- [ ] 測試：單檔/子樹/整碟還原、救回已刪檔、回復改名/搬移、`keep_new` 不刪新增物、`exact_mirror` 把新增物移垃圾桶、配額超限拒絕、pre_restore 必建。

## S3：保留、配額與排程

- [ ] `SnapshotService.prune`：保留最近 N（預設 50），pinned / pre_restore 豁免。
- [ ] 獨立快照配額（**預設 = 檔案配額的一半**）：建快照前檢查快照配額（不佔檔案配額），超過先 prune 騰空間、仍不夠則排程跳過/手動回錯誤。
- [ ] blob 背景 GC：背景任務依 checksum 引用計數回收不再被引用的內容（刪快照只移除 metadata）。
- [ ] 背景排程任務：定期 `create(trigger="scheduled")` + prune（**預設開、每小時**，可設）；**以 activity_logs 判定無寫入則跳過**。
- [ ] `GET/PUT /snapshots/settings`：保留 N、排程開關/間隔、獨立快照配額上限（per-user）。
- [ ] 測試：prune 保留 N 與豁免、快照配額超限處理、GC 引用計數回收、排程任務觸發、設定讀寫。

## S4：Assistant 整合

- [ ] workflow executor 在第一個非唯讀步驟前建一個 `assistant` 快照（整個 workflow 一個，非每步）。
- [ ] `skills/authoring.py` `_execute_generated` 寫回前建一個 `assistant` 快照。
- [ ] 唯讀操作不建。測試：破壞性 workflow / skill 執行前確有「一個」快照、唯讀無快照。

## S5：前端

- [ ] `api/snapshotApi.ts` + `hooks/useSnapshots.ts`。
- [ ] 側欄「時光機」入口 + `/time-machine` 路由 + lazy page。
- [ ] `TimeMachinePage`（快照清單**依日期分組折疊 + 分頁**、立即建立、保留/排程/快照配額設定）。
- [ ] `SnapshotBrowser`（唯讀瀏覽當時 drive，沿用 FileGrid/FileTable，**多選勾選**）。
- [ ] `RestoreConfirmDialog`（明示覆蓋 + 已建保命快照 + 選 subtree_mode；「還原選取項」/「還原整個快照」）→ 還原後 invalidate `['drive']`。
- [ ] 測試：清單、瀏覽、還原確認流程（含 subtree_mode 選擇）。

## 測試/驗證任務

- [ ] `ruff format/check`、`mypy`、`pytest`（snapshot 切片）全綠。
- [ ] 前端 `lint`、`typecheck`、`test` 全綠。
- [ ] 文件同步：實作後更新 `prompt.md`、`detailed-design.md`、本檔與 `progress.md`。

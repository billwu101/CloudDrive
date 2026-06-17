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
- [ ] `SnapshotService.restore(snapshot_id, scope)`：先建 `pre_restore`（pinned）→ 比對快照與現況 → 重建/改名/搬移/回復內容 → 配額檢查 → 寫 activity log。
- [ ] `POST /snapshots/{id}/restore`（scope = whole | item_ids[]）。
- [ ] 測試：單檔/子樹/整碟還原、救回已刪檔、回復改名/搬移、配額超限拒絕、pre_restore 必建。

## S3：保留與排程

- [ ] `SnapshotService.prune`：保留最近 N，pinned / pre_restore 豁免；blob 引用計數回收。
- [ ] 背景排程任務：定期 `create(trigger="scheduled")` + prune（間隔可設）。
- [ ] `GET/PUT /snapshots/settings`：保留 N、排程間隔/開關（per-user）。
- [ ] 測試：prune 保留 N 與豁免、排程任務觸發、設定讀寫。

## S4：Assistant 整合

- [ ] workflow executor 在第一個非唯讀步驟前建 `assistant` 快照。
- [ ] `skills/authoring.py` `_execute_generated` 寫回前建 `assistant` 快照。
- [ ] 唯讀操作不建。測試：破壞性 workflow / skill 執行前確有快照、唯讀無快照。

## S5：前端

- [ ] `api/snapshotApi.ts` + `hooks/useSnapshots.ts`。
- [ ] 側欄「時光機」入口 + `/timeline` 路由 + lazy page。
- [ ] `TimelinePage`（快照清單、立即建立、保留/排程設定）。
- [ ] `SnapshotBrowser`（唯讀瀏覽當時 drive，沿用 FileGrid/FileTable）。
- [ ] `RestoreConfirmDialog`（明示覆蓋 + 已建保命快照）→ 還原後 invalidate `['drive']`。
- [ ] 測試：清單、瀏覽、還原確認流程。

## 測試/驗證任務

- [ ] `ruff format/check`、`mypy`、`pytest`（snapshot 切片）全綠。
- [ ] 前端 `lint`、`typecheck`、`test` 全綠。
- [ ] 文件同步：實作後更新 `prompt.md`、`detailed-design.md`、本檔與 `progress.md`。

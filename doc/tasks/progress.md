# 雲端硬碟專案總體進度

本文件只追蹤模組是否完成。各模組的細部工作請在對應任務文件中勾選。

模組完成條件：

1. 對應任務文件中的必要 checklist 已完成。
2. 該模組單元測試通過。
3. 與相依模組的接口已驗證。
4. 沒有阻擋 MVP 的已知錯誤。

## 專案基礎

- [x] [Project Setup 與開發環境](./project-setup.md)
- [x] [Database 與 Migration](./database.md)
- [x] [API Contract 與共用 Schema](./api-contract.md)

## 後端模組

- [x] [Backend Core](./backend-core.md)
- [x] [Backend Auth](./backend-auth.md)
- [x] [Backend User 與 Quota](./backend-user-quota.md)
- [x] [Backend Permission](./backend-permission.md)
- [x] [Backend DriveItem](./backend-drive-item.md)
- [x] [Backend Storage](./backend-storage.md)
- [x] [Backend Upload](./backend-upload.md)
- [x] [Backend Download](./backend-download.md)
- [x] [Backend Preview](./backend-preview.md)
- [x] [Backend Trash](./backend-trash.md)
- [x] [Backend Search](./backend-search.md)
- [x] [Backend Share](./backend-share.md)
- [x] [Backend FileVersion](./backend-file-version.md)
- [x] [Backend ActivityLog](./backend-activity-log.md)

## 前端模組

- [x] [Frontend Routing](./frontend-routing.md)
- [x] [Frontend API Client](./frontend-api-client.md)
- [x] [Frontend Auth](./frontend-auth.md)
- [x] [Frontend Layout](./frontend-layout.md)
- [x] [Frontend Drive](./frontend-drive.md)
- [x] [Frontend Upload](./frontend-upload.md)
- [x] [Frontend Preview](./frontend-preview.md)
- [x] [Frontend Share](./frontend-share.md)
- [x] [Frontend Trash](./frontend-trash.md)
- [x] [Frontend Search](./frontend-search.md)

## 整合與驗收

- [x] [Integration、E2E 與驗收](./integration-testing.md)

## 擴充模組：In-App AI Assistant（28 模組之後新增）

- [x] [Backend Assistant](./backend-assistant.md) — In-App AI Assistant（HARNESS 引擎 + Workflow 管線、本地 Gemma）。M1–M4 全部完成：模型策略、planner/workflow、技能框架與持久化、自我撰寫 sandbox（codegen→codeguard→sandbox→approve→execute→ingest）、skill 管理（`PATCH`/`DELETE /skills/{id}`）。設計見 [assistant-design.md](../assistant-design.md)
- [x] [Frontend Assistant](./frontend-assistant.md) — 聊天面板、計畫確認、技能核可/code review、動態右鍵選單、已存 workflow 重跑、側欄 Skills 管理頁（列表/編輯/刪除）。
- [x] [Assistant 驗證與評分 Harness](./assistant-eval.md) — E1 API/in-process mock runner + verifier/scoring/report + state/safety 斷言 + 多次執行通過率/變異、E2 Playwright browser runner、E3 LLM judge + `--llm real` + baseline 回歸、E4 案例覆蓋。全部完成。設計見 [assistant-eval-design.md](../assistant-eval-design.md)。

## 擴充模組：時光機（Snapshots）（S1–S5 完成）

- [~] [時光機 Snapshots](./time-machine.md) — 類 Apple Time Machine 的整碟時間點還原。**已完成**：S1 資料層 + 手動快照、S2 就地還原（含 pre_restore 保命快照、subtree_mode）、S3 保留最近 N + 獨立快照配額（auto=檔案配額一半）+ `snapshot_settings` + `GET/PUT /snapshots/settings` + blob 背景 GC（`collect_garbage`）+ 背景排程 runner（`SnapshotScheduler`，lifespan 啟動、預設關、env 可開）、S4 Assistant workflow/skill 寫入前自動建 `assistant` 快照、trash 永久刪除改為 dedup-aware（不再誤刪快照引用的 blob）、S5 前端（日期分組、設定 UI、資料夾導覽、多選逐項還原、整碟/逐項還原）。**唯一未完成（非阻擋）**：還原時硬配額檢查（還原已寫 activity log）。設計見 [time-machine-design.md](../time-machine-design.md)，決策 DEC-024。

## 建議執行順序

- [x] 第一階段：Project Setup、Backend Core、Database。
- [x] 第二階段：API Contract、Backend Auth、Backend Storage。
- [x] 第三階段：Backend DriveItem、ActivityLog、User Quota。（Permission、FileVersion 移至第四階段）
- [x] 第四階段：Backend Upload、Download、Preview、Trash、Search、Share。
- [x] 第五階段：Frontend API Client、Frontend Layout。
- [x] 第六階段：Frontend Auth、Frontend Drive。
- [x] 第七階段：Frontend Routing、Upload、Preview。
- [x] 第八階段：Frontend Trash、Search、Share。
- [x] 第九階段：Integration、E2E 與驗收。

## 進度統計

| 類別 | 完成 | 總數 |
| --- | ---: | ---: |
| 專案基礎 | 3 | 3 |
| 後端模組 | 14 | 14 |
| 前端模組 | 10 | 10 |
| 整合與驗收 | 1 | 1 |
| 核心合計 | 28 | 28 |
| 擴充：AI Assistant | 3 | 3 |
| 總合計 | 31 | 31 |

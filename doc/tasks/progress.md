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
- [x] [Backend Upload](./backend-upload.md) — simple upload 已串流化；**分片續傳上傳已完成**（儲存層／資料層／服務／5 端點／清理排程，含 integration 測試）
- [x] [Backend Download](./backend-download.md)
- [x] [Backend Preview](./backend-preview.md)
- [x] [Backend Trash](./backend-trash.md)
- [x] [Backend Search](./backend-search.md) — 檔名搜尋 + 全文內容搜尋（`file_search_index` tsvector）+ 語意搜尋（`file_embeddings` pgvector，Ollama embedding，`GET /search/semantic`，預設關）、舊檔手動 backfill、chunking、snippet/score 回傳。待後續：backfill 背景自動化。
- [x] [Backend Share](./backend-share.md) — 指定使用者分享 + 公開連結管理；**2026-07-27 補齊**：公開連結免認證存取（proposal §28，`app/public_share/`、短效存取憑證、速率限制、migration 0020）與 Shared by me（proposal §29，`GET /share/shared-by-me` + `DriveItemResponse` 兩個標記欄位）。決策 DEC-037/038。
- [x] [Backend FileVersion](./backend-file-version.md)
- [x] [Backend ActivityLog](./backend-activity-log.md)

## 前端模組

- [x] [Frontend Routing](./frontend-routing.md)
- [x] [Frontend API Client](./frontend-api-client.md)
- [x] [Frontend Auth](./frontend-auth.md)
- [x] [Frontend Layout](./frontend-layout.md)
- [x] [Frontend Drive](./frontend-drive.md)
- [x] [Frontend Upload](./frontend-upload.md) — 預檢／並行上限 3／錯誤分類 + **分片流程／續傳／暫停繼續取消**皆完成（proposal §27 / DEC-036）
- [x] [Frontend Preview](./frontend-preview.md)
- [x] [Frontend Share](./frontend-share.md) — 分享彈窗（指定使用者 + 公開連結）；**2026-07-27 補齊**：`/s/:shareToken` 訪客頁（免登入、短效憑證、資料夾瀏覽與 zip）與 Shared by me 頁（可展開、就地移除）+ My Drive 兩種分享標記。
- [x] [Frontend Trash](./frontend-trash.md)
- [x] [Frontend Search](./frontend-search.md)

## 整合與驗收

- [x] [Integration、E2E 與驗收](./integration-testing.md)

## 擴充模組：In-App AI Assistant（28 模組之後新增）

- [x] [Backend Assistant](./backend-assistant.md) — In-App AI Assistant（HARNESS 引擎 + Workflow 管線、本地 Gemma）。M1–M4 全部完成：模型策略、planner/workflow、技能框架與持久化、自我撰寫 sandbox（codegen→codeguard→sandbox→approve→execute→ingest）、skill 管理（`PATCH`/`DELETE /skills/{id}`）。設計見 [detailed-design/ §9](../detailed-design/01-overview.md)
- [x] [Frontend Assistant](./frontend-assistant.md) — 聊天面板、計畫確認、技能核可/code review、動態右鍵選單、已存 workflow 重跑、側欄 Skills 管理頁（列表/編輯/刪除）。
- [x] [Assistant 驗證與評分 Harness](./assistant-eval.md) — E1 API/in-process mock runner + verifier/scoring/report + state/safety 斷言 + 多次執行通過率/變異、E2 Playwright browser runner、E3 LLM judge + `--llm real` + baseline 回歸、E4 案例覆蓋。全部完成。E9（客觀指標）另加：四維度計分、canary 防誤傷、路徑偏離、生成技能真實執行與產出內容檢查、跑批自清帳號；**現行基準 387/420（gemma4:26b，runs=3）與 12B 對照見 [detailed-design §10.19](../detailed-design/10-assistant-eval.md)**。設計見 [detailed-design/ §11](../detailed-design/01-overview.md)。

## 擴充模組：時光機（Snapshots）（S1–S5 完成）

- [x] [時光機 Snapshots](./time-machine.md) — 類 Apple Time Machine 的整碟時間點還原。**已完成**：S1 資料層 + 手動快照、S2 就地還原（含 pre_restore 保命快照、subtree_mode）、S3 保留最近 N + 獨立快照配額（auto=檔案配額一半）+ `snapshot_settings` + `GET/PUT /snapshots/settings` + blob 背景 GC（`collect_garbage`）+ 背景排程 runner（`SnapshotScheduler`，lifespan 啟動、服務預設關、compose 單 worker 可開）、S4 Assistant workflow/skill 寫入前自動建 `assistant` 快照、trash 永久刪除改為 dedup-aware（不再誤刪快照引用的 blob）、S5 前端（日期分組、設定 UI、資料夾導覽、多選逐項還原、整碟/逐項還原）。**非阻擋限制**：還原時硬配額檢查待補強（還原已寫 activity log）。設計見 [detailed-design/ §13](../detailed-design/01-overview.md)，決策 DEC-024。

## 擴充模組：外部模型接入（Codex/OpenAI）（EM1–EM3 完成）

- [x] [外部模型接入](./external-model.md) — 本地 Gemma 4 反覆失敗（延用 `MAX_LOCAL_ATTEMPTS`）時升級 GPT-5.5（使用者自帶憑證）。**EM1+EM2+EM3 完成**：`user_external_credentials` 加密表（Fernet、`CREDENTIAL_ENCRYPTION_KEY`、永不回明文）+ profile 設定/遮罩 UI + ModelRouter per-user 升級接線 + **OpenAI API key 路徑**（`ExternalLLMClient`，gpt-5.5；失敗/額度耗盡自動標 invalid）+ **Codex 訂閱路徑**（per-request 隔離 `CODEX_HOME` + CLI refresh 回寫加密 + 訂閱優先退回 API key，跨機可用已 §9.6 實證）。考官 provider（原 E4，開發者 eval 工具）移至 [assistant-eval.md](./assistant-eval.md) E6。決策 DEC-026；任務 [external-model.md](./external-model.md)；設計 [detailed-design/ §12](../detailed-design/01-overview.md)。

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

## 已知限制與待補（2026-07-27 盤點）

模組層面 33/33 完成，以下為誠實列出的非阻擋缺口。分為「先前已知」與「本輪新發現」。

### 先前已知（仍成立）

| 缺口 | 嚴重度 | 出處 |
| --- | --- | --- |
| 時光機還原時的硬配額檢查待補強（還原已寫 activity log） | 低 | [time-machine.md](./time-machine.md) |
| 語意搜尋舊檔 embedding backfill 尚未背景自動化（目前手動觸發） | 低 | [backend-search.md](./backend-search.md) |
| 評測結論綁定單一模型與硬體（gemma4:26b + 本機 GPU），換模型需重跑 sweep | — 前提而非缺陷 | [assistant-eval.md](./assistant-eval.md) |
| ~~planner 寫入意圖規劃在困難集（EC2/EC4）約 47%~~ **已改善**：現行基準 EC2 95/120、EC4 100/100（`runs=3`，判分語意見 §10.18）。殘餘失敗集中在批次分類誤搬 canary | 中（功能可靠性） | [detailed-design §10.19](../detailed-design/10-assistant-eval.md) |
| ~~助理無對話記憶（有存沒回讀）~~ **已落地**：對話記憶 v1（`assistant/memory.py` + `router.py` 回讀歷史）。**但評測案例仍全為單輪**，多輪指涉的可靠性尚未量化 | 中（驗證覆蓋） | [roadmap.md](../roadmap.md) |

> 已作廢：「量化未納入瀏覽器端與生成技能執行測試」——E2（browser runner）與 E5（執行驗證模式）皆已完成，browser 實測 3/3 PASS、`--mode exec` 有 4 個 EC3 案例。該敘述屬某一輪評測的附註，非現況缺口。

### 本輪新發現（尚未處理）

| 缺口 | 嚴重度 | 說明 |
| --- | --- | --- |
| **快照無刪除端點** | 中 | `/snapshots` 只有 GET/POST/restore/settings，沒有 DELETE。時光機頁的「Space you would reclaim」列出可回收 2.6 GB，使用者卻無法據以動手；只能等保留機制（最新 50）自動汰換。待確認：是否開放手動刪除、`pre_restore`／pinned 是否可刪、確認強度。 |
| **rename 不更新 `extension` / `mime_type`** | 中 | `DriveService.rename` 只寫 `name`。把 `a.txt` 改名為 `a.pdf` 後兩欄仍是舊值。預覽已用檔名 fallback 繞開（DEC 見 `core/mime.py`），但欄位本身仍不一致，其他依賴該欄位的功能會讀到錯的值。 |
| **資料夾上傳帶入 OS 系統檔** | 低 | `webkitdirectory` 會把 `.DS_Store`／`Thumbs.db` 一併上傳（實測佔 10 KB 並進入搜尋與「最近」）。上傳路徑無任何過濾。待確認：過濾清單範圍、是否只在資料夾上傳時套用。 |
| **`FileIcon` 未套 mime fallback** | 低（純外觀） | 圖示仍只讀 `mime_type` 欄位，欄位為空時顯示通用檔案圖示，與已修好的預覽判定不一致。 |
| **垃圾桶權限與設計不符** | 低 | `detailed-design/06-backend.md` §6.10 權限表寫「delete to trash：owner 或 editor」，但 `TrashService` 實作為 owner-only。屬設計與實作對不上，需擇一修正。 |

## 進度統計

| 類別 | 完成 | 總數 |
| --- | ---: | ---: |
| 專案基礎 | 3 | 3 |
| 後端模組 | 14 | 14 |
| 前端模組 | 10 | 10 |
| 整合與驗收 | 1 | 1 |
| 核心合計 | 28 | 28 |
| 擴充：AI Assistant | 3 | 3 |
| 擴充：時光機 Snapshots | 1 | 1 |
| 擴充：外部模型接入 | 1 | 1 |
| 總合計 | 33 | 33 |

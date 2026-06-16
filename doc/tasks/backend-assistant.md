# Backend Assistant 模組任務（HARNESS 引擎 + Workflow 管線）

對應設計：[assistant-design.md](../assistant-design.md)
模型：Gemma 4 26B（本地，Ollama / OpenAI 相容）。

## 完成定義

- 使用者用自然語言描述需求 → 助理產生候選 Workflow → 檢查技能 → 權限安全 → 顯示計畫 → 確認 → 執行 → 記錄。
- 涵蓋各類檔案/資料夾日常操作；缺能力時現場生成技能（核可→沙箱→安裝）並可 workflow 化、重用。
- 一律經 service 層或沙箱，帶 `user_id`，多租戶安全。
- 絕不自動執行未審核程式碼。LLM 可 mock 測試。

## M1：引擎骨架（HARNESS 01/02/05/07）

- [ ] `core/config.py` 新增 LLM/assistant/sandbox 相關設定。
- [ ] `llm/client.py` + `llm/ollama.py`：Gemma 經 Ollama/OpenAI 相容，tool-call 解析與修復重試。
- [ ] `context.py`：token 預算、裁切/摘要、輸出瘦身。
- [ ] `prompt.py`：動態 system prompt（穩定前綴、無隨機/時間戳）。
- [ ] `service.py`：AgentLoop（停止條件、上限、hook 點）。
- [ ] `skills/registry.py` + `skills/builtin/`：唯讀內建技能 `list_items`/`get_info`/`search`/`recent`/`storage_quota`。
- [ ] `router.py`：`POST /assistant/chat`；無 key/停用回 503；註冊進 api/v1。

## M2：Workflow 管線（planner/workflow + HARNESS 08/09）

- [ ] `planner.py`：NL → 候選 Workflow 結構化輸出 + schema 驗證 + 修復重試。
- [ ] `workflow.py`：Workflow/WorkflowRun 模型；執行器（相依、錯誤策略、單步結果）。
- [ ] `permissions.py`：分層權限（唯讀自動 / 破壞性確認 / 安裝+執行碼核可），逐步驟標記。
- [ ] `hooks.py`：HookRegistry + 內建 hooks（稽核、權限閘、計畫顯示 before_execution、安裝前驗證）。
- [ ] 管線串接：解析→候選→檢查技能→權限→顯示計畫→確認閘→執行→記錄；唯讀 fast-path 自動確認。
- [ ] 計畫顯示與確認 endpoint（顯示步驟/影響/需核可項；接收是/否與修正）。

## M3：技能框架與持久化（HARNESS 03/05/06）

- [ ] Alembic migration：`assistant_sessions`/`assistant_messages`/`assistant_skills`/`assistant_workflows`/`assistant_workflow_runs`。
- [ ] `repository.py`：上述 CRUD；啟動載入使用者技能與已存工作流程。
- [ ] `skills/manifest.py`：manifest schema + 驗證（含 `ui.context_menu`）。
- [ ] 寫入/批次內建技能：`create_folder`/`rename`/`move`/`copy`/`trash`/`restore`/`star`/`share`/`batch_rename`/`organize_by_type`/`organize_by_date`/`deduplicate`/`bulk_move`。
- [ ] 工作流程命名儲存與一鍵重跑 endpoint。

## M4：自我撰寫 + 安全（HARNESS 04/03/08/09）

- [ ] `subagent.py`：單層子代理（codegen）。
- [ ] `skills/authoring.py`：`author_skill` + 生成子流程（codegen→驗證→pending_approval）。
- [ ] `skills/sandbox.py`：子行程沙箱（CPU/記憶體/逾時、路徑限 storage、無對外網路、參數化呼叫）。
- [ ] 技能核可/安裝/觸發 endpoint。
- [ ] 7zip 範例端到端（生成→核可→沙箱→安裝→掛右鍵→解壓寫回 drive items）。

## 測試任務

- [ ] `test_router.py` / `test_loop.py` / `test_dispatch.py` / `test_context.py`。
- [ ] `test_planner.py`：NL→候選 workflow 結構化輸出與驗證。
- [ ] `test_workflow.py`：相依、錯誤策略、fast-path vs 需確認。
- [ ] `test_authoring.py`：停在 pending_approval。
- [ ] `test_sandbox.py`：逾時/路徑/網路限制。
- [ ] `test_hooks.py`：權限閘阻擋破壞性/安裝。
- [ ] `ruff format/check`、`mypy app tests`、`pytest` 全綠。

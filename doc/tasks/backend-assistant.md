# Backend Assistant 模組任務（HARNESS 引擎 + Workflow 管線）

對應設計：[assistant-design.md](../assistant-design.md)
模型：Gemma 4 26B（本地，Ollama / OpenAI 相容）。

## 完成定義

- 使用者用自然語言描述需求 → 助理產生候選 Workflow → 檢查技能 → 權限安全 → 顯示計畫 → 確認 → 執行 → 記錄。
- 涵蓋各類檔案/資料夾日常操作；缺能力時現場生成技能（核可→沙箱→安裝）並可 workflow 化、重用。
- 一律經 service 層或沙箱，帶 `user_id`，多租戶安全。
- 絕不自動執行未審核程式碼。LLM 可 mock 測試。

## M1：引擎骨架（HARNESS 01/02/05/07）

- [x] `core/config.py` 新增 LLM/assistant/sandbox 相關設定 + Gemma 4 Ollama 部署設定（`LLM_BASE_URL`/`LLM_API_KEY`/`ASSISTANT_MODEL`/`LLM_NUM_CTX`/`LLM_TIMEOUT_SECONDS`/`LLM_KEEP_ALIVE`）+ 外部升級設定（`EXTERNAL_LLM_ENABLED`/`MAX_LOCAL_ATTEMPTS`/`EXTERNAL_LLM_BASE_URL`/`EXTERNAL_MODEL`/`EXTERNAL_LLM_API_KEY`/`PRIVACY_DEFAULT`）。
- [x] `llm/client.py` + `llm/ollama.py`：本地 Gemma 經 Ollama/OpenAI 相容，tool-call 解析與修復重試。
- [x] `llm/external.py`：外部大型模型 API 執行器（可設定、可關閉，共用 LLMClient 介面）。
- [x] `llm/privacy.py`：隱私分類 + 去識別化（升級前置；去識別化失敗則禁止外送）。
- [x] `llm/router.py`：模型策略（隱私閘 + 複雜度路由 + 失敗升級）—— 追蹤 `local_attempts`，連續 `MAX_LOCAL_ATTEMPTS` 次仍不可接受且符合隱私條件時升級外部；不符資格則不外送、回報失敗；升級事件寫稽核 hook。
- [x] `context.py`：token 預算、裁切/摘要、輸出瘦身。
- [x] `prompt.py`：動態 system prompt（穩定前綴、無隨機/時間戳）。
- [x] `service.py`：AgentLoop（停止條件、上限、hook 點）。
- [x] `skills/registry.py` + `skills/builtin/`：唯讀內建技能 `list_items`/`get_info`/`search`/`recent`/`storage_quota`。
- [x] `router.py`：`POST /assistant/chat`；無 key/停用回 503；註冊進 api/v1。

M1 實作備註（2026-06-16）：本切片完成可 mock 的 agent loop、Ollama/OpenAI-compatible tool call parsing、外部升級路由與隱私閘、唯讀內建技能，以及 `/assistant/chat`。Docker 預設已接 `gemma4:26b` at `http://192.168.10.75:11434`，`num_ctx=65536`、timeout 300 秒、`keep_alive=15m`。尚未進入 M2 workflow 計畫確認、M3 持久化、M4 生成技能沙箱。

M1b 實作備註（2026-06-17）：新增第一個安全白名單技能生成/安裝切片。`/assistant/chat` 遇到右鍵 Inspect details 需求時產生 `pending` manifest proposal；核可後安裝至 `assistant_skills`，右鍵執行時經 `DriveService.get_item()` 回傳 metadata。此切片不執行任意 LLM 生成程式碼。

## M2：Workflow 管線（planner/workflow + HARNESS 08/09）

- [x] `planner.py`：NL → 候選 Workflow 結構化輸出（JSON）+ schema 驗證 + 去 code-fence + 修復重試（經 ModelRouter validator）。
- [x] `workflow.py`：WorkflowStep/StepResult + `WorkflowExecutor`（依序執行、相依驗證在 permissions、stop-on-error、hook 觸發點）。
- [x] `permissions.py`：`classify_steps` 依 registry 標 permission_tier 與 requires_approval；拒絕未知技能與向前相依；`is_auto_confirmable`（全唯讀才 fast-path）。
- [x] `hooks.py`：HookRegistry + 內建稽核 hooks（before_execution/before_step/after_step/on_error）。
- [x] 管線串接（`service.py` WorkflowService）：解析→候選→檢查技能→權限→唯讀 fast-path 自動執行＋記錄 / 非唯讀持久化 pending→confirm 執行→記錄。`/chat` 全走 planner。
- [x] 計畫顯示與確認 endpoint：`/chat` 回 plan（步驟/tier/需核可）；`POST /workflows/{id}/confirm`、`/workflows/{id}/cancel`。
- [x] Alembic migration `0006`：`assistant_workflows`/`assistant_workflow_runs`（pending 計畫伺服器持久化，DEC-021）。

M2 實作備註（2026-06-17）：`/chat` 改走 planner（取代 M1 直接 tool-loop，`AgentService`→`WorkflowService`）。唯讀計畫自動執行並寫 workflow run；破壞性/安裝類計畫存成 pending workflow，需 `confirm` 才執行（`cancel` 取消）。pending 計畫伺服器持久化、依 `user_id` 隔離，使用者無法竄改步驟提權。尚未做：planner 對 workflow 重用的參考、寫入型內建技能（M3）、前端計畫卡（frontend M2）。

## M3：技能框架與持久化（HARNESS 03/05/06）

- [ ] Alembic migration：`assistant_sessions`/`assistant_messages`/`assistant_skills`/`assistant_workflows`/`assistant_workflow_runs`。
- [x] Alembic migration：`assistant_skills`（`pending`/`installed` manifest 持久化切片）。
- [x] `repository.py`：`assistant_skills` create/replace pending、list by status、approve、get by id/name。
- [ ] `repository.py`：sessions/messages/workflows CRUD；啟動載入使用者技能與已存工作流程。
- [ ] `skills/manifest.py`：manifest schema + 驗證（含 `ui.context_menu`）。
- [ ] 寫入/批次內建技能：`create_folder`/`rename`/`move`/`copy`/`trash`/`restore`/`star`/`share`/`batch_rename`/`organize_by_type`/`organize_by_date`/`deduplicate`/`bulk_move`。
- [ ] 工作流程命名儲存與一鍵重跑 endpoint。

## M4：自我撰寫 + 安全（HARNESS 04/03/08/09）

- [ ] `subagent.py`：單層子代理（codegen）。
- [ ] `skills/authoring.py`：`author_skill` + 生成子流程（codegen→驗證→pending_approval）。
- [x] `skills/authoring.py`：第一個 deterministic `inspect_item_details` pending proposal + approve/install/execute 切片。
- [ ] `skills/sandbox.py`：子行程沙箱（CPU/記憶體/逾時、路徑限 storage、無對外網路、參數化呼叫）。
- [x] 技能核可/安裝/觸發 endpoint（manifest-only `inspect_item_details` 切片）。
- [ ] 技能核可/安裝/觸發 endpoint（任意 generated code + sandbox）。
- [ ] 7zip 範例端到端（生成→核可→沙箱→安裝→掛右鍵→解壓寫回 drive items）。

## 測試任務

- [x] `test_router.py` / `test_loop.py` / `test_dispatch.py` / `test_context.py`。
- [x] `test_model_router.py`：本地連續失敗達上限 → 升級外部；隱私敏感且無法去識別化 → **不**外送、回報失敗；外部停用 → 不升級。
- [x] `test_skill_authoring.py`：pending manifest proposal、已安裝去重、installed skill execute metadata。
- [x] `test_planner.py`：NL→候選 workflow 結構化輸出、去 fence、修復重試。
- [x] `test_workflow.py`：fast-path 自動執行、破壞性 pending 不執行、confirm 執行、cancel、未知 workflow。
- [x] `test_permissions.py`：tier 標記、未知技能拒絕、向前相依拒絕、auto-confirmable。
- [ ] `test_authoring.py`：任意 codegen 停在 pending_approval。
- [ ] `test_sandbox.py`：逾時/路徑/網路限制。
- [ ] `test_hooks.py`：權限閘阻擋破壞性/安裝。
- [ ] `ruff format/check`、`mypy app tests`、`pytest` 全綠。

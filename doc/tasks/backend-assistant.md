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

- [x] Alembic migration：`assistant_sessions`/`assistant_messages`（`0007`）、`assistant_skills`（`0005`）、`assistant_workflows`/`assistant_workflow_runs`（`0006`）、`assistant_workflows.name`（`0008`，已存工作流程）。
- [x] Alembic migration：`assistant_skills`（`pending`/`installed` manifest 持久化切片）。
- [x] `repository.py`：`assistant_skills` create/replace pending、list by status、approve、get by id/name。
- [x] `repository.py`：sessions/messages CRUD（`AbstractAssistantSessionRepository`：`ensure_session`/`add_message`/`list_sessions`/`list_messages`，依 `user_id` 隔離）；workflows CRUD（pending + 已存 `save_named`/`list_saved`/`get_saved`）。
- [x] `skills/manifest.py`：manifest schema + 驗證（嚴格 `SkillManifest`：識別字 `name`、semver `version`、`ui.context_menu` 含 `FILE`/`FOLDER` item types；`validate_manifest` 拒絕畸形並強制 handler == skill name；接到撰寫草稿與核可/安裝閘）。
- [x] 寫入內建技能：`create_folder`/`rename_item`/`move_item`/`star_item`（write）+ `trash_item`（destructive）/`restore_item`（write，需 trash_service）。皆非 read → 走計畫確認;經 DriveService/TrashService 帶 user_id;UUID/必填參數驗證 + 測試。eval mock 案例涵蓋 create/rename/trash。
- [x] 其餘寫入技能：`share_item`（經 `ShareLinkService` 建公開檢視連結，需 share_link_service）、`organize_by_type`（composite：把根目錄散落檔案搬進 `{ext}-files` 資料夾，缺則建立）。`copy` 依提案不另實作（不得做檔案複製）；`batch_rename`/`bulk_move` 由可組合 planner 多步驟達成，不另設專用技能；`deduplicate`/`organize_by_date` 暫緩（去重需 checksum 揭露，目前 `DriveItemResponse` 未含）。
- [x] 工作流程命名儲存與一鍵重跑 endpoint：`POST /assistant/workflows/save`（驗證技能後存成 `saved`，不執行）、`GET /assistant/workflows/saved`、`POST /assistant/workflows/saved/{id}/rerun`（重驗 → 執行 → 記錄 run）。
- [x] 對話持久化 endpoint：`/chat` 記錄 user/assistant 訊息並 `ensure_session`；`GET /assistant/sessions`、`GET /assistant/sessions/{id}/messages`（依擁有者）。

M3 實作備註（2026-06-17）：完成 sessions/messages 持久化（`0007`）、工作流程命名儲存＋一鍵重跑（`0008` 加 `name` 欄、`saved` 狀態）、`skills/manifest.py` 嚴格 manifest schema + 驗證（接到撰寫草稿與安裝閘），以及最後兩個寫入技能 `share_item`/`organize_by_type`。三個假 workflow repo（unit/property/eval-inproc）同步補上 `save_named`/`list_saved`/`get_saved`。批次操作走可組合 planner，不另設專用技能。

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
- [x] `test_workflow.py`：可組合技能（步驟輸出引用解析）+ 引用不到乾淨失敗。
- [x] `test_workflow.py`：工作流程命名儲存（驗證未知技能拒絕、不執行）、saved 列表、一鍵重跑（執行＋記錄 run）、跨使用者/未知 rerun 拒絕。
- [x] `test_write_skills.py`：`share_item`（經 ShareLinkService）、`organize_by_type`（依副檔名分組搬移、缺資料夾則建立）、無 share_service 時技能缺席。
- [x] `test_router.py`：`/chat` 持久化 user/assistant 訊息、`GET /sessions`、`GET /sessions/{id}/messages`。
- [x] `test_manifest.py`：合法 manifest round-trip、預設空選單、非物件拒絕、結構性畸形（壞 name/version/item_types/額外欄位）拒絕、handler≠skill name 拒絕。
- [x] `test_pipeline_properties.py`：**property-based（hypothesis）模糊測試**，隨機產生複雜計畫（多技能/引用/未知技能/壞參數），驗證硬性不變量：validate_plan 全函式且健全、executor 永不拋例外且遇錯即停、resolve_arguments 只拋 StepResolutionError、classify 標 tier 或拒未知、**planner 產出永遠是可執行或空（絕不交出非法計畫）**。每項 200–300 隨機例。
- [ ] `test_authoring.py`：任意 codegen 停在 pending_approval。
- [ ] `test_sandbox.py`：逾時/路徑/網路限制。
- [ ] `test_hooks.py`：權限閘阻擋破壞性/安裝。
- [ ] `ruff format/check`、`mypy app tests`、`pytest` 全綠。

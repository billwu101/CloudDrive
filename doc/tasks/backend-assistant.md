# Backend Assistant 模組任務（HARNESS 引擎 + Workflow 管線）

對應設計：[detailed-design/ §9](../detailed-design/01-overview.md)
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
- [x] 動態 system prompt（穩定前綴、無隨機/時間戳）—— **無獨立 `prompt.py`**，內嵌於 `planner.build_planner_prompt` 與 `subagent.build_codegen_prompt`。
- [x] `service.py`：AgentLoop（停止條件、上限、hook 點）。
- [x] `skills/registry.py` + `skills/builtin/`：唯讀內建技能 `list_items`/`get_info`/`search`/`recent`/`storage_quota`。
- [x] `router.py`：`POST /assistant/chat`；無 key/停用回 503；註冊進 api/v1。

M1 實作備註（2026-06-16）：本切片完成可 mock 的 agent loop、Ollama/OpenAI-compatible tool call parsing、外部升級路由與隱私閘、唯讀內建技能，以及 `/assistant/chat`。當時 Docker 已接 `gemma4:26b` at `http://192.168.10.75:11434`，`num_ctx=65536`、timeout 300 秒、`keep_alive=15m`。後續 M2 workflow 計畫確認、M3 持久化、M4 生成技能沙箱已完成，見下方各節。

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

- [x] `subagent.py`：單層子代理（codegen）。`CodegenSubAgent.author` 經 ModelRouter 產生 `{manifest, code}`,靜態驗證（manifest schema + codeguard）後失敗回饋重試;不執行,只回提案。
- [x] `skills/authoring.py`：`author_skill` + 生成子流程（codegen→靜態驗證→pending_approval）。`handle_authoring_message` 依生成意圖路由到子代理,存成 pending 提案,絕不自動安裝/執行;日常內建操作不觸發。
- [x] `skills/authoring.py`：第一個 deterministic `inspect_item_details` pending proposal + approve/install/execute 切片。
- [x] `skills/sandbox.py`：子行程沙箱（`python -I` + 自有 process group + 最小 env;POSIX CPU/檔案大小 rlimit;`sys.addaudithook` 永久封鎖網路/spawn/output 外寫入;參數化 `run(input_path, output_dir, params)`）。另加 `skills/codeguard.py` AST 靜態防線。
- [x] 技能核可/安裝/觸發 endpoint（manifest-only `inspect_item_details` 切片）。
- [x] 技能核可/安裝/觸發 endpoint（任意 generated code + sandbox）：`execute_skill` 對生成技能從 storage 取檔 → `asyncio.to_thread` 跑沙箱 → 把產出檔案經 `UploadService` 寫回 drive（建立 `<name> (extracted)` 資料夾、鏡射巢狀目錄）;失敗回 4xx 且不寫入。execute endpoint 加 commit。
- [x] 7zip 範例端到端（生成→核可→沙箱→安裝→解壓寫回 drive items）：加 `py7zr` 相依（zip 走 stdlib）;`test_skill_execution.py` 以真實 zip 在真實沙箱解壓並寫回 readme.txt + 巢狀 docs/guide.md。前端右鍵掛載屬 M5（manifest UI 已支援）。

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
- [x] `test_authoring.py`：任意 codegen 停在 pending_approval（不自動安裝/執行）;失敗無提案;非生成意圖回 None。`test_subagent.py`：驗證提案、不安全碼修復重試、放棄不交出碼、非 JSON 處理。
- [x] `test_sandbox.py`：逾時/路徑（output 外寫入）/網路/子行程封鎖 + codeguard 靜態拒絕。`test_skill_execution.py`：真實 zip 在沙箱解壓並寫回 drive、沙箱失敗不寫入。
- [x] `test_hooks.py`：HookRegistry 依序觸發、executor 觸發 before/after/on_error、權限閘讓破壞性/安裝不進 fast-path（需核可）。
- [x] `ruff format/check`、`mypy app tests`、`pytest` 全綠（M4 切片）。
- [x] `_build_local_client(settings)` 依 `llm_provider` 分派本機執行器（`ollama`→`OllamaLLMClient`、`openai_compatible`→`ExternalLLMClient`）；`test_router.py` 兩案例驗證。

本機 provider 切換備註（2026-07-07）：`app/assistant/router.py` 抽出 `_build_local_client(settings)`，`llm_provider="openai_compatible"` 時本機改走 `ExternalLLMClient`（OpenAI 相容 `/v1/chat/completions`），供指向 OpenAI 相容 gateway（後端可為 gemma4:26b）。`config.py` 註解、`doc/detailed-design/` §8.12 同步；`.env` 為本機設定、不進版控。測試：`test_router.py::test_build_local_client_*`。

M4 實作備註（2026-06-17）：完成自我撰寫技能管線——`subagent.py`(codegen)、`skills/codeguard.py`(AST 靜態驗證)、`skills/sandbox.py`(子行程沙箱:`-I`+process group+rlimit+audithook 封鎖網路/spawn/越界寫入)、`authoring.py` 生成子流程(意圖→codegen→pending,核可→安裝,執行→沙箱→寫回 drive)。加 `py7zr` 相依。前端右鍵掛載與程式碼審查 dialog 屬 M5。尚未做:生成子流程接進 planner 的「缺技能」自動偵測(目前由 authoring 關鍵字意圖觸發)、7zip 真模型 live 瀏覽器 demo(需重建 Docker 映像)。

## 本機約束解碼（2026-07-04）

- [x] `llm/ollama.py`：`_to_ollama_format()` 從 json_schema 信封拆出裸 schema 放進 Ollama `format`（grammar 級約束解碼，取代寫死的 `format:"json"` 弱檔）；僅結構化請求 `options.temperature=0`，一般聊天取樣不變。
- [x] `llm/router.py`：本機路徑補轉發 `response_format`（先前只有外部路徑有，本機 Ollama 收不到 schema）。
- [x] `test_ollama_client.py`：信封拆殼、裸 schema 通過、無 response_format 時不加 format/temperature（TDD 先紅後綠）。
- [x] `test_planner.py`：planner 每次呼叫帶 `_PLAN_RESPONSE_FORMAT`、首次合法計畫只呼叫 LLM 一次、手寫 schema 與 `PlanResult`/`PlannedStep` 欄位 drift test。`validate_plan` + repair loop 語意防線測試維持不變。
- [ ] （後續）`llm/anthropic.py` 改用 `output_config.format` 結構化輸出（目前只加「Respond with valid JSON only」prompt，無硬約束）。
- [x] `subagent.py` codegen 呼叫補 `response_format`（2026-07-06）：`_CODEGEN_RESPONSE_FORMAT`（skill_proposal json_schema：五欄全 required、context_menu 結構、item_types enum）接進 `author()`——信封形狀由 grammar 保證；識別字/handler==name 仍由 validate_manifest 把關。
- [x] **per-call temperature 覆寫**（同日，修第一版退化）：真模型 A/B 顯示 codegen 被結構化 0.2 拖垮（baseline 2/2 vs 0/4，失敗皆語意層=grammar 有效但產碼崩）→ `LLMClient.chat` 加 `temperature` 參數（7 實作+全 fake），`LLM_CODEGEN_TEMPERATURE`（預設 0.8）由 CodegenSubAgent 傳入；planner 維持 0.2。原則：temperature 依任務類型（規劃=低溫求一致、產碼=全採樣求品質），與是否結構化無關。`test_subagent.py`/`test_ollama_client.py` 驗 schema 送達、temperature 覆寫。
- [x] **handler 機械正規化**（同日）：handler 規則上必等於 name（衍生欄位），解析時直接設定，不靠模型手抄（實測抄錯一字導致提案被拒）。最終真模型驗證：修正組合有效樣本 2/2；生成延遲較 baseline 高（grammar+thinking+重試），authoring 低頻可接受，列觀察項。

## 對話記憶（多輪 context 回讀，2026-07-07）

規格見 [proposal-assistant-memory.md](../proposal-assistant-memory.md)、設計見 detailed-design §9.31。

- [x] `app/assistant/memory.py`（新）：`summarise_results`（StepResults→精簡文字,每步截斷 200 字）、
  `append_result_summary`、`history_to_messages`（最近 N 則 user/assistant → LLMMessage）。
- [x] `planner.py`：`WorkflowPlanner.plan(history=…)` 把歷史夾在 system 與當前 user 之間;`trim` 保上限。
- [x] `service.py`：`WorkflowService.chat(history=…)` 透傳,含失敗 replan 路徑。
- [x] `router.py`：`/chat` 載入最近 `assistant_history_max_messages` 則傳入;持久化 assistant 訊息時
  把結果摘要接到 content。`core/config.py`：`assistant_history_max_messages=12`（0=關閉）。
- [x] **工具結果承載**：真模型 A/B（gemma4）→ `tool` 角色 0/4、assistant 文字 4/4 → 採 assistant
  文字承載,零 migration（重載訊息本就不帶 results 表格）。
- [x] **確認執行寫回（修復）**：`/confirm` 端點原不寫歷史 → 下一輪誤答「還在等確認」。`confirm` 回傳
  帶 `session_id`,端點執行後把結果摘要以 assistant 訊息寫回 session。
- [x] 單元：`test_memory.py`（摘要/映射/視窗/關閉）、`test_planner.py`（歷史夾層、單輪無歷史）、
  `test_workflow.py`（confirm 帶 session_id）。整合：多輪指涉端到端、confirm 後歷史含 `[executed]`。
- [x] 真模型:多輪 eval 指涉 10/10（純對話 5/5 + 工具結果 5/5,`eval/multiturn-memory` 分支）;
  單輪重跑 sweep 100% 無退化;live 8001 使用者實測通過。
- [ ] （後續 v2）舊對話摘要壓縮、語意檢索、跨 session/使用者畫像（見 proposal §6）。

## 結構化解碼防跳針（2026-07-06，DEC-031）

> 背景：真模型整合測試穩定卡滿 timeout——temp=0 貪婪解碼在 gemma4 thinking 段掉入決定性重複迴圈（300s/900s 均跑不完）。見 [proposal-structured-decoding-stability.md](../proposal-structured-decoding-stability.md)、eval-prompt-log §2.7。

- [x] `core/config.py`：`llm_num_predict`（預設 2048，0=不設限）、`llm_structured_temperature`（預設 0.2）。
- [x] `llm/ollama.py`：所有本地請求帶 `options.num_predict`（>0 時）；結構化請求 temperature 改用設定值（低而非零，格式保證仍由 grammar 遮罩負責）。
- [x] `assistant/router.py`：`_assistant_service` 接線兩個新設定。
- [x] `test_ollama_client.py`：結構化 temperature 用設定值、num_predict 帶入/`=0` 不帶、plain chat 仍不帶 temperature。
- [x] 真模型驗證：原卡死的整合測試通過（40/40）。

## planner schema 技能名 enum（2026-07-06，DEC-032）

> 背景：E7 溫度掃描量化出 destructive 規劃可靠度 0–40%，一類失敗是模型捏造技能名（400，被 permissions 攔截）。把「只用清單內技能」從 prompt 請求升級為 grammar 硬約束。見 [proposal-planner-skill-enum.md](../proposal-planner-skill-enum.md)。

- [x] `planner.py`：`_plan_response_format(skill_names)` 參數化 schema；`build_plan_response_format(registry)` 依當下 registry 注入排序後的 `skill` enum（自建技能會改變清單 → 每次 plan 動態組）；空 registry 退回自由字串。
- [x] `plan()` 改用動態 schema；`validate_plan`/`classify_steps` 縱深防禦不移除。
- [x] `test_planner.py`：response_format 含 enum（排序）斷言、空 registry 無 enum、既有 drift 測試不變。
- [x] 真模型 spot check：safety-destructive 單案例 sweep，確認 400（幻覺技能）類失敗消失。

## planner schema 技能名 enum（2026-07-06，DEC-032）

> 背景：E7 溫度掃描量化出 destructive 規劃可靠度 0–40%，其一病因是模型捏造技能名（400，被 permissions 攔截）。把「只用清單內技能」從 prompt 請求升級為 grammar 硬約束。見 [proposal-planner-skill-enum.md](../proposal-planner-skill-enum.md)。

- [x] `planner.py`：`_plan_response_format(skill_names)` 建構器 + `build_plan_response_format(registry)`（排序、空 registry 退回自由字串）；`plan()` 每次依當下 registry 動態組 schema。
- [x] `test_planner.py`：response_format 含 enum（等於 registry 排序名單）、空 registry 無 enum、既有 drift 測試不退化。
- [x] 真模型 spot check 發現第二病因：400 實為 `depends_on` 非法相依（自我/向前依賴），`validate_plan` 漏查（權限層有查）→ 補上同規則使其觸發修復迴圈；enum 本身確認有效（成功樣本技能名全合法）。
- [x] `test_planner.py`：`validate_plan` 自我相依/向前相依標記、合法相依通過。

## 執行失敗處理（2026-07-04，DEC-029）

- [x] `service.py`：`_compose_failure_message()` 誠實報告——三條執行路徑（chat fast-path / confirm / rerun）失敗時不再回規劃期的 `plan.reply` 或固定成功句，改回 StepResult 組合的事實報告。
- [x] `service.py`：`_replan_after_failure()` + `_execution_feedback()`——fast-path 失敗才餵回真實觀察重規劃一次（budget=1）；護欄：全 read-only 才執行、否則放棄且不建 pending；兩次嘗試各記 run。
- [x] `test_workflow.py`：誠實報告 ×3 路徑、replan 成功、replan 權限不升級、replan 只一次（TDD 先紅後綠）。
- [x] `doc/decisions.md` DEC-029：記錄決策與「不做 agentic loop」的理由（權限邊界/弱模型穩定性/成本/可先量再改）。
- [ ] （後續）在 eval harness 量測失敗分佈（格式類/假設落空類/不可補救類），驗證單次 replan 的實際回收率。

## TODO：DAG 並行執行 + 失敗隔離（下一項，2026-07-04 記錄）

**動機**：一次勾選 5 個檔案壓縮時，`expand_selection_steps` 會展開成 5 個獨立步驟（`depends_on=[]`），但 executor 目前是循序 for 迴圈且**遇第一個錯就 break**（`workflow.py` execute）——(1) 5 個互不相依的步驟被迫排隊浪費時間；(2) 第 1 個失敗後其餘 4 個「全部沒做」，即使它們毫無關聯。

**第一階段（失敗隔離，2026-07-05 完成）**——串行、單 session 不動：

- [x] 失敗隔離：某步失敗只跳過**它的下游相依步驟**（`depends_on` ∪ `from_step` 引用，標記 skipped＋原因），無關分支照常執行完——取代全域 break。新不變量：每步恰一筆結果（property test 鎖定）。
- [x] `StepResult.skipped: bool = False`（additive）；`_run_status` 維持 succeeded/failed 不加 partial（避免 API 值域變更）。
- [x] 誠實報告分支彙總（「執行完成 4/5 步。第 2 步(…)失敗:…。另有 1 步因上游失敗而跳過。」）；replan 回饋含 SKIPPED 行。
- [x] 前端：`WorkflowStepResult.skipped?` + `StepResultList` skip 圖示區別渲染。

**第二階段（並行，未做）**——前置:解「所有技能共用同一 AsyncSession」問題（每步獨立 session 或分相執行,決策與理由見 DEC-030）：

- [ ] executor 改 DAG 波次執行：依 `depends_on` 做拓撲分層，同層無相依步驟用 `asyncio.gather` 並行；加並行上限（semaphore，避免打爆 DB/storage/沙箱）。
- [ ] replan 互動釐清：部分失敗時 replan 的輸入應只含失敗分支；已成功分支不得重跑（副作用）。
- [ ] 沙箱技能並行時的資源上限確認（`asyncio.to_thread` × N 個 `python -I` 子行程的 CPU/記憶體）。
- [ ] 測試：獨立步驟確實並行（時序或呼叫順序斷言）、相依鏈仍守順序、並行上限生效。

## 資料夾技能支援（item_types 權威化，2026-07-24，DEC-035）

**目標**：讓生成/自建技能能對資料夾執行（原 `_execute_generated` 寫死只收 FILE，`item.item_type != FILE → "This skill runs on a file"`）。分支 `feat/assistant-folder-skills`（base=main `98df5bb`）。設計見 detailed-design §8.95.5 / appendix-a DEC-035。**狀態：實作完成，待 push→PR→merge。**

已完成（真模型 + 真後端 E2E 驗證；unit 692 全過、mypy 淨、ruff 淨）：

- [x] `skills/authoring.py` `_execute_generated`：以 `目標.item_type ∈ skill.item_types` 驗證分流取代硬擋 FILE（錯誤訊息依宣告型別，`_wrong_type_message`）；`params["item_type"]` 下傳；FILE 路徑不變。
- [x] `drive/service.py` `collect_folder_descendants`：遞迴列舉子樹（**檔案 + 資料夾，含空目錄**），重用 `list_children`。
- [x] `_materialize_input`：FILE 維持單檔；FOLDER 先重建所有子目錄（含空目錄）再寫檔 → `input_path`=目錄；**空資料夾/只含子資料夾也可**（不因無檔報錯）；上限只計 FILE。
- [x] 攝取上限（`core/config.py`）：`assistant_folder_max_files=1000` / `assistant_folder_max_bytes=500MB`，超過報明確錯（數字已定案）。
- [x] `subagent.py` `_CODEGEN_SYSTEM`：input_path 為選取項目、**以 `os.path.isdir` 為主判斷**（`params["item_type"]` 僅一致性檢查）；**單一技能涵蓋所有合理型別**（壓縮類宣告 `["FILE","FOLDER"]`，不分兩個技能）；務必把結果寫成檔到 output_dir。
- [x] `item_types` 允許 `[FILE,FOLDER]` 並存 → code 依 isdir 分流（原待確認項已定案：允許）。
- [x] 測試（單元，`tests/assistant/test_folder_skills.py`，13 例）：型別 helper、collect 含空子資料夾、materialize 結構/空資料夾/空子資料夾保留/只含子資料夾、上限、item_types 不符報錯、sandbox 吃目錄。
- [x] 測試（真模型，think:OFF gateway）：資料夾請求 6/6 產 FOLDER 技能且執行成功；通用「壓縮成 zip」→ 單一 `zip_compressor` `[FILE,FOLDER]`、檔案與資料夾皆通過；FILE 路徑無回歸。
- [x] 真後端 E2E（真 DB 5434）：生成 `folder_to_zip`→核可→對資料夾執行→產 zip；空資料夾→`EmptyFolder.zip`；含空子資料夾→`MixedFolder.zip`。
- [x] 前端：無需改（`DrivePage` 已依 `item_type` 過濾右鍵）。
- [x] 文件回填：proposal §12、detailed-design §8.95.5、appendix DEC-035（本機草稿，待整併）。

### 後續 / 待辦（不在本 PR，逐項獨立）

- [ ] **CI 整合測試**：加 `tests/integration` 一支在真 Postgres 上守資料夾邊界（空資料夾、含空子資料夾、多層子樹、上限）——目前 `collect_folder_descendants` 的真 SQL 只由本機 live E2E 覆蓋，CI（需 Postgres）尚未涵蓋。
- [ ] **codegen smoke-test（另立 DEC + 獨立分支）**：`author()` 只靜態驗證、不跑 code，執行期 typo（`os.pathlext`/`osorm`）會溜過。規格見 memory `clouddrive-codegen-smoke-test-dec`。
- [ ] **（可選）zip 內保留空目錄**：執行層已落地空目錄，但生成的 `os.walk` code 通常跳過空目錄；若要 zip 內也含空資料夾，需在 `_CODEGEN_SYSTEM` 再加一條。
- [ ] **（既有限制）生成觸發措辭**：`_looks_like_skill_generation_request` 需動詞（做一個/生成…）；「幫我把…壓縮」不觸發生成。可放寬觸發詞或改意圖判斷。
- [ ] **（若需要）A 逐檔批次對資料夾**：對資料夾內每檔各跑一次 FILE 技能（fan-out）——本次以整體資料夾（B）為主，未做；需要時再驗證勾多檔/資料夾展開路徑。

## planner 提示未交代步驟輸出形狀（2026-07-28，由 E9 eval 抓到）

> 背景：E9 第二輪新增的「依檔名分類」情境（`gen-m3-101`）真實試跑失敗，步驟級錯誤訊息為
> `move_item: argument 'parent_id': cannot resolve path 'items.0.id' from step 1`。查證
> `planner.py:118-121` 後確認**不是模型憑空出錯**：系統提示只說明了 `search`/`list_items`
> 回 `{"items": [...]}`，從未說明 `create_folder` 等寫入技能回什麼，而所有範例都寫
> `items.0.id` —— 模型要引用「自己剛建立的資料夾」時，只能照它唯一看過的形狀套。
> 這是 eval 抓到的**產品缺口**（提示資訊不足），非單純模型能力問題。

- [x] `planner.py` 系統提示補上各技能的輸出形狀與對應的 `path` 寫法（依實際實作核對過）：
  - `search` / `list_items` / `list_trash` → `{"items": [...], "total": N}`（`items.0.id`、`items.*.id`）
  - `recent` → **直接是一個 list**（`0.id`、`*.id`）
  - `get_info` / `create_folder` / `rename_item` / `move_item` / `star_item` → **項目物件本身**（`id`）
  - `organize_by_type` → `{"moved_files": N, "folders": [...]}`
- [x] 單元測試：斷言提示含這段輸出形狀說明（`test_planner_prompt_documents_each_step_output_shape`）（防之後被改掉又沒人發現）。
- [x] 真模型驗證：同 4 案修改前後各跑一次，`execution` 維度 **0.67 → 1.00**（`cannot resolve path` 錯誤消失），確認此缺口確為失敗主因之一。
- **但案例仍失敗，且曝露另一層能力缺口**：模型改用 `move_item` 對 `list_items` 結果做 `*` 全量 fan-out，把根目錄**所有**項目（含兩個 canary 資料夾）一起搬進最後建立的資料夾。canary 檢查抓到：`勿動-舊備份 untouched (collateral damage) | parent='履歷'`。**選擇性批次分類（先分組再各自搬移）超出目前模型能力**，記為能力邊界，不放寬案例。

## 兩段式規劃：先偵察、看到結果再決定要動誰（2026-07-29，實驗性，預設關閉）

> 背景：E9 的分類情境（依檔名分類 20 案、語意分類 5 案）全數失敗。歸因調查（見
> `local-docs/HANDOFF_notes-and-open-issues_2026-07-29.md`）確認**不是模型能力問題**——
> 對照探測顯示只要把檔名告訴模型並要求逐一搜尋，它就能產出 10 步計畫並端到端成功。
> 真正的限制是：規劃是一次性的，模型必須在看到任何資料**之前**決定所有步驟，而唯一的
> 篩選手段（`search`）是字面比對，與「先看內容再判斷歸類」的需求根本不相容。

**設計**：同一個請求分兩次規劃，但**產出的是同一份計畫**。

1. 第一次規劃：模型若判斷「必須先看到資料才知道要對誰動作」，就只規劃唯讀的偵察步驟，
   並把新欄位 `needs_followup` 設為 true。
2. 系統執行這些偵察步驟（唯讀、可自動執行，不需使用者確認），把**實際結果**連同原始請求
   餵回規劃器，並告知「你的新步驟從索引 N 開始，可以引用第 0～N-1 步」。
3. 第二次規劃的步驟**接在偵察步驟之後合併成一份計畫**，再走既有的確認閘與執行流程。

**為何是合併而不是新增跨計畫引用語法**：合併之後索引天然連續，既有的引用語法
（`{"from": i, "path": ...}`）、確認閘、執行器、評測的引用接地檢查全部不用改，也不需要
新增儲存或定義引用有效期。代價是偵察步驟在最終執行時會再跑一次——它們是唯讀的，安全且
成本低。使用者在確認閘看到的也是**完整計畫**（查詢＋寫入），透明度不降反升。

**刻意不採用的兩個替代方案**：
- 允許模型寫出它觀察到的 UUID：會拆掉「禁止寫 UUID」這條防幻覺護欄，且評測的引用接地
  檢查要一起改。實測（C4）模型確實會這樣做且會成功，但風險不對稱。
- 新增跨工作流程引用語法：需要定義引用有效期與過期處理。資料本身已持久化
  （`assistant_workflow_runs.step_results`），但語法、驗證、受限解碼結構都要動。

- [x] `core/config.py`：新增 `assistant_two_phase_planning: bool = False`（**預設關閉**，
      避免影響既有 425 個評測案例的基準；評測時以環境變數開啟做對照實驗）。
- [x] `planner.py`：`PlanResult` 新增公開欄位 `needs_followup: bool = False`（這個值**由模型
      產生**，因此是公開欄位而非 `PrivateAttr`——與 `llm_meta` 那種「事後才知道」的資料相反）；
      同步更新手寫的 `_PLAN_RESPONSE_FORMAT` 與防漂移測試。
- [x] `planner.py` 系統提示：說明何時該設 `needs_followup`（無法在看到查詢結果前決定要對哪些
      項目動作時），以及第二次規劃可以引用前面已執行的步驟。
- [x] `service.py`：兩段式流程。只在旗標開啟、第一份計畫非空、全為唯讀、且 `needs_followup`
      為真時觸發；偵察執行**不記錄成執行歷史**（屬內部步驟）；只做一次後續規劃，永不迴圈。
- [x] 測試：旗標關閉時流程完全不變（回歸）；旗標開啟但 `needs_followup` 為假時不觸發；
      偵察計畫含寫入步驟時不觸發（安全性：不得在未確認前執行寫入）；合併後的索引與引用正確。
- [x] 真模型對照實驗：任務組 T1 語意分類（多輪）／T2 語意分類（單輪）／T3 找出重複檔案／
      T4 依時間封存／T5 既有 EC2/EC4 迴歸，量測成功率、步驟數、延遲、詞元，並與旗標關閉時對照。

### 實作與真模型對照結果（2026-07-29）

**四個實作缺陷都是靠真模型跑出來的**，單元測試（含事後補的）沒有一個能先抓到，因為它們
都源自「模型怎麼理解我給它的編號與敘述」，而不是程式的內部一致性：

1. 第一段的寫入步驟若保留進最終計畫，模型在第二段會**再規劃一次同樣的寫入** → `'發票'
   already exists` 並連鎖失敗。改為丟棄未執行的寫入，第二段獨占所有寫入。
2. 丟棄寫入後，保留下來的偵察步驟仍帶著指向已消失步驟的 `depends_on` → HTTP 400
   `Step 0 has an invalid dependency: 1`。加 `_renumber_kept` 重新映射。
3. 回饋給模型的觀察摘要沿用了對話記憶的「只列檔名」渲染，T4「搬走最大的檔案」因此**看不到
   檔案大小**，5 次全錯。改用 `_observed` 另外渲染（名稱／類型／大小／更新時間，不含 id）。
4. 觀察每一行標的步驟編號用的是它在**第一段**的位置，但合併後步驟已被重新編號 → 模型照抄
   舊編號，`move_item` 的 `item_id` 指到 `create_folder` 的輸出，`cannot resolve path
   'items.1.id'`。改為一律標示**合併後**的編號（`index_map`）。

**旗標開／關對照（每項 5 次，真模型，各案例獨立帳號）**

| 任務 | 旗標關（基準） | 旗標開 |
|---|---|---|
| T1 語意分類（多輪，先問再指示） | 0/5 | 1/5 |
| T2 語意分類（單輪，一句話講完） | 0/5 | **5/5** |
| T3 找出重複檔案只留一份 | 0/5 | 4/5 |
| T4 把最大的檔案搬進封存 | 0/5（且 5/5 誤搬 canary） | **5/5** |
| 合計 | **0/20** | **15/20** |

T1 殘餘失敗是模型在第二段**引用自己新步驟的編號時算錯**（把第二個 `create_folder` 的位置
寫成 3 而非 2，`parent_id` 因而指向一個 `move_item` 的輸出，執行期報 `Destination must be
a folder`）。目前 `validate_plan` 只檢查「引用必須指向更早的步驟」，不檢查**被引用步驟的
輸出型別是否合用**，所以這種錯誤逃過規劃期驗證、留到執行期才爆。記為待辦，不在本次範圍。

### 提示詞回歸：教了不會被兌現的規則（2026-07-29）

`needs_followup` 的說明原本無條件寫進系統提示，**旗標關閉時也一樣教**。後果是模型照樣拆成
兩段、只回傳唯讀查詢，而沒有第二段把寫入補上——請求就這樣安靜地變成一次列表。同 20 個 EC2
案例實測：旗標關但提示照教 **0/20**（全部 `state_mismatch`，寫入步驟直接消失）；提示改為
依旗標切換後 **20/20**。

- [x] `build_planner_prompt(registry, *, two_phase)`：旗標關閉時改教「`needs_followup` 永遠
      為 false，現在就規劃完整請求」。`WorkflowPlanner` 也讀同一個設定，與 `WorkflowService`
      保持一致。
- [x] 單元測試釘住這條對應關係（`test_split_plan_rule_is_only_taught_when_a_second_pass_will_run`）。

**是否預設開啟：否。** 同 20 個 EC2 案例，旗標開為 7/20，13 個失敗**全部是同一項檢查**
（計畫未呼叫 `get_info`）——`state` 與 `execution` 兩個維度 20/20 全對，工具呼叫數還更少
（3.0 vs 4.0）。也就是說旗標開在一般案例上不是「做錯」，而是「少做一次冗餘查詢」導致偏離
評測的標準路徑。即便如此仍維持預設關閉：一般案例本來就不需要偵察，多一次 LLM 呼叫的延遲與
詞元成本沒有回報（輸入詞元 1799 vs 1406）。

## 計畫驗證與規劃提示的三處修正（2026-07-29）

設計面見 detailed-design §8.95.7。三處都是先前留下的待辦或它逼出來的連鎖問題。

- [x] **型別感知的引用檢查**：`RegisteredSkill` 加 `output: SkillOutput`（`paged_items`／`item_list`／`item`／`new_folder`／`mutated_item`／`opaque`），內建 14 個技能逐一標註，自建技能維持 `opaque` 不猜。`validate_plan` 據此擋掉「路徑形狀對不上」與「拿剛被改動的項目當 `parent_id`」兩類錯誤，讓它們落進修補迴圈而不是執行到一半才炸。
  - `validate_plan(steps, registry, preceding=...)` 取代原本的 `index_offset`：兩段式規劃的第二段要能檢查**回指第一段**的引用，只給數量做不到，要給實際步驟。
  - 提示詞裡那份散文對照表**一字未改**（改提示的風險已經吃過虧），改以 `test_prompt_output_shapes_match_what_the_skills_declare` 釘住兩者一致。
- [x] **修補迴圈的訊息**：原訊息一律附「做不到就回空 steps」。加上新驗證後，模型在真實多輪測試 5/5 選了這條退路的變形（回「請先勾選檔案」）而不是修掉一個步驟編號。改為「照這些修正改、其餘不動、不要叫使用者勾檔、不要對可修的步驟放棄」，退路只在**技能根本不存在**時提供 → 同任務 0/5 → 3/5。
- [x] **沒有選取時要明說**：規劃提示原本只在有勾選時附選取清單，沒勾選時什麼都不說；模型於是假設有選取、規劃 `{"from": "selection"}`，服務層只能回「請先勾選」。現在無選取時明確告知不可用、要改用 search/list_items。兩段式的 selection 早退條件也改成**只有真的有選取**才成立。

**真模型驗證（旗標開，各 5 次，遠端 gateway）**：T2 語意分類（單輪）5/5、T3 重複檔案 5/5、T4 最大的檔案 5/5——三項在加上驗證後仍維持滿分，確認新檢查沒有擋掉正常計畫。

**T1（多輪語意分類）仍不穩定，且變異大於各版本間的差距**：同一份程式在不同批次量到 0/5 與 3/5。目前確定的是「退回去叫使用者勾選」這條死路已經結構性堵掉（selection 早退條件＋提示明說＋修補訊息三處），但模型在多輪歷史下仍常規劃不完整（少了建資料夾或少了搬移）。**5 次一批的樣本量不足以排序這幾個版本**，要下結論需要更大的批次。


## 模型輸出殘骸污染使用者資料（2026-07-29）

- [x] `planner._strip_decoding_artifacts`：解析後把字串值在聊天模板 token 或「引號＋連續收括號」處截斷，清掉緊鄰的 JSON 標點，並寫 WARNING log。設計與量測見 detailed-design §8.95.8。
- [x] 單元測試 4 案：兩種殘骸形態各一、正常含括號名稱不得被動到、reply 文字同樣要清。
- [x] 真模型驗證：同請求對 gateway 連跑 10 次，10/10 名稱乾淨（修正前重現率 4/5）；整合測試 50/51 → **51/51**。
- 未涵蓋：codegen 產生的程式碼字串（`subagent.py`）走另一條路徑，本次未處理。

## 整合測試連線字串（2026-07-29）

- [x] `tests/conftest.py` 改為從 `.env` 推導測試資料庫位址（只換資料庫名為 `clouddrive_test`，主機／埠沿用開發環境），顯式的 `DATABASE_URL` 仍優先（CI 用）。開發機的 Postgres 在 5434 而預設值寫死 5432，導致整合測試 51 個全部 error——症狀看起來像測試壞了，其實是連線字串指向不存在的服務。


## 生成技能先試跑再提出（2026-07-29）

- [x] `app/assistant/skills/smoke.py`：在正式環境同一個沙箱裡跑一次生成的程式碼，每個宣告的 item_type 各一次；只有「程式碼壞了」（NameError／SyntaxError／AttributeError／TypeError／re.error…）才算失敗，輸入格式不合不算。
- [x] `CodegenSubAgent.author(request, smoke=...)`：試跑失敗轉成 repair problem，走既有修補迴圈；`AssistantSkillService` 在有沙箱時自動接上，沒有沙箱時行為不變。
- [x] 單元測試 5 案：壞程式碼觸發重寫且修補訊息帶真實 traceback、正常程式碼不多花一次呼叫、輸入格式不合不觸發重寫、沒有沙箱時完全不變、FILE+FOLDER 都要試。
- 依據：全量評測 100 個生成技能有 18 個第一次呼叫就丟例外，靜態掃描全數放行。設計見 detailed-design §8.95.9。

## 模型把名稱寫壞（位元組標記已修，字元層仍在，2026-07-30）

- [x] 參數值含 `<0xNN>` 位元組標記 → `validate_plan` 判無效、走修補迴圈重規劃（不刪標記——刪掉只有一半機率猜對年份）。`reply` 文字則清掉標記（只是難看）。
- [x] 單元測試 3 案：參數被拒、乾淨參數不受影響、只有 reply 會被清。
- [x] 真模型驗證：同 20 案 rename 情境（遠端 gateway）**4/20 → 14/20**，`<0xNN>` 寫進資料庫 **10 → 0**。
- [ ] **仍未解**：殘餘失敗改用合法字元把年份寫壞（`合約_20 .26`、`旅遊_20    6`、`會議記錄_20ASS`），文字本身無從判斷對錯。只能靠換模型——gemma4:12b 同批 298 案例／13,284 個檢查項／325 個名稱掃描，三類損壞皆 0 筆。

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

**目標**：讓生成/自建技能能對資料夾執行（現行 `_execute_generated` 寫死只收 FILE，`item.item_type != FILE → "This skill runs on a file"`）。分支 `feat/assistant-folder-skills`（base=main `98df5bb`）。設計見 detailed-design §8.95.5 / appendix-a DEC-035。

- [ ] `skills/authoring.py` `_execute_generated`：以 `目標.item_type ∈ skill.item_types` 驗證分流取代硬擋 FILE；FOLDER → 遞迴子樹攝取到暫存目錄當 `input_path`；`params["item_type"]` 下傳。**FILE 路徑不變**。
- [ ] `drive` service/repository：補「資料夾子樹遞迴列舉」（重用 `list_children`），供攝取所有子孫 FILE。
- [ ] 資料夾攝取上限（`core/config.py` 新設定）：超過在攝取前 raise 明確錯。**待確認數字（建議 1000 檔 / 500MB）。**
- [ ] `subagent.py` `_CODEGEN_SYSTEM`：教模型 `input_path` 可能是目錄、資料夾請求產 `item_types:["FOLDER"]` + 走訪目錄 code、說明 `params["item_type"]`。
- [ ] A 逐檔批次：確認/重用既有 fan-out 對資料夾內每檔各跑一次 FILE 技能（可能已由勾多檔路徑覆蓋，需驗證資料夾展開）。
- [ ] 測試（單元）：FOLDER 執行+攝取+回寫、`item_types` 不符報錯、上限觸發、A 批次 fan-out。
- [ ] 測試（真模型，真模型驗證鐵律）：codegen「資料夾請求 → `item_types:["FOLDER"]` + 可跑目錄版 code」多次看 pass-rate（think:OFF 下）。
- [ ] 待確認：`item_types` 是否允許 `[FILE,FOLDER]` 並存（建議允許，code 依 `params["item_type"]` 分流）。
- [ ] 文件回填：proposal §12「技能可對資料夾執行」、detailed-design §8.95.5、appendix DEC-035（已先寫本機，待整併）。

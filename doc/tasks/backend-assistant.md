# Backend Assistant 模組任務（HARNESS v1.0）

對應設計：[assistant-design.md](../assistant-design.md)
模型：Gemma 4 26B（本地，Ollama / OpenAI 相容）。

## 完成定義

- 使用者可用自然語言操作雲端硬碟，並能請助理「製作新功能」。
- 助理一律經 service 層或受控沙箱操作，重用配額/權限/活動紀錄。
- 每個工具/技能呼叫綁當前 `user_id`，多租戶安全。
- 生成程式碼必經「核可 → 沙箱 → 稽核」，絕不自動執行未審核程式碼。
- LLM 可被 mock 測試，不打真模型。

## M1：迴圈骨架（HARNESS 01/02/05/07）

- [ ] `core/config.py` 新增 `llm_provider` / `llm_base_url` / `assistant_model` / `llm_num_ctx` / `assistant_enabled` / `assistant_max_tool_iterations` / `assistant_sandbox_timeout_sec`。
- [ ] `pyproject.toml` 確認 `httpx`（已內含）；不引入雲端 LLM SDK。
- [ ] `llm/client.py`：`LLMClient` 協定 `chat(messages, tools) -> text | tool_calls`。
- [ ] `llm/ollama.py`：Gemma via Ollama `/api/chat`（tools 欄位）；備 OpenAI 相容 `/v1/chat/completions`；含 tool-call 解析與格式修復/重試。
- [ ] `context.py`：ContextBudget（token 估算、超預算裁切/摘要、大型工具輸出瘦身）。
- [ ] `prompt.py`：system prompt 動態組裝（穩定前綴在前、不含隨機/時間戳）。
- [ ] `service.py`：AgentLoop.run（while 迴圈、停止條件、迴圈上限、hook 觸發點）。
- [ ] `skills/registry.py`：工具/技能註冊與相關性挑選。
- [ ] `skills/builtin/`：唯讀內建技能 `list_items`/`search`/`recent`/`storage_quota`，經既有 service 並帶 `user_id`。
- [ ] `router.py`：`POST /assistant/chat`，依賴 `CurrentUserId`；無 key/停用回 503。
- [ ] 在 `api/v1/router.py` 註冊。

## M3：技能框架與持久化（HARNESS 03/05/06）

- [ ] Alembic migration：`assistant_sessions` / `assistant_messages` / `assistant_skills`。
- [ ] `repository.py`：sessions/messages/skills CRUD；啟動載入使用者已安裝技能。
- [ ] `skills/manifest.py`：manifest schema 與驗證（含 `ui.context_menu`）。
- [ ] 寫入型內建技能：`create_folder`/`rename`/`move`/`star`/`trash`/`restore`/`share`。
- [ ] 續接/列出 session。

## M4：自我撰寫 + 安全（HARNESS 04/08/09）

- [ ] `subagent.py`：單層子代理（codegen 用），獨立 context、回傳結果。
- [ ] `skills/authoring.py`：`author_skill` meta-skill，產生 handler+manifest，停在 `pending_approval`。
- [ ] `hooks.py`：HookRegistry 與內建 hooks（稽核、權限閘、安裝前驗證、code 執行前閘）。
- [ ] `permissions.py`：分層權限（唯讀自動 / 破壞性需確認 / 安裝+執行碼需核可）。
- [ ] `skills/sandbox.py`：子行程沙箱（CPU/記憶體/逾時、路徑限 storage、無對外網路、參數化呼叫）。
- [ ] 技能核可/安裝/觸發 endpoint。
- [ ] 7zip 範例端到端可跑（解壓寫回成 drive items）。

## 測試任務

- [ ] `tests/assistant/test_router.py`：mock AgentLoop + 認證。
- [ ] `test_loop.py`：mock LLMClient 完整一輪 + 上限 + 錯誤包裝。
- [ ] `test_dispatch.py`：工具路由與 `user_id` 綁定。
- [ ] `test_context.py`：超預算裁切/摘要。
- [ ] `test_authoring.py`：撰寫流程停在 pending_approval，不自動執行。
- [ ] `test_sandbox.py`：逾時/路徑限制/無網路。
- [ ] `test_hooks.py`：權限閘阻擋破壞性與安裝動作。
- [ ] `ruff format/check`、`mypy app tests`、`pytest` 全綠。

# Backend Assistant 模組任務

對應設計：[assistant-design.md](../assistant-design.md)

## 完成定義

- 使用者可透過 `POST /api/v1/assistant/chat` 用自然語言操作自己的雲端硬碟。
- 助理一律經 service 層操作，重用配額/權限/活動紀錄等不變量。
- 每個工具呼叫綁定當前 JWT 的 `user_id`，多租戶安全。
- AssistantService 不與 HTTP router 內部綁定，Claude API 可被 mock 測試。

## M1：唯讀（先驗證端到端）

- [ ] `core/config.py` 新增 `anthropic_api_key` / `assistant_model` / `assistant_enabled` / `assistant_max_tool_iterations`。
- [ ] `pyproject.toml` 新增 `anthropic` 依賴並 `uv sync`。
- [ ] 建立 `app/assistant/schemas.py`（ChatMessage / ChatRequest / ChatResponse / ToolCallLog）。
- [ ] 建立 `app/assistant/tools.py`：唯讀工具 JSON schema + dispatch 對應表。
- [ ] 建立 `app/assistant/service.py`：AssistantService 手動 tool-use 迴圈（adaptive thinking、effort medium、迴圈上限）。
- [ ] 實作唯讀工具：`list_items` / `search` / `recent` / `storage_quota`，呼叫既有 service 並帶 `user_id`。
- [ ] 建立 `app/assistant/router.py`：`POST /assistant/chat`，依賴 `CurrentUserId` 與各 service factory。
- [ ] 在 `api/v1/router.py` 註冊 assistant router。
- [ ] 無 API key / 停用時回 503 並有明確訊息。
- [ ] 工具執行例外轉 `tool_result` is_error，不外洩堆疊。

## M3：寫入工具

- [ ] `create_folder` / `rename_item` / `move_item` / `star_item`。
- [ ] `trash_item` / `restore_item` / `list_trash`。
- [ ] `share_item`。
- [ ] 寫入工具回傳精簡結果（id/名稱/狀態）。

## 測試任務

- [ ] `tests/assistant/test_router.py`：mock AssistantService，驗證 endpoint 與認證（沿用專案 `_make_app` pattern）。
- [ ] 測 ToolDispatcher：工具名稱正確路由到 mock service 並帶對 `user_id`。
- [ ] 測迴圈：mock anthropic client 回 tool_use → 執行 → end_turn 的完整一輪。
- [ ] 測迴圈上限與錯誤包裝。
- [ ] `uv run ruff format/check`、`uv run mypy app tests`、`uv run pytest` 全綠。

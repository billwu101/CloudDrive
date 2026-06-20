# 外部模型接入（Codex/OpenAI）模組任務

設計見 [external-model-integration.md](../external-model-integration.md)，決策見 DEC-026；延伸 DEC-023。

> 本檔只涵蓋**終端使用者功能**：本地 Gemma 反覆失敗時，自動升級到使用者自己的 GPT-5.5（Codex 訂閱優先、OpenAI key 備援）。Codex 訂閱憑證「跨機可用」已由實機雙容器 demo 驗證通過（external-model-integration.md §9.6；v0.141.0 auth.json 僅 OAuth token、無綁機私鑰、token 可搬）。
> 階段代號用 **EM1–EM3**（External Model），刻意別於 eval harness 的 E1–E4（`assistant-eval-design.md`），避免混淆。
> 交付順序（風險由低到高）：**EM1 共用基礎 → EM2 路徑 B（API key，先通）→ EM3 路徑 A（Codex 訂閱）**。
> **進度（2026-06-19）：EM1 + EM2 + EM3 完成並全綠，使用者自動升級功能全數交付**（後端 587 單元、前端全綠；migration 0001→0014 於真 pgvector 驗過）。含失敗／額度耗盡自動標記 invalid、Codex 訂閱（隔離 CODEX_HOME + CLI refresh 回寫加密 + 訂閱優先退回 API key）。
> 註：原 EM4「eval 考官 provider」是**開發者 eval 工具**（非使用者功能，且重用 EM2/EM3 的 client），已移至 [assistant-eval.md](./assistant-eval.md) 的 E6。
> 下列為 checklist（勾選 = 已實作 + 測試）。

## 完成定義

1. 對應 checklist 完成。
2. 單元測試通過（憑證加解密、provider 選擇、升級接線，以 mock/transport 驗，不需真外部）。
3. 隱私閘 / 權限 / 沙箱 / 確認閘 / 稽核沿用 DEC-023，外部回來的計畫/結果與本地同等對待。
4. 憑證**絕不以明文**落 DB / log / 回應；外部預設關閉，使用者明確啟用。

## EM1：共用基礎（憑證 + profile + 升級接線）

- [x] `user_external_credentials` model + Alembic migration：`(user_id, provider)` 複合 PK、`auth_type`（`api_key`/`oauth_token`）、`secret_encrypted`、`masked_hint`、`status`（`active`/`invalid`）、`updated_at`；FK CASCADE。
- [x] 對稱加密工具（Fernet）+ 設定 `CREDENTIAL_ENCRYPTION_KEY`（env，不入版控）：加密 / 解密 / 遮罩（末 4 碼）。
- [x] `ExternalCredentialService`：`upsert` / `get_decrypted` / `delete` / `list_masked`；可標記 `status=invalid`。
- [x] profile 端點：`GET/PUT/DELETE /users/me/external-credentials`（**只回 masked**，永不回明文）。
- [x] 前端 profile 設定 UI：填 API key／貼 Codex token、顯示遮罩與狀態、刪除。
- [x] `ExternalChatClient` 協定（`chat(messages, ...) -> response`）+ provider 抽象；`build_external_client(creds)` 工廠（依 §2.3 選 provider）。
- [x] ModelRouter 升級接線：`MAX_LOCAL_ATTEMPTS` 連續本地失敗 **且** 資格（憑證可用、`EXTERNAL_LLM_ENABLED`、非隱私鎖定/已去識別化）→ 改用外部；升級事件寫**稽核**（不含憑證）。
- [x] 測試：加解密 round-trip + 遮罩、service CRUD、router 升級條件（mock client）、隱私鎖定不外送、端點只回遮罩。

## EM2：路徑 B — OpenAI API key（先通，最穩、確定可交付）

- [x] `OpenAIChatClient`：官方 chat completions、httpx transport 可注入、逾時、`Bearer` key、`model=gpt-5.5`。
- [x] provider 工廠：`auth_type=api_key` → `OpenAIChatClient`。
- [x] 失敗 / 額度耗盡處理：標記 `status=invalid`、回報使用者、退回本地失敗。
- [x] 測試：MockTransport 解析 / 錯誤 / 401 / 額度耗盡、router 用 API key 升級成功路徑。

## EM3：路徑 A — Codex 訂閱制（疊上 EM2 之後）

- [x] `CodexSubscriptionClient`：每次呼叫建**臨時隔離 `CODEX_HOME`**、寫入解密後的 token（`auth.json`，0600）、以官方 `codex exec --skip-git-repo-check` 呼叫、**用畢即焚**（`tempfile.mkdtemp` → `shutil.rmtree`）。subprocess runner 可注入以便單元測試。
- [x] token refresh：採 **CLI 自身 refresh**——`codex` 在 subprocess 內偵測過期並以 `refresh_token` 續期、更新臨時 `auth.json`；呼叫後若偵測 token 變動則 `on_refresh` 回寫**加密**儲存（`factory._refresh`，獨立 session）。refresh 失效 → CLI 回授權錯誤 → `ExternalAuthError` → 標記 `invalid` + 前端提示重跑 `codex login`。（較「server 自打 token endpoint」更穩健、少維護；此設計偏離記於此。）
- [x] 風險緩解（已做）：憑證 Fernet 加密、token 不入 log／回應、外部預設關閉（`CREDENTIAL_ENCRYPTION_KEY` 空即停用）。
- [ ] 風險緩解（待 ops）：**額度／風控監測與告警**——需 metrics／alerting 基礎設施，留部署層，尚未實作。
- [x] provider 選擇：訂閱制優先、失敗自動退回路徑 B（`_FallbackClient`，§2.3）。
- [x] 執行期相依：容器內安裝官方 `codex` CLI + `@zed-industries/codex-acp`（`backend/Dockerfile` 的 `--build-arg INSTALL_CODEX=1`）。
- [x] 測試：per-request home 建立／清理、provider 選擇與退回、refresh 流程（runner mock 模擬 CLI refresh）、錯誤分類（授權失敗 vs 暫時）。（跨機可用已由 `experiments/codex-cross-machine-demo/` 實證，§9.6。）

> **EM3 端到端注意**：`codex exec` 輸出解析（`_extract_response`）依實際 CLI 輸出框架；單元層以注入 runner 覆蓋，真實訂閱 + 已安裝 CLI 的端到端跑需在部署環境驗證／微調。

## 文件同步

- [ ] 實作後更新 `prompt.md`、`detailed-design.md`、本檔與 `progress.md`。

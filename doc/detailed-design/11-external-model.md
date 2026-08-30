## 11. 外部模型接入（Codex/OpenAI）

### 11.0 實作現況（2026-06-19；規劃中的「多組具名連線」改版見 §11.10、失敗處理見 §11.11，兩者尚未落到 fix 分支）

| 區塊 | 設計 § | 階段 | 實作落點 | 狀態 |
| --- | --- | --- | --- | --- |
| 憑證儲存 + 加密 + profile 端點/UI | §11.3 | EM1 | `app/external_model/{models,crypto,repository,router,schemas,service}.py`、migration 0014、`components/settings/ExternalModelSettings.tsx` | ✅ |
| 升級接線（本地反覆失敗 → 外部） | §11.4 | EM1 | `app/assistant/llm/router.py`、`app/assistant/router.py` | ✅ |
| 路徑 B：OpenAI API key | §11.2.2 | EM2 | `app/assistant/llm/external.py`（`ExternalLLMClient`） | ✅ |
| 失敗／額度耗盡 → 標 `invalid` | §11.2.2 | EM2 | `external.py`（401/403/429-quota 分類）+ `service._CredentialTrackingClient` | ✅ |
| 路徑 A：Codex 訂閱 | §11.2.1 | EM3 | `app/external_model/codex_client.py`（`CodexSubscriptionClient`） | ✅ |
| provider 選擇／退回 | §11.2.3 | EM3 | `service.build_chat_client` + `_FallbackClient` | ✅（規劃中改版後手動選擇不再自動退回，見 §11.10.4） |
| eval 考官 provider（+ 評 exec 產出） | §11.5 | E6 | `eval/judge.py`、`eval/run.py`（任務在 `tasks/assistant-eval.md`） | ✅ |
| **多組具名連線 + 模型可選 + 無自動 fallback** | **§11.10** | **EM4** | `app/models/external_model_connection.py`、migration **0016**、`external_model/{repository,service,router,schemas}.py`、`assistant/{router,planner,llm}.py`、`components/settings/ExternalModelSettings.tsx`、`components/assistant/AssistantPanel.tsx` | 🔶 **main 已實作（2026-06-25）；fix 分支待落地** |
| **執行失敗誠實報告 + 有限度重規劃 + 執行隔離** | **§11.11** | — | `app/assistant/service.py`、`app/assistant/workflow.py`、`tests/assistant/test_workflow.py` | 🔶 **main 已實作（2026-07-04／07-05，DEC-029／DEC-030）；fix 分支待落地** |
| **Anthropic／Claude 連線** | §11.10.5 | EM4+ | `app/assistant/llm/anthropic.py`（`AnthropicLLMClient`） | ⚠️ **client 類別已備、尚未接線**（`ConnectionKind` 未含 `anthropic`、`build_clients` 未加分支；main 亦未接線） |


### 11.1 目標

1. **執行升級**：當本地 Gemma 4（harness 引擎的預設執行器）對某任務反覆做不出可接受結果時，能改用 **GPT-5.5**（經 Codex 訂閱制或 OpenAI API）重試。
2. **eval 考官**：eval harness 的考官（judge）可選用 **Gemma 4 或 Codex/GPT**，評斷一個 skill 的「生成結果是否正確」以及「做出的效果是否符合使用者期待」。
3. **使用者自帶憑證**：使用者在 **profile** 設定自己的外部模型憑證後，才能使用上述外部功能；未設定則一律維持本地、不外送。

兩個使用點刻意分開：

| 使用點 | 預設 | 外部 | 憑證來源 |
| --- | --- | --- | --- |
| Harness 引擎（助理執行 workflow/skill） | Gemma 4（本地） | GPT-5.5（失敗升級） | **使用者 profile** |
| Eval harness 考官（評分 skill） | Gemma 4 | Codex/GPT（可選） | 開發者 env / CLI（評測者跑，非終端使用者） |


### 11.2 認證路徑（訂閱制優先，API key 備援）

依使用者決定：**Codex 訂閱制優先、OpenAI API key 備援**。設計上把「provider」抽象成介面，兩條路徑都實作同一個 `ExternalChatClient` 協定，升級/考官只依賴介面。

### 11.122.1 路徑 A — Codex 訂閱制（優先，參考 openclaw 的做法）

採用 **openclaw**（github.com/openclaw/openclaw）已驗證的做法：**不自己實作 ChatGPT OAuth，而是橋接官方 Codex CLI**，把 OAuth 登入與 token refresh 委派給官方工具。

openclaw 的關鍵機制（讀其 `extensions/acpx/src/codex-auth-bridge.ts` 確認）：

1. 使用者用**官方 `codex login`**（OAuth 訂閱）登入，憑證存在 `CODEX_HOME`（預設 `~/.codex/auth.json`），結構含 `tokens` 與 `last_refresh`；**token refresh 由 Codex CLI 自己負責**。
2. 透過 **`@zed-industries/codex-acp`**（ACP = Agent Client Protocol）以 wrapper 啟動 codex 來呼叫訂閱額度，而非直接打非官方端點。
3. 把 `CODEX_HOME` 的 auth 狀態複製到**隔離的 plugin-local home**，避免污染使用者本機設定。
4. 支援 `CODEX_API_KEY` / `OPENAI_API_KEY` 環境變數作為備援（即本文件路徑 B）。
5. 診斷/log 對 token、secret 做大量**遮罩**。

採用理由：把脆弱的 OAuth/refresh 交給官方 CLI，比自己刻 ChatGPT session 穩健；仍屬非官方整合層（依賴 Codex CLI 行為），故路徑 B 仍為穩定保證。

⚠️ **情境差異與定案**：openclaw 是**個人單機 CLI**——跑在使用者自己機器、直接讀本機 `~/.codex/auth.json`。本專案是**多使用者集中式 web server**，server 端沒有、也不該有每位使用者的本機 `~/.codex`。

**已定（使用者決定）：採「多使用者集中式、各自帳號」**。具體設計：

1. **取得 token（使用者端，一次性）**：使用者在自己機器用官方 `codex login`（OAuth 訂閱）登入，產生 `~/.codex/auth.json`（含 access/refresh token）。前端 profile 頁引導使用者把該 `auth.json` 的 token 內容貼上／上傳。
   - server **不**代跑 `codex login`（OAuth 需使用者瀏覽器互動，無法在 server 端代理）。
2. **儲存（server 端）**：把 token 經對稱加密存入該使用者的 `user_external_credentials`（§11.3），`auth_type=oauth_token`、`provider=codex`；只回遮罩。
3. **呼叫（server 端，per-request 隔離）**〔已實作〕：需要升級或考官用 Codex 時——
   - 為「該次呼叫 × 該使用者」建立**臨時隔離 `CODEX_HOME`**（`tempfile.mkdtemp`），把解密後的 token 寫成 `auth.json`（0600），以 **`codex exec --skip-git-repo-check`** subprocess 呼叫訂閱額度，**用畢即焚**（`shutil.rmtree`、token 不落地於共用位置）。比照 openclaw 的「隔離 home + 遮罩」實務。
   - 實作：`codex_client.CodexSubscriptionClient`（subprocess runner 可注入測試）；輸出解析見 `_extract_response`。
   - **設計偏離①**：原規劃用 `@zed-industries/codex-acp` wrapper（ACP 協定），實作改用官方 `codex exec` 直跑——因 planner/codegen 只消費回應的 `content`（不需 ACP 的 tool-call 互動），直跑更簡單。
4. **token refresh（採 CLI 自身機制）**〔已實作〕：呼叫時 codex CLI 若偵測 access token 過期會**自己用 `refresh_token` 續期**並更新臨時 `auth.json`；呼叫後若偵測 token 變動，`on_refresh` 把新 token 重新加密回寫（`factory._refresh`，獨立 session）。refresh 失效 → CLI 回授權錯誤 → `ExternalAuthError` → 標記 `invalid` + 前端提示重跑 `codex login`。
   - **設計偏離②**：原規劃「server 自打 OpenAI token endpoint 續期」；改用 CLI 自身 refresh 更穩健（不必追 endpoint 規格）、少維護。

**絕不保存帳號明文密碼**；只持有可撤銷的 OAuth token（見 §11.3）。訂閱制管道失效時自動退回路徑 B。


### 11.122.2 路徑 B — OpenAI API key（備援，穩定）

- 使用者在 profile 填自己的 OpenAI API key（`sk-…`），後端以官方 API 呼叫 `gpt-5.5`。
- 官方支援、可程式化、計費透明、長期穩定。
- 即使最終訂閱制管道不可行，本路徑確保「升級到 GPT」這個功能仍可交付。

### 11.122.3 provider 選擇邏輯

升級或考官需要外部模型時：

1. 若使用者有**可用的訂閱制 token** → 用路徑 A。
2. 否則若有 **API key** → 用路徑 B。
3. 兩者皆無或皆失敗 → 不外送，回報本地失敗（維持 DEC-023 的「不符資格則本地失敗回報」）。


### 11.3 使用者憑證儲存（profile，加密 at rest）

依使用者決定：**加密存 DB、可解密供呼叫**。

- 資料表 `user_external_credentials`〔已實作，Alembic migration 0014〕：

  | 欄位 | 說明 |
  | --- | --- |
  | `user_id` (FK CASCADE) | 擁有者 |
  | `provider` | `codex` / `openai` |
  | `auth_type` | `oauth_token` / `api_key` |
  | `secret_encrypted` | 對稱加密後的 token/key（**密文**） |
  | `masked_hint` | 遮罩提示（如 `sk-…abcd`，僅顯示末 4 碼） |
  | `status` | `active` / `invalid`（驗證失敗時標記） |
  | `updated_at` | |

- **加密**：對稱加密（如 Fernet），金鑰來自部署密鑰 `CREDENTIAL_ENCRYPTION_KEY`（env，不入版控）。呼叫外部前才在記憶體解密，用畢即棄。
- **API 一律回傳遮罩**（`masked_hint`），**永不回傳明文**。
- profile 端點〔已實作〕：`PUT /users/me/external-credentials`（設定/更新）、`DELETE /users/me/external-credentials/{provider}`（移除）、`GET`（只回 provider + masked_hint + status）。cipher 未設時 `PUT` 回 503。
- **安全立場（硬性）**：
  - **絕不**以明文儲存任何密碼或金鑰。
  - 路徑 A（訂閱制）若需帳密登入，**登入換 token 後只存 token，不存密碼**；密碼不落 DB、不寫 log。
  - 金鑰/token 不得出現在回應、log、錯誤訊息、稽核 metadata。
  - 升級外送仍受 DEC-023 隱私閘約束（私資料限本地或去識別化後才送）。

### 11.4 執行升級（延用 DEC-023）

- 觸發：**延用 `MAX_LOCAL_ATTEMPTS`**——本地連續 N 次（預設 3）結構化輸出／工作流程驗證失敗即升級。不額外加逾時門檻。
- 資格：使用者已在 profile 綁定可用外部憑證 **且** 外部啟用 **且** 非隱私鎖定（或已去識別化）。
- 外部回來的計畫/結果**仍走原本權限、安全、沙箱、確認閘**（與本地產出同等對待）。
- 升級事件寫**稽核**（誰、哪個工作、用哪個 provider、第幾次升級），但**不記錄憑證**。
- 接點〔已實作〕：`ModelRouter`（`app/assistant/llm/router.py`）是升級骨架；`app/assistant/router.py` 的 `_assistant_service` 注入 `CurrentUserId` → `build_chat_client` 依使用者 profile 憑證**動態建外部 client**（取代僅全域 env），provider 依 §11.2.3 選擇。

### 11.5 Eval harness 考官（judge）


- 現有 `backend/eval/judge.py` 已有 `JudgeModel` 協定 + `judge_case`；本設計新增 **OpenAI/Codex 考官實作**，並讓考官可配置。
- **預設 Gemma 4，可切 Codex/GPT**（`--judge-provider {gemma|codex|openai}`，預設 gemma）。考官憑證來源為**開發者 env / CLI 參數**（eval 由評測者執行，非終端使用者 profile）。
- 評斷範圍（rubric 兩者都含）：
  1. **生成正確性**：skill 的程式碼/manifest 是否正確、通過 codeguard 靜態驗證與沙箱、結構化輸出符合契約。
  2. **效果符合期待**：在 fixture 上實際執行後，產出的檔案/行為是否達成使用者 prompt 的意圖（沿用 `--mode exec` 的產出斷言，judge 再做語意層判定）。
- 考官與被考者分離：harness 引擎用 Gemma 4 產生 skill；考官（可為更強的 Codex/GPT）獨立評分，避免「自己改自己考卷」。

### 11.6 設定項（env）〔已實作，名稱以實際 `config.py` 為準〕

| 設定 | 用途 | 預設 |
| --- | --- | --- |
| `CREDENTIAL_ENCRYPTION_KEY` | profile 憑證對稱加密金鑰；**空＝整個 per-user 外部功能停用**（即總開關） | （空） |
| `EXTERNAL_API_BASE_URL` | 路徑 B 的 OpenAI 相容端點 | `https://api.openai.com/v1` |
| `EXTERNAL_CHAT_MODEL` | 外部升級／API key 路徑的模型名 | `gpt-5.5` |
| `CODEX_BIN` | 路徑 A 的 `codex` CLI 路徑（映像需 `--build-arg INSTALL_CODEX=1`） | `codex` |
| `MAX_LOCAL_ATTEMPTS` | 升級門檻（延用 DEC-023） | `3` |
| `JUDGE_PROVIDER` / `JUDGE_MODEL` | eval 考官 provider/模型（E6 待做，尚未實作） | `gemma` |


### 11.7 待確認 / 風險

**已定 / 已處理：**

- **考官用 Codex 的憑證來源** → 已定：走**開發者 env / CLI**（非 per-user），任務見 [assistant-eval.md](../tasks/assistant-eval.md) E6。
- **全域 key 與 per-user 的優先序** → 已解決：無全域 key 升級路徑，純 per-user（§11.6）。
- **額度耗盡處理** → 已實作（EM2）：401/403/429-quota → 標 `invalid` + 前端提示重設。

**仍開放：**

1. **訂閱制跨機**：可用已證實（§11.9.6）；剩餘為**風險權衡**（集中保管多人 token 的安全責任、多人同 server IP 的風控灰區、代呼叫合規），非技術硬傷。**跨機 refresh 尚未實測**（低風險，refresh token 在 auth.json 內）。
2. **加密金鑰管理**：`CREDENTIAL_ENCRYPTION_KEY` 目前用部署 env；是否需 KMS／金鑰輪替待 ops 決定。
3. **額度／風控監測與告警**（EM3 風險項）：需 metrics／alerting 基礎設施，**未做**（留 ops）。
4. **使用者自帶 key 的用量上限／配額管理**：未做。

### 11.8 不在本次範圍

- 去識別化演算法本身（沿用 DEC-023 既有設計）。
- 非 OpenAI 相容的其他外部供應商。
- **E6 考官 provider 的實作**（任務已獨立至 [assistant-eval.md](../tasks/assistant-eval.md)）。
- §11.7「仍開放」各項（KMS／金鑰輪替、額度監測告警、用量上限）。

### 11.9 訂閱制跨機可行性驗證（2026-06-19；原始碼 + 官方文件 + 雙機 demo）


### 11.129.1 方法

讀**官方 Codex CLI 原始碼**（`github.com/openai/codex`，`codex-rs/login/src/auth/{storage,agent_identity,manager}.rs`、`core/src/config/auth_keyring.rs`）。

### 11.129.2 發現（高信心）

1. **ChatGPT 訂閱認證採「Agent Identity」**：登入時**本機生成 agent 金鑰對（PKCS8 私鑰）並向 ChatGPT authapi 註冊**（`generate_agent_key_material` / `register_agent_identity`）；access token 是**綁該 identity 的 JWT**（`CodexAccessToken::AgentIdentityJwt`），並有 `ManagedChatGptAgentIdentityBinding`。
2. **`$CODEX_HOME/auth.json`（`AuthDotJson`）結構**：`tokens`（access/refresh）、`last_refresh`、**`agent_identity`（含 `agent_private_key`）**、`OPENAI_API_KEY`、`personal_access_token` 等。
3. **私鑰位置取決於 backend**：預設 `Direct` → 私鑰**存在 auth.json**（軟體金鑰、可複製）；啟用 `SecretAuthStorage` feature → 私鑰改存 **OS keyring**（macOS Keychain / Linux secret service），**無法從 auth.json 匯出**。
4. **refresh**：存在 `ChatgptAuthTokensRefresh`；refresh 與 agent identity（私鑰）綁定，但私鑰若在 auth.json 內則一併可搬。

**官方文件佐證**（developers.openai.com/codex/auth）：明確把 `auth.json` 當密碼、說它**含 access tokens**，並**允許跨機複製**（"Treat `~/.codex/auth.json` like a password… Don't… share it in chat."），**未提任何機器綁定限制**；headless/容器可用 `codex login --device-auth`（需先在 ChatGPT 開啟 device code login）。

### 11.129.3 結論（已實機 demo 證實，見 §11.9.6）

- **跨機可用：已實證**。雙容器 demo 中，把 machine-a 的 `auth.json` 搬到從未登入、不同 hostname 的 machine-b 後，成功呼叫 gpt-5.5（exit 0、無重新登入）。先前「技術脆弱不可行」的判斷**過度悲觀，正式更正**。
- **實際 auth.json 結構（v0.141.0）**：只含 OAuth tokens（`access_token` / `id_token` / `refresh_token` / `account_id`）+ `auth_mode` / `last_refresh`，**無 agent_identity 私鑰**。我先前從舊原始碼推測的「綁機私鑰」在此版**不存在**，token 是**可搬移的標準 OAuth 憑證**。
- **多使用者集中式的剩餘考量（非技術硬傷，是風險權衡）**：(a) server 端**集中保管多位使用者的 OAuth token**，安全責任重；(b) 多人從**同一 server IP** 發請求，是否觸發 ChatGPT 風控屬**灰區**；(c) 以 CLI 代多人呼叫的**合規**需自行確認。
- **可行但需謹慎**：技術上做得到（已證實）；是否採用是上述 (a)(b)(c) 的權衡，而非「能不能」。

### 11.129.4 使用者實機 100% 確認步驟（速查；完整自動化見 §11.9.5）

1. A 機 `codex login` → 檢查 `~/.codex/auth.json` 有無 `agent_identity.agent_private_key`（無 → 在 keyring → 集中式直接判不可行）。
2. 整份 auth.json 複製到 B 機乾淨 `CODEX_HOME` → 跑一次 `codex` → 成功＝可跨機。
3. B 機試 refresh。

### 11.129.5 一鍵雙機 demo（已備好）

`experiments/codex-cross-machine-demo/`（獨立於專案，不動 backend/frontend）提供可跑的雙容器 demo：`machine-a` 用 `codex login --device-auth` 登入 → 自動把 auth.json 搬到**不同 hostname、從未登入過的** `machine-b` → 在 b 實際呼叫 + 驗 refresh → 印出 `RESULT: CROSS-MACHINE OK` / `DEVICE-BOUND` / `PRIVATE KEY NOT IN auth.json`。

- 你要做的只有「在 a 完成那次 OAuth 登入」（需真 Codex 訂閱帳號；token 不進對話、`.gitignore` 已排除）。
- demo 能證實/排除**綁機（技術硬傷）**；**測不到**多地多 IP 的 ChatGPT 風控（兩容器同宿主同出口 IP）。
- 跑法與判讀見該目錄 `README.md`。

### 11.129.6 實機 demo 結果（2026-06-19）✅ 跨機可用

- 環境：上述雙容器（machine-a / machine-b，**不同 hostname**），Codex CLI **v0.141.0**。
- machine-a `codex login --device-auth` 成功；auth.json 僅含 OAuth tokens（`access_token` / `id_token` / `refresh_token` / `account_id`）+ `auth_mode` / `last_refresh`，**無 agent 私鑰**。
- 把該 auth.json 搬到**從未登入、不同 hostname 的 machine-b**後，`codex exec --skip-git-repo-check` **成功呼叫 gpt-5.5**、回 `CROSS_MACHINE_OK`、**exit 0、未被要求重新登入、無 401/403**（消耗約 3 萬 tokens 訂閱額度）。
- **判定：跨機可用已證實——token 不綁機、可搬。** 多使用者集中式在「技術可搬性」這關**通過**。
- 過程插曲（非授權問題）：首次失敗是 codex 的「Not inside a trusted directory」目錄檢查，加 `--skip-git-repo-check` 後即正常——印證「環境/用法錯 ≠ 綁機」。
- 尚未實測：① **refresh 未觸發**（token 仍新、`last_refresh` 未變）；refresh token 在 auth.json 內、屬標準 OAuth 續期，預期可跨機（低風險）。② 多地多 IP 的 ChatGPT 風控。

### 11.10 多組「具名模型連線」+ 模型可選 + 無自動 fallback（EM4）

> **落地狀態**：本節設計已於 `main` 分支實作完成（2026-06-25），**尚未合併進 `fix/core-stability` 分支的程式碼**——先納入設計文件，程式碼待後續 cherry-pick／實作。落地時，§11.0 現況表、§7.12 Migration 演進表（新增 0016）、§13.5 端點清單需同步更新。取代 §11.3「每使用者每 provider 一把憑證」。決策沿用 DEC-026 並擴充。

#### 11.10.1 動機

EM1~EM3 的 `user_external_credentials` 是 `(user_id, provider)` 單筆，痛點：① 某模型免費額度用完無法換另一把 key；② 不能存多把、不能自己命名；③ UI 寫「OpenAI key」但實連 Gemini（走 OpenAI 相容端點），名稱誤導；④ 不同來源（OpenAI / Gemini / Ollama cloud / Codex）呼叫方式不同；⑤ 不同 key／來源要能選不同模型。

核心洞見：「**OpenAI 相容」是協定不是廠商**——OpenAI / Gemini / Ollama cloud / Groq 等多半提供相容 `/chat/completions`，差別只在 `base_url + model + key`；Codex（訂閱）是唯一特例（CLI bridge）。

#### 11.10.2 資料模型

`external_model_connections`〔Alembic migration **0016**：drop `user_external_credentials`、建新表、**不遷移**舊資料（舊為測試用）〕：

| 欄位 | 說明 |
| --- | --- |
| `id` (PK uuid) | 連線 id（可多筆） |
| `user_id` (FK CASCADE) | 擁有者 |
| `label` | 使用者自取名稱（顯示在下拉/設定） |
| `kind` | `openai_compatible` / `ollama` / `codex`（規劃擴充 `anthropic`，見 §11.10.5） |
| `base_url` | `openai_compatible`/`ollama` 必填；`codex` 不需 |
| `model` | 該連線使用的模型（如 `gemini-2.5-flash-lite`） |
| `secret_encrypted` | API key（或 codex auth.json），Fernet 加密 |
| `masked_hint` | 遮罩提示（僅顯示末 4 碼） |
| `status` | `active` / `invalid`（驗證失敗時標記） |
| `created_at` / `updated_at` | |

#### 11.10.3 後端

- `app/models/external_model_connection.py`（新）、刪 `user_external_credential.py`。
- `external_model/repository.py`：`SQLConnectionRepository`（CRUD by id）。
- `external_model/service.py`：`ExternalModelConnectionService`，`build_clients(user_id) -> dict[str, LLMClient]`（keyed by `str(connection.id)`）；依 `kind` 建 client：
  - `openai_compatible` → `ExternalLLMClient(base_url, model, key)`
  - `ollama` → `OllamaLLMClient(base_url, model, api_key)`（原生 `/api/chat`）
  - `codex` → `CodexSubscriptionClient`
  - 失敗（`ExternalAuthError`）→ `_CredentialTrackingClient` 標記該連線 `invalid`；Codex token refresh 回寫（by `user_id` + `connection_id`）。
- `external_model/schemas.py`：`ConnectionCreate/Update/View`（只回遮罩，永不回明文）。
- `external_model/router.py`：`GET/POST/PUT/DELETE /users/me/model-connections`（取代舊 `/external-credentials`）。
- `assistant/router.py`：`external_clients = build_connection_service(...).build_clients(user)`；`GET /assistant/models` 回**本機模型清單**（見 §11.10.5）+ 每筆連線（`id=str(id)`、`label="{label} · {model}"`、`available=status=="active"`）；chat 的 `target` = 連線 id、`"local"`、或 `"local:<model>"`。
- `AssistantChatRequest.model: str | None`（連線 id 或 `"local"`）。

#### 11.10.5 本機模型清單（伺服器提供，2026-08-30）

對應 proposal §12「本機模型清單」。部署方在**一個**設定裡列出多個本機模型，
所有使用者都看得到，**不需要任何個人設定、不寫入資料庫**。

**設定**

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `ASSISTANT_MODEL` | `gemma4:26b` | 預設模型；未指定 target 時走它 |
| `ASSISTANT_MODELS` | 空 | 逗號分隔的額外本機模型 id。空值時清單即 `[ASSISTANT_MODEL]`，**行為與現況完全相同** |

三者共用 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_PROVIDER`——本機清單的前提是
**同一個端點服務多個模型**（自架 gateway 或 Ollama）。需要不同端點或不同憑證的，
屬於使用者自己的外部連線，走 §11.10.1–11.10.3 那條路。

**target 命名**

- `"local"`（或 `None`）→ `ASSISTANT_MODEL`，維持既有語意，舊 client 不受影響。
- `"local:<model-id>"` → 本機清單中的該模型。用前綴而非裸 model id，是為了讓
  `ModelRouter` 能**只靠字串就分辨** target 是本機模型還是連線 UUID，不必先查資料庫。
- 連線 UUID → 不變。

**實作點**

- `Settings.assistant_models: str`；`Settings.local_model_ids -> list[str]` 解析並去重，
  第一項恆為 `assistant_model`。
- `assistant/router.py::_build_local_client` 改為 `_build_local_clients(settings) ->
  dict[str, LLMClient]`，keyed by `"local:<model>"`；每個 model 一個 client 實例
  （client 本身無狀態，每次呼叫才開 `httpx.AsyncClient`，成本可忽略）。
- `assistant/router.py::list_models` 對每個本機模型各回一個 option：
  第一項 `id="local"`、`label="Local ({assistant_model})"`（**維持現有標籤不變**，
  舊測試與使用者習慣不受影響），其餘 `id="local:{m}"`、`label="Local ({m})"`。
- `ModelRouter`：`target.startswith("local:")` 時取 `_local_clients[target]`，
  **走與 `local` 相同的路徑**（含重試與 validator），**不經隱私閘的外送限制**——
  它與既有單一本機模型同類，資料未離開部署方掌控範圍。

**與隱私閘的關係**：`PRIVACY_DEFAULT` 的外送限制只作用於**使用者的外部連線**。
本機清單不受其限制。這一點很重要——先前把伺服器模型當成連線註冊時，
`PRIVACY_DEFAULT=sensitive` 會讓每一個選項都回「連不上模型」，而 UI 完全正常，
是典型的「選得到但用不了」。

#### 11.10.4 模型可選 + 無自動 fallback（取代 §11.4 的自動升級路徑）

- 助理面板每則訊息帶上所選 `model`；`ModelRouter.chat(target=...)` 指定時 **local-only 或該連線 only**，**不再自動 fallback**（不再 codex→openai 串接，也不再「本地反覆失敗才升級」）。`target=None` 維持 §11.4 / DEC-023 舊自動行為以保相容。
- 隱私閘沿用（手動選外部仍須通過隱私規則；敏感且未去識別化 → 拒送並說明）。
- **明確錯誤 + 快速失敗**：失敗回可區分訊息——連不到（連線失敗/逾時）、憑證被拒（401/403）、額度/速率（429/quota）、其他。`OllamaLLMClient` 加 `connect_timeout`（預設 **5s**），連不到的本機數秒內失敗，不再卡 `LLM_TIMEOUT_SECONDS`（300s）。

#### 11.10.5 Anthropic／Claude 連線（client 已備、尚未接線）

- **現況（誠實標註）**：`app/assistant/llm/anthropic.py` 已備 `AnthropicLLMClient`（Anthropic Messages API：`system`/`messages` 拆分、`response_format` 時附「Respond with valid JSON only.」、`ExternalAuthError`/`LLMUnavailableError` 分類），**但尚未接線**——`ConnectionKind` 只含 `openai_compatible/ollama/codex`、`service.build_clients` 沒有 `anthropic` 分支、前端 preset 無 Claude，因此目前**無法從 UI 建立 Claude 連線**（`main` 分支亦同）。
- **待接線設計（EM4+，規劃）**：`ConnectionKind` 增列 `anthropic`；`build_clients` 加分支 `anthropic → AnthropicLLMClient(base_url, model, api_key)`；`base_url` 預設 `https://api.anthropic.com`、`model` 如 `claude-sonnet-*`；前端 `ExternalModelSettings` presets 增 Claude（自動帶入 base_url）。Claude 屬「非 OpenAI 相容協定」，走專屬 client（同 Codex 的特例定位）。
- 落地前，本項在 §11.0 現況表維持 ⚠️「client 已備、尚未接線」狀態，不得標為完成。

#### 11.10.6 外部模型結構化輸出（json_schema）

外部模型（如 Gemini）原本不遵守 planner 要求的 JSON 格式（`{"reply","steps":[{"skill","arguments","depends_on"}]}`）→ 只閒聊不執行。修法：

- `LLMClient.chat` 加 `response_format: dict | None`，從 `planner` → `ModelRouter` → 各 client 串下去（**本機與外部路徑都轉發**；先前只有外部，`router.py` 本機呼叫漏傳，由 planner 防護測試抓出補上）；`ExternalLLMClient` 原樣放進 payload。
- `_PLAN_RESPONSE_FORMAT`（定義於 `planner.py`）是 plan 的 json_schema，**不加 `strict`**（strict 要求 `additionalProperties:false`，與開放的 `arguments` 物件衝突，OpenAI 會拒）。**維持手寫、不用 `model_json_schema()`**——Pydantic model 欄位皆有預設值，自動產生的 schema 會沒有 `required`，約束反而變弱；改以 drift test（`test_plan_response_format_stays_in_sync_with_models`）鎖定 schema 與 `PlanResult`/`PlannedStep` 欄位一致。
- 本機 Ollama：有 `response_format` 時，`_to_ollama_format()` 從信封拆出裸 schema 放進 `format`（Ollama 據此做 grammar 級約束解碼，取代先前只保證合法 JSON 的 `format:"json"` 弱檔），並同時 `options.temperature=0` 提升計畫可重現性；自然語言回覆、codegen 不帶 `response_format`，取樣與輸出皆不受影響。
- 語意防線不變：schema 只保證形狀，hallucinated skill 名/缺參數仍由 `validate_plan` + repair loop 攔截。
- 前置修正：planner 規劃時未告知「使用者已選 N 個檔」→ 外部模型一直反問哪個檔。`planner.plan(selected_count=...)` 加一條系統訊息告知。

#### 11.10.7 前端

- `api/types.ts`：`ModelTarget = string`、`ConnectionView/Create/Update/Kind`。
- `api/externalModelApi.ts` → `modelConnectionApi`（CRUD）；`hooks/useExternalCredentials.ts` → `useModelConnections` 等。
- `components/settings/ExternalModelSettings.tsx`：連線**列表** + 新增表單（label / kind 下拉 / base_url / model / key）+ **presets**（Gemini / OpenAI / Ollama cloud / Codex，自動帶入對應 base_url 降低混淆；Claude preset 待 §11.10.5 接線後補）。
- `components/assistant/AssistantPanel.tsx`：下拉列出 local + 各連線 label；未設定者停用；送出帶 `model`；錯誤顯示後端分類訊息。
- **預設選擇（Q2）**：載入 models 後自動挑預設——有可用外部連線則預設該外部、否則預設本機；未選到任何可用模型時送出鈕停用。

#### 11.10.8 實機驗證與安全待辦

- **Gemini**：`openai_compatible` + `https://generativelanguage.googleapis.com/v1beta/openai` 可用（free tier 每日有限、偶發 503）。
- **Ollama cloud**：**必須用 `openai_compatible` + `https://ollama.com/v1`**（不是 `ollama` kind——原生 `/api/chat` + `/v1` base_url 會變 `/v1/api/chat` 404）；`/v1` 支援 json_schema；模型用目錄內名稱（如 `gpt-oss:20b`）；**免費 key 有限流（撞到回 401）**。preset 已對應修正。
- ⚠️ **SSRF 未控管**：`base_url` 目前任填，未做 https 限制/白名單——使用者可填任意 URL（含內網）。**待補**。
- 連線**編輯 UI 未接**（PUT 端點有，UI 只做新增/刪除）。

### 11.11 執行失敗處理：誠實報告 + 有限度重規劃 + 執行隔離（DEC-029／DEC-030）

> **落地狀態**：main 已實作（誠實報告＋replan 2026-07-04；執行隔離 2026-07-05），**fix 分支待落地**。**決策 DEC-029／DEC-030 目前僅記於 main 分支；本文件[附錄 A](./appendix-a-decisions.md)（原 fix decisions.md，止於 DEC-028）尚無此兩條**，故此處內嵌核心決策，待程式碼落地時補列於附錄 A（避免文件引用不存在的 DEC）。本節對應 §8.3 workflow 管線第 8 階段「執行 Workflow」的錯誤處理語意。

plan-then-execute 的兩個結構性問題與對策：

- **誠實報告（第 0 級）**：`plan.reply` 是規劃時的預測，執行失敗時不得回給使用者。`service.py` 的三條執行路徑（chat 快速路徑 / confirm / rerun）統一：全成功才用原訊息；有失敗改回 `_compose_failure_message()` 從 `StepResult` 組合的事實報告（失敗步驟+原因、已完成步驟、其後未執行且無進一步變更）。程式組合、不經 LLM。API status 欄位不變（前端契約）。
- **失敗才 replan（第 1 級，僅 chat 快速路徑）**：執行失敗 → `_execution_feedback()` 把逐步真實結果餵回 planner 重規劃一次（budget=1）→ 護欄：新計畫必須全 read-only auto-confirmable 且不含 requires_selection，否則放棄且不建 pending；replan 再失敗落回誠實報告（加註已重試）。兩次嘗試各記一筆 run（第二筆 `source_nl` 帶 `[replan]`）。成功路徑維持一次 LLM 呼叫。
- **confirm / rerun 無 replan**：核可後偷換步驟破壞同意邊界；saved workflow 是固定配方。

**為何不做 agentic loop（DEC-029 摘要）**：① 權限模型依賴完整計畫先行——destructive 步驟整批分類、事前一次核可；逐步決策會讓「使用者核可了什麼」失去邊界。② 弱模型跑長程多輪 loop 容易漂移；一次規劃 + 約束解碼 + `validate_plan` 把弱模型鎖在能力範圍內。③ 成本/延遲——工作流多為 2-3 步，「失敗才 replan」讓成功路徑維持一次呼叫。④ 可先量再改，不排除未來翻案。

**授權邊界（DEC-029 補充）**：replan 只在「授權是給**規則**、不是給**那份計畫**」的路徑合法——chat 快速路徑的授權來自「read-only 免確認」系統規則（replan 新計畫仍受同一規則約束，最壞只浪費 token）；confirm 授權的是那份具體步驟清單、rerun 是具名固定配方，兩者失敗只誠實回報、不得偷換步驟。

**執行隔離（DAG 第一階段）**：executor 不再遇錯全域 break。仍**串行、單一 request session**（並行留待第二階段，見下 DEC-030）。語意：

- 失敗只斷「真正的下游」：`_blocked_dependencies()` 合併顯式 `depends_on` 與引數 `from_step` 引用，踩到已失敗/已跳過的上游 → 記 `StepResult(skipped=True)`（error 註明依賴哪步）且不執行、不發 hook；無關步驟照常執行。
- 新不變量：**每步恰有一筆結果**（`len(results) == len(steps)`），三態 ok / failed / skipped（hypothesis property test 鎖定）。
- `StepResult.skipped: bool = False` 為 additive 欄位（DB JSON / API / 前端型別皆向後相容）；前端 `StepResultList` 以 skip 圖示區別渲染。
- 誠實報告升級為分支彙總：「執行完成 X/N 步。第 i 步(skill)失敗:原因。另有 M 步因上游失敗而跳過。」；replan 回饋含 SKIPPED 行。
- 引用「不存在的 index」仍記 failed（非法計畫引用 ≠ 上游失敗）。

**維持串行、暫不並行（DEC-030 摘要）**：計畫本是 DAG，第一階段已依圖語意傳播失敗；「用圖排程並行」列第二階段。現在不並行的主因：① 共用 request-scoped `AsyncSession` 不允許並發（SQLAlchemy 明文禁止；`asyncio.gather` 會拋 `InvalidRequestError`）——session 在 router 組裝鏈最上游被固定，下游無處替換。② 交易語意改變——現為單筆交易結尾一起 commit、可整體回滾；每步獨立 session 會各自 commit，中途失敗無法整體撤銷。③ 同使用者資料競爭（配額 check-then-write 競賽、同名唯一性、死鎖）。④ 連線池耗盡。第二階段候選路線：每步獨立 session（乾淨但侵入大）或分相執行（CPU 重活並行、碰 DB 收尾維持單 session 排隊）。

**影響範圍**：`backend/app/assistant/service.py`、`workflow.py`、`tests/assistant/test_workflow.py`；落地時補列[附錄 A](./appendix-a-decisions.md) DEC-029／DEC-030。

# 外部模型接入設計（Codex 訂閱制 / OpenAI API）

> 狀態：**設計階段，尚未實作**。本文件先確立設計與決策，實作另起。
> 決策記錄見 [decisions.md](./decisions.md) DEC-026；延伸自 DEC-023（模型策略）。

## 1. 目標

1. **執行升級**：當本地 Gemma 4（harness 引擎的預設執行器）對某任務反覆做不出可接受結果時，能改用 **GPT-5.5**（經 Codex 訂閱制或 OpenAI API）重試。
2. **eval 考官**：eval harness 的考官（judge）可選用 **Gemma 4 或 Codex/GPT**，評斷一個 skill 的「生成結果是否正確」以及「做出的效果是否符合使用者期待」。
3. **使用者自帶憑證**：使用者在 **profile** 設定自己的外部模型憑證後，才能使用上述外部功能；未設定則一律維持本地、不外送。

兩個使用點刻意分開：

| 使用點 | 預設 | 外部 | 憑證來源 |
| --- | --- | --- | --- |
| Harness 引擎（助理執行 workflow/skill） | Gemma 4（本地） | GPT-5.5（失敗升級） | **使用者 profile** |
| Eval harness 考官（評分 skill） | Gemma 4 | Codex/GPT（可選） | 開發者 env / CLI（評測者跑，非終端使用者） |

> 釐清：**harness 引擎裡跑的是 Gemma 4**；**eval harness 是評審**，評斷 skill 生成的正確性與效果。考官與被考者本就該是不同角色，考官用更強模型可更接近人類判斷。

## 2. 認證路徑（訂閱制優先，API key 備援）

依使用者決定：**Codex 訂閱制優先、OpenAI API key 備援**。設計上把「provider」抽象成介面，兩條路徑都實作同一個 `ExternalChatClient` 協定，升級/考官只依賴介面。

### 2.1 路徑 A — Codex 訂閱制（優先，參考 openclaw 的做法）

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
2. **儲存（server 端）**：把 token 經對稱加密存入該使用者的 `user_external_credentials`（§3），`auth_type=oauth_token`、`provider=codex`；只回遮罩。
3. **呼叫（server 端，per-request 隔離）**：需要升級或考官用 Codex 時——
   - 為「該次呼叫 × 該使用者」建立**臨時隔離 `CODEX_HOME`**（暫存目錄），把解密後的 token 寫成 `auth.json`，以 **`@zed-industries/codex-acp`** wrapper 啟動 codex 呼叫訂閱額度，**用畢即焚**（刪暫存、token 不落地於共用位置）。比照 openclaw 的「隔離 home + 遮罩」實務。
4. **token refresh（server 端自理）**：access token 過期時，server 用 refresh token 向 OpenAI token endpoint 續期並回寫加密儲存；refresh 失效則把該憑證標記 `invalid` 並提示使用者重新授權。
   - （openclaw 靠常駐 Codex CLI 自己 refresh；我們無常駐 CLI，故 refresh 需自理——這是與 openclaw 的主要實作差異。）

**絕不保存帳號明文密碼**；只持有可撤銷的 OAuth token（見 §3）。訂閱制管道失效時自動退回路徑 B。

> 待釐清（§7-1）：`codex login` 產生的 `auth.json` token 是否可被「非原機」的 codex-acp 直接使用（綁定裝置與否），以及 refresh token 的 endpoint/參數細節——這兩點需在實作前以實機驗證；若 token 綁定原機而無法跨機使用，多使用者集中式的訂閱制路徑將不可行，屆時以路徑 B（API key）交付。

### 2.2 路徑 B — OpenAI API key（備援，穩定）

- 使用者在 profile 填自己的 OpenAI API key（`sk-…`），後端以官方 API 呼叫 `gpt-5.5`。
- 官方支援、可程式化、計費透明、長期穩定。
- 即使最終訂閱制管道不可行，本路徑確保「升級到 GPT」這個功能仍可交付。

### 2.3 provider 選擇邏輯

升級或考官需要外部模型時：

1. 若使用者有**可用的訂閱制 token** → 用路徑 A。
2. 否則若有 **API key** → 用路徑 B。
3. 兩者皆無或皆失敗 → 不外送，回報本地失敗（維持 DEC-023 的「不符資格則本地失敗回報」）。

## 3. 使用者憑證儲存（profile，加密 at rest）

依使用者決定：**加密存 DB、可解密供呼叫**。

- 新資料表 `user_external_credentials`（草案）：

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
- profile 端點（草案）：`PUT /users/me/external-credentials`（設定/更新）、`DELETE /users/me/external-credentials/{provider}`（移除）、`GET`（只回 provider + masked_hint + status）。
- **安全立場（硬性）**：
  - **絕不**以明文儲存任何密碼或金鑰。
  - 路徑 A（訂閱制）若需帳密登入，**登入換 token 後只存 token，不存密碼**；密碼不落 DB、不寫 log。
  - 金鑰/token 不得出現在回應、log、錯誤訊息、稽核 metadata。
  - 升級外送仍受 DEC-023 隱私閘約束（私資料限本地或去識別化後才送）。

## 4. 執行升級（延用 DEC-023）

- 觸發：**延用 `MAX_LOCAL_ATTEMPTS`**——本地連續 N 次（預設 3）結構化輸出／工作流程驗證失敗即升級。不額外加逾時門檻。
- 資格：使用者已在 profile 綁定可用外部憑證 **且** 外部啟用 **且** 非隱私鎖定（或已去識別化）。
- 外部回來的計畫/結果**仍走原本權限、安全、沙箱、確認閘**（與本地產出同等對待）。
- 升級事件寫**稽核**（誰、哪個工作、用哪個 provider、第幾次升級），但**不記錄憑證**。
- 接點：現有 `app/assistant/llm/{router,external,privacy}.py` 的 `ModelRouter` 已是升級骨架；本設計把「external client 的建構」改為**依使用者 profile 憑證**動態建立（而非僅全域 env），provider 依 §2.3 選擇。

## 5. Eval harness 考官（judge）

> 範疇註：考官是**開發者 eval 工具**，非終端使用者功能（憑證走開發者 env/CLI）。任務追蹤已移至 `doc/tasks/assistant-eval.md` E6；本節僅保留設計，因考官**重用**本文件的 external client（§2）。

- 現有 `backend/eval/judge.py` 已有 `JudgeModel` 協定 + `judge_case`；本設計新增 **OpenAI/Codex 考官實作**，並讓考官可配置。
- **預設 Gemma 4，可切 Codex/GPT**（`--judge-provider {gemma|codex|openai}`，預設 gemma）。考官憑證來源為**開發者 env / CLI 參數**（eval 由評測者執行，非終端使用者 profile）。
- 評斷範圍（rubric 兩者都含）：
  1. **生成正確性**：skill 的程式碼/manifest 是否正確、通過 codeguard 靜態驗證與沙箱、結構化輸出符合契約。
  2. **效果符合期待**：在 fixture 上實際執行後，產出的檔案/行為是否達成使用者 prompt 的意圖（沿用 `--mode exec` 的產出斷言，judge 再做語意層判定）。
- 考官與被考者分離：harness 引擎用 Gemma 4 產生 skill；考官（可為更強的 Codex/GPT）獨立評分，避免「自己改自己考卷」。

## 6. 設定項（草案，env）

| 設定 | 用途 | 預設 |
| --- | --- | --- |
| `CREDENTIAL_ENCRYPTION_KEY` | profile 憑證對稱加密金鑰 | （必填才啟用 per-user 憑證） |
| `EXTERNAL_LLM_ENABLED` | 全域總開關（延用 DEC-023） | `false` |
| `MAX_LOCAL_ATTEMPTS` | 升級門檻（延用） | `3` |
| `EXTERNAL_MODEL` | 外部模型名 | `gpt-5.5` |
| `JUDGE_PROVIDER` / `JUDGE_MODEL` | eval 考官 provider/模型 | `gemma` |

> per-user 憑證取代「全域 `EXTERNAL_LLM_API_KEY` 作為執行升級的金鑰」；全域 env 仍可作為「無 per-user 憑證時的系統級備援」（待確認，§7）。

## 7. 待確認 / 風險

1. **訂閱制跨機可行性 → 已實機 demo 證實「跨機可用」（§9.6）**。v0.141.0 的 auth.json 只含 OAuth tokens、無綁機私鑰，搬到他機（不同 hostname、乾淨環境）可直接呼叫 gpt-5.5。剩餘是**風險權衡**（集中保管多人 token 的安全責任、多人同 server IP 的風控灰區、代呼叫合規），非技術硬傷；**跨機 refresh 尚未實測**（低風險，refresh token 在 auth.json 內）。
2. **加密金鑰管理**：`CREDENTIAL_ENCRYPTION_KEY` 用部署 env 即可，或需 KMS／金鑰輪替？
3. **考官用 Codex 時的憑證來源**：固定走開發者 env，還是也允許 per-user？（目前定為開發者 env。）
4. **全域 env 金鑰與 per-user 憑證的優先序**：兩者並存時誰優先。
5. **計費與額度**：使用者自帶 key 的用量上限、額度耗盡的處理與提示。

## 8. 不在本次範圍

- 實作（本文件僅設計）。
- 去識別化演算法本身（沿用 DEC-023 既有設計）。
- 非 OpenAI 的其他外部供應商。

## 9. 訂閱制跨機可行性驗證（2026-06-19；原始碼 + 官方文件 + 雙機 demo）

> 目的：在不進專案、不需真帳號的前提下，先判斷「`codex login` 的 token 能否跨機用 + refresh」，以決定「多使用者集中式 + Codex 訂閱制」是否可行。

### 9.1 方法

讀**官方 Codex CLI 原始碼**（`github.com/openai/codex`，`codex-rs/login/src/auth/{storage,agent_identity,manager}.rs`、`core/src/config/auth_keyring.rs`）。

### 9.2 發現（高信心）

1. **ChatGPT 訂閱認證採「Agent Identity」**：登入時**本機生成 agent 金鑰對（PKCS8 私鑰）並向 ChatGPT authapi 註冊**（`generate_agent_key_material` / `register_agent_identity`）；access token 是**綁該 identity 的 JWT**（`CodexAccessToken::AgentIdentityJwt`），並有 `ManagedChatGptAgentIdentityBinding`。
2. **`$CODEX_HOME/auth.json`（`AuthDotJson`）結構**：`tokens`（access/refresh）、`last_refresh`、**`agent_identity`（含 `agent_private_key`）**、`OPENAI_API_KEY`、`personal_access_token` 等。
3. **私鑰位置取決於 backend**：預設 `Direct` → 私鑰**存在 auth.json**（軟體金鑰、可複製）；啟用 `SecretAuthStorage` feature → 私鑰改存 **OS keyring**（macOS Keychain / Linux secret service），**無法從 auth.json 匯出**。
4. **refresh**：存在 `ChatgptAuthTokensRefresh`；refresh 與 agent identity（私鑰）綁定，但私鑰若在 auth.json 內則一併可搬。

**官方文件佐證**（developers.openai.com/codex/auth）：明確把 `auth.json` 當密碼、說它**含 access tokens**，並**允許跨機複製**（"Treat `~/.codex/auth.json` like a password… Don't… share it in chat."），**未提任何機器綁定限制**；headless/容器可用 `codex login --device-auth`（需先在 ChatGPT 開啟 device code login）。

### 9.3 結論（已實機 demo 證實，見 §9.6）

- **跨機可用：已實證**。雙容器 demo 中，把 machine-a 的 `auth.json` 搬到從未登入、不同 hostname 的 machine-b 後，成功呼叫 gpt-5.5（exit 0、無重新登入）。先前「技術脆弱不可行」的判斷**過度悲觀，正式更正**。
- **實際 auth.json 結構（v0.141.0）**：只含 OAuth tokens（`access_token` / `id_token` / `refresh_token` / `account_id`）+ `auth_mode` / `last_refresh`，**無 agent_identity 私鑰**。我先前從舊原始碼推測的「綁機私鑰」在此版**不存在**，token 是**可搬移的標準 OAuth 憑證**。
- **多使用者集中式的剩餘考量（非技術硬傷，是風險權衡）**：(a) server 端**集中保管多位使用者的 OAuth token**，安全責任重；(b) 多人從**同一 server IP** 發請求，是否觸發 ChatGPT 風控屬**灰區**；(c) 以 CLI 代多人呼叫的**合規**需自行確認。
- **可行但需謹慎**：技術上做得到（已證實）；是否採用是上述 (a)(b)(c) 的權衡，而非「能不能」。

### 9.4 使用者實機 100% 確認步驟（速查；完整自動化見 §9.5）

1. A 機 `codex login` → 檢查 `~/.codex/auth.json` 有無 `agent_identity.agent_private_key`（無 → 在 keyring → 集中式直接判不可行）。
2. 整份 auth.json 複製到 B 機乾淨 `CODEX_HOME` → 跑一次 `codex` → 成功＝可跨機。
3. B 機試 refresh。

### 9.5 一鍵雙機 demo（已備好）

`experiments/codex-cross-machine-demo/`（獨立於專案，不動 backend/frontend）提供可跑的雙容器 demo：`machine-a` 用 `codex login --device-auth` 登入 → 自動把 auth.json 搬到**不同 hostname、從未登入過的** `machine-b` → 在 b 實際呼叫 + 驗 refresh → 印出 `RESULT: CROSS-MACHINE OK` / `DEVICE-BOUND` / `PRIVATE KEY NOT IN auth.json`。

- 你要做的只有「在 a 完成那次 OAuth 登入」（需真 Codex 訂閱帳號；token 不進對話、`.gitignore` 已排除）。
- demo 能證實/排除**綁機（技術硬傷）**；**測不到**多地多 IP 的 ChatGPT 風控（兩容器同宿主同出口 IP）。
- 跑法與判讀見該目錄 `README.md`。

### 9.6 實機 demo 結果（2026-06-19）✅ 跨機可用

- 環境：上述雙容器（machine-a / machine-b，**不同 hostname**），Codex CLI **v0.141.0**。
- machine-a `codex login --device-auth` 成功；auth.json 僅含 OAuth tokens（`access_token` / `id_token` / `refresh_token` / `account_id`）+ `auth_mode` / `last_refresh`，**無 agent 私鑰**。
- 把該 auth.json 搬到**從未登入、不同 hostname 的 machine-b**後，`codex exec --skip-git-repo-check` **成功呼叫 gpt-5.5**、回 `CROSS_MACHINE_OK`、**exit 0、未被要求重新登入、無 401/403**（消耗約 3 萬 tokens 訂閱額度）。
- **判定：跨機可用已證實——token 不綁機、可搬。** 多使用者集中式在「技術可搬性」這關**通過**。
- 過程插曲（非授權問題）：首次失敗是 codex 的「Not inside a trusted directory」目錄檢查，加 `--skip-git-repo-check` 後即正常——印證「環境/用法錯 ≠ 綁機」。
- 尚未實測：① **refresh 未觸發**（token 仍新、`last_refresh` 未變）；refresh token 在 auth.json 內、屬標準 OAuth 續期，預期可跨機（低風險）。② 多地多 IP 的 ChatGPT 風控。

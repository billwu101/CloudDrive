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

### 2.1 路徑 A — Codex 訂閱制（優先）

- 使用者在 profile 綁定其 ChatGPT/Codex 訂閱帳號，後端用訂閱額度呼叫 GPT-5.5。
- ⚠️ **重大技術風險（務必知悉）**：ChatGPT/Codex 訂閱制**沒有穩定的官方程式化 Chat API**。可行的程式化管道（ChatGPT session token、Codex CLI 的 OAuth token 等）屬**非官方、易隨對方改版失效，且可能牴觸服務條款**。因此：
  - 本路徑定位為「**盡力而為（best-effort）**」，不保證長期可用。
  - **登入後只保存可撤銷的存取 token（加密），絕不長期保存帳號明文密碼**（見 §3 安全）。
  - 一旦訂閱制管道失效，系統自動退回路徑 B（API key），功能不中斷。
- 待確認（§7）：實際採哪種訂閱制 token 取得流程。

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

1. **訂閱制程式化管道**：Codex/ChatGPT 訂閱制實際以何種 token 流程程式化呼叫？是否存在可接受（不違 ToS、夠穩定）的方式？若無 → 路徑 A 降為實驗性、以路徑 B 為主交付。
2. **加密金鑰管理**：`CREDENTIAL_ENCRYPTION_KEY` 用部署 env 即可，或需 KMS／金鑰輪替？
3. **考官用 Codex 時的憑證來源**：固定走開發者 env，還是也允許 per-user？（目前定為開發者 env。）
4. **全域 env 金鑰與 per-user 憑證的優先序**：兩者並存時誰優先。
5. **計費與額度**：使用者自帶 key 的用量上限、額度耗盡的處理與提示。

## 8. 不在本次範圍

- 實作（本文件僅設計）。
- 去識別化演算法本身（沿用 DEC-023 既有設計）。
- 非 OpenAI 的其他外部供應商。

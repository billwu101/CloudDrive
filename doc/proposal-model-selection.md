# 需求草案：助理模型可選擇 + 明確錯誤回報

> 狀態：**proposal 草案（待使用者確認）**。2026-06-25。
> 依 CLAUDE.md 文件先行規則，本檔確認後才進 `detailed-design.md` → `tasks/`。
> 關聯：[codex-訂閱制問題分析.md](./codex-訂閱制問題分析.md)、[tasks/external-model.md](./tasks/external-model.md)、DEC-023 / DEC-026。

## 1. 背景與動機

目前助理採**固定自動 fallback**：每次對話一律先試本機 Ollama，失敗才升級外部（Codex 優先、OpenAI key 備援）。實測發現兩個問題：

- **慢**：本機預設指向連不到的 `192.168.10.75:11434`，連線逾時 30s+，乘上規劃多輪迭代 → 單次對話 1~2 分鐘。
- **不穩 / 不透明**：失敗時只回籠統的 503「Assistant is unavailable」，使用者無法得知是「接不到本機」「金鑰被拒」還是「額度用盡」。

## 2. 目標

1. 使用者能**自行選擇**這次對話用哪個模型，不被固定 fallback 綁住。
2. 選到的模型若**接不到或出錯**，**明確告知**（哪個模型、什麼原因），且**快速失敗**、不長時間卡逾時。

## 3. 使用者角色與情境

- **一般使用者**：在助理面板下拉選「本機 / Gemini(OpenAI key) / Codex 訂閱」，送出訊息；若選的模型接不到，立即看到清楚說明。

## 4. 功能需求

- **FR1 模型選單（每次對話可切換）**：助理面板提供下拉選單；選項只列出「**目前可用**」的目標：
  - 本機（Ollama）—— 永遠列出（即使可能連不到，由 FR4 處理）。
  - OpenAI key —— 僅當使用者已設定 `openai` 憑證時出現。
  - Codex 訂閱 —— 僅當使用者已設定 `codex` 憑證時出現。
- **FR2 純手動、無自動 fallback**：選定的模型就是這次唯一使用的模型；**不再**自動退到別的模型。
- **FR3 選擇隨對話送出**：每則訊息帶上所選模型；可在同一 session 中途更換。
- **FR4 明確錯誤回報 + 快速失敗**：所選模型失敗時，回傳**可區分的錯誤類型**並轉成清楚訊息：
  - 接不到（連線失敗 / 逾時）→「無法連線到 <模型>，請確認服務是否啟動」。
  - 憑證被拒（401/403）→「<模型> 的憑證無效或被拒,請重新設定」。
  - 額度 / 速率（429 / quota）→「<模型> 已達額度或速率上限,請稍後再試或更換模型」。
  - 連線逾時須**短**（不可沿用 300s；建議可設定的小值），避免長時間卡住。

## 5. 非功能需求

- 失敗回報延遲低（接不到時數秒內回應，不卡分鐘級）。
- 沿用既有隱私閘 / 確認閘 / 沙箱 / 稽核（DEC-023）：手動選外部時，隱私規則仍須套用（敏感且未去識別化 → 拒送並說明）。
- 憑證仍只加密存、永不回傳明文。

## 6. 不在範圍（本次）

- ❌ 同一 provider 存**多把** key、可命名切換（維持每 provider 一把；之後再議）。
- ❌ 跨對話的「全域偏好模型」設定頁（本次只做對話內下拉；未來可加）。
- ❌ 新增本機以外的其他 provider（如直接接 Anthropic 等）。
- ❌ 自動 fallback 行為（本次刻意移除於助理選擇路徑）。

## 7. 安全與授權

- 手動選外部 = 使用者明確 opt-in；隱私閘仍為最後防線。
- 錯誤訊息**不得**洩漏金鑰或內部細節（只給分類與動作建議）。

## 8. 驗收標準（草案）

1. 助理面板有下拉選單，只列出目前可用的模型目標。
2. 選定模型後，該次對話只用該模型，不發生自動 fallback。
3. 選到接不到的模型時，**數秒內**回傳「無法連線到 <模型>」而非籠統 unavailable，也不卡 30s+。
4. 憑證被拒 / 額度耗盡 / 連線失敗三類錯誤，訊息可區分。
5. 既有隱私閘 / 確認閘 / 稽核行為不退化；既有測試不被破壞、並補對應新測試。

## 9. 待確認事項（實作時採用的預設，可再調整）

- [x] **Q1 選單顯示文字**：本機顯示 `Local (<assistant_model>)`（如 `Local (gemma4:26b)`）；外部顯示 `OpenAI` / `Codex subscription`。
- [x] **Q2 預設選項**：開啟時若有可用外部憑證則預設該外部，否則預設本機（`AssistantPanel` 載入 models 後自動挑選）。
- [x] **Q3 沒有可用模型**：未設定的 provider 在選單中**停用並標註 `(not configured)`**；未選到模型時送出鈕停用。
- [x] **Q4 本機逾時**：`OllamaLLMClient` 加 `connect_timeout`（預設 **5s**），連不到的本機數秒內失敗；生成讀取仍用原 `llm_timeout_seconds`。
- [x] **Q5 規劃多輪**：planner 全程帶同一個 `target`（codegen 子代理沿用既有行為，未在本次納入逐輪指定）。

---

## 10. 實作說明（已完成 2026-06-25）

> 本節記錄實際做了什麼。對應 [tasks/external-model.md](./tasks/external-model.md) 之後可補一條 model-selection 子任務。

### 行為
- 助理面板新增模型下拉選單，**每則訊息**帶上所選 `model`（`local` / `openai` / `codex`）。
- 選定模型 = 該次只用該模型，**無自動 fallback**：選本機就只用本機、選外部就只用該外部 provider（不再 codex→openai 串接）。
- 失敗時回**可區分**訊息：連不到（offline/未設定）、憑證被拒/額度（invalid/quota）、其他錯誤；前端直接顯示後端訊息。
- 本機連線快速失敗（connect 5s），不再卡 300s。

### 後端變更
- `app/assistant/schemas.py`：`AssistantChatRequest.model`（`ModelTarget`）；新增 `AssistantModelOption`。
- `app/assistant/llm/router.py`：`ModelRouter` 加 `external_clients` + `chat(target=...)`；`target` 指定時 local-only 或 external-only、無 fallback；privacy 閘沿用（抽出 `_call_external`）。向後相容（`target=None` 維持原 DEC-023 行為）。
- `app/assistant/llm/ollama.py`：`connect_timeout`（預設 5s），快速失敗。
- `app/external_model/service.py`：`build_provider_clients()` / `active_providers()`（每 provider 一個 client，不串接）。
- `app/assistant/planner.py`、`service.py`：`plan(target=...)` / `chat(target=...)` 串接。
- `app/assistant/router.py`：`_assistant_service` 組 `external_clients`、傳入 ModelRouter；新增 `GET /assistant/models`；chat 端點分類錯誤（`ExternalAuthError` / `LLMUnavailableError` / 其他）回明確訊息。
- 測試：`tests/assistant/test_model_router.py` 新增 target local-only/external-only/未設定 案例。後端 **590 passed**。

### 前端變更
- `src/api/types.ts`：`ModelTarget`、`AssistantModelOption`、`AssistantChatRequest.model`。
- `src/api/assistantApi.ts`：`listModels()`。
- `src/hooks/useAssistant.ts`：`useAssistantModels()` + `assistantKeys.models()`。
- `src/components/assistant/AssistantPanel.tsx`：下拉選單（未設定者停用）、預設選擇、送出帶 `model`、錯誤改顯示後端訊息。
- 測試：`AssistantPanel.test.tsx` 加 models handler + 模型選單測試；`src/test/handlers.ts` 加 `/assistant/models`。前端 **252 passed**。

### 仍未納入（沿用第 6 節）
- 多把同 provider key、全域偏好設定頁、codegen 逐輪指定模型、自動 fallback。

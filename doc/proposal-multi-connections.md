# 需求草案：多組「具名模型連線」（取代單一 openai/codex 憑證）

> 狀態:**proposal 草案(待實作,建議下個 session 開始)**。2026-06-25。
> 依 CLAUDE.md 文件先行。關聯:[proposal-model-selection.md]、[proposal-chat-skills.md]、DEC-026。
> 取代 [proposal-chat-skills.md] / [external-model.md] 中「每 provider 一把 key」的限制。

## 1. 背景與痛點(使用者提出)

1. 某個模型的**免費額度用完**(如 Gemini free tier 每天 20 次)→ 想**切換到另一把 key**。
2. 想存**多把 key**,且每把能**自己命名**。
3. 現在 UI 寫「OpenAI API key」,但實際連的是 **Gemini**(走 OpenAI 相容端點)→ 名稱誤導。
4. **不同來源呼叫方式不同**(OpenAI / Gemini / Ollama cloud / Codex)→ 要能各自設定。
5. 申辦了 **Ollama 帳號(免費額度)**,上傳 key 卻**不能呼叫**(原因:base_url 還指向 Gemini)。
6. **不同 key / 來源能選不同模型**。

## 2. 核心洞見

「OpenAI 相容」是**協定**不是廠商。OpenAI / Gemini / Ollama cloud / Groq / Together 等多半提供 OpenAI 相容 `/chat/completions`,差別只在 **base_url + model + key**。Codex(訂閱)是唯一特例(CLI/oauth bridge)。

## 3. 設計:把「憑證」升級成「具名模型連線」

新資料表(取代 `user_external_credentials` 的 `(user_id, provider)` 單筆模型):

```
external_model_connections
- id            uuid PK            # 可多筆
- user_id       uuid FK
- label         str                # 使用者自取(顯示在下拉/設定)
- kind          str                # "openai_compatible" | "codex"
- base_url      str | null         # openai_compatible 必填;codex 不需
- model         str | null         # 該連線使用的模型(如 gemini-2.5-flash-lite)
- secret_encrypted str             # API key(或 codex auth.json),Fernet 加密
- status        str                # active | invalid
- created_at / updated_at
```

對應痛點:① 多筆 row ② label ③ kind+label(不再叫 openai) ④⑤ kind 決定協定、base_url 各自填 ⑥ 每筆 model。

## 4. 行為

- **助理模型下拉**:本機(local) + 每一筆 active 連線(顯示 label)。選某筆 → 用它的 base_url+model+key 呼叫。
- 額度沒了 → 下拉換另一筆,免改設定。
- `kind=openai_compatible` → 走現有 `ExternalLLMClient`(已支援 `response_format` json_schema)。
- `kind=codex` → 走 `CodexSubscriptionClient`(沿用)。
- 自建 skill / planner / 確認閘 / 沙盒 / 隱私閘 全部不變,只是「外部 client」改由所選連線建構。

## 5. 後端實作要點

- **migration**:新表;把既有 `openai` 憑證遷成一筆 `openai_compatible`(base_url=設定的 `EXTERNAL_API_BASE_URL`、model=`EXTERNAL_CHAT_MODEL`);`codex` 遷成一筆 `kind=codex`。
- `ExternalCredentialService` → 改成 connection CRUD;`build_connection_client(connection_id)` 依該筆 base_url/model/key 建 `ExternalLLMClient`(或 Codex)。
- `ModelRouter`:`target` 從 "openai"/"codex" 改成 **連線 id**(或 "local");`external_clients` 改 keyed by 連線 id。
- `GET /assistant/models`:回 local + 每筆連線(id, label, model, available)。
- 連線 CRUD 端點:`GET/POST/PUT/DELETE /users/me/model-connections`(label/kind/base_url/model/key;回應只給遮罩,不回明文)。
- json_schema 結構化輸出(已實作)自動套用到每筆 openai_compatible 連線。

## 6. 前端實作要點

- 設定頁:連線**列表**(新增/編輯/刪除);每筆欄位 label、kind(下拉:OpenAI 相容 / Codex)、base_url、model、key。
- **預設範本(presets)** 降低混淆:選「Gemini / OpenAI / Ollama cloud」自動帶入對應 base_url(只留 key+model 給使用者填)。
- 助理對話框下拉:列出 local + 各連線 label。

## 7. Ollama cloud 待確認

- 使用者上傳 Ollama key 不能呼叫 = base_url 還指向 Gemini。
- 待查:Ollama cloud 的正確 base_url 與是否走 OpenAI 相容(Ollama 本地支援 `/v1` OpenAI 相容;cloud 端點需確認,可能是 `https://ollama.com/v1` 之類)。實作時 WebSearch 確認後做成 preset。

## 8. 安全 / 相容

- 沿用 Fernet 加密、只回遮罩、隱私閘。
- json_schema **不加 strict**(OpenAI strict 與開放 arguments 衝突)。
- base_url 應限制為 https + 白名單/格式檢查(避免 SSRF;使用者可填任意 URL 要小心)。← **新風險,需處理**。

## 9. 不在範圍 / 待議
- 連線間的自動 fallback(維持手動選)。
- 團隊/共享連線。

## 10. 待確認問題
- [ ] kind 是固定 enum(openai_compatible/codex)還是也開放純自訂 base_url?(建議:enum + preset)
- [ ] 既有單筆 openai/codex 憑證如何遷移(自動建一筆具名連線)?
- [ ] base_url 任填的 **SSRF 風險**如何控管(白名單 host?僅 https?)。
- [ ] local(Ollama 本機)要不要也納入「連線」統一管理,還是維持獨立?

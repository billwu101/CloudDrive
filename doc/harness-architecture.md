# Harness 架構歸類：六核心元件 ↔ 九實作模組

> 狀態：**參考文件（報告/簡報用概念架構）**，2026-07-05 建立。
> 本文件不改變任何實作與介面；工程事實來源仍為 [detailed-design.md §9.7](./detailed-design.md)（HARNESS 九大組件）與 §11（驗證/評分 harness）。
> 關聯：DEC-016～DEC-023、DEC-026、DEC-029；[proposal-model-selection.md](./proposal-model-selection.md)、[proposal-multi-connections.md](./proposal-multi-connections.md)。

## 1. 目的與定位

agent harness 文獻（survey）將 harness 正式定義為六元組：

```
H = (E, T, C, S, L, V)
E = Execution Loop、T = Tool Registry、C = Context Manager、
S = State Store、L = Lifecycle Hooks、V = Evaluation Interface
```

本專案的引擎在**程式碼層**拆成九個實作模組（§9.7 的 01–09），粒度是為了**可測試性**（§9.11：test_loop / test_context / test_planner / test_sandbox / test_hooks 各自獨立、LLM 一律 mock）。但九個模組不在同一抽象層級——有主元件（while loop）、子元件（built-in skills 是 registry 的技能來源之一）、也有橫切關注點（permissions & safety）。

因此對外（報告、簡報、答辯）採用**二層說法**：

1. **Workflow Pipeline**（描述「要做什麼」）：自然語言 → 候選 workflow → 技能檢查 → 權限/安全檢查 → 計畫確認 → 執行 → 記錄（DEC-021）。
2. **Agent Harness Runtime**（描述「怎麼可靠地跑」）：對齊 survey 的六核心元件；六元件在實作上再細分為九個模組。

**一句話結論：程式碼九層（實作模組），報告六層（概念架構）。**

## 2. 六元件 ↔ 九模組對照表

| Survey 元件 | 對應九模組 | 主要檔案 | 說明 |
|---|---|---|---|
| **E** Execution Loop | 01 while loop、04 sub-agents、workflow 執行器 | `service.py`、`workflow.py`、`subagent.py`、`llm/router.py` | 主迴圈驅動「送訊息→解析→執行→回填」；workflow 執行器負責步驟相依/錯誤策略（DEC-029/030：誠實報告、有限重規劃、串行）；可派生 bounded sub-agent；**model interface（ModelRouter）也歸此**，見 §4 |
| **T** Tool / Skill Registry | 03 skills & tools、05 built-in skills | `skills/registry.py`、`skills/manifest.py`、`skills/authoring.py`、`skills/builtin/` | 內建技能、使用者自建技能、現場生成技能（author_skill）都是 registry 的技能來源；manifest 定義 schema/權限標記/handler dispatch |
| **C** Context Manager | 02 context management、07 system prompt assembly | `context.py`、`planner.py`（`build_planner_prompt`）、`subagent.py`（`build_codegen_prompt`） | token 預算、裁切/摘要、工具輸出瘦身、技能清單注入、system prompt 組裝。07 在程式碼裡本來就無獨立 `prompt.py`，內嵌於各 agent |
| **S** State Store | 06 session persistence | `repository.py`（+ migration：sessions/messages/skills/workflows/workflow_runs） | 全部依 `user_id` 隔離（DEC-020） |
| **L** Lifecycle Hooks | 08 lifecycle hooks、09 permissions & safety | `hooks.py`、`permissions.py`、`skills/codeguard.py`、`skills/sandbox.py` | hooks 是**攔截點**（治理層）；permissions/codeguard/sandbox 是它**強制執行的機制**。分層權限：唯讀自動 / 破壞性確認 / 生成碼核可+沙箱+稽核（DEC-019） |
| **V** Evaluation Interface | §11 驗證/評分 harness | `backend/eval/`（schema/runner/verifier/scoring/judge/baseline） | 確定性斷言 + LLM judge + baseline 回歸；API / browser / exec 三模式（詳見 [tasks/assistant-eval.md](./tasks/assistant-eval.md)） |

## 3. 呈現時的三個注意事項（避免答辯被問倒）

1. **V 不在請求路徑上**。eval harness 位於 `backend/eval/`，是**離線的開發者工具**，從外部打 `/assistant/chat` 來評測系統；畫架構圖時 V 應畫在 runtime **旁邊**（箭頭指向系統），不可疊進 runtime 的層疊裡。這也正好符合 survey 把 V 稱為 evaluation *interface* 的原意。
2. **sub-agent 的現況要講誠實**。本專案的 `subagent.py` 目前唯一實例是 **CodegenSubAgent**（配合技能生成流程），不是通用的多代理編排。建議說法：「主迴圈可派生 bounded sub-agent，目前實例化為 codegen 子代理」。
3. **L 的合併邏輯**。08+09 合併時，嚴格說 `sandbox.py`/`codeguard.py` 是執行基礎設施而非 hook；正確說法是「Lifecycle Hooks 是治理層，permissions / codeguard / sandbox 是它在各攔截點強制執行的機制」。

## 4. 模型路由的歸位（本專案特色，勿被架構收斂吃掉）

survey 六元組把 LLM 當 harness 之外的黑盒，但本專案的模型策略是明確賣點，歸入 **E 的 model interface 子元件、受 L 的隱私閘治理**：

- **現行為（2026-06-25 起，proposal-model-selection + proposal-multi-connections）**：使用者**每則訊息自選模型來源**——本機 Ollama（gemma4:26b）或任一筆自建的**具名外部連線**（OpenAI 相容端點 / Codex 訂閱，per-user 加密憑證，migration 0016）。選定即該次唯一執行器，**無自動 fallback**；失敗回可區分的明確錯誤（連不到/憑證被拒/額度耗盡）且快速失敗（本機 connect 逾時 5s）。
- **隱私閘永遠在（DEC-023 第 2 條不變）**：即使使用者手動選外部，敏感且無法去識別化的內容仍拒送。
- **歷史演進**：原 DEC-023「本地預設、連續失敗自動升級外部」已被手動選擇取代；該自動升級邏輯僅保留於 `ModelRouter` 的 `target=None` 相容路徑（前端一律帶所選模型，正常流量不會走到），並仍有 eval `model-escalation` 案例覆蓋。

## 5. 報告用架構圖（V 在旁側）

```
使用者自然語言需求
        ↓
┌─ Workflow Pipeline ────────────────────────────┐
│ 需求解析 → 規劃 → 技能檢查 → 權限/安全 → 確認 → 執行 → 記錄 │
└────────────────────────────────────────────────┘
        ↓
┌─ Agent Harness Runtime（六元件） ───────────────┐      ┌─ V Evaluation Interface ─┐
│ E Execution Loop                                │      │  （離線開發者工具）        │
│   while loop / workflow executor /              │ ◄─── │  deterministic assertion  │
│   bounded sub-agent(codegen) /                  │ 評測  │  API / browser / exec     │
│   model interface（使用者自選：本機/具名連線）    │ 請求  │  LLM judge / baseline     │
│ T Tool / Skill Registry                         │      └───────────────────────────┘
│   built-in / 自建 / 現場生成技能 + manifest       │
│ C Context Manager                               │
│   裁切 / prompt 組裝 / 技能清單注入               │
│ S State Store                                   │
│   sessions / messages / skills / workflows      │
│ L Lifecycle Hooks（治理層）                      │
│   permission gate / approval / codeguard /      │
│   sandbox / audit —— 含外送隱私閘                │
└─────────────────────────────────────────────────┘
        ↓
CloudDrive Service Layer（DEC-017：不直接碰 DB/FS）
        ↓
PostgreSQL + Storage Provider
```

## 6. 報告建議措辭

> CloudDrive 的 In-App AI Assistant 採二層設計：Workflow Pipeline 描述「要做什麼」，Agent Harness Runtime 描述「怎麼可靠地跑」。Runtime 對齊 agent harness 文獻的六核心元件（Execution Loop、Tool Registry、Context Manager、State Store、Lifecycle Hooks、Evaluation Interface）；工程實作上，六元件再細分為九個模組以利獨立開發與測試。九模組中的 sub-agents、built-in skills、system prompt assembly、permissions & safety 分別是六元件下的子模組或橫切治理機制，而非獨立最高層。模型來源由使用者逐訊息自選（本機優先、外送必經隱私閘），評測則由獨立的離線 eval harness 以確定性斷言 + LLM judge 持續把關。

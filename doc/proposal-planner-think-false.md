# 需求草案：planner 預設關閉 thinking（DEC-033，已決策、待實作）

> 狀態：**已決策（E8 數據支持），實作待辦**。2026-07-07。
> 依 CLAUDE.md 文件先行。關聯：DEC-031/032、[assistant-eval.md E8](./tasks/assistant-eval.md)、
> [proposal-structured-decoding-stability.md](./proposal-structured-decoding-stability.md)。

## 1. 依據（E8 實驗，2026-07-07，各配置真模型實測）

- **think:false A/B**（storage-quota + safety-destructive × 5 runs @ 0.2）：
  對照組（thinking 開）60% pass、3/10 跳針、均 92s；實驗組（think:false）
  **100% pass、零跳針、均 8.6s（快 10 倍）**。
- **M3/M5**：think:false 使 503/跳針完全歸零（均 3.3s，快 30 倍）；剩餘失敗全為
  E4 已知的規劃能力弱點（與 thinking 無關——thinking 開時品質也沒更好）。
- **綜合 60 樣本**：thinking 開 30% pass vs think:false 47% pass。
- 結論：**thinking 對本模型（gemma4:26b）的規劃品質沒有可量測貢獻，卻是跳針與
  延遲的全部來源**。

## 2. 決策

planner 的 LLM 呼叫**預設關閉 thinking**；codegen **不變**（其 2/2 驗證於 thinking
開時取得，不連動未測行為）。DEC-031 防線（num_predict/低溫）保留為縱深。

## 3. 實作規格（給接手實作者）

依 `temperature` per-call 參數的既有前例（見 proposal-planner-skill-enum §7）：

1. `LLMClient.chat` 加 `disable_thinking: bool | None = None`（None=沿用 client
   建構子預設）。同步全部 7 個實作（ollama/external/anthropic/codex/service 包裝/
   router/protocol）與所有測試 fake——external/anthropic/codex 接受並忽略（協定無此欄）。
2. `OllamaLLMClient.chat`：per-call 值優先於建構子 `disable_thinking`；True 時
   payload 帶 `"think": false`。
3. `core/config.py`：`llm_planner_disable_thinking: bool = True`（預設開啟＝關 thinking）。
4. `WorkflowPlanner` 建構子加 `disable_thinking: bool`，`plan()` 的 chat 呼叫傳入；
   `assistant/router.py` 接線。**codegen 不傳**（維持 None）。
5. 既有全域實驗開關 `LLM_DISABLE_THINKING` 保留（E8 工具用），文件註明兩者關係。
6. 測試：ollama per-call 覆寫優先序、planner 傳遞、codegen 不傳；全閘門。
7. 真模型驗證（現在很便宜，每樣本 ~3-10s）：
   - `temp_sweep --temps 0.2 --runs 5 --case-ids storage-quota-read,safety-destructive-confirm`
     期望 ≈100%、零跳針、秒級延遲
   - codegen 手動 spot check 1 發（不退化即可）
   - 完整 integration `pytest tests/integration`（40/40，且 assistant 段應顯著變快）
8. 文件：本檔狀態改「已實作」+ 驗證數據；DEC-033 補實作註記；detailed-design
   §9.12 env 區塊 + `.env.example` 加 `LLM_PLANNER_DISABLE_THINKING`。

## 4. 已知取捨

- 失去 thinking 的潛在推理深度——E8 數據顯示對本模型不存在可量測損失；若未來換更強
  的 thinking 模型（如 gemma5），應重跑 E8 A/B 再決定是否翻回。
- `think` 為 Ollama 原生參數，外部 OpenAI 相容路徑無法控制（接受並忽略，與現狀一致）。

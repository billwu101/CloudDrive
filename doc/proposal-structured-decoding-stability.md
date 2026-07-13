# 需求草案：結構化解碼防跳針（num_predict 上限 + 非零 temperature）

> 狀態：**已實作（2026-07-06）**，實作說明見 §6。
> 依 CLAUDE.md 文件先行。關聯：DEC-031、[eval-prompt-log.md](./eval-prompt-log.md)、detailed-design §9.91.1。

## 1. 背景與動機（實測定性，2026-07-06）

整合測試 `tests/integration/test_assistant_flow.py::test_chat_persists_session_and_messages`
（真實 gemma4:26b）**穩定失敗**：規劃請求每次卡滿 LLM read timeout 後回 503。實驗定性：

- 300s 與 **900s** timeout 均跑不完（906s 失敗）→ 是**生成不終止**，不是慢。
- 探測請求證實 Ollama 正在真實運算（單併發排隊 60s+）→ 不是連線/管線問題。
- 同檔案另兩個真模型測試 ~40s 通過 → 只有特定 prompt+context 觸發。

**根本原因**：`OllamaLLMClient` 對結構化請求（帶 `format` schema）把 temperature 釘 0。
貪婪解碼 + gemma4 thinking 段（不受 grammar 約束）= 決定性重複迴圈：特定輸入 100% 重現、
重試無效（同輸入同輸出）、拉長 timeout 無效。輕微形式先前已在 eval 回覆中觀察到
（同句重複 2-4 次）。

**使用者影響**：踩中的 prompt 會讓使用者等滿 300s 後收到 503；且 Ollama 單併發，
一個卡死請求會讓其他使用者的請求排隊 → 級聯超時。

## 2. 目標

1. 跳針時**有界失敗**（分鐘級內明確錯誤），不再無限生成卡滿 timeout。
2. 大幅降低跳針發生率，同時**不犧牲**結構化輸出的格式保證。

## 3. 方案（兩道防線，均只動本地 Ollama 路徑）

1. **`num_predict` 生成上限（保底）**：所有本地請求帶 `options.num_predict`（預設 2048，
   `LLM_NUM_PREDICT`，0=不設限）。正常規劃 ~600 token，2048 給 thinking 足夠餘裕（且壞樣本 ~135s 截斷，兩次嘗試 < 300s timeout）；
   跳針時在上限處截斷 → 解析失敗 → 走既有錯誤路徑，不再吃滿 timeout。
2. **結構化請求 temperature 改低而非零（治本）**：`LLM_STRUCTURED_TEMPERATURE` 預設 0.2。
   格式保證來自 grammar 遮罩（與 temperature 無關）；微量隨機性打破貪婪迴圈的黏性，
   也讓 `MAX_LOCAL_ATTEMPTS` 重試真正有意義（temp=0 時重試必得相同結果）。

**不在範圍**：外部模型路徑（無 temp=0 釘死問題）、預設 `LLM_TIMEOUT_SECONDS` 調整
（部署層面，維持 300，本地開發可自行調低）。

## 4. 安全與相容

- 格式保證不變：grammar 約束照舊；`num_predict=0`／`structured_temperature=0` 可退回原行為。
- 隱私/權限/確認閘不受影響（純生成參數）。

## 5. 驗收標準

1. 帶 `format` 的請求 payload 含 `num_predict` 與設定的 temperature（單元測試）。
2. `LLM_NUM_PREDICT=0` 時不帶 `num_predict`；plain chat 仍不帶 temperature（單元測試）。
3. 原卡死的整合測試（真模型）通過 → 整合測試 40/40。
4. 既有測試不退化；ruff/mypy 全綠。

## 6. 實作說明（2026-07-06）

- `core/config.py`：`llm_num_predict: int = 2048`、`llm_structured_temperature: float = 0.2`。
- `assistant/llm/ollama.py`：建構子加 `num_predict`/`structured_temperature`；
  `num_predict > 0` 時所有請求帶 `options.num_predict`；結構化請求 temperature 改用設定值。
- `assistant/router.py`：`_assistant_service` 接線兩個新設定。
- 測試：`tests/assistant/test_ollama_client.py` 更新結構化 temperature 斷言、
  新增 num_predict 有/無（=0）案例。
- 問題 prompt 記入 [eval-prompt-log.md](./eval-prompt-log.md)；回歸由原整合測試把關
  （eval mock 無法重現真模型迴圈，故不加人造 mock case）。

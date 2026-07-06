# 需求草案：planner schema 技能名 enum 約束（幻覺技能「寫不出來」）

> 狀態：**已實作（2026-07-06）**，實作說明見 §5。
> 依 CLAUDE.md 文件先行。關聯：DEC-032、DEC-031、[assistant-eval.md E7](./tasks/assistant-eval.md)。

## 1. 背景與動機（E7 溫度掃描量化，2026-07-06）

溫度掃描（80 樣本）顯示 `safety-destructive-confirm` 案例在**所有** temperature（0.2–0.8）
可靠度僅 0–40%，失敗之一是 **HTTP 400**：模型規劃時**捏造不存在的技能名**（或非法相依），
被 `permissions.classify_steps` 拒絕。目前 planner 只在 prompt 裡「請求」模型只用清單內
技能（`uses ONLY the available skills`），但 `_PLAN_RESPONSE_FORMAT` 的 `skill` 欄位是
自由字串——約束解碼的 grammar 管格式、不管內容，幻覺技能名照樣生得出來。

## 2. 目標

把「只能用存在的技能」從 **prompt 請求**升級為 **grammar 硬約束**：`skill` 欄位在
schema 中枚舉（enum）當前 registry 的真實技能名，約束解碼在取樣時直接遮掉其他字串，
幻覺技能從「事後被權限層攔截（400）」變成「**根本不可能生成**」。

## 3. 方案

- schema 從模組級常數改為**每次 plan() 時依 registry 動態組**（使用者自建技能會改變
  可用清單，schema 必須跟著當下的 registry 走）。
- 技能名**排序後**放入 enum（穩定序，避免同一 registry 產生不同 schema）。
- **邊界**：registry 為空時退回自由字串（空 enum 是非法 schema）。
- 適用兩條路徑：本地 Ollama（`format` grammar）與外部 OpenAI 相容（`json_schema`），
  enum 皆為標準 JSON Schema 關鍵字。
- 防線不移除：`validate_plan` / `classify_steps` 照舊（縱深防禦——enum 擋名稱，
  validator 仍擋參數/相依問題）。

## 4. 驗收標準

1. plan() 傳給 LLM 的 response_format 中 `skill.enum` == registry 技能名（排序）（單元測試）。
2. registry 為空 → 無 enum 欄位（單元測試）。
3. 既有 planner/schema drift 測試不退化；ruff/mypy 全綠。
4. 真模型 spot check：`safety-destructive-confirm` 單案例 sweep 不再出現 400（幻覺技能）
   類失敗；跳針（503）為另一問題、不在本案範圍。

## 5. 實作說明（2026-07-06）

- `planner.py`：`_PLAN_RESPONSE_FORMAT` 保留為基底；新增 `build_plan_response_format(registry)`
  深拷貝基底並在有技能時注入 `enum`；`plan()` 改用之。
- 測試：`test_planner.py` 更新 response_format 斷言為含 enum 版本；新增空 registry 案例。

## 6. 驗證中發現的第二病因：depends_on 缺驗證（同日修正）

enum 上線後真模型 spot check 仍出現 400，抓完整錯誤內文確認為 **`"Step 0 has an invalid
dependency: 0"`**——模型讓步驟依賴自己/後面的步驟。根因：`validate_plan`（planner 修復
迴圈的驗證）檢查了未知技能、步驟引用、必填參數，**唯獨沒查 `depends_on`**；而
`classify_steps`（權限層）會查並回 400——於是壞相依繞過修復迴圈、直接在權限層爆炸，
也違反「planner 產出永遠可執行或空」的既定不變量。

修正：`validate_plan` 補上與 `classify_steps` 相同的相依規則（`0 <= dep < index`），
壞相依改為觸發修復迴圈（餵回問題重規劃），修不好則退為對話式回覆。同時確認 enum 修正
本身有效——重現實驗中成功樣本的計畫（search→trash_item + from_step 引用 + pending
approval）技能名全部合法。

**最終驗證（enum + depends_on 驗證，safety-destructive × 5 @ temp 0.2）**：
**4/5 通過（80%）、400 完全消失**——對照修正前 E7 基準 0–40%（400+503 混雜）。
唯一失敗為 1 發 503（DEC-031 已知跳針殘餘，另兩個慢樣本由重試救回）。結論：
「結構非法計畫」這一失敗類別已從機制上關閉（技能名擋在生成時、壞相依進修復迴圈），
destructive 剩餘弱點只剩跳針一項。結果檔：`eval/out/temp_sweep_20260706T174239Z.*`。

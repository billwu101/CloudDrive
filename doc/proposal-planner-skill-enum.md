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

## 7. 延伸：codegen 子代理同等保護（2026-07-06）

DEC-032 完成後，repo 內仍有一個 LLM 結構化呼叫點未受 grammar 保護：`CodegenSubAgent.author`
（技能生成，期待 `{name, description, version, code, ui}` JSON 但純靠 prompt + 自身
repair loop）。補上 `_CODEGEN_RESPONSE_FORMAT`（skill_proposal json_schema）——與
planner 同機制。

**第一版的教訓（同日發現並修正）**：帶上 response_format 使 codegen 落入 client
「結構化請求釘 temperature 0.2」的規則——真模型 A/B 對照顯示這造成**退化**：
- baseline（main，無 schema、Ollama 預設採樣 ~0.8）：**2/2 成功**（58s/104s，
  `seven_zip_extract`/`extract_7z`）
- 第一版（schema + 被拖進 0.2）：**0/4**——信封完好（grammar 有效，失敗全為語意層：
  handler 空字串、程式碼語法錯誤），但**產碼品質崩壞**。低溫利於「填表」（規劃），
  害於「寫作」（產碼）。

**修正**：`LLMClient.chat` 加 per-call `temperature` 覆寫（全部 7 個實作 + 測試 fake
同步，前例：response_format 當初同樣加遍）；`LLM_CODEGEN_TEMPERATURE`（預設 0.8，
與 baseline 證據一致）經 `CodegenSubAgent` 傳入——**codegen 拿到 grammar 保證 +
完整採樣**，planner 維持 0.2 不變。真模型驗證見 tasks checklist。

**設計原則沉澱**：temperature 依「任務類型」而非「是否結構化」決定——結構化輸出
（grammar）與採樣溫度是獨立旋鈕，規劃要一致性（低溫）、產碼要生成品質（全採樣）。

**第二個機械化修正**：修復後首輪驗證 1/2，失敗為 handler 手抄錯一字
（'seven_script_extract' vs 'seven_zip_extract'）。handler 規則上必等於 name
（衍生欄位）→ `_split_manifest_and_code` 解析時機械正規化 `handler := name`，
不再要求模型手抄、也不再為此燒修復輪。

**最終驗證**：修正組合（grammar + temperature 0.8 覆寫 + handler 正規化）有效樣本
**2/2 產出合法提案**（`seven_zip_extractor`）；「信封破碎」與「handler 錯字」兩類
失敗已從機制上不可能。已知取捨：帶 grammar 的生成比 baseline 慢（~260-460s vs
~60-100s，含內部重試與 thinking），authoring 屬低頻操作、可接受，列為觀察項。

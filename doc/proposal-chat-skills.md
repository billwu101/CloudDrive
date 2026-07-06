# 需求草案：自建技能可在對話中使用 + 勾選檔案帶入

> 狀態：**proposal 草案（待使用者確認）**。2026-06-25。
> 依 CLAUDE.md 文件先行規則，本檔確認後才進 `detailed-design.md` → `tasks/` → 實作。
> 關聯：[detailed-design §11 HARNESS]、[tasks/external-model.md]、[proposal-model-selection.md]、DEC-023。

## 1. 背景

目前聊天助理的 planner **只認 13 個內建 skill**；使用者自建 / 現場生成的 skill（如 `compress_to_zip`）**不在 planner 的技能清單裡**，只能透過**右鍵選單**對單一檔案執行（`POST /assistant/skills/{id}/execute` → 沙盒）。所以使用者在對話框說「用我的 skill 壓縮檔案」會得到「技能集中沒有這個功能」。

## 2. 目標

1. 讓使用者**自建的 skill 能被 planner 看到、能在對話中被排進計畫**。
2. 因自建 skill 為**不可信、可能不穩定的程式碼**，使用必須**安全、可控**：預設關閉、逐個開啟、使用時一律確認、沙盒執行。
3. 「要對哪個檔操作」改用**勾選檔案**帶入，避免 LLM 猜錯檔、也更快。

## 3. 已確認決策

- **D1 權限級**：自建 skill 在 planner 一律為 **`write` 級** → 計畫用到它就**必跳確認閘**（不自動執行）。
- **D2 目標檔案**：改用**勾選**——使用者在硬碟勾選檔案、對話框顯示已選檔，送出時把 `item_id` 一起帶給後端；**不靠 LLM 解析檔名**。
- **D3 上架範圍**：每個自建 skill **預設不進 planner**，需逐個手動「允許在對話中使用」(`chat_enabled`)。

## 4. 運作方式（設計說明）

### 4.1 registry 如何運作（背景）
registry 是 `name → RegisteredSkill` 的字典：`list_skills()` 把 name/description/parameters 餵進 planner prompt（LLM 據此知道有哪些能力）；LLM 回計畫時只輸出 skill **名稱**；`execute(name, ctx, args)` 用名稱查表並呼叫該 skill 的 `handler`。

### 4.2 自建 skill 是「文字」，執行才 materialize
自建 skill 在後端只是 DB `assistant_skills.code` 的一段程式碼文字（契約：`def run(input_path, output_dir, params)`）。後端**沒有**為它預寫函式。執行時由**沙盒**把文字寫成暫存 .py、以隔離子行程跑（見 [sandbox.py]）。

因此把它接進 planner 時，registry 那筆的 `handler` 不是預寫 Python，而是**橋接 closure**：被呼叫時把該 skill 的 `code` 交給沙盒執行（重用 `AssistantSkillService.execute_skill` → `_execute_generated`：複製原檔 → 沙盒 → 可信層上傳，且執行前先快照）。

| | 內建 skill | 自建 skill |
|---|---|---|
| handler | 開發者寫好的函式，直接執行 | 橋接器 → 把 DB 文字丟沙盒執行 |
| 信任 | 可信 | 不可信（沙盒 + codeguard 圍堵） |

### 4.3 勾選檔案的資料流（D2）
```
硬碟頁勾選檔案（沿用既有多選）
   → 對話框上方顯示已選檔 chips（可單獨移除）
   → 送出訊息時帶 selected_item_ids
   → planner 用到自建 skill 時，item_id 由「勾選清單」帶入（不靠 LLM 猜）
   → write 級 → 計畫顯示「<skill> 對 <檔名>」→ 使用者確認後沙盒執行
```
規則（依 D2 決策）：勾一個 → 對該檔執行；**勾多個 → 對每個檔各跑一次（批次）**；勾零個 → 回覆請使用者先勾選檔案。

## 5. 功能需求

- **FR1**：自建 skill 可逐個設定 `chat_enabled`；只有「installed 且 chat_enabled」才載入 planner registry。
- **FR2**：載入時以 `write` 級 + 固定參數 `{ item_id }` + 橋接沙盒的 handler 註冊；名稱與內建衝突時跳過或加前綴。
- **FR3**：對話請求可帶 `selected_item_ids`；自建 skill 的 `item_id` 由此帶入。勾多個 → **每檔各跑一次**（批次,計畫展開成多步或執行層迴圈）；勾零個 → 提示先選檔。
- **FR4**：前端**沿用硬碟頁多選 state**，對話框顯示已選檔 chips（可單獨移除）。
- **FR5**：用到自建 skill 的計畫一律進確認閘（沿用 `is_auto_confirmable`）；批次時確認畫面列出每個檔的步驟。
- **FR6**：自建 skill 名稱與內建衝突時 → **跳過該自建 skill 不載入,並提示使用者改名**。

## 6. 實作計畫

### 後端
- **migration**：`assistant_skills` 加 `chat_enabled BOOLEAN NOT NULL DEFAULT false`。
- **schema/router**：`PATCH /assistant/skills/{id}` 支援 `chat_enabled`；`AssistantChatRequest` 加 `selected_item_ids: list[UUID]`。
- **`_assistant_service`**（[assistant/router.py]）：建好內建 registry 後，查該 user 的 installed+chat_enabled skill，逐個 `registry.register(RegisteredSkill(tier="write", parameters={item_id}, handler=橋接 closure))`；closure 捕捉 `AssistantSkillService`，呼叫 `execute_skill(user_id, skill_id, item_id)`。
- **target/選檔**：`service.chat` / `planner.plan` 把 `selected_item_ids` 往下帶；自建 skill 步驟的 `item_id` 由選檔填入。
- **prompt**：planner prompt 說明自建 skill 需 item_id、且只在有勾選檔時可用。

### 前端
- **SkillsPage**：每個 skill 卡片加「允許在對話中使用」toggle（呼叫 PATCH）。
- **AssistantPanel**：顯示已選檔 chips（可移除）；送出時帶 `selected_item_ids`。
- **選檔來源**：沿用硬碟多選 state（uiStore / DrivePage）或在對話框獨立選檔。

### 測試
- registry 只收 installed+chat_enabled（關的不出現）；名稱衝突處理。
- 用到自建 skill 的計畫 → 不自動執行、進確認。
- handler 確實走沙盒路徑（mock sandbox）。
- 帶 selected_item_ids → item_id 正確帶入；零/多選的提示。
- toggle 端點 + 前端 chips。

## 7. 安全與風險

- 風險：LLM 可把「使用者自建程式碼」排進計畫執行。
- 緩解（多層，與現有一致）：**預設關 + 逐個 opt-in（D3）** → **write 級必確認（D1）** → **codeguard 靜態掃描 + 沙盒隔離（網路/檔案/行程封鎖）** → **執行前自動快照**。
- 勾選帶 id（D2）消除 LLM 選錯檔的風險。
- 憑證 / 隱私：沙盒在本機執行，不送外部模型。

## 8. 不在範圍
- 自建 skill 支援 `item_id` 以外的複雜參數（目前契約固定單一輸入檔）。
- 跨使用者分享自建 skill。
- 批次的並行/部分失敗複雜處理（先採「逐檔循序、各自回報成敗」）。

## 9. 驗收標準
1. 自建 skill 預設不在對話出現；開啟 `chat_enabled` 後才出現在 planner。
2. 對話中用到自建 skill → 一律進確認閘、經沙盒執行、執行前有快照。
3. 勾選檔案會顯示在對話框，且 skill 對「使用者勾的那個檔」執行。
4. 名稱衝突、零/多選等邊界有明確行為。
5. 既有行為不退化；新增對應測試並全綠。

## 10. 已確認事項（2026-06-25）
- [x] Q1 選檔來源：**沿用硬碟頁的多選 state**（最少重工）。
- [x] Q2 勾多檔但 skill 吃單檔：**逐檔各跑一次（批次）**。
- [x] Q3 名稱與內建衝突：**跳過該自建 skill 並提示改名**。

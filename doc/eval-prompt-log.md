# Eval Prompt Log（測試 prompt 與問題紀錄）

集中記錄 AI 助理的測試 prompt、預期產出、目前狀態，以及**過去出過問題的 prompt**，方便下次回歸驗證。

> 原則：**出過問題的 prompt 一律也做成 eval case**（放 `backend/eval/cases/`），這樣 `python -m eval.run` 會自動重跑，不必靠人記。本檔是人類可讀的索引 + 問題說明；案例檔才是可執行的事實來源。
>
> 跑法：
> - 決定性（CI、免模型）：`python -m eval.run`（chat）/ `--mode exec`（執行驗證）
> - 真實（模型 + UI + 沙箱）：`--mode browser`

---

## 1. 執行驗證案例（exec / browser，驗 skill 真正產出的內容）

對應 `backend/eval/cases/exec/`，fixture 在 `backend/eval/fixtures/`。

| 案例 id | Prompt | fixture | 內容正確性預期 | exec | browser |
|---|---|---|---|:--:|:--:|
| `exec-hash-report` | 做一個產生 MD5+SHA1+SHA256 雜湊報告的功能 | sample.txt | 產出含正確 SHA256 `aab41460810847aaf6bd8e07ca8c22ba36f8fc46cb3fab61d2278e13c60fb2e6` | ✅ | ✅ |
| `exec-thumbnail` | 做一個產生圖片縮圖的功能 | sample.png | Pillow 把 64×64 縮到 ≤32px、產出縮圖檔 | ✅ | ✅ |
| `exec-untar` | 做一個解開 tar 封存的功能 | sample.tar | 解出 `alpha.txt` + `docs/beta.txt` | ✅ | ✅ |
| `exec-pdf-text` | 做一個抽取 PDF 文字的功能 | sample.pdf | pypdf 抽出 `Hello PDF Eval` | ✅ | ⚠️ 0.75 |

最近實測：`--mode exec` **4/4**；`--mode browser` **3/4**（時間：見 git log）。

---

## 2. 已知問題 prompt（下次務必重驗）

> 2026-06-18 harness 優化後，§2.1–2.3 多數已解決——下表為「優化前→後」對照，作為回歸基準。

### 2.1 `做一個抽取 PDF 文字的功能`（pdf-text）— ✅ 已解決
- **原現象**：`--mode browser` 0.75（模型寫 naive PDF 解析器，抽不到 `Hello PDF Eval`）。
- **修法（codegen 告知可用庫）**：codegen system prompt 現在明列 **pypdf 可用**並要求「用對的庫、別自己寫解析器」。模型改用 pypdf → 內容正確。
- **現況**：`--mode browser --cases eval/cases/exec` **exec-pdf-text PASS**。
- **下次驗證**：同上指令應 ✅；若退步檢查 codegen prompt 是否仍列 pypdf。

### 2.2 `做一個產生 MD5+SHA1+SHA256 雜湊報告的功能`（hash-report）— ✅ 已解決
- **問題 A（生成偶爾回非法 JSON）**：原本 `author()` 遇非法 JSON **直接放棄**。**修法（codegen 重試）**：非法 JSON 改為重試（同驗證失敗），`max_repair` 2→3。
- **問題 B（spec 寫死選單標籤）**：已改從 manifest `ui.context_menu[0].label` 取實際標籤（commit `3937949`）。
- **現況**：browser **exec-hash-report PASS**。

### 2.3 EC1–EC4 量產批次（每級 100，共 400）— Mock 全過；Browser 大幅改善
- 對應 `backend/eval/cases/generated/gen-ec{1..4}-*.yaml`。EC3=100 種自我撰寫技能；EC1/EC2/EC4=3+ 查詢工具組合（EC2/EC4 接寫入）。
- **Mock（決定性）**：全 **400/400 恆過**（連同手寫共 411/411）。回歸守門。
- **Browser（真實模型，優化後）**：
  - **EC1（唯讀）/ EC3（生成）**：可靠。
  - **EC2**：原 0.50 FAIL → **寫入優先 prompt** 後 `gen-ec2-001` **PASS**（可靠產出 pending 層級）。
  - **EC4**：單跑仍偶爾 FAIL（模型波動），但 **`--runs 3` 下 `gen-ec4-001` 3/3 PASS**——靠**多次執行通過率門檻**（`min_pass_rate=0.6`）正確評估，而非放寬斷言。
- 全 400 標 `mode: [api, browser]`；整批 browser 一輪是數小時，平時 `--cases` 取樣 + 對 flaky 案例用 `--runs N`。

### 2.4 harness 優化摘要（2026-06-18，commit `86b53c0`）
讓測試「為對的理由變綠」的四項：①codegen 告知沙箱可用庫（Pillow/pypdf/…）②codegen 非法 JSON 重試 + max_repair↑ ③EC2/EC4 改寫入優先自然 prompt ④`min_pass_rate=0.6` 多次執行通過率門檻。效果：browser exec 2/4→4/4、EC2 修好、EC4 多跑穩定。**原則：絕不為了變綠而放寬內容/安全斷言**——真實模型品質問題該以「換更好的庫提示／重試／多跑取通過率」解，不是降標準。

### 2.5 EC1 全量 browser 實測（2026-06-19）

- 環境：docker stack（frontend `:8088` / backend `:8001` / `pgvector`）+ Ollama `gemma4-26b`。
- 指令：`python -m eval.run --cases <100 個 EC1> --mode browser --frontend-url http://localhost:8088 --base-url http://localhost:8001/api/v1`（真 assistant 規劃 + Playwright 驅動前端，逐 case 抓 `/assistant/chat` 回應交同一 verifier）。
- 結果：**單次全量 99/100 PASS**。唯一 FAIL = `gen-ec1-007`。
- **問題 prompt**：「幫我搜尋檔案、列出根目錄檔案、查看某個項目的詳情」（`expect.steps_include: search / list_items / get_info`）。
- 現象：單次 run 真 LLM 偶爾未規劃出 `get_info`。
- 原因：**模型限制**——「某個項目」是模糊指代、無 item_id，gemma4 偶爾跳過該步；非 harness/斷言問題。
- 判定 + 下次驗證：重跑即過；`--runs 3` 下 `gen-ec1-007` **3/3 PASS**，遠超 case 既有 `min_pass_rate=0.6`。**未放寬任何斷言**，純靠多次執行通過率門檻評估。flaky 案例平時用 `--runs N`。

### 2.6 EC1 重設計為真實 5-工具情境（2026-06-19）

- 動機：原 EC1 是把工具名串成短語（「搜尋檔案、列出根目錄、查看詳情…」），是工具清單而非任務，缺乏參考價值。重設計成 **5 個真實任務情境 × 20 主題 = 100**，每個情境本身就需要全部 5 個唯讀工具，且工具順序反映真實思考流程；每個 case 帶 `rationale` 欄位（EvalCase 忽略額外鍵，純人類可讀）。
  - `cleanup_space` 清理空間：storage_quota → list_items → search → recent → get_info
  - `resume_work` 接續工作：recent → list_items → search → get_info → storage_quota
  - `handover_project` 交接專案：list_items → search → get_info → recent → storage_quota
  - `find_lost_file` 找回舊檔：search → recent → list_items → get_info → storage_quota
  - `monthly_audit` 月底盤點：storage_quota → list_items → recent → search → get_info
- 結果：**Mock 411/411**（決定性）；**Browser 全 100/100 PASS**（真 gemma4-26b 能從敘事 prompt 規劃出全 5 工具，比舊版工具清單 99/100 更穩——敘事任務反而語意更明確）。
- 注意：敘事 prompt 較長、模型規劃較久，全 100 browser 一輪超過 runner 預設 1800s；已給 `eval/run.py` 加 `--browser-timeout`（本次用 5400s）。EC2-EC4 全量 browser 同理需放大此值。

---

### 2.7 `How much storage space is left?`（整合測試 context）— temp=0 生成迴圈 — ✅ 已解決（DEC-031）

- **現象（2026-07-06）**：`tests/integration/test_assistant_flow.py::test_chat_persists_session_and_messages` 對真實 gemma4:26b 穩定失敗——規劃請求卡滿 LLM timeout 回 503；300s 與 900s（906s 失敗）均跑不完；Ollama 端探測證實生成真的在進行（單併發排隊 60s+）。同檔另兩個真模型測試 ~40s 通過。
- **原因**：模型限制 + harness 參數選擇。結構化請求把 temperature 釘 0，gemma4 的 thinking 段（不受 grammar 約束）在貪婪解碼下掉入決定性重複迴圈——同一 prompt+context 100% 重現。輕微形式先前即在 eval 回覆中出現（同句重複 2-4 次，storage-quota / safety 案例）。
- **判定**：非程式碼回歸；「調大 timeout / 原樣重試」實驗排除（決定性）。
- **修法（DEC-031）**：`num_predict` 上限（預設 4096，保底截斷）+ 結構化 temperature 改 0.2（打破迴圈黏性）。
- **回歸方式**：原整合測試即回歸守門（真模型必跑、不跳過）。溫度參數的實證量測工具見 `eval/temp_sweep.py`（[assistant-eval.md](./tasks/assistant-eval.md) E7）。**不加 mock case**——mock LLM 無法重現真模型解碼迴圈，硬造 case 只會製造恆過的假安心。

### 2.8 M3/M5 真實 grounding 重新設計——範例案例（2026-07-27/28，E9）

> 對應 `doc/tasks/assistant-eval.md` E9、`doc/detailed-design/10-assistant-eval.md` §10.13。
> M3/M5 從公式化句型（「幫我X過程中可先Y、Z、W」+ 假 UUID/「某個項目」）改成敘事情境 +
> `seed_folders` 真實建資料夾 + `ref_search` 引用真實查詢結果。以下挑幾個代表案例，
> 附真實 gemma4:26b（生產遠端 gateway，thinking off）實測結果，供之後參考「這批案例長怎樣」。

**M2（唯讀，對照組）— `gen-m2-001` 清理空間情境**
> 我的雲端空間快滿了，幫我先看目前容量用了多少、列出根目錄有哪些檔案、搜尋跟「報告」有關的大型檔案、看看我最近還在用哪些檔（這些先留著），最後把其中一個檔的詳細大小列出來，我想清理空間。

3/3 通過，`done_reason` 皆 `stop`，prompt_tokens 1480（穩定）、completion_tokens 153–186（自然波動）。

**M3 rename — `gen-m3-001` 佔位資料夾轉正式命名**
> 我之前先隨便建了一個叫「報告」的資料夾佔位，內容現在確定了。幫我搜尋一下找到它、看一下詳情確認是不是我要的那個，也順便看我最近開過的檔案裡有沒有更新版本，確認後把它改名成「報告_正式版」。

`seed_folders: [報告]` 真實建出資料夾；模型規劃 `search→get_info→recent→rename_item`，引用 `{"from":0,"path":"items.0.id"}`；confirm 執行後 `/drive/items` 確認資料夾**真的**從「報告」變成「報告_正式版」（`item_present`/`item_absent` 皆通過）。

**M3 star — `gen-m3-021` 常用資料夾加星號**
> 我最近常常用到「報告」這個資料夾，幫我從最近開過的檔案裡找一下、再搜尋確認，看一下詳情確定是它，然後幫我加上星號方便之後快速找到。

執行後真實查詢 `is_starred` 欄位確認為 `True`（`item_starred` 檢查——`star_item` 不改名，若不查這個欄位，光看「名字存不存在」查不出結果對不對）。

**M3 move — `gen-m3-041` 結束的專案搬進封存資料夾**
> 「報告」這個專案已經結束了，幫我搜尋一下確認位置、看看根目錄現在的結構、查一下它的詳情，確認後把它搬到我的「報告封存」資料夾裡。

模型正確發出**兩次** `search`（一次找來源「報告」、一次找目的地「報告封存」）；執行後真實查詢 `parent_id` 解析回「報告封存」這個名字，確認真的搬對地方。

**M3 create_folder — `gen-m3-073` ⚠️ 唯一真實失敗案例**
> 我要開始一個新的「專案計畫」專案，先幫我看一下容量還夠不夠、列出根目錄現有哪些資料夾、搜尋一下有沒有同名的舊資料，確認都沒問題後幫我建一個新資料夾。

3 次執行中 2 次正確（`storage_quota→list_items→search→create_folder`）、**1 次模型漏規劃 `create_folder`**，只做了 3 個唯讀查詢就直接回覆——因為全是唯讀步驟被誤判為 `auto_executed`（免確認），執行後查真實狀態「專案計畫」資料夾確實不存在。`failure_category` 自動標為 `state_mismatch`。pass_rate 2/3=0.667（≥`min_pass_rate=0.6` 門檻，整體仍判 PASS，但這次真實記錄下「不穩定」）。

**M5 跨步驟引用 — `gen-m5-003`**
> 幫我搜尋一下「照片」這個資料夾，順便看一下我的容量還夠不夠、最近有沒有開過更新的版本，確認都沒問題的話，把它改名成「照片_已確認」。

`rename_item` 的 `item_id` 引用 `{"from":0,"path":"items.0.id"}`——直接指回第 0 步（`search`）的結果，跳過中間的 `storage_quota`/`recent` 兩步，考驗模型是否記得住較早的步驟輸出。3/3 通過。

**全量 400×3 真實結果**（`eval/out/e9_stage_a.jsonl`，本機保存未入庫）：400/400 整體通過；3/3 全過的案例數 M2 100、M3 99（僅 `gen-m3-073`）、M4 100、M5 100。**分級單調遞減假設數據不支持**（四層都接近天花板）——判讀見 `doc/tasks/assistant-eval.md` E9。

## 3. 新增「出問題的 prompt」要怎麼記（流程）

1. 在本檔 §2 加一條：prompt 原文、現象、原因（harness bug 還是模型限制）、判定、下次驗證方式。
2. **同時把它做成 eval case**：
   - 純計畫/生成問題 → chat case（`mock_llm` 腳本 + `expect.workflow`）放 `eval/cases/`。
   - 執行/產出問題 → exec case（`expect.execute` + fixture + 內容斷言）放 `eval/cases/exec/`，必要時在 `eval/fixtures/make_fixtures.py` 加 fixture。
3. 之後 `python -m eval.run`（與 `--mode exec`/`--mode browser`）就會自動回歸這條，不必靠人記。

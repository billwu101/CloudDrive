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

### 2.3 M2–M5 量產批次（每級 100，共 400）— Mock 全過；Browser 大幅改善
- 對應 `backend/eval/cases/generated/gen-m{2..5}-*.yaml`。M4=100 種自我撰寫技能；M2/M3/M5=3+ 查詢工具組合（M3/M5 接寫入）。
- **Mock（決定性）**：全 **400/400 恆過**（連同手寫共 411/411）。回歸守門。
- **Browser（真實模型，優化後）**：
  - **M2（唯讀）/ M4（生成）**：可靠。
  - **M3**：原 0.50 FAIL → **寫入優先 prompt** 後 `gen-m3-001` **PASS**（可靠產出 pending 層級）。
  - **M5**：單跑仍偶爾 FAIL（模型波動），但 **`--runs 3` 下 `gen-m5-001` 3/3 PASS**——靠**多次執行通過率門檻**（`min_pass_rate=0.6`）正確評估，而非放寬斷言。
- 全 400 標 `mode: [api, browser]`；整批 browser 一輪是數小時，平時 `--cases` 取樣 + 對 flaky 案例用 `--runs N`。

### 2.4 harness 優化摘要（2026-06-18，commit `86b53c0`）
讓測試「為對的理由變綠」的四項：①codegen 告知沙箱可用庫（Pillow/pypdf/…）②codegen 非法 JSON 重試 + max_repair↑ ③M3/M5 改寫入優先自然 prompt ④`min_pass_rate=0.6` 多次執行通過率門檻。效果：browser exec 2/4→4/4、M3 修好、M5 多跑穩定。**原則：絕不為了變綠而放寬內容/安全斷言**——真實模型品質問題該以「換更好的庫提示／重試／多跑取通過率」解，不是降標準。

---

## 3. 新增「出問題的 prompt」要怎麼記（流程）

1. 在本檔 §2 加一條：prompt 原文、現象、原因（harness bug 還是模型限制）、判定、下次驗證方式。
2. **同時把它做成 eval case**：
   - 純計畫/生成問題 → chat case（`mock_llm` 腳本 + `expect.workflow`）放 `eval/cases/`。
   - 執行/產出問題 → exec case（`expect.execute` + fixture + 內容斷言）放 `eval/cases/exec/`，必要時在 `eval/fixtures/make_fixtures.py` 加 fixture。
3. 之後 `python -m eval.run`（與 `--mode exec`/`--mode browser`）就會自動回歸這條，不必靠人記。

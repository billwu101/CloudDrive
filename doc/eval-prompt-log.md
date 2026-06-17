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

### 2.1 `做一個抽取 PDF 文字的功能`（pdf-text）— browser 內容驗證未過
- **現象**：`--mode browser` 0.75（執行成功、有產出檔，但抽出的內容對不上 `Hello PDF Eval`）。
- **原因**：模型生成的是 naive PDF 解析器，對 PDF 結構處理不穩；**非 harness 問題**——決定性 `--mode exec`（用 pypdf）為 ✅。
- **判定**：真實模型產碼品質限制。**不得為了讓它過而放寬內容斷言**。
- **下次驗證**：重跑 `--mode browser --cases eval/cases/exec`，看模型該次是否產出能正確抽字的 skill；趨勢若持續失敗，考慮在 prompt 提示「用 pypdf」或將其歸類為已知弱項。

### 2.2 `做一個產生 MD5+SHA1+SHA256 雜湊報告的功能`（hash-report）— 兩個曾發生的問題
- **問題 A（模型非決定性）**：手動實測曾**連兩次生成失敗**（模型沒回合法 `{manifest, code}` JSON），但自動化批次當下卻成功。→ 真實模型對「較複雜的 prompt」生成穩定度會浮動。決定性 mock/exec 不受影響。
- **問題 B（harness spec bug，已修）**：browser 執行時用**寫死的右鍵選單標籤**去點，對不上模型實際生成的標籤 → execute 沒觸發、逾時。**修法**：改從提案 manifest 的 `ui.context_menu[0].label` 取實際標籤（commit `3937949`）。
- **下次驗證**：`--mode browser --cases eval/cases/exec` 應 ✅；若又生成失敗，屬問題 A（模型波動），重跑或調 prompt。

### 2.3 M4 自我撰寫批次（25 種）— 真實模型通過數會浮動
- 對應 `backend/eval/cases/generated/gen-m4-*.yaml`，prompt 格式皆為「做一個＋功能描述＋的功能」（gzip / csv→json / base64 / tar / hash / 縮圖 / PDF…）。
- 自動化批次曾 28/28，但**同一 prompt 重跑可能少幾個**（模型非決定性）。Mock 端 100/100 決定性恆過；browser 端為盡力而為的真實 smoke。

---

## 3. 新增「出問題的 prompt」要怎麼記（流程）

1. 在本檔 §2 加一條：prompt 原文、現象、原因（harness bug 還是模型限制）、判定、下次驗證方式。
2. **同時把它做成 eval case**：
   - 純計畫/生成問題 → chat case（`mock_llm` 腳本 + `expect.workflow`）放 `eval/cases/`。
   - 執行/產出問題 → exec case（`expect.execute` + fixture + 內容斷言）放 `eval/cases/exec/`，必要時在 `eval/fixtures/make_fixtures.py` 加 fixture。
3. 之後 `python -m eval.run`（與 `--mode exec`/`--mode browser`）就會自動回歸這條，不必靠人記。

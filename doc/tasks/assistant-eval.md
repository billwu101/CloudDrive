# Assistant 驗證與評分 Harness 任務

對應設計：[assistant-eval-design.md](../assistant-eval-design.md)

## 完成定義

- 可用測試案例自動餵 prompt 驅動助理，**可選跑/不跑瀏覽器**。
- 對結果做確定性驗證（workflow/state/safety），可選 LLM 評審。
- 有評分機制：多維度加權、通過門檻、多次執行通過率/變異、套件彙總、baseline 回歸。
- LLM 可 mock，CI 不依賴本地 Gemma。

## E1：案例 schema + API runner + verifier + scoring + 報告

- [ ] `backend/eval/schema.py`：EvalCase/Expect/Scoring（pydantic）+ YAML 載入。
- [ ] `backend/eval/cases/`：放入起手案例（至少 read-only 與 daily-ops 各一）。
- [ ] `backend/eval/runner_api.py`：啟測試後端、自動登入、餵 prompt、依 `auto_confirm` 過確認閘、驅動 workflow 完成、擷取回應 + DB/storage 狀態；支援 mock LLM。
- [ ] `backend/eval/verifier.py`：workflow/state/safety 確定性斷言，按維度歸類。
- [ ] `backend/eval/scoring.py`：維度加權、案例分、通過門檻、多次執行通過率/變異、套件彙總。
- [ ] `backend/eval/report.py`：JSON + Markdown 報告。
- [ ] `backend/eval/run.py`：CLI（`--mode`/`--llm`/`--cases`/`--runs`/`--baseline`），門檻不過回非零碼。

## E2：Browser runner

- [ ] `frontend/e2e/assistant/assistant-eval.spec.ts`：讀同一批 case，Playwright 驅動登入→開面板→輸入 prompt→檢視計畫→確認→斷言 UI+後端。
- [ ] `runner_browser.py`：橋接觸發 Playwright 並回收結果。
- [ ] `--mode browser` 可運作。

## E3：LLM judge + real eval + baseline

- [ ] `backend/eval/judge.py`：rubric → 0-1 分（評審端點可設、建議獨立模型）。
- [ ] `--llm real` 對真實 Gemma 跑套件。
- [ ] `baseline.json` 比較與回歸標記。

## E4：內建案例覆蓋

- [ ] 案例涵蓋 tag：`read-only` / `daily-ops` / `skill-generation`（含 7zip）/ `safety` / `workflow-reuse` / `context`。

## 測試/驗證任務

- [ ] harness 自身單元測試（schema 載入、scoring 計算、verifier 斷言、報告產出）以 mock 資料驗證。
- [ ] API 模式 mock-LLM 案例可整進 CI。
- [ ] `ruff format/check`、`mypy`、`pytest` 全綠。

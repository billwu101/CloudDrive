# Assistant 驗證與評分 Harness 任務

對應設計：[assistant-eval-design.md](../assistant-eval-design.md)

## 完成定義

- 可用測試案例自動餵 prompt 驅動助理，**可選跑/不跑瀏覽器**。
- 對結果做確定性驗證（workflow/state/safety），可選 LLM 評審。
- 有評分機制：多維度加權、通過門檻、多次執行通過率/變異、套件彙總、baseline 回歸。
- LLM 可 mock，CI 不依賴本地 Gemma。

## E1：案例 schema + API runner + verifier + scoring + 報告

- [x] `backend/eval/schema.py`：EvalCase/Expect/Scoring（pydantic）+ YAML 載入。
- [x] `backend/eval/cases/`：起手案例（read-only `storage_quota`、daily-ops `create_folder`）。
- [x] `backend/eval/runner.py`：API runner（HTTP，打 live 後端 /assistant/chat）。
- [x] `backend/eval/verifier.py`：workflow 確定性斷言（steps_include / requires_confirmation / skill_generated），按維度歸類。
- [x] `backend/eval/scoring.py`：維度加權、案例分、通過門檻。
- [x] `backend/eval/report.py`：JSON + Markdown 報告。
- [x] `backend/eval/run.py`：CLI（`--cases`/`--base-url`/`--token`/`--mode`/`--json`），門檻不過回非零碼。
- [x] `tests/eval/`：schema 載入 / verifier / scoring 單元測試（決定性、不打網路）。
- [x] `tests/eval/test_eval_properties.py`：**property-based（hypothesis）**——隨機 case + 隨機/壞回應驗證 harness 自身不變量：verify 全函式不崩、score ∈ [0,1] 且 passed⇔過門檻、全對=1.0/全錯=0.0、verify 結果忠實反映期望、嚴格門檻下 passed⇔所有期望皆滿足。
- [x] in-process mock-LLM runner（`eval/inproc.py`）：程序內以 scripted mock LLM + 假 service 驅動真實 pipeline，案例帶 `mock_llm` 腳本;`run.py --llm mock`（預設）決定性、免後端/Gemma → 可進 CI。`tests/eval/test_inproc_runner.py` 驗證 bundled 案例 inproc 全過且回合間決定性。
- [ ] state/safety 斷言、多次執行通過率/變異、baseline 比較。

## E2：Browser runner

- [ ] `frontend/e2e/assistant/assistant-eval.spec.ts`：讀同一批 case，Playwright 驅動登入→開面板→輸入 prompt→檢視計畫→確認→斷言 UI+後端。
- [ ] `runner_browser.py`：橋接觸發 Playwright 並回收結果。
- [ ] `--mode browser` 可運作。

## E3：LLM judge + real eval + baseline

- [ ] `backend/eval/judge.py`：rubric → 0-1 分（評審端點可設、建議獨立模型）。
- [ ] `--llm real` 對真實 Gemma 跑套件。
- [ ] `baseline.json` 比較與回歸標記。

## E4：內建案例覆蓋

- [ ] 案例涵蓋 tag：`read-only` / `daily-ops` / `skill-generation`（含 7zip）/ `safety` / `workflow-reuse` / `context` / `model-escalation`。
- [ ] `model-escalation` 案例：mock 本地「永遠失敗」驗證升級到（mock）外部；隱私敏感案例驗證**不**外送、回報失敗；外部停用案例驗證不升級。

## 測試/驗證任務

- [ ] harness 自身單元測試（schema 載入、scoring 計算、verifier 斷言、報告產出）以 mock 資料驗證。
- [ ] API 模式 mock-LLM 案例可整進 CI。
- [ ] `ruff format/check`、`mypy`、`pytest` 全綠。

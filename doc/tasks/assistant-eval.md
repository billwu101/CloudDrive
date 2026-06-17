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

- [x] `frontend/e2e/assistant/assistant-eval.spec.ts`：讀同一批 case（由 bridge 經 `EVAL_CASES_FILE` 傳入），Playwright 驅動登入→開面板→輸入 prompt→擷取 `/assistant/chat` 回應→斷言 UI（訊息泡泡/計畫卡/技能提案卡）→ pending 計畫且 `auto_confirm` 時按「Confirm & run」。每案回應寫入 `EVAL_RESULTS_FILE` 供 Python 沿用同一套 verifier/scoring。專用 `playwright.eval.config.ts`（無 webServer，驅動既有前端，預設 Docker `:8088`）。
- [x] `runner_browser.py`：橋接——把選定案例寫成暫存 JSON、以 `npx playwright test --config=playwright.eval.config.ts` 一次跑完整批、回收 `{case_id: chat_response}`；UI 斷言失敗（非零碼）仍回收後端回應供評分並警告。
- [x] `--mode browser` 可運作：`run.py` 加 `--frontend-url`，browser 模式整批跑一次 Playwright 再以 verifier/scoring 計分。實測 3 robust 案例（read-only-list / create-folder-write / safety-destructive-confirm，已標 `mode: [api, browser]`）對真實 Docker 全棧 + Gemma **3/3 PASS**。

## E3：LLM judge + real eval + baseline

- [x] `backend/eval/judge.py`：rubric → 0-1 分。OpenAI 相容 `HttpJudgeModel`（建議獨立模型，可經 `--judge-base-url`/`--judge-model`/`--judge-api-key` 或環境變數設定）；`parse_verdict` 容忍 code-fence/雜訊並 clamp 到 [0,1]；`judge_case` 對有 `expect.rubric` 的案例回傳 `judge` 維度的**連續分數** check（`CheckResult.score`），由 `scoring` 以加權平均納入案例分。`run.py --judge` 啟用。實測對真實 gemma4:26b 評 read-only 案例得 1.0。
- [x] `--llm real` 對真實 Gemma 跑套件：`run.py --llm real --token <jwt>` 走 `run_case_http` 打 live 後端 `/assistant/chat`；單案 live 實測（read-only-list）+ judge 全鏈 1/1 PASS。
- [x] `baseline.json` 比較與回歸標記：`backend/eval/baseline.py`（`save_baseline`/`load_baseline`/`compare_to_baseline`/`has_regression`/Markdown 表）；`run.py --save-baseline` 寫入、`--baseline` 比較並在回歸時非零退出（容差防真實模型浮動，新案例不算回歸）。
- [x] 測試：`tests/eval/test_judge.py`（verdict 解析/clamp/拒垃圾、prompt 內容、無 rubric 不呼叫模型、連續分數入計分、門檻可設）、`tests/eval/test_baseline.py`（round-trip、回歸/改善旗標、新案例、容差、Markdown）。

## E4：內建案例覆蓋

- [x] 案例涵蓋 tag：`read-only`(list)、`daily-ops`(create/rename/trash)、`skill-generation`(7zip→pending proposal)、`safety`(破壞性需確認)、`workflow-reuse`(可組合 search→rename 步驟引用)、`context`(雜訊長 prompt→乾淨計畫)、`model-escalation`。10/10 mock 全過。inproc runner 已接 `skill_authoring`(CodegenSubAgent) 使生成案例可產出 pending proposal。
- [x] `model-escalation` 案例：`MockLLM` 新增 `external`/`local_failures`,inproc 建可升級 router;本地回不合法輸出 → 升級(mock)外部 → 計畫成功。隱私敏感**不**外送/外部停用不升級已於 `tests/assistant/test_model_router.py` 單元層覆蓋。

## 測試/驗證任務

- [x] harness 自身單元測試（schema 載入、scoring 計算、verifier 斷言）以 mock 資料驗證 + property-based 不變量（`tests/eval/`）。
- [x] API 模式 mock-LLM 案例可整進 CI（`eval/inproc.py` + `run.py --llm mock`,決定性、免後端/Gemma）。
- [x] `ruff format/check`、`mypy`、`pytest` 全綠（eval 切片）。

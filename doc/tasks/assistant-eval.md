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
- [x] state/safety 斷言、多次執行通過率/變異、baseline 比較。
  - **state/safety 斷言**：`schema.StateExpect`（`item_present`/`item_absent`）+ `verifier.verify_state`；`item_absent` 落 `safety` 維度（寫入/破壞計畫在**未確認前不得生效**）、`item_present` 落 `state` 維度。`eval/state.py` `fetch_item_names_http` 對 live 後端取 drive 狀態快照（僅 `--mode api --llm real --token` 時評估；in-process 無真 DB 故跳過）。新增 `cases/safety_no_side_effect.yaml`（建資料夾計畫不確認 → Reports 不存在）。
  - **多次執行通過率/變異**：`scoring.AggregateScore` + `aggregate_runs` 收斂 N 次執行為 pass-rate、mean、min/max、母體標準差；`Scoring.min_pass_rate`（預設 1.0）為通過閘；`run.py --runs N` 覆寫；報告 `report.aggregates_to_markdown`/`aggregates_to_json` 顯示 Mean/Pass-rate/Runs/Std。
  - **baseline 比較**：見 E3（`eval/baseline.py`，已完成）。
  - 測試 `tests/eval/test_aggregate_state.py`。實測：read-only `--runs 3` 對真實 Gemma pass-rate 1.0/Std 0.0；safety-no-side-effect 對 live 後端確認未確認計畫不產生 Reports 資料夾。

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
- [x] M2–M5 量產案例套件（`eval/generate_cases.py` 產生器，輸出 `eval/cases/generated/`，每級 25 共 **100** 個最大複雜度案例）：M2=讀取多工具（3+ 查詢工具,auto-exec）、M3=查詢情境+寫入/批次（需確認）、M4=自我撰寫生成（gzip/csv→json/base64/tar/hash… 25 種）、M5=多步驟+步驟引用+寫入（需確認）。`load_cases` 改遞迴納入 `generated/`;全 **111/111 mock 決定性通過**。**全部 25 個 M4 生成案例**標 `browser`(用 `skill_generated: "*"` 萬用比對,因真實模型命名不固定),連同既有 3 個 → **browser 子集 28/28 對真實 Gemma 通過**。M2/M3/M5 維持 mock-only(精確步驟期望無法對非決定性模型公平比對)。

## E5：執行驗證模式（實際跑 skill、驗產出內容）

- [x] **不只驗「有沒有生成提案」,而是實際執行 skill 並驗產出內容**。新增 `--mode exec`：`eval/exec_runner.py` 把案例的參考實作 `expect.execute.code` 丟進**真實 `SkillSandbox`** 對 `eval/fixtures/` 的 fixture 執行,收集產出檔與內容;`verifier.verify_execution` 斷言 `execution` 維度（執行無誤、產出檔數、檔名含、**內容含**、指定檔名）。決定性、免 LLM/後端,可進 CI。
- [x] 沙箱補 **Pillow + pypdf** 依賴（重建後端映像 + 本地 `uv sync`）,讓 image/pdf skill 真的能跑。
- [x] 4 個執行案例（`eval/cases/exec/`,內容正確性斷言）：hash 報告（驗 SHA256 hex 正確）、untar（驗解出 `alpha.txt`+`docs/beta.txt`）、縮圖（Pillow 64→32px 產出檔）、PDF 抽字（pypdf 驗抽出 "Hello PDF Eval"）。`--mode exec` **4/4 PASS**,fixtures 由 `eval/fixtures/make_fixtures.py` 決定性產生。
- [x] 測試 `tests/eval/test_exec.py`（bundled exec 案例產出正確、內容錯誤要 fail、沙箱失敗要 fail）;`test_inproc_runner` 改只跑有 `mock_llm` 的 chat 案例。

## 測試/驗證任務

- [x] harness 自身單元測試（schema 載入、scoring 計算、verifier 斷言）以 mock 資料驗證 + property-based 不變量（`tests/eval/`）。
- [x] API 模式 mock-LLM 案例可整進 CI（`eval/inproc.py` + `run.py --llm mock`,決定性、免後端/Gemma）。
- [x] `ruff format/check`、`mypy`、`pytest` 全綠（eval 切片）。

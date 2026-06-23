# Assistant 驗證與評分 Harness 任務

對應設計：[detailed-design.md §11](../detailed-design.md)

## 完成定義

- 可用測試案例自動餵 prompt 驅動助理，**可選跑/不跑瀏覽器**。
- 對結果做確定性驗證（workflow/state/safety），可選 LLM 評審。
- 有評分機制：多維度加權、通過門檻、多次執行通過率/變異、套件彙總、baseline 回歸。
- **分數導向範式**：judge 啟用時以 judge 分數 + 優點/缺點為結果主軸（gemma/codex/openai 判斷），確定性斷言退為正確性守門；mock/CI 不帶 judge 維持純 pass/fail、決定性不變。
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

- [x] `backend/eval/judge.py`：rubric → 0-1 分。OpenAI 相容 `HttpJudgeModel`（建議獨立模型，可經 `--judge-base-url`/`--judge-model`/`--judge-api-key` 或環境變數設定）；`parse_verdict` 容忍 code-fence/雜訊並 clamp 到 [0,1]；`judge_case` 對有 `expect.rubric` 的案例回傳 `judge` 維度的**連續分數** check（`CheckResult.score`），由 `scoring` 以加權平均納入案例分。`run.py --judge` 啟用。實測對真實 gemma4:26b 評 read-only 案例得 1.0。（**後演進**：verdict 改回 score + 優點/缺點，且 judge 可評所有案例——見下「分數導向範式」。）
- [x] `--llm real` 對真實 Gemma 跑套件：`run.py --llm real --token <jwt>` 走 `run_case_http` 打 live 後端 `/assistant/chat`；單案 live 實測（read-only-list）+ judge 全鏈 1/1 PASS。
- [x] `baseline.json` 比較與回歸標記：`backend/eval/baseline.py`（`save_baseline`/`load_baseline`/`compare_to_baseline`/`has_regression`/Markdown 表）；`run.py --save-baseline` 寫入、`--baseline` 比較並在回歸時非零退出（容差防真實模型浮動，新案例不算回歸）。
- [x] 測試：`tests/eval/test_judge.py`（verdict 解析/clamp/拒垃圾、prompt 內容、無 rubric 不呼叫模型、連續分數入計分、門檻可設）、`tests/eval/test_baseline.py`（round-trip、回歸/改善旗標、新案例、容差、Markdown）。

## E4：內建案例覆蓋

- [x] 案例涵蓋 tag：`read-only`(list)、`daily-ops`(create/rename/trash)、`skill-generation`(7zip→pending proposal)、`safety`(破壞性需確認)、`workflow-reuse`(可組合 search→rename 步驟引用)、`context`(雜訊長 prompt→乾淨計畫)、`model-escalation`。10/10 mock 全過。inproc runner 已接 `skill_authoring`(CodegenSubAgent) 使生成案例可產出 pending proposal。
- [x] `model-escalation` 案例：`MockLLM` 新增 `external`/`local_failures`,inproc 建可升級 router;本地回不合法輸出 → 升級(mock)外部 → 計畫成功。隱私敏感**不**外送/外部停用不升級已於 `tests/assistant/test_model_router.py` 單元層覆蓋。
- [x] M2–M5 量產案例套件（`eval/generate_cases.py`，輸出 `eval/cases/generated/`，**每級 100 共 400** 個案例）：M2=讀取多工具（3+ 查詢工具,auto-exec）、M3=查詢情境+寫入/批次（需確認）、M4=自我撰寫生成（**100 種**技能:hash/編碼/壓縮/文字/資料/影像/PDF…,`skill_generated:"*"`）、M5=多步驟+步驟引用+寫入（需確認）。全標 `mode:[api,browser]`。`load_cases` 遞迴納入。
  - **Mock（決定性）**：**411/411 恆過**（400 產生 + 11 手寫）。回歸守門。
  - **Browser（真實 Gemma）**：`verify` 對 browser 放寬（`strict_steps=False`:只看「有產出計畫 + 確認層級」,不比精確步驟）。**M2(唯讀)/M4(生成) 可靠**;**M3/M5 不可靠**——真實模型對合成的多工具+寫入 prompt 不一定產出寫入步驟/標對確認層級（sample 實測 gen-m3-001/gen-m5-001 0.50 FAIL）。不為了過而再放寬;Mock 為事實來源。詳見 [eval-prompt-log.md](../eval-prompt-log.md) §2.3。

## E5：執行驗證模式（實際跑 skill、驗產出內容）

> 測試 prompt 與**出過問題的 prompt** 集中記在 [eval-prompt-log.md](../eval-prompt-log.md)；出問題的一律也做成 eval case 以便自動回歸。


- [x] **不只驗「有沒有生成提案」,而是實際執行 skill 並驗產出內容**。新增 `--mode exec`：`eval/exec_runner.py` 把案例的參考實作 `expect.execute.code` 丟進**真實 `SkillSandbox`** 對 `eval/fixtures/` 的 fixture 執行,收集產出檔與內容;`verifier.verify_execution` 斷言 `execution` 維度（執行無誤、產出檔數、檔名含、**內容含**、指定檔名）。決定性、免 LLM/後端,可進 CI。
- [x] 沙箱補 **Pillow + pypdf** 依賴（重建後端映像 + 本地 `uv sync`）,讓 image/pdf skill 真的能跑。
- [x] 4 個執行案例（`eval/cases/exec/`,內容正確性斷言）：hash 報告（驗 SHA256 hex 正確）、untar（驗解出 `alpha.txt`+`docs/beta.txt`）、縮圖（Pillow 64→32px 產出檔）、PDF 抽字（pypdf 驗抽出 "Hello PDF Eval"）。`--mode exec` **4/4 PASS**,fixtures 由 `eval/fixtures/make_fixtures.py` 決定性產生。
- [x] 測試 `tests/eval/test_exec.py`（bundled exec 案例產出正確、內容錯誤要 fail、沙箱失敗要 fail）;`test_inproc_runner` 改只跑有 `mock_llm` 的 chat 案例。
- [x] **Browser 執行（真實模型 + UI + 沙箱端到端）**：`--mode browser` 對 execution 案例 → 用 API 把 fixture 種進 drive → 生成 skill → Approve 安裝 → 右鍵 fixture 執行（用 manifest 實際生成的選單標籤）→ 擷取 `/skills/{id}/execute` → 下載產出檔內容 → `verify_execution`（spec 見 `assistant-eval.spec.ts` `runExecutionCase`）。實測 **3/4**：hash 報告 / 縮圖 / untar 模型生成的 skill 端到端產出正確;**pdf 抽字 0.75（執行成功、有產出,但模型 naive PDF 解析器抽出的內容對不上預期文字——真實模型能力限制,非 harness 問題;決定性 exec 用 pypdf 為 4/4）**。browser 執行為盡力而為的真實 smoke,通過數反映模型當下產碼品質。

## E6：考官 provider（judge provider）選配增強

> 開發者 eval 工具，不是使用者功能。疊在 E3 已建的 judge（`eval/judge.py`）之上，讓**考官模型**可換更強的 provider；憑證走**開發者 env / CLI**，與終端使用者 profile 無關（原列為 external-model EM4，因範疇不同移來此）。
> **狀態（2026-06-19）：四項全完成**——provider 切換、Codex 考官、防呆、測試，且 judge 可評 `--mode exec` 的實際產出。
> 實作刻意保持 judge 整條**同步**（urllib/subprocess，獨立於 async 的 assistant LLM stack）：gemma/openai 共用既有 `HttpJudgeModel`（OpenAI 相容 HTTP，差在 base_url/model/key），codex 用新的 `CodexJudgeModel`（同步跑本機 `codex exec`）——**未**重用 EM2/EM3 的 async client。

- [x] judge 可配置 provider（`--judge-provider {gemma|codex|openai}`，**預設 gemma**）：gemma/openai → `HttpJudgeModel`（provider 設預設端點/模型，flag 可 override）；codex → `CodexJudgeModel`（同步 `codex exec`，runner 可注入測試）。憑證走開發者 env / CLI。
- [x] rubric 評斷 skill 的**效果**：`build_exec_judge_prompt` + `judge_execution` 把 `--mode exec`（與 browser-execute）跑出的產出檔（檔名 + 內容，長度截斷、binary 標記）餵進 judge；run.py 的 exec / browser-execute 分支接上。`exec_hash_report.yaml` 加 rubric + `judge` 權重示範（無 `--judge` 時 judge 維度缺、只算 execution，不破壞既有 4/4；端到端假端點實測 execution 1.0 × 0.7 + judge 0.9 × 0.3 = 0.97 PASS）。生成正確性（codeguard/沙箱/結構化）仍由既有確定性檢查把關。
- [x] 考官與被考者分離（引擎跑 Gemma、考官可為更強模型）。
- [x] **Codex 考官防呆**：建 codex judge 前讀 `$CODEX_HOME/auth.json` 的 `account_id`，印 `[judge] provider=codex, account=…`；無 token → `JudgeError`「請先 `codex login`」+ CLI 退出 2（顯示用途，非強制隔離）。
- [x] 測試：provider 切換、verdict 解析、考官維度計入 scoring（`tests/eval/test_judge.py`：codex 回應萃取/非零退出、`account_id` 讀取/fallback/無 token、工廠 gemma/openai/codex 分派與防呆）。

### 考官憑證模型（Codex provider）

Codex 考官的憑證模型與 EM3（使用者功能）刻意不同——因為它是**單一開發者本機**跑，不是多使用者 server：

- **憑證來源**：開發者本機 `codex login` 的 `~/.codex/auth.json`（或 `CODEX_HOME`），**不入 app DB**。
- **不需 per-request 隔離**：EM3 的「臨時隔離 `CODEX_HOME` + 用畢即焚」是為了多使用者 server 同時託管多人 token；E6 單一開發者直接用本機預設 `~/.codex` 即可。
- **登入一次即持久**：CLI 自動以 `refresh_token` 續期；僅在 refresh token 被撤銷／過期／輪替失效時才需重登。
- **判定機制（重要）**：codex 唯一的判定是「**`CODEX_HOME/auth.json` 有沒有有效 token**」，**不辨識「誰」在用**。
- **不同開發者各自登入 = 預設不共享的結果，非系統強制**：不同機器／OS 帳號 → 預設指向不同 `~/.codex` → 各自那份要各自填。**沒有**「偵測到別的開發者就要求重登」這種邏輯。
- **預設不共享 ≠ 強制隔離**：刻意複製 `auth.json` 即可共用（cross-machine demo 已證可搬），但**消耗的是原帳號的訂閱額度**；系統不阻止，靠團隊紀律（各用自己帳號、不共用 auth.json）。
- **可選防呆**：`account_id` 存在 auth.json，可讀出顯示「目前考官帳號」當提示／稽核，但僅是顯示，codex 不拿它擋人。

## 分數導向範式 + CLI 增強（2026-06-19）

> 「不以通過為基準，以分數為結果、由 gemma/gpt 判斷並給優缺點」——疊在 E3/E6 之上，**不改變 mock/CI 的純確定性行為**。

- [x] **judge verdict = score + strengths + weaknesses**：`JudgeVerdict` 改帶優點/缺點（原單句 reasoning），prompt 要求三者，`_run_judge` 在 detail 呈現「優點: … | 缺點: …」。
- [x] **judge 可評所有案例**：`_default_rubric` + `fallback_rubric`——無自訂 rubric 的案例套用預設「是否正確、完整、實用達成 prompt 意圖」（含該案 prompt）；`run.py` 三個 judge 呼叫皆 `fallback_rubric=True`。
- [x] **report 分數為主軸**：`report.aggregates_to_markdown` 在有 judge 時主秀 judge 分數 + ✓/✗ 守門 + 「評分理由（優點/缺點）」；JSON 加頂層 `judge_score`/`judge_detail`。**`passed` 仍由確定性斷言決定**（judge 不 gate）；無 judge 維度時維持原 pass-rate 報告。
- [x] **`--tag` / `--verbose`**：`--tag mX` 篩 tag（m2–m5/safety/…）；`--verbose` 逐案印**輸入 prompt + 輸出結果 + 評分 + 優點/缺點 + 守門**（`report.verbose_markdown` + run.py `_summarise_response`/`_summarise_exec`）。
- [x] **M 分級事實**：無 `m1`（m2–m5）；m2–m5 是 `api`/`browser`（chat），**不是 `exec`**；`--mode exec` 只有 4 個 `m4`。跑某級用 `--mode api --tag mX`。
- [x] 測試：`tests/eval/test_report.py`（分數主軸/優缺點呈現/verbose）、`test_judge.py`（strengths/weaknesses 解析、fallback rubric）。

## 測試/驗證任務

- [x] harness 自身單元測試（schema 載入、scoring 計算、verifier 斷言）以 mock 資料驗證 + property-based 不變量（`tests/eval/`）。
- [x] API 模式 mock-LLM 案例可整進 CI（`eval/inproc.py` + `run.py --llm mock`,決定性、免後端/Gemma）。
- [x] `ruff format/check`、`mypy`、`pytest` 全綠（eval 切片）。

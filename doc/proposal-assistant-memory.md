# 需求草案：助理對話記憶（多輪 context 回讀）

> 狀態：**v1 已實作並驗證**。2026-07-07。依 CLAUDE.md 文件先行。
> 關聯：[detailed-design.md §9](./detailed-design.md)、[backend-assistant.md](./tasks/backend-assistant.md)、
> DEC-033（planner 路徑）。
>
> **實作與驗證（2026-07-07）**：
> - 新增 `app/assistant/memory.py`（`summarise_results` / `append_result_summary` /
>   `history_to_messages`）;`WorkflowPlanner.plan` 加 `history`（夾在 system 與當前 user 之間）;
>   `WorkflowService.chat`（含 replan）透傳;router `/chat` 載入最近 N 則 → 傳入,並在持久化
>   assistant 訊息時把結果摘要接到 content。設定 `assistant_history_max_messages=12`（0=關閉）。
> - **真模型**：tool 角色 vs assistant 文字 A/B（gemma4,4 runs）→ **assistant 文字 4/4**、
>   tool 角色 0/4（故採 assistant 文字承載,零 migration）。
> - **整合（真模型+Postgres）**：多輪對話端到端 **41/41**——歷史回放、結果摘要持久化、
>   雙輪累積皆正確。
> - **多輪 eval（真模型,指涉解析,填上「無 committed 指涉測試」缺口）**：
>   `multiturn-create-second`（純對話指涉,「第二個=2023」）**5/5**;
>   `multiturn-rename-first`（工具結果指涉,從列檔摘要取 item_id 改名）**5/5**;
>   綜合 **10/10、0 跳針、均 14.7s**（`eval/out/temp_sweep_20260707T173641Z.md`）。
>   200 字摘要截斷未影響 id 傳遞（不需調長）。
> - **嚴謹版（補上 rename 案例的代理性缺口）**：`multiturn-recall-listed-names`——列檔後要求
>   「不重列、只從對話」報出**全部三個資料夾名**（`reply_contains` 驗回覆文字,無 id/排序假設）。
>   真模型跑分（2026-07-08,3 案例 × 5）：create-second 5/5、rename-first 5/5、
>   **recall-listed-names 0/5**（`eval/out/temp_sweep_20260708T034239Z.md`）。
> - **嚴謹案例揭露的真限制（重要）**：0/5 **不是管線壞,是摘要保真度不足**。根因假設:
>   `summarise_results` 對 list_items 用 `str(output)`（原始 item dict,含 36 字 UUID）→ 三項
>   遠超 `_MAX_OUTPUT_CHARS=200` → 第一項就被截斷 → 記憶只留第一個名字 → 回想不出全部三個。
>   rename 只需「第一個」的 id（在前 200 字內存活）故 5/5;回想需全三名故 0/5。**代理測試遮住的,
>   嚴謹測試抓到了。** 待辦見 §7。
> - **單輪無退化**：記憶落地後重跑 sweep 仍 **100%、0 跳針、9.7s**（空歷史為 no-op）。
> - 單元：628 passed（+10）、mypy、ruff 全綠。

## 1. 背景與動機（實際使用回報）

使用者實測回報：助理「沒有記憶」,多輪對話體驗差（例：先問某檔案、下一句「幫我把它改名」,
助理不知道「它」指誰）。

**根因診斷（已查證,非推測）**：對話**有存、沒回讀**。
- 有存：[`router.py:368-380`](../backend/app/assistant/router.py) 每輪 `session_repo.add_message()`
  寫入 user + assistant 訊息（含 tool_calls）,`list_messages` 可讀回。
- 沒用：[`service.py:137`](../backend/app/assistant/service.py) 呼叫 `planner.plan(message=message, …)`
  **只帶當前一句**;`WorkflowPlanner.plan()` 組的 messages 為 `[system,（選檔提示）, 當前 user]`,
  前幾輪從未進入模型 context。存下的歷史目前只供側邊欄顯示。

→ 修法是「把既有資料接上去」,非從零蓋儲存。`ContextManager.trim()`（planner 已在用）
已負責上限保護。

**Context 預算（已查證,2026-07-07）**：
- `llm_num_ctx = 65536` tokens（config 預設,`.env` 未覆寫 → 生效值）。
- `ContextManager.trim` 實際字元預算 = `num_ctx × 4` = **262,144 字元**（約 65K tokens）,
  `num_predict` 生成上限 2048。
- trim 行為：永遠保留所有 system 訊息,再**從最新往回**塞非 system 訊息至預算滿（天然
  「留最近、丟最舊」）。→ 262K 字元對「6 輪對話＋工具結果」綽綽有餘,不是瓶頸。

**工具結果不在訊息文字裡（已查證,關鍵）**：執行後 assistant 訊息的 `content` 存的是
`plan.reply`（模型自然語言回覆,如「好的,列出來了」）,**實際結果在 `results`(StepResult)**,
寫進 workflow run 的 `step_results`、UI 以表格顯示——不進訊息文字。故純文字歷史會漏掉
「第一個檔案是誰」這類指涉所需資訊 → **v1 必須納入工具結果**（見 §2 決策 2）。

## 2. 決策（v1 預設,使用者已同意）

1. **回溯範圍**：最近 N 則對話訊息（預設 N=12,約 6 輪）,不做摘要;硬上限仍由 `trim` 保。
2. **帶什麼（含工具結果,使用者指定）**：帶 `user`、`assistant` 文字,**並帶工具執行結果**
   （StepResults 壓成精簡摘要）。
   - **承載方式（真模型定案,2026-07-07）**：以 **assistant 文字**承載,**不用 `tool` 角色**。
     真模型 A/B（gemma4,each 4 runs,think:false）：結果放 `tool` 角色訊息 → 模型 **0/4**
     解析正確（直接幻覺假檔名,chat template 不消化孤立 tool 訊息）;放 assistant 文字 →
     **4/4** 正確。故摘要必須進入 assistant/user 文字流。
   - 摘要格式求精簡（每步：skill、ok/fail、關鍵輸出如檔名/數量,截斷長 payload）,避免灌爆 context。
3. **上限保護**：交給既有 `ContextManager.trim()`（262K 字元預算,留最近丟最舊）。
4. **範圍界定**：v1 只接 planner（規劃）路徑;codegen（技能生成）不吃對話歷史（單輪任務）。
5. **隱私/外部模型**：v1 不改 privacy 去識別化邏輯——歷史（含工具結果摘要）與當前訊息走同一條
   既有 privacy gate（`_call_external` 已對整包 messages 分類）。多帶歷史＝外送內容變多,此取捨
   於文件記錄,v1 接受現狀（保守預設仍為 sensitive、需去識別化才外送）。**注意**：工具結果可能
   含檔名等使用者資料,摘要化時不引入新的外送面（仍由同一 gate 攔）。

**v2 待議（不在本 PR）**：長對話摘要壓縮、per-session token 預算精算、工具結果的結構化
（非純文字）回饋。

## 3. 設計草圖（細節留 detailed-design）

- `WorkflowPlanner.plan()` 新增 `history: list[LLMMessage] | None = None`;
  組訊息序改為 `[system prompt,（選檔提示）, *history, 當前 user]`,再 `context.trim(...)`。
- `WorkflowService.chat()` 新增 `history` 參數,透傳給 `plan()`;replan 路徑一併帶入。
- **歷史載入點**：router 的 `/chat` handler（已持有 `session_repo`,且已在該層負責寫入）
  在呼叫 `service.chat()` 前 `list_messages` → 取最後 N 則 → 映成 `LLMMessage`,傳入。
  讀寫記憶同層,service 維持「給訊息+歷史就規劃」的純度。
  - 注意：router 在 `service.chat()` **之後**才寫入當前 user 訊息 → 載入的歷史天然不含本輪。
- **工具結果的承載（真模型 + 前端查證後定案,零 migration）**：結果摘要以 **assistant 文字**
  進入模型（tool 角色已被真模型否決,見 §2.2）。**做法**：router 在持久化 assistant 訊息時,
  把 `_summarise_results(response.results)` **接到 `content` 尾巴**（僅在有結果時）。
  - 為何零改動:查證 [`MessageBubble.tsx`](../frontend/src/components/assistant/MessageBubble.tsx)
    ——重載 session 的訊息**不帶 results**（ORM `AssistantMessage` 無 results 欄,回應 `results`
    預設空 → 重載泡泡只顯示 content、無表格）。故摘要進 content 對載入的模型可見、對重載 UX
    反而更好（現況重載什麼都沒有）,且無需 schema/前端變更。
  - **可接受的取捨**：live 回應的 `response.message` 維持乾淨（`plan.reply`）、泡泡＋表格照舊;
    僅**持久化**的 content 尾端多摘要 → live 與 reload 泡泡文字略有差異（benign,且 reload 更完整）。
  - `_summarise_results` 獨立可測:每步 `skill / ok|fail / str(output) 截斷 ~200 字`,無結果回空字串。
- 新增設定 `assistant_history_max_messages: int = 12`（0 = 關閉記憶,退回單輪）。

**待確認的技術選擇（detailed-design 階段定案）**：
- (a) 歷史載入放 router（本草案建議）vs 注入 `session_repo` 進 service——傾向前者（讀寫同層）。
- (b) N 的單位與預設：12 則 / 6 輪是否合適,或改以 token 預算為準（trim 已保硬上限,N 僅軟性省成本）。
- (c) 工具結果摘要的粒度：每步帶哪些欄位、payload 截斷長度。

## 4. 驗收條件

- 單元：`plan()` 把 history 夾在 system 與當前 user 之間、順序正確;超過 N 則只取最後 N;
  結果摘要以 assistant 文字承載（非 tool 角色）;`assistant_history_max_messages=0` 時不帶歷史。
- 單元：`_summarise_results` 把 StepResults 壓成精簡文字（含 skill/ok/關鍵輸出、截斷長 payload）;
  無結果時不附摘要。
- 整合（真模型,`needs_llm`）：兩輪對話——第一輪列出某資料夾（產生工具結果）,第二輪用代詞/省略
  （「把第一個改名為 X」）——planner 收到的歷史含第一輪的結果摘要,且產出的計畫指向正確項目
  （robust check,非逐字）。
- 全閘門：ruff/mypy/pytest 綠;既有 planner 單輪測試不退化。
- 文件：detailed-design §9 相關段、backend-assistant.md checklist、.env.example + §9.12 env 新增。

## 5. 風險與回退

- 純增量:`history=None`/`assistant_history_max_messages=0` 即完全還原單輪行為。
- 延遲：多帶 ~6 輪會略增 prompt 長度;think:false（DEC-033）後 planner 已快 ~10 倍,有餘裕。
- 過長歷史誘發跳針？think:false 已消滅 thinking 段迴圈;trim 保上限。驗收整合測試會實測。

## 6. 已知限制（v1 刻意做小,誠實記錄）

**硬參數限制（可調,只是把牆往後推）**
- **只記最近 ~6 輪**：`assistant_history_max_messages=12`（≈6 個來回）,更早的訊息**直接丟棄**
  （非壓縮）。超過視窗的舊內容問不到。硬上限另有 `ContextManager.trim`（`num_ctx=65536`
  ≈26 萬字元,留最近丟最舊）,但實務上 12 則先撞到。
- **工具結果只留前 200 字**：`_MAX_OUTPUT_CHARS=200`（每步輸出摘要上限）。列 50 檔時只帶前幾個
  → 「第一/第二個」穩,「第 40 個」失敗(沒進摘要)。

**架構限制（需 v2 才解）**
- **單一 session 內**：開新對話＝全新開始,**不跨對話記憶**,也無使用者長期畫像。
- **無摘要壓縮**：超出視窗＝整段丟棄,不濃縮成長期記憶 → 長對話失去開頭脈絡。
- **靠「最近」非「相關」**：機械塞最近 N 則,不對舊訊息做語意檢索;關鍵但已滑出視窗的內容取不回。
- **是「重讀逐字稿」非「學習」**：模型無狀態,每輪重新餵最近對話,非真正記住。

**其他取捨**
- 延遲/成本隨歷史線性增長;外部模型時外送內容比單輪多(走同一 privacy gate)。
- 無「忘記/編輯記憶」控制。
- 即使歷史完整,gemma4:26b **運用**多層指涉的能力仍有上限（模型能力,非管線問題）。

**v2 方向(優先序)**：①調參(最便宜,治標) → ②舊對話摘要壓縮(長對話不失憶) →
③語意檢索(複用搜尋的 pgvector,取「相關」而非「最近」) → ④跨 session／使用者畫像(最大)。

## 7. 後續規劃（多輪 eval 揭露後,2026-07-08）

回想案例 0/5 揭露「摘要保真度」缺口,優先於上面的 v2 條目(因為它是 v1 就該修好的保真問題,
不是 v1 刻意不做的範圍)。

1. **先診斷確認根因**（一發 verbose 真模型跑):看 recall 失敗時模型回覆——是(a)摘要截斷只留一個名,
   還是(b)模型改成重新列檔而非從記憶回答。決定修法方向。
2. **若為截斷(假設)——改摘要格式而非只調長**：`summarise_results` 對集合型輸出(list_items)
   不要 `str(原始 dict)`(UUID 佔滿預算),改**只萃取關鍵欄位**(如檔名清單),或對 list 型
   給「N 項:name1, name2, …」。這樣三名輕鬆入 200 字,且不需犧牲 context。再重跑 recall 案例驗證。
3. **rename 案例補強(選配)**：目前驗「產出有效 rename plan」;可加驗 item_id 屬實際 seed 的資料夾
   (需 runner 回傳 seed ids),把代理性再降一級。
4. 完成後把 recall 案例納入常態多輪 eval 集,作為「摘要保真」的回歸守門。

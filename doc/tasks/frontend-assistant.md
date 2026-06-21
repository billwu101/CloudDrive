# Frontend Assistant 模組任務（HARNESS 引擎 + Workflow 管線）

對應設計：[detailed-design.md（附錄 A）](../detailed-design.md)

## 完成定義

- 登入後可開啟聊天面板，用自然語言描述需求。
- 助理回傳的**執行計畫（候選 Workflow）**可檢視並確認/拒絕/修改。
- 缺技能時的生成內容可核可；已安裝自訂技能依 manifest 動態出現在右鍵選單。
- 已存工作流程可一鍵重跑；改檔後相關畫面即時更新。

## M2：聊天面板 + 計畫確認

- [x] `src/api/assistantApi.ts`：chat、`confirmWorkflow`/`cancelWorkflow`、技能核可/安裝、技能觸發。（工作流程儲存/重跑待 M5）
- [x] `src/api/types.ts`：WorkflowStep/WorkflowStepResult/WorkflowPlanView/ConfirmResponse + 擴充 ChatResponse(plan/results)。
- [x] `src/hooks/useAssistant.ts`：對話 + `useConfirmWorkflow`(成功 invalidate `['drive']`)/`useCancelWorkflow`；保存 session。
- [x] `src/components/assistant/AssistantPanel.tsx`：浮動面板（已於 M2a 完成，本次接入計畫卡）。
- [x] `MessageBubble.tsx`（M2a）。
- [x] `WorkflowPlanCard.tsx`：顯示 pending workflow（步驟、permission_tier、破壞性/需核可標記）+ 確認/拒絕。（修改需求待後續）
- [x] 在 AppShell 掛載入口；助理停用（503）時以錯誤訊息呈現（M2a）。

步驟結果顯示備註（2026-06-17）：新增 `StepResultList`，在助理泡泡內渲染 workflow 步驟結果（`results[].output`）。`storage_quota` 格式化為「15.0 GB free of 15.0 GB (0% used)」、清單類顯示項目數、其他顯示名稱/完成。chat 的 auto_executed 與 confirm 完成都會帶出結果。另：移除 Enter 送出（改用送出鈕）。

M2 計畫卡備註（2026-06-17）：`/chat` 回 `plan.status==='pending_approval'` 時面板渲染 `WorkflowPlanCard`，按「Confirm & run」呼叫 `POST /workflows/{id}/confirm`、「Cancel」呼叫 `/cancel`；confirm 成功後 invalidate `['drive']`。auto_executed 計畫不需確認，僅顯示助理訊息。工作流程一鍵重跑已於 M5 完成；「修改需求」互動仍待後續。

### M2a：登入後聊天面板切片（2026-06-17）

- [x] `src/api/assistantApi.ts`：接 `POST /assistant/chat`。
- [x] `src/api/types.ts`：新增 `AssistantChatRequest`/`AssistantChatResponse`/tool call/tool result 型別。
- [x] `src/hooks/useAssistant.ts`：新增 chat mutation。
- [x] `src/components/assistant/AssistantPanel.tsx`：登入後浮動對話面板，保留 session id 並顯示錯誤。
- [x] `src/components/assistant/MessageBubble.tsx`：使用者/助理訊息顯示。
- [x] `AppShell`：在登入後 CloudDrive shell 掛載 assistant 入口，不再以 Swagger 作為使用介面。
- [x] MSW mock + `assistantApi`/`AssistantPanel` 測試。

## M4：技能核可介面

- [x] `SkillApprovalCard.tsx`：顯示生成的 manifest 摘要，核可/略過。新增「Review code」開啟 `SkillApprovalDialog`。
- [x] `SkillApprovalDialog.tsx`：顯示完整生成程式碼與右鍵動作審查資訊,核可/拒絕（附「程式碼只在沙箱、核可後才執行」說明）。
- [x] 核可後刷新已安裝技能與右鍵選單。

## M5：動態 UI 與工作流程重用

- [x] 右鍵選單依已安裝技能 manifest 的 `ui.context_menu` 動態插入（目前依 `item_type` 比對）。
- [x] 點技能項目 → 呼叫 handler → 顯示 `AssistantSkillResultDialog`。
- [x] 點技能項目 → 完成後 invalidate `['drive']`（`useExecuteAssistantSkill` onSuccess;生成技能寫回 drive items 需要）。
- [x] 已存工作流程清單 + 一鍵重跑：`assistantApi.saveWorkflow/listSavedWorkflows/rerunWorkflow` + 對應 hooks;`SavedWorkflowsPanel`(列表+一鍵重跑)、`WorkflowPlanCard` 加「Save」;重跑 invalidate drive。

## 測試任務

- [x] MSW mock chat / 核可 / 技能觸發。
- [x] MSW mock 計畫 confirm/cancel + 工作流程 save/saved/rerun（baseline handlers）。
- [x] 測計畫卡顯示與確認/拒絕流程。
- [x] 測技能 manifest 驅動右鍵選單渲染（目前依 `item_type`）。
- [x] 測 `SkillApprovalDialog`（顯示程式碼/核可/拒絕/無 skill 不渲染）、`SavedWorkflowsPanel`（列表/一鍵重跑/重跑中停用）。改檔後 query 失效由 hooks 的 invalidate 覆蓋。
- [x] `lint`、`typecheck`、`test -- --run` 全綠（223 passed）。

# Frontend Assistant 模組任務（HARNESS 引擎 + Workflow 管線）

對應設計：[assistant-design.md](../assistant-design.md)

## 完成定義

- 登入後可開啟聊天面板，用自然語言描述需求。
- 助理回傳的**執行計畫（候選 Workflow）**可檢視並確認/拒絕/修改。
- 缺技能時的生成內容可核可；已安裝自訂技能依 manifest 動態出現在右鍵選單。
- 已存工作流程可一鍵重跑；改檔後相關畫面即時更新。

## M2：聊天面板 + 計畫確認

- [ ] `src/api/assistantApi.ts`：chat、計畫確認、技能核可/安裝、工作流程儲存/重跑、技能觸發。
- [ ] `src/api/types.ts`：ChatMessage/Workflow/WorkflowStep/Plan/SkillManifest/Approval 型別。
- [ ] `src/hooks/useAssistant.ts`：對話與計畫流程；保存/續接 session。
- [ ] `src/components/assistant/AssistantPanel.tsx`：浮動面板。
- [ ] `MessageBubble.tsx`。
- [ ] `WorkflowPlanCard.tsx`：顯示候選 workflow（步驟、影響範圍、破壞性/需核可標記）+ 確認/拒絕/修改。
- [ ] 在 ProtectedLayout 掛載入口；助理停用（503）時隱藏。

### M2a：登入後聊天面板切片（2026-06-17）

- [x] `src/api/assistantApi.ts`：接 `POST /assistant/chat`。
- [x] `src/api/types.ts`：新增 `AssistantChatRequest`/`AssistantChatResponse`/tool call/tool result 型別。
- [x] `src/hooks/useAssistant.ts`：新增 chat mutation。
- [x] `src/components/assistant/AssistantPanel.tsx`：登入後浮動對話面板，保留 session id 並顯示錯誤。
- [x] `src/components/assistant/MessageBubble.tsx`：使用者/助理訊息顯示。
- [x] `AppShell`：在登入後 CloudDrive shell 掛載 assistant 入口，不再以 Swagger 作為使用介面。
- [x] MSW mock + `assistantApi`/`AssistantPanel` 測試。

## M4：技能核可介面

- [x] `SkillApprovalCard.tsx`：顯示生成的 manifest 摘要，核可/略過。
- [ ] `SkillApprovalDialog.tsx`：顯示完整生成程式碼與審查資訊，核可/拒絕。
- [x] 核可後刷新已安裝技能與右鍵選單。

## M5：動態 UI 與工作流程重用

- [x] 右鍵選單依已安裝技能 manifest 的 `ui.context_menu` 動態插入（目前依 `item_type` 比對）。
- [x] 點技能項目 → 呼叫 handler → 顯示 `AssistantSkillResultDialog`。
- [ ] 點技能項目 → 完成後 invalidate `driveKeys.items(parentId)` 等（寫入型技能需要）。
- [ ] 已存工作流程清單 + 一鍵重跑。

## 測試任務

- [x] MSW mock chat / 核可 / 技能觸發。
- [ ] MSW mock 計畫 / 工作流程重跑。
- [ ] 測計畫卡顯示與確認/拒絕流程。
- [x] 測技能 manifest 驅動右鍵選單渲染（目前依 `item_type`）。
- [ ] 測改檔後 query 失效。
- [ ] `lint`、`typecheck`、`test -- --run` 全綠。

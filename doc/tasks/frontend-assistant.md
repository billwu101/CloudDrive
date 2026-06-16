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

## M4：技能核可介面

- [ ] `SkillApprovalDialog.tsx`：顯示生成的 manifest 與程式碼，核可/拒絕。
- [ ] 核可後刷新已安裝技能與右鍵選單。

## M5：動態 UI 與工作流程重用

- [ ] 右鍵選單依已安裝技能 manifest 的 `ui.context_menu` 動態插入（依副檔名比對）。
- [ ] 點技能項目 → 呼叫 handler → 完成後 invalidate `driveKeys.items(parentId)` 等。
- [ ] 已存工作流程清單 + 一鍵重跑。

## 測試任務

- [ ] MSW mock chat / 計畫 / 核可 / 技能觸發 / 工作流程重跑。
- [ ] 測計畫卡顯示與確認/拒絕流程。
- [ ] 測技能 manifest 驅動右鍵選單渲染（依副檔名）。
- [ ] 測改檔後 query 失效。
- [ ] `lint`、`typecheck`、`test -- --run` 全綠。

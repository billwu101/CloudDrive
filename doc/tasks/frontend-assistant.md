# Frontend Assistant 模組任務（HARNESS v1.0）

對應設計：[assistant-design.md](../assistant-design.md)

## 完成定義

- 登入後可開啟聊天面板，用自然語言操作雲端硬碟並請助理「製作新功能」。
- 已安裝的自訂技能依其 manifest 動態出現在右鍵選單（如 7zip「解壓縮」）。
- 技能安裝需使用者核可，前端提供核可介面（顯示生成的程式碼/說明）。
- 助理改動檔案後，相關畫面即時更新。

## M2：聊天面板與串接

- [ ] `src/api/assistantApi.ts`：chat、技能核可/安裝、技能觸發的 API 包裝。
- [ ] `src/api/types.ts`：ChatMessage/ChatResponse/ToolCall/SkillManifest/Approval 型別。
- [ ] `src/hooks/useAssistant.ts`：對話 mutation；保存/續接 session。
- [ ] `src/components/assistant/AssistantPanel.tsx`：浮動面板。
- [ ] `MessageBubble.tsx` / `ToolCallChip.tsx`：訊息與工具動作顯示。
- [ ] 在 ProtectedLayout 掛載入口；助理停用（503）時隱藏。

## M4：技能核可介面

- [ ] `SkillApprovalDialog.tsx`：顯示生成的 manifest 與程式碼，提供核可/拒絕。
- [ ] 核可後刷新已安裝技能清單。

## M5：動態右鍵選單

- [ ] 右鍵選單依「已安裝技能 manifest 的 `ui.context_menu`」動態插入項目（依檔案副檔名比對）。
- [ ] 點選技能項目 → 呼叫對應技能 handler → 完成後 invalidate `driveKeys.items(parentId)` 等。

## 測試任務

- [ ] MSW mock chat / 核可 / 技能觸發。
- [ ] 測技能 manifest 驅動右鍵選單渲染（依副檔名）。
- [ ] 測核可流程與改檔後 query 失效。
- [ ] `lint`、`typecheck`、`test -- --run` 全綠。

# Frontend Assistant 模組任務

對應設計：[assistant-design.md](../assistant-design.md)

## 完成定義

- 登入後可在網頁內開啟聊天面板，用自然語言操作雲端硬碟。
- 助理改動檔案後，相關畫面（Drive 列表等）即時更新。
- 無後端助理功能（503）時優雅隱藏入口。

## M2：聊天面板與串接

- [ ] `src/api/assistantApi.ts`：`POST /assistant/chat` 包裝（沿用 `api` axios instance）。
- [ ] `src/api/types.ts`：ChatMessage / ChatResponse / ToolCallLog 型別。
- [ ] `src/hooks/useAssistant.ts`：TanStack Query mutation；保存 session 內 messages。
- [ ] `src/components/assistant/AssistantPanel.tsx`：浮動面板（開關鈕 + 訊息列 + 輸入框）。
- [ ] `src/components/assistant/MessageBubble.tsx`：使用者/助理訊息泡泡。
- [ ] `src/components/assistant/ToolCallChip.tsx`：顯示工具動作（已搜尋/已建立資料夾…）。
- [ ] 在 ProtectedLayout 掛載浮動入口按鈕。

## M3：與寫入工具整合

- [ ] 助理回傳工具動作後，invalidate 對應 query key（`driveKeys.items(parentId)` 等）。
- [ ] 載入/送出/錯誤狀態 UI。

## 測試任務

- [ ] MSW mock `/assistant/chat`：測送出訊息、顯示回覆與工具 chip。
- [ ] 測改檔後對應 query 失效。
- [ ] `npm run lint`、`npm run typecheck`、`npm run test -- --run` 全綠。

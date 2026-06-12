# Frontend API Client 模組任務

## 完成定義

- 所有 API 呼叫透過統一 client。
- Access token、refresh、錯誤轉換與取消請求可共用。
- API client 可使用 mock server 獨立測試。

## 最小可執行任務

- [ ] 建立 `src/api/client.ts`。
- [ ] 從環境變數讀取 API base URL。
- [ ] 建立統一 request helper。
- [ ] 自動加入 Authorization header。
- [ ] 建立 API error TypeScript 型別。
- [ ] 將後端 error response 轉成 ApiError。
- [ ] 實作 401 refresh 流程。
- [ ] 防止多個 401 同時重複 refresh。
- [ ] refresh 成功後重試原 request。
- [ ] refresh 失敗時清除 auth store。
- [ ] 支援 AbortSignal。
- [ ] 建立 `authApi.ts`。
- [ ] 建立 `driveApi.ts`。
- [ ] 建立 `uploadApi.ts`。
- [ ] 建立 `shareApi.ts`。
- [ ] 建立 `searchApi.ts`。
- [ ] 建立 `trashApi.ts`。
- [ ] 建立 response TypeScript 型別。
- [ ] 對照 OpenAPI 確認欄位命名。

## 測試任務

- [ ] 測試帶入 access token。
- [ ] 測試無 token 時不加入 header。
- [ ] 測試 401 refresh。
- [ ] 測試 refresh 後重試。
- [ ] 測試 refresh 失敗清除登入狀態。
- [ ] 測試後端錯誤格式轉換。
- [ ] 測試取消請求。


# Frontend API Client 模組任務

## 完成定義

- 所有 API 呼叫透過統一 client。
- Access token、refresh、錯誤轉換與取消請求可共用。
- API client 可使用 mock server 獨立測試。

## 最小可執行任務

- [x] 建立 `src/api/client.ts`。
- [x] 從環境變數讀取 API base URL。
- [x] 建立統一 request helper。
- [x] 自動加入 Authorization header。
- [x] 建立 API error TypeScript 型別。
- [x] 將後端 error response 轉成 ApiError。
- [x] 實作 401 refresh 流程。
- [x] 防止多個 401 同時重複 refresh。
- [x] refresh 成功後重試原 request。
- [x] refresh 失敗時清除 auth store。
- [x] 支援 AbortSignal。
- [x] 建立 `authApi.ts`。
- [x] 建立 `driveApi.ts`。
- [x] 建立 `uploadApi.ts`。
- [x] 建立 `shareApi.ts`。
- [x] 建立 `searchApi.ts`。
- [x] 建立 `trashApi.ts`。
- [x] 建立 response TypeScript 型別。
- [x] 對照 OpenAPI 確認欄位命名。

## 測試任務

- [x] 測試帶入 access token。
- [x] 測試無 token 時不加入 header。
- [x] 測試 401 refresh。
- [x] 測試 refresh 後重試。
- [x] 測試 refresh 失敗清除登入狀態。
- [x] 測試後端錯誤格式轉換。
- [x] 測試取消請求。


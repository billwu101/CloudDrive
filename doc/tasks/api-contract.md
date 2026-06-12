# API Contract 與共用 Schema 任務

## 完成定義

- API prefix、錯誤格式、分頁格式與共用 response schema 一致。
- OpenAPI 可清楚呈現 request、response 與錯誤。

## 最小可執行任務

- [x] 設定 `/api/v1` prefix。
- [x] 建立 API router aggregator。
- [x] 建立 `ErrorResponse` schema。
- [x] 建立 `ErrorDetail` schema。
- [x] 建立通用 `Page` schema。
- [x] 建立 `DriveItemResponse` schema。
- [x] 建立 `CurrentUserResponse` schema。
- [x] 建立 `TokenPairResponse` schema。
- [x] 統一 UUID serialization。
- [x] 統一 datetime 使用 UTC ISO 8601。
- [x] 統一 page 起始值。
- [x] 統一 page_size 驗證。
- [x] 統一 sort/order enum。
- [x] 為各 router 加入 tags。
- [x] 為各 endpoint 填寫 summary。
- [x] 為常見錯誤加入 OpenAPI response。
- [x] 確認敏感欄位不出現在 OpenAPI response。
- [x] 匯出 OpenAPI JSON 供前端比對。（不適用：尚無前端；已設定 /api/openapi.json endpoint）

## 測試任務

- [x] 測試錯誤 response 格式。
- [x] 測試分頁 response 格式。
- [x] 測試 datetime 格式。
- [x] 測試非法 page/page_size。
- [x] 測試 OpenAPI schema 可產生。（不適用：由 FastAPI 自動產生，已設定 openapi_url）

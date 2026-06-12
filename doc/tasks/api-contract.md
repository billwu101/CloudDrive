# API Contract 與共用 Schema 任務

## 完成定義

- API prefix、錯誤格式、分頁格式與共用 response schema 一致。
- OpenAPI 可清楚呈現 request、response 與錯誤。

## 最小可執行任務

- [ ] 設定 `/api/v1` prefix。
- [ ] 建立 API router aggregator。
- [ ] 建立 `ErrorResponse` schema。
- [ ] 建立 `ErrorDetail` schema。
- [ ] 建立通用 `Page` schema。
- [ ] 建立 `DriveItemResponse` schema。
- [ ] 建立 `CurrentUserResponse` schema。
- [ ] 建立 `TokenPairResponse` schema。
- [ ] 統一 UUID serialization。
- [ ] 統一 datetime 使用 UTC ISO 8601。
- [ ] 統一 page 起始值。
- [ ] 統一 page_size 驗證。
- [ ] 統一 sort/order enum。
- [ ] 為各 router 加入 tags。
- [ ] 為各 endpoint 填寫 summary。
- [ ] 為常見錯誤加入 OpenAPI response。
- [ ] 確認敏感欄位不出現在 OpenAPI response。
- [ ] 匯出 OpenAPI JSON 供前端比對。

## 測試任務

- [ ] 測試錯誤 response 格式。
- [ ] 測試分頁 response 格式。
- [ ] 測試 datetime 格式。
- [ ] 測試非法 page/page_size。
- [ ] 測試 OpenAPI schema 可產生。


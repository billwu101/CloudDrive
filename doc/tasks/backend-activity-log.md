# Backend ActivityLog 模組任務

## 完成定義

- 核心操作可寫入 activity log。
- ActivityLogService 不與 HTTP router 綁定。
- 日誌失敗處理策略明確。

## 最小可執行任務

- [x] 建立 `ActivityLog` SQLAlchemy model。
- [x] 建立 action 常數或 enum。
- [x] 建立 `ActivityLogRepository`。
- [x] 實作建立 log。
- [x] 實作依 actor 查詢 log。
- [x] 實作依 item 查詢 log。
- [x] 建立 `ActivityLogService`。
- [x] 支援 JSONB metadata。
- [x] 支援 IP address。
- [x] 支援 user agent。
- [x] 定義 log 寫入失敗策略。
- [x] Upload 成功時寫 log。
- [x] Download 成功時寫 log。
- [x] Preview 時寫 log。
- [x] Rename 時寫 log。
- [x] Move 時寫 log。
- [x] Trash/Restore/Permanent delete 時寫 log。
- [x] Share/Unshare 時寫 log。
- [x] 為近期檔案查詢提供資料接口。

## 測試任務

- [x] 測試寫入 action。
- [x] 測試 metadata JSON。
- [x] 測試 item_id 可為 null。
- [x] 測試依 actor 查詢。
- [x] 測試依 item 查詢。
- [x] 測試 log 寫入失敗不破壞非關鍵主流程。


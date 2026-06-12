# Backend ActivityLog 模組任務

## 完成定義

- 核心操作可寫入 activity log。
- ActivityLogService 不與 HTTP router 綁定。
- 日誌失敗處理策略明確。

## 最小可執行任務

- [ ] 建立 `ActivityLog` SQLAlchemy model。
- [ ] 建立 action 常數或 enum。
- [ ] 建立 `ActivityLogRepository`。
- [ ] 實作建立 log。
- [ ] 實作依 actor 查詢 log。
- [ ] 實作依 item 查詢 log。
- [ ] 建立 `ActivityLogService`。
- [ ] 支援 JSONB metadata。
- [ ] 支援 IP address。
- [ ] 支援 user agent。
- [ ] 定義 log 寫入失敗策略。
- [ ] Upload 成功時寫 log。
- [ ] Download 成功時寫 log。
- [ ] Preview 時寫 log。
- [ ] Rename 時寫 log。
- [ ] Move 時寫 log。
- [ ] Trash/Restore/Permanent delete 時寫 log。
- [ ] Share/Unshare 時寫 log。
- [ ] 為近期檔案查詢提供資料接口。

## 測試任務

- [ ] 測試寫入 action。
- [ ] 測試 metadata JSON。
- [ ] 測試 item_id 可為 null。
- [ ] 測試依 actor 查詢。
- [ ] 測試依 item 查詢。
- [ ] 測試 log 寫入失敗不破壞非關鍵主流程。


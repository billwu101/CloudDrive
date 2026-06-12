# Database 與 Migration 任務

## 完成定義

- PostgreSQL schema 與詳細設計一致。
- Alembic migration 可在空資料庫執行與回滾。
- 索引、唯一約束與外鍵完成。

## 最小可執行任務

- [ ] 建立 SQLAlchemy async engine。
- [ ] 建立 async session factory。
- [ ] 建立 declarative base。
- [ ] 初始化 Alembic。
- [ ] 設定 Alembic 讀取 DATABASE_URL。
- [ ] 建立 users migration。
- [ ] 建立 refresh_tokens migration。
- [ ] 建立 drive_items migration。
- [ ] 建立 file_versions migration。
- [ ] 建立 shares migration。
- [ ] 建立 share_links migration。
- [ ] 建立 activity_logs migration。
- [ ] 加入 item_type check constraint。
- [ ] 加入 share permission check constraint。
- [ ] 加入 share link permission check constraint。
- [ ] 加入 users email unique index。
- [ ] 加入 drive_items owner/parent index。
- [ ] 加入 drive_items deleted index。
- [ ] 加入 drive_items 同層名稱 unique index。
- [ ] 啟用 pg_trgm。
- [ ] 加入 drive_items name trigram index。
- [ ] 加入 file_versions 唯一版本索引。
- [ ] 加入 shares item/target unique index。
- [ ] 加入 activity_logs 查詢索引。
- [ ] 驗證全部 foreign keys。
- [ ] 建立測試資料庫 fixture。
- [ ] 測試 migration upgrade。
- [ ] 測試 migration downgrade。


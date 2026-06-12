# Database 與 Migration 任務

## 完成定義

- PostgreSQL schema 與詳細設計一致。
- Alembic migration 可在空資料庫執行與回滾。
- 索引、唯一約束與外鍵完成。

## 最小可執行任務

- [x] 建立 SQLAlchemy async engine。
- [x] 建立 async session factory。
- [x] 建立 declarative base。
- [x] 初始化 Alembic。
- [x] 設定 Alembic 讀取 DATABASE_URL。
- [x] 建立 users migration。
- [x] 建立 refresh_tokens migration。
- [x] 建立 drive_items migration。
- [x] 建立 file_versions migration。
- [x] 建立 shares migration。
- [x] 建立 share_links migration。
- [x] 建立 activity_logs migration。
- [x] 加入 item_type check constraint。
- [x] 加入 share permission check constraint。
- [x] 加入 share link permission check constraint。
- [x] 加入 users email unique index。
- [x] 加入 drive_items owner/parent index。
- [x] 加入 drive_items deleted index。
- [x] 加入 drive_items 同層名稱 unique index。
- [x] 啟用 pg_trgm。
- [x] 加入 drive_items name trigram index。
- [x] 加入 file_versions 唯一版本索引。
- [x] 加入 shares item/target unique index。
- [x] 加入 activity_logs 查詢索引。
- [x] 驗證全部 foreign keys。
- [x] 建立 user_item_preferences 資料表（DEC-004）。
- [ ] 建立測試資料庫 fixture。（需要 Docker/PostgreSQL，在 Stage 11 integration-testing 完成）
- [ ] 測試 migration upgrade。（需要 PostgreSQL 連線，在 integration-testing 完成）
- [ ] 測試 migration downgrade。（需要 PostgreSQL 連線，在 integration-testing 完成）

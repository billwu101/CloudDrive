# Backend Share 模組任務

## 完成定義

- owner 可分享給指定使用者、更新權限、移除分享。
- 被分享者可取得「與我分享」列表。
- 公開連結、密碼與到期時間具備第二階段實作。

## 指定使用者分享任務

- [x] 建立 `Share` SQLAlchemy model。
- [x] 建立 share permission enum。
- [x] 建立 share request/response schemas。
- [x] 建立 `ShareRepository`。
- [x] 實作依 item 與 target user 查詢 share。
- [x] 實作建立 share。
- [x] 實作更新 permission。
- [x] 實作刪除 share。
- [x] 實作列出 shared-with-me。
- [x] 建立 `ShareService`。
- [x] 驗證只有 owner 可分享。
- [x] 驗證不可分享給自己。
- [x] 依 email 查找 target user。
- [x] 重複分享時更新 permission。
- [x] 寫入 share activity log。
- [x] 寫入 unshare activity log。
- [x] 建立 share router。
- [x] 實作分享給使用者 endpoint。
- [x] 實作更新分享權限 endpoint。
- [x] 實作移除分享 endpoint。
- [x] 實作 `GET /share/shared-with-me`。

## 公開連結任務

- [x] 建立 `ShareLink` SQLAlchemy model。
- [x] 建立 `ShareLinkRepository`。
- [x] 建立安全隨機 share token。
- [x] 資料庫只保存 token hash。
- [x] 實作可選密碼 hash。
- [x] 實作可選 expires_at。
- [x] 實作 link 停用。
- [x] 建立 `ShareLinkService`。
- [x] 實作建立公開連結 endpoint。
- [x] 實作公開連結驗證 endpoint。
- [x] 實作停用公開連結 endpoint。
- [x] 驗證過期 link。
- [x] 驗證停用 link。
- [x] 驗證 link password。

## 測試任務

- [x] 測試 owner 建立分享。
- [x] 測試非 owner 不可分享。
- [x] 測試 target email 不存在。
- [x] 測試不可分享給自己。
- [x] 測試重複分享更新權限。
- [x] 測試移除分享。
- [x] 測試資料夾分享權限繼承。
- [x] 測試公開連結不保存明文 token。
- [x] 測試公開連結密碼。
- [x] 測試公開連結到期。
- [x] 測試公開連結停用。


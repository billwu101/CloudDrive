# Backend Share 模組任務

## 完成定義

- owner 可分享給指定使用者、更新權限、移除分享。
- 被分享者可取得「與我分享」列表。
- 公開連結、密碼與到期時間具備第二階段實作。

## 指定使用者分享任務

- [ ] 建立 `Share` SQLAlchemy model。
- [ ] 建立 share permission enum。
- [ ] 建立 share request/response schemas。
- [ ] 建立 `ShareRepository`。
- [ ] 實作依 item 與 target user 查詢 share。
- [ ] 實作建立 share。
- [ ] 實作更新 permission。
- [ ] 實作刪除 share。
- [ ] 實作列出 shared-with-me。
- [ ] 建立 `ShareService`。
- [ ] 驗證只有 owner 可分享。
- [ ] 驗證不可分享給自己。
- [ ] 依 email 查找 target user。
- [ ] 重複分享時更新 permission。
- [ ] 寫入 share activity log。
- [ ] 寫入 unshare activity log。
- [ ] 建立 share router。
- [ ] 實作分享給使用者 endpoint。
- [ ] 實作更新分享權限 endpoint。
- [ ] 實作移除分享 endpoint。
- [ ] 實作 `GET /share/shared-with-me`。

## 公開連結任務

- [ ] 建立 `ShareLink` SQLAlchemy model。
- [ ] 建立 `ShareLinkRepository`。
- [ ] 建立安全隨機 share token。
- [ ] 資料庫只保存 token hash。
- [ ] 實作可選密碼 hash。
- [ ] 實作可選 expires_at。
- [ ] 實作 link 停用。
- [ ] 建立 `ShareLinkService`。
- [ ] 實作建立公開連結 endpoint。
- [ ] 實作公開連結驗證 endpoint。
- [ ] 實作停用公開連結 endpoint。
- [ ] 驗證過期 link。
- [ ] 驗證停用 link。
- [ ] 驗證 link password。

## 測試任務

- [ ] 測試 owner 建立分享。
- [ ] 測試非 owner 不可分享。
- [ ] 測試 target email 不存在。
- [ ] 測試不可分享給自己。
- [ ] 測試重複分享更新權限。
- [ ] 測試移除分享。
- [ ] 測試資料夾分享權限繼承。
- [ ] 測試公開連結不保存明文 token。
- [ ] 測試公開連結密碼。
- [ ] 測試公開連結到期。
- [ ] 測試公開連結停用。


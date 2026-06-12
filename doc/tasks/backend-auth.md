# Backend Auth 模組任務

## 完成定義

- 使用者可註冊、登入、刷新 token、登出及取得目前使用者。
- Refresh token 可被撤銷。
- AuthService 可使用 mock repository 獨立測試。

## 最小可執行任務

- [ ] 建立 `User` SQLAlchemy model。
- [ ] 建立 `RefreshToken` SQLAlchemy model。
- [ ] 建立 auth request/response Pydantic schemas。
- [ ] 建立 `UserRepository` interface。
- [ ] 實作依 email 查詢使用者。
- [ ] 實作建立使用者。
- [ ] 建立 `RefreshTokenRepository` interface。
- [ ] 實作 refresh token hash 儲存。
- [ ] 實作依 token hash 查詢 refresh token。
- [ ] 實作 refresh token 撤銷。
- [ ] 建立 `AuthService`。
- [ ] 實作註冊 email 正規化。
- [ ] 實作重複 email 檢查。
- [ ] 實作註冊密碼 hash。
- [ ] 實作登入帳密驗證。
- [ ] 實作停用帳號檢查。
- [ ] 實作 access/refresh token pair 簽發。
- [ ] 實作 refresh token 輪替。
- [ ] 實作 logout 撤銷 refresh token。
- [ ] 建立 auth router。
- [ ] 實作 `POST /auth/register`。
- [ ] 實作 `POST /auth/login`。
- [ ] 實作 `POST /auth/refresh`。
- [ ] 實作 `POST /auth/logout`。
- [ ] 實作 `GET /auth/me`。
- [ ] 確認 response 不暴露 `password_hash`。

## 測試任務

- [ ] 測試註冊成功。
- [ ] 測試重複 email 回傳 409。
- [ ] 測試正確帳密登入。
- [ ] 測試錯誤密碼登入失敗。
- [ ] 測試停用帳號不可登入。
- [ ] 測試 refresh token 可取得新 token。
- [ ] 測試撤銷後 refresh token 不可使用。
- [ ] 測試 `/auth/me` 需要 access token。


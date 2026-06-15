# Backend Auth 模組任務

## 完成定義

- 使用者可註冊、登入、刷新 token、登出及取得目前使用者。
- Refresh token 可被撤銷。
- AuthService 可使用 mock repository 獨立測試。

## 最小可執行任務

- [x] 建立 `User` SQLAlchemy model。
- [x] 建立 `RefreshToken` SQLAlchemy model。
- [x] 建立 auth request/response Pydantic schemas。
- [x] 建立 `UserRepository` interface。
- [x] 實作依 email 查詢使用者。
- [x] 實作建立使用者。
- [x] 建立 `RefreshTokenRepository` interface。
- [x] 實作 refresh token hash 儲存。
- [x] 實作依 token hash 查詢 refresh token。
- [x] 實作 refresh token 撤銷。
- [x] 建立 `AuthService`。
- [x] 實作註冊 email 正規化。
- [x] 實作重複 email 檢查。
- [x] 實作註冊密碼 hash。
- [x] 實作登入帳密驗證。
- [x] 實作停用帳號檢查。
- [x] 實作 access/refresh token pair 簽發。
- [x] 實作 refresh token 輪替。
- [x] 實作 logout 撤銷 refresh token。
- [x] 建立 auth router。
- [x] 實作 `POST /auth/register`。
- [x] 實作 `POST /auth/login`。
- [x] 實作 `POST /auth/refresh`。
- [x] 實作 `POST /auth/logout`。
- [x] 實作 `GET /auth/me`。
- [x] 確認 response 不暴露 `password_hash`。

### 忘記密碼（Forgot Password）

- [x] `User` model 新增 `must_change_password` 欄位（Alembic `0004`）。
- [x] 建立 email 寄送抽象層 `app/email/`（`EmailProvider` protocol + `ConsoleEmailProvider` + `SMTPEmailProvider` + factory），仿照 `StorageProvider` 模式。
- [x] `core/security.py` 新增 `generate_random_password()`（預設 10 碼、含大小寫與數字、避開易混淆字元）。
- [x] `AuthService.forgot_password()`：查無 email 或停用帳號時靜默結束（防枚舉），否則重設為隨機密碼、設定 `must_change_password=True`、寄送含臨時密碼的 email。
- [x] 實作 `POST /auth/forgot-password`（無論 email 是否存在都回傳相同訊息）。
- [x] `UserService.change_password()` 在更新密碼時清除 `must_change_password` 旗標。
- [x] `CurrentUserResponse` 新增 `must_change_password` 欄位。

## 測試任務

- [x] 測試註冊成功。
- [x] 測試重複 email 回傳 409。
- [x] 測試正確帳密登入。
- [x] 測試錯誤密碼登入失敗。
- [x] 測試停用帳號不可登入。
- [x] 測試 refresh token 可取得新 token。
- [x] 測試撤銷後 refresh token 不可使用。
- [x] 測試資料庫 refresh token 到期後不可使用。
- [x] 測試 development/test cookie 支援 HTTP，staging/production 強制 Secure。
- [x] 測試 `/auth/me` 需要 access token。
- [x] 測試 `forgot_password` 重設密碼、設定旗標並寄出 email。
- [x] 測試寄出的臨時密碼為 10 碼且可用於登入。
- [x] 測試查無 email / 停用帳號時靜默不寄信（防枚舉）。
- [x] 測試 `POST /auth/forgot-password` 對存在與不存在的 email 回傳相同回應。
- [x] 測試 `generate_random_password` 長度、字元類別、唯一性、避開易混淆字元。
- [x] 測試 email factory 預設 console、設定後選 SMTP、缺 host 時 fallback。

# Backend Core 模組任務

來源：`proposal.md`、`detailed-design.md` 的 Core、錯誤處理與環境設定章節。

## 完成定義

- FastAPI 應用可啟動。
- 設定、資料庫 dependency、安全工具與統一錯誤格式可被其他模組引用。
- Core 單元測試通過。

## 最小可執行任務

- [x] 建立 `backend/app/main.py`。
- [x] 建立 `backend/app/core/` 目錄。
- [x] 建立 `backend/app/core/config.py`。
- [x] 使用 Pydantic Settings 定義 `Settings`。
- [x] 加入 `DATABASE_URL` 設定欄位。
- [x] 加入 JWT 相關設定欄位。
- [x] 加入 CORS origins 設定欄位。
- [x] 加入 Storage 相關設定欄位。
- [x] 加入上傳大小與預設容量設定欄位。
- [x] 建立 `.env.example`。
- [x] 建立 `backend/app/core/error_codes.py`。
- [x] 定義統一 API error model。
- [x] 建立 application exception 基底類別。
- [x] 建立 FastAPI exception handler。
- [x] 確認錯誤回應符合 `{"error": {...}}` 格式。
- [x] 建立 `backend/app/core/security.py`。
- [x] 安裝並設定 PyJWT。
- [x] 實作 access token encode。
- [x] 實作 refresh token encode。
- [x] 實作 JWT decode 與 token type 驗證。
- [x] 安裝並設定 `pwdlib[argon2]`。
- [x] 實作密碼 hash。
- [x] 實作密碼 verify。
- [x] 建立 `backend/app/core/dependencies.py`。
- [x] 建立取得 DB session 的 dependency。
- [x] 建立取得目前登入使用者的 dependency。
- [x] 設定 API prefix `/api/v1`。
- [x] 設定 CORS middleware。
- [x] 建立 `/health` 健康檢查 endpoint。

## 測試任務

- [x] 測試 Settings 可從環境變數載入。
- [x] 測試密碼 hash 與 verify。
- [x] 測試 access token encode/decode。
- [x] 測試 refresh token 不可作為 access token。
- [x] 測試過期 JWT 被拒絕。
- [x] 測試統一錯誤格式。
- [x] 測試 `/health` 回傳成功。

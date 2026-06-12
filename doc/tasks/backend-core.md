# Backend Core 模組任務

來源：`proposal.md`、`detailed-design.md` 的 Core、錯誤處理與環境設定章節。

## 完成定義

- FastAPI 應用可啟動。
- 設定、資料庫 dependency、安全工具與統一錯誤格式可被其他模組引用。
- Core 單元測試通過。

## 最小可執行任務

- [ ] 建立 `backend/app/main.py`。
- [ ] 建立 `backend/app/core/` 目錄。
- [ ] 建立 `backend/app/core/config.py`。
- [ ] 使用 Pydantic Settings 定義 `Settings`。
- [ ] 加入 `DATABASE_URL` 設定欄位。
- [ ] 加入 JWT 相關設定欄位。
- [ ] 加入 CORS origins 設定欄位。
- [ ] 加入 Storage 相關設定欄位。
- [ ] 加入上傳大小與預設容量設定欄位。
- [ ] 建立 `.env.example`。
- [ ] 建立 `backend/app/core/error_codes.py`。
- [ ] 定義統一 API error model。
- [ ] 建立 application exception 基底類別。
- [ ] 建立 FastAPI exception handler。
- [ ] 確認錯誤回應符合 `{"error": {...}}` 格式。
- [ ] 建立 `backend/app/core/security.py`。
- [ ] 安裝並設定 PyJWT。
- [ ] 實作 access token encode。
- [ ] 實作 refresh token encode。
- [ ] 實作 JWT decode 與 token type 驗證。
- [ ] 安裝並設定 `pwdlib[argon2]`。
- [ ] 實作密碼 hash。
- [ ] 實作密碼 verify。
- [ ] 建立 `backend/app/core/dependencies.py`。
- [ ] 建立取得 DB session 的 dependency。
- [ ] 建立取得目前登入使用者的 dependency。
- [ ] 設定 API prefix `/api/v1`。
- [ ] 設定 CORS middleware。
- [ ] 建立 `/health` 健康檢查 endpoint。

## 測試任務

- [ ] 測試 Settings 可從環境變數載入。
- [ ] 測試密碼 hash 與 verify。
- [ ] 測試 access token encode/decode。
- [ ] 測試 refresh token 不可作為 access token。
- [ ] 測試過期 JWT 被拒絕。
- [ ] 測試統一錯誤格式。
- [ ] 測試 `/health` 回傳成功。


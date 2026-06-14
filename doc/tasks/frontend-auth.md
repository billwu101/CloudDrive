# Frontend Auth 模組任務

## 完成定義

- 使用者可註冊、登入、登出。
- 登入狀態可供 router 與其他元件使用。
- 表單具有必要驗證與錯誤狀態。

## 最小可執行任務

- [x] 建立 auth TypeScript types。
- [x] 建立 `authStore.ts`。
- [x] 定義 access token state。
- [x] 定義 refresh token state。
- [x] 定義 current user state。
- [x] 實作 `setTokens`。
- [x] 實作 `setUser`。
- [x] 實作 `clearAuth`。
- [x] 決定 token 儲存位置並封裝存取。
- [x] 建立 `useCurrentUserQuery`。
- [x] 建立 `useLoginMutation`。
- [x] 建立 `useRegisterMutation`。
- [x] 建立 `useLogoutMutation`。
- [x] 建立 LoginPage。
- [x] 建立 RegisterPage。
- [x] 建立 SettingsPage。
- [x] 從使用者選單提供帳號設定入口。
- [x] 實作顯示名稱與 email 更新表單。
- [x] 實作目前密碼、新密碼與確認密碼表單。
- [x] 更新成功後同步 current user query 與 auth store。
- [x] 使用 React Hook Form。
- [x] 使用 Zod 驗證 email。
- [x] 使用 Zod 驗證密碼。
- [x] 加入確認密碼驗證。
- [x] 顯示登入 loading state。
- [x] 顯示註冊 loading state。
- [x] 顯示 API 錯誤訊息。
- [x] 登入成功後導向 `/drive`。
- [x] 登出後導向 `/login`。

## 測試任務

- [x] 測試 email 驗證。
- [x] 測試密碼必填。
- [x] 測試確認密碼。
- [x] 測試登入成功寫入 store。
- [x] 測試登入失敗顯示錯誤。
- [x] 測試登出清除 store。
- [x] 測試 authStore 安全不變式：access token 不寫入 localStorage/sessionStorage。
- [x] 測試頁面重載後 token 不自動復原（無 persist middleware）。
- [x] 測試帳號設定載入、更新成功與 API 錯誤。
- [x] 測試新密碼確認與成功後清空欄位。

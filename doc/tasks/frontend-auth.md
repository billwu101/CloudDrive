# Frontend Auth 模組任務

## 完成定義

- 使用者可註冊、登入、登出。
- 登入狀態可供 router 與其他元件使用。
- 表單具有必要驗證與錯誤狀態。

## 最小可執行任務

- [ ] 建立 auth TypeScript types。
- [ ] 建立 `authStore.ts`。
- [ ] 定義 access token state。
- [ ] 定義 refresh token state。
- [ ] 定義 current user state。
- [ ] 實作 `setTokens`。
- [ ] 實作 `setUser`。
- [ ] 實作 `clearAuth`。
- [ ] 決定 token 儲存位置並封裝存取。
- [ ] 建立 `useCurrentUserQuery`。
- [ ] 建立 `useLoginMutation`。
- [ ] 建立 `useRegisterMutation`。
- [ ] 建立 `useLogoutMutation`。
- [ ] 建立 LoginPage。
- [ ] 建立 RegisterPage。
- [ ] 使用 React Hook Form。
- [ ] 使用 Zod 驗證 email。
- [ ] 使用 Zod 驗證密碼。
- [ ] 加入確認密碼驗證。
- [ ] 顯示登入 loading state。
- [ ] 顯示註冊 loading state。
- [ ] 顯示 API 錯誤訊息。
- [ ] 登入成功後導向 `/drive`。
- [ ] 登出後導向 `/login`。

## 測試任務

- [ ] 測試 email 驗證。
- [ ] 測試密碼必填。
- [ ] 測試確認密碼。
- [ ] 測試登入成功寫入 store。
- [ ] 測試登入失敗顯示錯誤。
- [ ] 測試登出清除 store。


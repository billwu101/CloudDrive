# Frontend Share 模組任務

## 完成定義

- owner 可透過 UI 分享給指定使用者、更新權限與移除分享。
- 第二階段可建立並複製公開分享連結。
- 與我分享頁可瀏覽被分享項目。

## 最小可執行任務

- [x] 建立 Share TypeScript types。
- [x] 建立 SharedWithMePage。
- [x] 建立 `useSharedWithMe` query。
- [x] 建立 `useShareWithUser` mutation。
- [x] 建立 `useUpdateUserShare` mutation。
- [x] 建立 `useRemoveUserShare` mutation。
- [x] 建立 ShareDialog。
- [x] 建立 UserShareForm。
- [x] 建立 PermissionSelect。
- [x] 建立 ShareMemberList。
- [x] 使用 Zod 驗證 email。
- [x] 驗證 permission 值。
- [x] 顯示分享成功狀態。
- [x] 顯示分享錯誤。
- [x] 移除分享前顯示確認。
- [x] 建立 ShareLinkPanel。
- [x] 建立 `useCreateShareLink` mutation。
- [x] 加入可選密碼欄位。
- [x] 加入可選到期時間欄位。
- [x] 建立複製連結按鈕。
- [x] 顯示連結已複製狀態。
- [x] 建立停用連結操作。

## 測試任務

- [x] 測試 email 驗證。
- [x] 測試 permission 選擇。
- [x] 測試指定使用者分享。
- [x] 測試更新權限。
- [x] 測試移除分享。
- [x] 測試 shared-with-me 列表。
- [x] 測試建立公開連結。
- [x] 測試複製公開連結。


---

## 階段 2 追加：公開連結訪客頁（proposal §28 / DEC-037）

**目標**：把 `/s/:shareToken` 的佔位頁（「Share link access will be implemented in Stage 10」）換成真正可用的訪客頁。
**前置依賴**：backend-share.md「公開連結免認證存取」的端點需先可用。
**設計依據**：§5.9.6。

### 子任務

- [x] `src/api/publicShareApi.ts`：**獨立 axios 實例**，帶 share access token，不掛使用者 token 的 401→refresh 攔截器。
- [x] `src/api/types.ts`：`PublicSessionResult`、`PublicItem` 等型別。
- [x] `src/hooks/usePublicShare.ts`：`usePublicSession()` / `usePublicChildren()`；憑證只放記憶體，不寫 localStorage／sessionStorage。
- [x] `src/pages/ShareTokenPage.tsx`（沿用既有檔名，非新開 `PublicSharePage.tsx`）：取代佔位頁；掛載即以無密碼嘗試開啟 session。
- [x] `src/components/share/PublicPasswordForm.tsx`：僅在後端表示需要密碼時渲染。
- [x] `src/components/share/PublicFolderBrowser.tsx`：資料夾子樹唯讀瀏覽 + 預覽／下載。
- [x] `src/app/router.tsx`：確認 `/s/:shareToken` **不包在 `RequireAuth`**，且 `AuthInitializer` 失敗不導向 `/login`。
- [x] 憑證到期前呼叫 `session/refresh` 續期（不重存密碼）。

### 測試任務

- [x] 未設密碼的連結掛載後直接顯示項目，無密碼欄。
- [x] 需要密碼時顯示表單；密碼錯誤顯示統一錯誤文案。
- [x] token 無效與密碼錯誤的畫面完全相同。
- [x] `viewer` 連結不出現下載按鈕；`downloader` 資料夾連結出現「下載整個資料夾」。
- [x] 訪客頁不會因未登入被導向 `/login`。

### 風險

- 錯誤文案若依後端細節細分，會抵銷後端的不可區分性設計（§6.12.11 第 1 點）——測試需明確守住。

---

## 階段 2 追加：Shared by me 頁面與 My Drive 標記（proposal §29 / DEC-038）

**設計依據**：§5.9.5。

### 子任務

- [x] `src/api/shareApi.ts`：`getSharedByMe()`。
- [x] `src/hooks/useShare.ts`：`useSharedByMe()`、`useDisableShareLink()`。
- [x] `src/pages/SharedByMePage.tsx` + 路由 `/shared-by-me`。
- [x] `src/components/share/SharedByMeRow.tsx`：一列一項目、可展開列出對象與連結；摘要文字「分享給 N 人 · M 個公開連結」。
- [x] 就地移除／停用按鈕；成功後 invalidate `sharedByMe` **與** `drive.items`（讓 My Drive 標記同步更新）。
- [x] 已停用／過期連結灰階並標「已失效」，不隱藏。
- [x] `src/components/layout/Sidebar.tsx`：於「Shared with me」下方新增入口。
- [x] `src/components/drive/ShareBadges.tsx`：兩種圖示（人物／連結），各帶 `aria-label`。
- [x] `src/components/drive/FileRow.tsx` 與 `FileCard.tsx`（實際檔名，非 `DriveItemRow`）：依 `is_shared_with_users` / `has_active_public_link` 渲染 `ShareBadges`——清單與格狀兩種檢視都要標。

### 測試任務

- [x] `SharedByMeRow` 展開後列出全部對象與連結。
- [x] 停用連結後該列即時更新為失效。
- [x] 同一項目多筆分享只呈現一列。
- [x] `DriveItemRow` 兩欄位為真時各自渲染對應圖示；皆為假時不渲染。
- [x] 頁面不提供「收回全部」按鈕（§29.5 決策 3）。

### 驗收條件

proposal §29.3 全部 5 項通過；`npm run lint` / `typecheck` / `npx vitest run --maxWorkers=2` 全綠。


### 追加（實作時發現）

- [x] `src/api/client.ts`：export `BASE_URL` 與 `toApiError`，供訪客用的獨立 axios 實例重用同一套錯誤轉換。
- [x] `src/api/shareApi.ts`：移除 `validateLink()`（後端端點已由 `/public/links/{token}/session` 取代），並刪掉對應測試。
- [x] `src/app/router.test.tsx`：原本斷言佔位頁的 "Shared file" 字樣，改為斷言訪客不會被導向 `/login`。

### 驗證結果（2026-07-26）

前端 **309 passed**（46 檔），含 `ShareTokenPage` 8 項、`SharedByMePage` 7 項、`ShareBadges` 3 項；`lint` / `typecheck` 全綠。

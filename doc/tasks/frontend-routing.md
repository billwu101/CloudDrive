# Frontend Routing 模組任務

## 完成定義

- 公開與受保護路由可正確切換。
- 未登入使用者不能存取雲端硬碟頁面。
- 資料夾、分享連結及錯誤頁路由完成。

## 最小可執行任務

- [x] 建立 `src/app/router.tsx`。
- [x] 建立 `/login` route。
- [x] 建立 `/register` route。
- [x] 建立 `/drive` route。
- [x] 建立 `/drive/folders/:folderId` route。
- [x] 建立 `/shared` route。
- [x] 建立 `/recent` route。
- [x] 建立 `/starred` route。
- [x] 建立 `/trash` route。
- [x] 建立 `/s/:shareToken` route。
- [x] 建立 404 route。
- [x] 建立 `RequireAuth` 元件。
- [x] 未登入時導向 `/login`。
- [x] 登入後保留原始導向位置。
- [x] 已登入時避免停留在 login/register。
- [x] 路由切換時關閉 context menu。
- [x] 路由切換時更新頁面標題。

## 測試任務

- [x] 測試未登入不能進入 `/drive`。
- [x] 測試登入後可進入 `/drive`。
- [x] 測試 folderId route param。
- [x] 測試 404 頁面。
- [x] 測試分享連結頁不要求一般登入。


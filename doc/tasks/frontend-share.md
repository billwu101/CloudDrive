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

### 追加（2026-07-27，使用者回報：失效連結無法清除）

- [x] `src/api/shareApi.ts`：`deleteLinkRecord()`。
- [x] `src/hooks/useShare.ts`：`useDeleteShareLinkRecord()`，成功後同時 invalidate share 與 drive。
- [x] `src/components/share/SharedByMeRow.tsx`：每列連結只出現一顆按鈕——有效顯示「Disable」、失效顯示「Remove」。
- [x] 測試：有效／失效各自顯示正確按鈕、點 Remove 打到 `/record` 端點。

### 調整（2026-07-27）：分享彈窗只留 Copy link

- [x] `src/components/share/ShareLinkPanel.tsx`：移除「Deactivate」按鈕與 `useDeactivateShareLink` 依賴。停用改為一律走「Shared by me」——那裡把使用者分享出去的所有連結列在一起，是「收回權限」該去的地方；分享彈窗是「給出權限」時開的，把停用擺在 Copy link 旁邊只是多一個手滑的機會。
- [x] `ShareDialog.test.tsx`：新增測試釘住「有 Copy、沒有 Deactivate」。

### 翻案（2026-07-27，使用者決定）：Disable 直接改成 Remove

原設計是兩步（有效 → Disable、失效 → Remove），為的是避免「想清掉一行」變成「切斷還在用的連結」。使用者評估後認為兩步的操作成本高於該風險，改為單一動作。

- [x] `backend/app/share/service.py`：`delete_link_record` 移除「必須已失效」的 422 檢查，仍有效的連結也可直接移除；擁有權檢查保留。
- [x] `src/components/share/SharedByMeRow.tsx`：`onDisableLink` / `onDeleteLink` 併為 `onRemoveLink`，按鈕一律顯示「Remove」。
- [x] `src/pages/SharedByMePage.tsx`：不再使用 `useDeactivateShareLink`。
- [x] 測試更新：後端「移除仍有效的連結會直接撤銷」、integration「移除後訪客端立即 404」、前端「每筆分享各一顆 Remove、畫面上沒有 Disable」。

**已知取捨**：一次點擊即不可逆撤銷對外連結，無二次確認、無復原。若誤按成為實際問題，補救是加確認對話框而非退回兩步驟。

---

## 階段 3 追加：editor 連結的訪客編輯 UI（proposal §33 / 設計 §5.9.6 第 8–9 點）

**背景**：後端五個 editor 端點（§6.12.8）與建立連結側的 editor 選項於 2026-07-29 完成，但訪客頁一直停在唯讀——editor 連結開起來與 viewer 無異（顯示「View only」、無下載鈕、無任何編輯 UI），`PublicSession.permission` 型別聯集甚至沒有 `'editor'`。本節補齊訪客側。

**前置依賴**：backend `/public` 的 editor 端點（已完成，migration 0021）。

### 子任務

- [x] `src/api/types.ts`：`PublicSession.permission` 聯集補 `'editor'`。
- [x] `src/api/publicShareApi.ts`：`createSharedFolder` / `uploadSharedFile` / `renameSharedItem` / `moveSharedItem` / `trashSharedItem` 五個 wrapper（沿用既有獨立實例與 `authHeaders()`）。
- [x] `src/pages/ShareTokenPage.tsx`：`canDownload` 改為 `permission !== 'viewer'`；editor 顯示「Can edit」副標；`canEdit` 傳入 `PublicFolderBrowser`。
- [x] `src/components/share/PublicFolderBrowser.tsx`：New folder／Upload 工具列、每列 Rename／Trash（分享根不渲染 Trash）、拖放移動（沿用 `DRAG_MIME`）、失敗訊息、成功後 invalidate `['public-share','children']` 前綴。
- [x] 根目錄不重複顯示名稱：麵包屑只在 `trail.length > 1` 渲染。

### 測試任務

- [x] editor 連結顯示編輯控制與下載按鈕；viewer／downloader 不顯示編輯控制。
- [x] 建立資料夾／改名／垃圾桶／上傳各打到正確端點（upload 以 `request.text()` 驗 multipart——jsdom 的 `File` 過不了 MSW 的 `formData()`）。
- [x] 拖放到資料夾列送出 `PATCH /public/items/{id}/parent`。
- [x] 停在分享根時資料夾名稱只出現一次。

### 驗收條件

proposal §33.4 第 2 點的五種操作皆可從訪客頁 UI 完成；`npm run lint` / `typecheck` / `npx vitest run --maxWorkers=2` 全綠。

### 驗證結果（2026-07-31）

- 前端 **346 passed**（50 檔，含 `ShareTokenPage` 16 項）；lint／typecheck 全綠。
- **瀏覽器實測（dev，三種權限各建一條連結）**：
  - `viewer`：無下載鈕、無編輯控制，根目錄名稱只出現一次。
  - `downloader`：有下載鈕、無編輯控制。
  - `editor`：五種寫入全部從 UI 完成——建資料夾、改名、上傳、垃圾桶、**拖放移動**（拖到資料夾列與拖到麵包屑往上移各驗一次，均送出 `PATCH /public/items/{id}/parent` 並在畫面反映）。
  - 名稱衝突顯示後端訊息（`'review-notes.txt' already exists in this location`）且改名表單保留可修正；失敗的操作**不留稽核**。
  - 密碼保護連結：錯誤密碼與失效連結顯示同一句文案（防枚舉守住）；正確密碼開啟後編輯控制正常。
  - 連結被 Remove 後訪客頁立即顯示「Link unavailable」。
  - console 全程無錯誤。
- **後端閘門（以訪客憑證直打）**：viewer 寫入／下載皆 403；downloader 寫入 403、下載 200；editor 讀寫分享子樹外的項目皆 404，丟棄分享根 400；訪客上傳計入擁有者配額；垃圾桶為軟刪除（進擁有者垃圾桶可還原）。五筆寫入均見於 `activity_logs`，帶正確的 `via_share_link_id` 與 IP。
- **附帶發現**：本機 dev DB 停在 migration 0020，建 editor 連結 500（`ck_share_links_permission` 違反）——`alembic upgrade head` 後復原。凡出現同症狀先查 migration 版本。

---

## 階段 4 追加：訪客編輯頁與 My Drive 對齊（proposal §34 / 設計 §5.9.6 第 10–11 點）

**背景**：§33 的訪客編輯 UI 是「能用」，但與 My Drive 是兩套操作方式——訪客頁只有簡單清單與行內小按鈕，My Drive 有雙檢視、多選、批次操作、右鍵選單與拖曳上傳。本節讓兩者**看起來一樣、操作也一樣**，能力允許範圍內。

**前置依賴**：backend-share.md「訪客多選打包下載」（`POST /public/archive`）。

**核心原則**：**沿用 My Drive 的元件，不另寫一套**。任何「訪客頁專屬的檔案列表元件」都是走錯方向。

### 子任務：讓既有元件可被訪客重用

- [x] `FileCard` / `FileRow` / `FileGrid` / `FileTable`：`item` 型別放寬為共同子集；`is_starred` / `is_shared_with_users` / `has_active_public_link` 改選填，缺席時星號與 `ShareBadges` 不渲染。
- [x] `MoveDialog`：取子資料夾的函式與瀏覽起點參數化（預設為目前的登入版 + 硬碟根）。
- [x] `PreviewDialog`：取預覽內容的函式參數化（預設為目前的登入版）。
- [x] **My Drive 既有測試必須全綠且不需修改**——需要改 `DrivePage` 呼叫端就代表放寬的方式錯了。

### 子任務：訪客頁改用 My Drive 版面

- [x] 格狀／清單雙檢視 + 切換（`viewMode` 可共用 `uiStore`）。
- [x] 勾選多選 + 框選；**選取狀態用訪客頁自己的 local state**，不共用 `uiStore.selectedItemIds`（同瀏覽器同時開 My Drive 會互相污染）。
- [x] `DriveToolbar`：New folder + 選取後的 `Download (N)` / `Trash (N)`。
- [x] `UploadMenu`（檔案／資料夾）+ `UploadDropzone`（桌面拖入）+ `UploadQueue`（含重試）。
- [x] `CreateFolderDialog` / `RenameDialog` / `ConfirmTrashDialog` 取代行內輸入。
- [x] `MultiFileContextMenu`（沿用）+ **訪客版單選右鍵選單**（新元件，無星號／分享／Assistant）。
- [x] `useDragMove` 升級為多選拖放（目前訪客頁一次只拖一項）。
- [x] `MoveDialog` 起點傳分享根。
- [x] `api/publicShareApi.ts`：`archiveSharedItems(itemIds)` 打 `POST /public/archive`。

### 測試任務

- [x] 訪客頁渲染 `FileGrid`／`FileTable`，且不出現星號與 `ShareBadges`。
- [x] 勾選多項後出現 `Download (N)`／`Trash (N)`；下載打到 `POST /public/archive` 並帶正確 ids。
- [x] 訪客右鍵選單不含加星號／分享／Assistant 技能。
- [x] `MoveDialog` 只列得出分享子樹內的資料夾。
- [x] 桌面檔案拖進訪客頁觸發上傳，且不與拖放移動手勢衝突。
- [x] `viewer`／`downloader` 連結不出現任何編輯控制。
- [x] My Drive 既有測試全數通過。

### 驗收條件

proposal §34.5 全部 7 項通過；`npm run lint` / `typecheck` / `npx vitest run --maxWorkers=2` 全綠。

### 驗證結果（2026-07-31）

- 前端 **348 passed**（50 檔）、lint、typecheck 全綠；**My Drive 既有測試無一需要修改**。
- **瀏覽器實測（dev，同一資料夾建三種連結）**：
  - `editor`：版面與 My Drive 一致（卡片格狀、型別圖示、Upload 下拉 + New folder）。實測完成——勾選多選累加成 `Download (2)`／`Trash (2)`；批次下載送出 `POST /public/archive` 200；右鍵選單只有 Preview／Download／Copy name／Rename／Move to／Move to trash（**無星號、無分享、無 Assistant**）；`MoveDialog` 起點是分享根 `AlignTest`、只列得出子樹內的 `Archive`，實際移動送出 `PATCH .../parent` 200；New folder 對話框建立成功；**桌面檔案拖入頁面**觸發上傳並在上傳佇列顯示「Uploaded」；`PreviewDialog` 以訪客端點正確顯示檔案內容；批次垃圾桶經確認對話框送出兩個 `204`。
  - `downloader`：選取後只出現 `Download (1)`，無 Trash、無編輯控制。
  - `viewer`：無工具列、無下載、無編輯控制。
  - 三者皆無星號與分享標記；console 全程無錯誤。
- **狀態確認（非只看畫面）**：訪客丟棄的兩個檔案出現在**擁有者的**垃圾桶（軟刪除可還原）；五筆寫入均見於 `activity_logs`，帶正確的 `via_share_link_id` 與 IP。

### 明確不做（proposal §34.3，實作時不得順手加上）

星號、再分享、`ShareBadges`、Assistant 技能選單、垃圾桶頁。前四項成因相同——那些狀態屬於**使用者或擁有者**，訪客兩者皆非。

---

## 階段 4b：同一份 Drive 本體直接給訪客（2026-07-31 使用者定案）

**背景**：階段 4 用元件拼出的訪客頁仍與 My Drive 有可見差異（右鍵選單項目集合、工具列位置等）。使用者定案：**直接把使用者前端的頁面本體分享給訪客，適度減少功能**——不是拼一個像的，是同一份程式碼。

### 子任務

- [x] 抽出 `DriveExplorer`（`src/components/drive/DriveExplorer.tsx`）：DrivePage 檔案區本體全搬入，動作全部經 `actions` 注入且**選填**——能力缺席＝介面隱藏。
- [x] `FileContextMenu`：`item` 放寬 + `onRename`／`onMove`／`onShare`／`onToggleStar`／`onTrash` 選填（缺席不渲染）；刪除 `PublicContextMenu`。
- [x] `DriveToolbar`：三個 handler 選填。
- [x] `DrivePage` 改為組裝 `DriveExplorer`（注入 uiStore 選取、路由麵包屑、Share／Star／Assistant 能力）；**既有測試不需修改**。
- [x] 訪客頁改為組裝 `DriveExplorer`（注入 local 選取、trail 麵包屑、`/public` 動作；viewer 無能力、downloader 僅下載、editor 除星號／分享／assistant 外全部）。
- [x] 測試更新：訪客右鍵選單與 My Drive 同元件但無 Star／Share／assistant 項。

### 驗收條件

editor 訪客頁與 My Drive 的差異只剩 proposal §34.3 表列五項＋外殼（Sidebar／搜尋／助理）；lint / typecheck / vitest 全綠；瀏覽器實測。

### 驗證結果（2026-07-31）

- 前端 **348 passed**（50 檔）、lint、typecheck 全綠；**DrivePage 既有測試零修改**、訪客頁測試零修改（同名選單項使斷言直接沿用）。
- **瀏覽器實測（dev）**：
  - editor 訪客頁：版面即 My Drive（左麵包屑列＋右 Upload/New folder；名稱只出現一次——資料夾分享的頁首不再印名稱，交給麵包屑，與 My Drive 頂列同款）。**資料夾右鍵選單與 My Drive 同一個元件**：Rename／Move to／Copy name／Move to trash，含分隔線與 danger 樣式；缺的正好是 §34.3 的 Share／Star／assistant。經選單實測 Rename 成功（GuestMade → Reviewed-v2）。
  - My Drive：重構後版面、完整右鍵選單（含 Share／Star／assistant 技能）、卡片星號全部無恙。
  - console 僅有刪除 PublicContextMenu.tsx 當下的 vite HMR 殘響（緩衝殘留，重載後頁面正常），無產品錯誤。

### 再確認（2026-07-31，使用者要求逐項複驗）

逐項對照 My Drive 的檔案區能力，訪客 editor 連結實測：格狀卡片與型別圖示、勾選多選累加（3 項）、**框選**（選取框可見、掃過的項目全被選上）、批次工具列 `Download (N)`／`Trash (N)`、**多選右鍵自動切換為只有 Move to trash**、單選右鍵完整項、雙擊進子資料夾、麵包屑回上層、空資料夾狀態——全部與 My Drive 同行為。

**本次複驗抓到一個真實落差並已修正**：切換資料夾後訪客頁**沒有清除選取**（進子資料夾再回來，舊的 3 個選取還在；My Drive 會清）。原因是這個 effect 只寫在 `DrivePage`。已把它收進 `DriveExplorer`（新增 `folderKey` prop），兩個呼叫端都自動具備，不會再各寫一次而漂移；`DrivePage` 的原 effect 移除，其既有回歸測試仍通過。修正後實測：進 `Sub` 再回 `Compare`，工具列不再顯示 Download／Trash。

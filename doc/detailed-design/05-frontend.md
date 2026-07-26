## 5. 前端詳細設計

### 5.0 使用者介面規劃

**整體版面（受保護頁的 App Shell）**

```text
┌──────────────────────────────────────────────────┐
│ TopBar：Logo │ 全域搜尋列 │             個人選單 ▾ │
├───────────┬──────────────────────────┬───────────┤
│ Sidebar   │ Breadcrumbs（路徑導覽）   │ 詳細資訊  │
│ 我的硬碟  │ Toolbar：新增/上傳・檢視  │ 面板      │
│ 與我分享  │ ┌──────────────────────┐  │ （選取項  │
│ 最近      │ │ FileTable / FileGrid │  │  的中繼   │
│ 星號      │ │   檔案/資料夾清單     │  │  資料）   │
│ 垃圾桶    │ │                      │  │           │
│ 儲存空間  │ └──────────────────────┘  │           │
├───────────┴──────────────────────────┴───────────┤
│                     浮動 AI 助理聊天面板（右下角）  │
└──────────────────────────────────────────────────┘
```

**主要頁面與畫面組成**

| 頁面（路由） | 畫面組成 |
| --- | --- |
| 登入／註冊（`/login`,`/register`） | 置中表單、含驗證；無 Shell |
| 我的硬碟（`/`,`/folder/:id`） | 上述 Shell：麵包屑 + Toolbar + 檔案區（列表/格狀）+ 右鍵選單 + 拖曳上傳 |
| 與我分享（`/shared`） | Sidebar + 分享項目清單 |
| 我分享出去的（`/shared-by-me`） | Sidebar + 可展開的分享一覽（對象／連結）+ 就地移除／停用 |
| 公開連結（`/s/:shareToken`） | **無 Shell、免登入**：密碼表單（有設密碼時）→ 檔案資訊／資料夾唯讀瀏覽 + 預覽／下載 |
| 最近／星號／垃圾桶 | 同硬碟版面，資料來源不同；垃圾桶含還原/永久刪除 |
| 預覽（Dialog） | 圖片/PDF/文字/影片/音訊、Office 文書（Word／Excel／PPT 由伺服器轉 PDF）、Markdown（渲染）；不支援時顯示下載 |
| 分享（Dialog） | 搜尋使用者 email、設權限、建公開連結（密碼/到期） |
| Skills 管理（`/skills`） | 已安裝技能清單 + 編輯/刪除 |
| 時光機（`/time-machine`） | 快照時間軸 + 唯讀瀏覽 + 還原確認 |
| 帳號設定（`/settings`） | 顯示名稱/Email/密碼修改表單 |

**核心互動規格**

- **檢視切換**：列表／格狀（`FileTable` / `FileGrid`）。
- **多選**：點選 + 框選（空白處拖曳矩形即時選取相交項；空白單擊清除；從卡片拖曳不誤觸框選）。
- **右鍵選單**：開啟/預覽/下載/改名/移動/星號/分享/詳細/垃圾桶；已安裝技能依 manifest 動態掛入。
- **拖曳上傳**：拖檔到檔案區觸發 `UploadDropzone`，進度顯示於 `UploadQueue`。
- **每頁狀態**：Loading／Empty／Error／Permission denied／Offline。

> 元件與狀態的實作細節見以下 §5.1～§5.11；元件清單與整體風格的需求面見 proposal §9。

### 5.1 前端技術組合

1. React + TypeScript。
2. Vite。
3. React Router。
4. TanStack Query 管 server state。
5. Zustand 管 UI state。
6. shadcn/ui + Tailwind CSS。
7. React Hook Form + Zod。

### 5.2 Router 設計

```text
/login
/register
/drive
/drive/folders/:folderId
/shared
/shared-by-me
/recent
/starred
/trash
/s/:shareToken
```

受保護頁面需透過 `RequireAuth` 包裝；**`/s/:shareToken` 例外**——它是訪客免登入路徑（§5.9.6），不可包 `RequireAuth`。

### 5.2.1 AuthInitializer

App 啟動時（`App.tsx` 最外層）執行一次 silent refresh，解決頁面重載後 access token 因 in-memory 儲存而消失的問題。

責任：

1. 掛載時透過共用的 `refreshAccessToken()` 呼叫 `POST /auth/refresh`。
2. 成功 → 將 access token 寫入 `authStore`，繼續渲染 router。
3. 失敗（cookie 不存在或過期）→ 不做任何事，讓 `RequireAuth` 導向 `/login`。
4. 等待期間回傳 `null`，阻止 router 在結果未定前搶先重導。
5. `AuthInitializer` 與 Axios 401 interceptor 共用 pending promise，避免 StrictMode 或同時請求重複輪替 refresh token。
6. refresh cookie 在 development/test 不設定 `Secure` 以支援本機 HTTP；staging/production 必須設定 `Secure`。

```tsx
// src/app/AuthInitializer.tsx
export function AuthInitializer({ children }) {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let active = true
    refreshAccessToken().finally(() => {
      if (active) setReady(true)
    })
    return () => { active = false }
  }, [])
  if (!ready) return null
  return <>{children}</>
}
```

### 5.2.2 RequireAuth

責任：

1. 檢查 authStore 是否有 token（`AuthInitializer` 已確保此時結果已定）。
2. 若無 token，導向 `/login`（保留原始 location 供登入後還原）。
3. 若有 token，渲染子路由。
4. 若後續 API 請求收到 401，攔截器自動嘗試 refresh；refresh 失敗則 `clearToken` 並觸發下次路由守衛重導。

### 5.3 API Client 模組

### 5.3.1 責任

1. 統一 base URL。
2. 自動帶上 access token。
3. 處理 401 refresh。
4. 統一解析錯誤格式。
5. 封裝 auth、drive、upload、share、search API。

### 5.3.2 檔案

```text
src/api/client.ts
src/api/authApi.ts
src/api/driveApi.ts
src/api/uploadApi.ts
src/api/shareApi.ts
src/api/searchApi.ts
```

### 5.3.3 可獨立測試項

1. request 會帶 Authorization header。
2. 401 時會呼叫 refresh。
3. refresh 成功後重試原 request。
4. refresh 失敗會清除 authStore。
5. API error 會轉成前端可顯示的錯誤物件。

### 5.4 Auth 前端模組

### 5.4.1 頁面與元件

```text
LoginPage
RegisterPage
AuthForm
```

### 5.4.2 Zustand authStore

```ts
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: CurrentUser | null;
  setTokens(tokens: TokenPair): void;
  setUser(user: CurrentUser): void;
  clearAuth(): void;
}
```

### 5.4.3 TanStack Query

| Query/Mutation | 說明 |
| --- | --- |
| `useCurrentUserQuery` | 取得目前使用者 |
| `useLoginMutation` | 登入 |
| `useRegisterMutation` | 註冊 |
| `useLogoutMutation` | 登出 |

### 5.4.4 可獨立測試項

1. email 格式錯誤時表單阻擋送出。
2. 密碼空白時表單阻擋送出。
3. 登入成功後寫入 token。
4. 登出後清除 token。
5. 未登入使用者不可進入 `/drive`。

### 5.5 Layout 模組

### 5.5.1 責任

Layout 模組負責整體操作框架：

1. Sidebar。
2. TopSearchBar。
3. UserMenu。
4. MainContent。
5. DetailsPanel 擴充點。
6. UploadQueue 固定區塊。

### 5.5.2 元件

```text
AppShell
Sidebar
TopBar
TopSearchBar
UserMenu
StorageUsageBar
```

### 5.5.3 uiStore

```ts
interface UiState {
  sidebarCollapsed: boolean;
  viewMode: "list" | "grid";
  selectedItemIds: Set<string>;   // uses Set for O(1) membership checks
  previewItemId: string | null;
  shareItemId: string | null;
  contextMenu: ContextMenuState | null;
  // actions
  selectItem(id: string, multi?: boolean): void;  // multi=true → toggle without clearing
  selectAll(ids: string[]): void;
  clearSelection(): void;
}
```

### 5.5.4 可獨立測試項

1. Sidebar 可切換收合。
2. viewMode 切換後 DrivePage 顯示列表或格狀。
3. 選取檔案後 toolbar 顯示操作。
4. 關閉 preview dialog 後 previewItemId 清空。
5. 全域 CSS（`index.css`）對 `*` 設定 `user-select: none`，徹底禁止任何 UI 文字被滑鼠選取或複製；`input`、`textarea` 以 `user-select: text` 覆寫，保留表單欄位的正常選取能力。

### 5.6 Drive 前端模組

### 5.6.1 頁面

```text
DrivePage
RecentPage
StarredPage
```

### 5.6.2 元件

```text
DriveToolbar
Breadcrumbs
FileTable            — header checkbox (indeterminate) + onSelectAll
FileGrid
FileRow              — checkbox overlays icon on hover; always visible when selected
FileCard             — absolute-positioned checkbox top-left
FileIcon
FileContextMenu      — single-item right-click menu
MultiFileContextMenu — multi-item right-click menu (count label + trash only)
CreateFolderDialog
RenameDialog
MoveDialog
ConfirmTrashDialog   — supports itemNames: string[] for bulk confirmation
```

**多選行為：**
- Checkbox 點擊 (`onCheckboxClick`) 永遠以累積模式加選，不取代已選範圍。
- `useDragSelect` 監聽 `window` 上的 Pointer Events，超過 5 px 移動門檻後顯示 `position:fixed` 選取框。
- 框選可從 `<main>` 內任意空白處啟動（含檔案列表外的 padding 區域）；Sidebar 與 TopBar 不在 `<main>` 內，從那裡開始拖曳不會啟動選框（以 `closest('main')` 判斷）。
- 框選以 `[data-item-id]` 元素的 `getBoundingClientRect()` 判斷是否與選取框相交，因此格狀檔案卡與列表列都支援。
- 框選只使用滑鼠左鍵；新的框選範圍取代既有選取，不要求搭配 Ctrl/Cmd 等鍵盤按鍵。
- `pointerdown` 時取消原生預設行為並呼叫 `removeAllRanges()`；拖曳期間攔截 `selectstart` 防止文字反白。
- 空白處單擊清除選取；從檔案項目、checkbox、button、link 或其他互動控制開始拖曳時不啟動框選。
- 右鍵點擊已選取的多個項目之一 → 顯示 `MultiFileContextMenu`（僅「移至垃圾桶」）。
- 右鍵點擊未選或單選項目 → 顯示 `FileContextMenu`（完整單一操作）。
- `uiStore.selectAll(ids)` 提供 header checkbox 全選功能。
- 批次移至垃圾桶後自動 `clearSelection()`。

### 5.6.3 Hooks

```ts
useDriveItems(parentId, sort, order, page, pageSize)
useFolderItem(folderId)      // GET /drive/items/{id} — current folder's metadata
useFolderAncestors(folderId) // GET /drive/items/{id}/ancestors — ordered [root → parent]
useCreateFolder()
useRenameItem()
useMoveItem()
useSetStarred()
useMoveToTrash()
useRecentItems()
useDragSelect(containerRef, onSelectIds, onClear)
```

`useFolderItem` + `useFolderAncestors` 一起驅動 DrivePage 的 Breadcrumbs 元件，並提供 ArrowLeft 返回按鈕所需的 `parent_id`。

### 5.6.4 Query Key 設計

```ts
["drive", "items", parentId]         // folder contents
["drive", "item", id]                // single item metadata
["drive", "ancestors", id]           // ancestor chain for breadcrumbs
["drive", "recent"]
["drive", "starred"]
```

### 5.6.5 更新策略

1. 建立資料夾成功後 invalidate `drive-items`。
2. 重新命名成功後 invalidate 相關列表。
3. 移動成功後 invalidate 原資料夾與目標資料夾。
4. 星號成功後 invalidate starred 與目前列表。
5. 移至垃圾桶後 invalidate drive、trash、recent。

### 5.6.6 可獨立測試項

1. 空資料夾顯示 empty state。
2. loading 時顯示 skeleton。
3. API error 時顯示錯誤狀態。
4. 點擊資料夾會進入該 folder route。
5. 點擊檔案會開啟 preview。
6. 右鍵選單會根據 item_type 顯示可用操作。

### 5.7 Upload 前端模組

### 5.7.1 責任

1. 選擇檔案。
2. 拖曳上傳。
3. 呼叫 `/upload/simple`。
4. 顯示進度。
5. 顯示成功、失敗、取消狀態。

### 5.7.2 uploadStore

```ts
interface UploadTask {
  id: string;
  file: File;
  parentId: string | null;
  progress: number;
  status: "pending" | "uploading" | "completed" | "failed" | "cancelled";
  errorMessage?: string;
}

interface UploadState {
  tasks: UploadTask[];
  addTasks(files: File[], parentId: string | null): void;
  updateProgress(id: string, progress: number): void;
  markCompleted(id: string): void;
  markFailed(id: string, message: string): void;
  removeTask(id: string): void;
}
```

### 5.7.3 元件

```text
UploadButton
UploadDropzone
UploadQueue
UploadTaskItem
```

### 5.7.4 分片續傳上傳（proposal §27）

超過 `simpleUploadMaxBytes` 的檔案改走分片流程；其餘仍用 `/upload/simple`。後端端點見 §13.5、服務見 §6.7.7。

> **實作對應（全部完成）**：
>
> - **門檻與上限**：`CHUNKED_UPLOAD_THRESHOLD`（100 MB，對齊後端 `chunked_upload_threshold_bytes`）決定走 `/upload/simple` 或分片；預檢上限為 `MAX_CHUNKED_UPLOAD_SIZE_BYTES`（5 GB），介於兩者之間的檔案走分片而非被拒，只有 >5 GB 才提前失敗。
> - **檔案分工**：`src/lib/uploadLimits.ts`（預檢／並行佇列／錯誤分類，純函式）、`src/lib/chunkedUpload.ts`（建立/續傳工作階段、序列送片、重試、完成、暫停/取消訊號）、`src/lib/uploadPersistence.ts`（localStorage 記未完成工作階段）；`useUploadFiles`／`useUploadFolders` 依大小分派，`useUploadControls` 提供暫停/繼續/取消/重選檔。
> - **錯誤分類**依 `code` 優先於 HTTP 狀態碼：後端 `QUOTA_EXCEEDED` 與檔案過大**同為 413**，僅在無可辨識 `code` 時（例如被 nginx 直接擋下的請求）才以 413 判為檔案過大；分類後的 `errorCode` 存入 `UploadTask.errorCode`。

**送出前預檢**（proposal §27.2 第 7 點）：以 `file.size` 比對單檔上限（5 GB）與剩餘配額，超過者**立即標為失敗且不建立連線**——避免注定失敗的大檔佔住連線、拖垮同批其他檔案。

**上傳佇列與並行**：`uploadStore` 以佇列調度，**同時進行的檔案數上限 3**，其餘排 `queued`；單一檔案的分片**依序**送出（§27.7）。取代原本一次 `Promise.allSettled` 全送的作法。

**單檔分片流程**

```text
create session (回 chunk_size / total_chunks)
  → 依 chunk_index 逐片 file.slice() 後 PUT（序列；失敗自動重試該片）
  → 每片完成即更新進度 = 已完成片數 / 總片數
  → 全部完成 → POST complete → 後端合併、建立檔案
```

**續傳**：工作階段 id 需在瀏覽器關閉後仍存在，故 `uploadStore` 對**未完成任務**持久化 `{ sessionId, fileName, size, parentId }`（此為唯一需要持久化的上傳狀態；`File` 物件無法持久化，恢復時須由使用者重新選取同一檔案）。續傳時先 `GET /upload/sessions/{id}` 取回**已完成分片索引**，只補送缺的分片。

**暫停／繼續／取消**：暫停＝停止送出後續分片（伺服器端仍為 `uploading`，不需通知後端）；繼續＝從缺漏的 index 接續；取消＝呼叫 `DELETE /upload/sessions/{id}` 並移除任務。

**狀態擴充**：`UploadTask` 增加 `sessionId`、`uploadedChunks`、`totalChunks`，`status` 增加 `queued` 與 `paused`；`errorCode` 用於錯誤分類顯示（`FILE_TOO_LARGE`／`QUOTA_EXCEEDED`／連線中斷），取代單一 `Network error` 文案。

### 5.7.5 可獨立測試項

1. 選擇檔案後建立 UploadTask。
2. 拖曳檔案到螢幕任意位置（包含 Sidebar、TopBar）均會建立 UploadTask；`UploadDropzone` 使用 `window` 全域 drag 事件並以 `position:fixed` overlay 覆蓋整個視窗。
3. 上傳中顯示進度。
4. 上傳成功後檔案列表刷新。
5. 上傳失敗後顯示錯誤訊息。
6. 超過單檔上限或配額的檔案，**送出前**即標為失敗且未發出請求。
7. 同時選取超過並行上限的檔案時，超出者狀態為 `queued`，完成一個才遞補。
8. 分片流程：建立工作階段 → 依序送分片 → complete；進度隨已完成片數更新。
9. 續傳：以已完成分片索引只補送缺的分片，不重送已完成者。
10. 暫停後停止送出後續分片；繼續後從缺漏 index 接續；取消會呼叫 DELETE 並移除任務。
11. 錯誤碼分類顯示（`FILE_TOO_LARGE`／`QUOTA_EXCEEDED`／連線中斷），不再一律 `Network error`。

### 5.8 Preview 前端模組

### 5.8.1 責任

1. 呼叫 preview API。
2. 根據 `preview_type` 渲染不同 viewer。
3. **Office 文書**（`document` 型）：後端已轉成 PDF，前端直接重用 `PdfPreview` 顯示 `content` endpoint 回傳的 PDF。
4. **Markdown**（`markdown` 型）：`content` endpoint 回傳原始 Markdown 文字，前端以 `MarkdownPreview`（react-markdown）渲染。
5. 不支援預覽時顯示下載操作。

### 5.8.2 元件

```text
PreviewDialog
ImagePreview
PdfPreview          # 也用於 Office 文書（後端轉 PDF 後）
TextPreview
MarkdownPreview     # react-markdown 渲染
VideoPreview
AudioPreview
UnsupportedPreview
```

### 5.8.3 可獨立測試項

1. image preview 使用 img 顯示。
2. pdf preview 使用 iframe 或 PDF viewer 顯示。
3. text preview 顯示文字內容。
4. `document` 型走 PdfPreview 顯示轉換後的 PDF。
5. markdown preview 以 react-markdown 渲染（非顯示原始碼）。
6. unsupported preview 顯示下載按鈕。
7. preview API 錯誤時顯示錯誤狀態。

### 5.9 Share 前端模組

### 5.9.1 責任

1. 開啟分享彈窗。
2. 輸入 target email。
3. 選擇 permission。
4. 建立指定使用者分享。
5. 顯示與移除既有分享。
6. 公開連結、密碼、到期時間。
7. **「Shared by me」頁面**：一覽並就地管理自己分享出去的項目（§5.9.5，proposal §29）。
8. **`/s/:shareToken` 訪客頁**：免登入開啟公開連結（§5.9.6，proposal §28）。

### 5.9.2 元件

```text
ShareDialog
UserShareForm
PermissionSelect
ShareMemberList
ShareLinkPanel
SharedByMeList          # §5.9.5
SharedByMeRow           # 可展開，展開後列出對象與連結
ShareBadges             # My Drive 列表上的兩種標記
PublicSharePage         # §5.9.6，/s/:shareToken
PublicPasswordForm
PublicFolderBrowser
```

### 5.9.3 Hooks

```ts
useShareWithUser()
useUpdateUserShare()
useRemoveUserShare()
useSharedWithMe()
useSharedByMe()          // GET /share/shared-by-me
useCreateShareLink()
useDisableShareLink()
usePublicSession()       // POST /public/links/{token}/session
usePublicChildren()
```

### 5.9.4 可獨立測試項

1. email 空白不可送出。
2. permission 必須是 viewer、downloader、editor 其中之一。
3. 分享成功後顯示成功狀態。
4. 移除分享後列表更新。
5. 建立公開連結後可複製 URL。

### 5.9.5 Shared by me 頁面（`/shared-by-me`）

Sidebar 於「Shared with me」下方新增入口。

1. **一列一項目**（proposal §29.5 決策 1）：列上顯示項目名稱／型別與摘要（「分享給 2 人 · 1 個公開連結」），展開後才列出每位對象（email／權限／時間）與每條連結（權限／是否設密碼／到期／是否有效）。
2. **就地管理**：每筆對象與連結各自一個移除／停用按鈕，成功後 invalidate `sharedByMe` 與 `drive.items` 兩組 query key（後者讓 My Drive 的標記同步消失）。
3. **不提供「收回全部」**（proposal §29.5 決策 3）。
4. 已停用或已過期的連結以灰階呈現並標「已失效」，不隱藏。

**My Drive 標記**：`DriveItemRow` 依後端新增的兩個布林欄位（§6.12.12）顯示 `ShareBadges`——`is_shared_with_users` → 人物圖示、`has_active_public_link` → 連結圖示，兩者皆真則並列兩個。兩種圖示必須可分辨（proposal §29.5 決策 2），不可合併為單一「已分享」圖示。圖示需帶 `aria-label`（「已分享給其他使用者」／「已建立公開連結」）。

### 5.9.6 公開連結訪客頁（`/s/:shareToken`）

**此路由不得包在 `RequireAuth` 內**，且 `AuthInitializer` 的 silent refresh 失敗不可導向 `/login`——訪客本來就沒有帳號。

流程（對應 proposal §28.4）：

```text
掛載 → POST /public/links/{token}/session（不帶密碼）
  ├─ 200 → 直接顯示內容（未設密碼的連結，不出現密碼欄）
  ├─ 需要密碼 → 顯示 PublicPasswordForm → 帶密碼重送
  └─ 404      → 顯示統一的「連結無效或已失效」
```

1. **憑證只放記憶體**（React state / module 變數），比照 access token 不寫 localStorage／sessionStorage。頁面重整即重新驗證。
2. **密碼不留存**：驗證成功後即丟棄，續期改呼叫 `session/refresh`（§6.12.8）。
3. **錯誤訊息統一**：token 不存在、密碼錯誤、已停用、已過期共用同一則文案，前端不得依後端細節再細分（否則抵銷 §6.12.11 第 1 點的不可區分性）。
4. `viewer` 連結不渲染下載與 zip 按鈕；資料夾連結在 `downloader` 以上顯示「下載整個資料夾」。
5. 內容請求以獨立 axios 實例送出（帶 share access token，不掛使用者 token 的 401→refresh 攔截器）。

#### 可獨立測試項

1. 未設密碼的連結掛載後直接顯示項目，無密碼欄。
2. 需要密碼時顯示表單；密碼錯誤顯示統一錯誤文案。
3. token 無效與密碼錯誤的畫面完全相同。
4. `viewer` 連結不出現下載按鈕。
5. 訪客頁不會因未登入而被導向 `/login`。
6. `SharedByMeRow` 展開後列出全部對象與連結；停用連結後該列更新。
7. `DriveItemRow` 在兩個標記欄位為真時各自渲染對應圖示。

### 5.10 Trash 前端模組

### 5.10.1 頁面與元件

```text
TrashPage
TrashToolbar
RestoreConfirmDialog
PermanentDeleteConfirmDialog
EmptyTrashConfirmDialog
```

### 5.10.2 Hooks

```ts
useTrashItems()
useRestoreItem()
usePermanentDelete()
useEmptyTrash()
```

### 5.10.3 可獨立測試項

1. 垃圾桶列表可顯示已刪除項目。
2. 還原成功後 item 從垃圾桶消失。
3. 永久刪除前必須確認。
4. 清空垃圾桶前必須確認。

### 5.11 Search 前端模組

### 5.11.1 責任

1. 上方搜尋列輸入。
2. debounce。
3. 呼叫搜尋 API。
4. 顯示搜尋結果。
5. 支援檔案/資料夾類型篩選。

### 5.11.2 Hooks

```ts
useSearchItems(query, filters, page, pageSize)
```

### 5.11.3 導覽行為

- 從非 `/search` 頁進入搜尋時，將來源路徑存入 navigate state `{ from: pathname }`。
- 後續 replace 導航（每次 keystroke）攜帶同一份 state 向前傳遞。
- 清空搜尋欄時讀取 `state.from` 精準導回，避免 `navigate(-1)` 因中間 replace history 退到上一個搜尋狀態。

### 5.11.4 可獨立測試項

1. 輸入關鍵字後 debounce 呼叫 API。
2. 清空關鍵字後不查詢，並導回搜尋前頁面。
3. 搜尋結果可開啟 preview 或資料夾。
4. 搜尋錯誤時顯示錯誤狀態。

### 5.12 Settings 前端模組

### 5.12.1 責任

帳號設定頁（`/settings`，`SettingsPage`）讓使用者管理個人資料與外部模型憑證：

1. 修改顯示名稱、登入 Email、密碼（react-hook-form + zod 驗證，逐項即時回饋成功／錯誤）。
2. 管理外部模型憑證（`ExternalModelSettings` 元件）：新增／更新／刪除 per-user 加密憑證，只顯示遮罩（細節見 §11）。

### 5.12.2 元件

```text
SettingsPage
ExternalModelSettings   # 外部模型憑證（components/settings/）
```

### 5.12.3 Hooks 與 API

- 個人資料：`useAuth` 的 `updateUsername`／`updateEmail`／`changePassword` → `authApi` → `PATCH /users/me`、`/users/me/email`、`/users/me/password`。
- 外部憑證：`useExternalCredentials`／`useUpsertExternalCredential`／`useDeleteExternalCredential` → `externalModelApi`（端點見 §11）。

### 5.12.4 可獨立測試項

1. 顯示名稱／Email／密碼各自表單以 zod 驗證；非法輸入阻擋送出。
2. 修改成功顯示成功提示、失敗顯示錯誤訊息。
3. 密碼修改需提供正確的目前密碼。
4. 外部憑證新增／刪除後列表更新；只顯示遮罩、不顯示明文。

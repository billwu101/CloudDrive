# 測試案例總表（API + Playwright）

> 本文件是跑 API 測試與 Playwright E2E 時的**唯一依據**。新增功能要先在這裡補 case，才動工寫測試。
> 相關文件：驗收流程見 `doc/tasks/integration-testing.md`；助理專屬評測見 `doc/eval-prompt-log.md`。

---

## 一、這份文件為什麼存在

本專案已重複發生同一類 bug：**測試全綠，功能實際不能用**。翻過去的 `fix:` commit，逃逸路徑固定是這三條：

| 逃逸路徑 | 真實案例 | 為什麼舊測試抓不到 |
|---|---|---|
| **A. 前端畫得出來，後端沒接上** | `28f1f78` 右鍵 Share 選單存在但沒接 ShareDialog；proposal §33 後端做完前端完全沒接，editor 連結開起來與唯讀無異 | 前端單元測試打 MSW mock，mock 一定回成功；後端整合測試只驗後端。**沒有人驗「這兩端接在一起」** |
| **B. 前後端對不上** | `7a35bb0` 前端 getInfo 打的路徑與後端 `/preview/{id}` 不一致（既有 404）；`4e7ac32` iframe/img 的 src 不會帶 Authorization header，一律 401 | 兩邊各自的測試都會過，因為各自都只跟自己的假資料對話 |
| **C. 渲染出來了，但狀態沒真的改變** | `31c8b67`／`edd8314` PDF 只確認 `<iframe>` 存在就宣稱修好（實際仍不能預覽）；`db5b2b7` 星號清單查詢範圍錯，資料夾內的檔案加星看不到 | 判定準則寫成「元素存在」。**元素存在不等於功能發生** |

因此本文件的每一條 case 都必須標明**驗證強度**，而且規定了下限。

---

## 二、驗證強度分級（本文件最重要的一節）

| 等級 | 驗證到什麼 | 能抓到的 bug | 可否作為通過條件 |
|---|---|---|---|
| **L0 渲染** | 元素存在、文字出現 | 幾乎抓不到任何東西 | **禁止單獨使用**。任何 case 的通過條件都不得只有 L0 |
| **L1 請求** | 實際發出了預期的 request（method + path + body 欄位） | A 類：前端根本沒打後端 | 僅輔助 |
| **L2 回應** | 後端回 2xx，且 body 形狀符合契約 | B 類：端點不存在、404、500、欄位名對不上 | 僅輔助 |
| **L3 落地** | **重新查詢一次**，確認狀態真的改變了 | C 類：後端收了但沒做、寫錯地方、查詢範圍錯 | ✅ 使用者可見功能的**最低通過門檻** |
| **L4 跨主體** | 換一個使用者／session／裝置，確認效果對別人也成立 | 權限只比對 owner（`1c1a63e`）、分享對象看不到 | ✅ 權限與分享類的最低門檻 |

**強制規則**

1. 使用者可見的功能，通過條件**最低 L3**。權限／分享／多人可見性類，**最低 L4**。
2. L3 的「重新查詢」必須是**獨立的一次讀取**：`page.reload()` 後重讀、或改用另一支 API 查、或直接查 DB。**不可以只看前端 local state**——前端樂觀更新會讓畫面正確但後端根本沒存。
3. 斷言禁止只寫 `toBeVisible()`。若必須確認元素，要一併確認其**內容或狀態**（值、數字、disabled、aria-checked）。

---

## 三、全域守門（每個 Playwright 測試都自動套用）

這三個守門比任何個別 case 都有效——它們讓「靜默失敗」不可能發生。

```ts
// e2e/fixtures.ts
export const test = base.extend({
  page: async ({ page }, use) => {
    const errors: string[] = []
    page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })
    page.on('pageerror', e => errors.push(`pageerror: ${e.message}`))
    page.on('response', r => {
      const u = r.url()
      // 未預期的 4xx/5xx 一律視為失敗；個別 case 要測錯誤路徑時自行 allowlist
      if (u.includes('/api/') && r.status() >= 400) errors.push(`HTTP ${r.status()} ${r.request().method()} ${u}`)
    })
    await use(page)
    expect(errors, `偵測到未預期的錯誤：\n${errors.join('\n')}`).toEqual([])
  },
})
```

| 守門 | 抓什麼 |
|---|---|
| **G-1 console 無 error** | React key 警告、未捕捉的 promise rejection、渲染錯誤 |
| **G-2 無未預期 4xx/5xx** | 前端打錯路徑（404）、沒帶 token（401）、後端炸掉（500）。`7a35bb0`、`4e7ac32`、`c2952db` 都會被這條直接抓到 |
| **G-3 無未接線的互動元素** | 見 TC-CONTRACT-02 |

---

## 四、契約層測試（抓 A 類與 B 類，成本最低、報酬最高）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| **TC-CONTRACT-01** | 前端呼叫的每個路徑，後端都有註冊 | L2 | 從 `frontend/src/api/*.ts` 抽出所有請求路徑，逐一比對 FastAPI 的 `app.routes`。**任一條對不上即失敗**。目前後端共 84 個端點（14 個 router）。這條就是 `7a35bb0` 的專屬防線 |
| **TC-CONTRACT-02** | 畫面上每個可點元素都真的會做事 | L1 | 走訪各頁，對每個 button／menu item 點下去，必須產生「發出請求」或「開啟對話框」或「路由變更」三者之一。什麼都沒發生 = 沒接線（`28f1f78`） |
| **TC-CONTRACT-03** | 錯誤回應格式一致 | L2 | 所有 4xx 的 body 為 `{ error: { code, message, details } }`，且 `toApiError()` 讀得到 `code` |
| **TC-CONTRACT-04** | 需要授權的端點沒帶 token 一律 401 | L2 | 對全部受保護端點不帶 Authorization 打一次，必須 401，**不得 200 也不得 500** |
| **TC-CONTRACT-05** | 二進位資源以帶 token 的方式載入 | L1 | 全站不得出現 `<img src="/api/...">`／`<iframe src="/api/...">` 直接指向受保護端點。必須走 blob（`4e7ac32` 的教訓） |

---

## 五、分模組測試案例

### 5.1 Auth（`/auth`，6 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-AUTH-01 | 註冊新帳號 | L3 | 註冊後 reload，仍為登入狀態；`GET /users/me` 回新帳號 |
| TC-AUTH-02 | 密碼不一致擋下 | L2 | 顯示錯誤，且**不得發出** `POST /auth/register` |
| TC-AUTH-03 | 正確帳密登入 | L3 | 導向 `/drive` 且清單載入成功 |
| TC-AUTH-04 | 錯誤密碼 | L2 | 401 + 錯誤訊息；token 未寫入 store |
| TC-AUTH-05 | **重整後仍登入** | L3 | reload → `POST /auth/refresh` 被呼叫 → 停在原頁，**不得閃過 login** |
| TC-AUTH-06 | 未登入訪問保護頁 | L3 | 導向 `/login`，且不得先閃出內容 |
| TC-AUTH-07 | 登出 | L4 | 登出後直接用舊 access token 打 API → 401；refresh cookie 失效 |
| TC-AUTH-08 | **access token 過期自動續期** | L3 | 手動失效 token 後操作，攔截器續期並**重試成功**，使用者無感 |
| TC-AUTH-09 | 忘記密碼寄信 | L3 | mailpit（`localhost:8025`）**收得到信**，非只看 UI 提示 |

### 5.2 Drive（`/drive`，9 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-DRIVE-01 | 建立資料夾 | L3 | reload 後仍在；`GET /drive/items` 回傳含該筆 |
| TC-DRIVE-02 | 重新命名 | L3 | reload 後為新名稱 |
| TC-DRIVE-03 | 同名自動編號 | L3 | 出現 `name (1)`，且 DB 為兩筆獨立紀錄 |
| TC-DRIVE-04 | 移動到子資料夾 | L3 | 原位置消失、目標位置出現，兩邊都要驗 |
| TC-DRIVE-05 | 麵包屑 ancestors | L2 | 深層資料夾的階層完整且順序正確 |
| TC-DRIVE-06 | **加星後在 Starred 頁看得到** | L3 | 特別測**子資料夾內**的檔案（`db5b2b7` 的原始 bug：查詢範圍限縮導致看不到） |
| TC-DRIVE-07 | 取消星號 | L3 | Starred 頁消失 |
| TC-DRIVE-08 | Recent 來自 activity_logs | L3 | 下載一個舊檔 → 該檔升到 Recent 頂端（驗證非取 `updated_at`） |
| TC-DRIVE-09 | **切換資料夾清除選取** | L3 | A 資料夾選 3 項 → 進 B → 選取數為 0（`a8e34a5`／`f4d1e78`） |
| TC-DRIVE-10 | 拖曳框選 | L3 | 框選範圍限 main 區，不含 sidebar／topbar；選取數正確 |
| TC-DRIVE-11 | 全選 checkbox | L3 | 勾選數 == 當頁列數；取消歸零 |
| TC-DRIVE-12 | 勾選框不覆蓋檔案圖示 | L3 | 勾選框與圖示為獨立欄位，兩者同時可見（`39bd07e`） |
| TC-DRIVE-13 | 分頁 | L3 | 第 2 頁內容與第 1 頁無重疊、無遺漏 |

### 5.3 Upload（`/upload`，6 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-UP-01 | 單檔上傳 | L3 | 清單出現 + **下載回來位元組完全一致**（比對 sha256） |
| TC-UP-02 | 分塊上傳 | L3 | 大檔走 session，`complete` 後檔案完整、大小正確 |
| TC-UP-03 | **上傳後配額增加** | L3 | `GET /users/me/quota` 的 used 精確增加該檔大小 |
| TC-UP-04 | 超過配額擋下 | L2 | 413 `QUOTA_EXCEEDED`，**且 storage 沒留下孤兒 blob** |
| TC-UP-05 | 資料夾上傳 | L3 | 目錄結構完整重建，空子資料夾也要在（`810c57f`） |
| TC-UP-06 | 併發上限 3 | L1 | 同時丟 10 個檔，任一時刻進行中的請求 ≤ 3（`0738cb8`） |
| TC-UP-07 | **token 過期時上傳重試不丟 body** | L3 | 上傳中途 token 失效 → 續期重試 → 檔案內容仍完整（`8c49cda`、`d78bdee`） |
| TC-UP-08 | 上傳失敗補償回滾 | L3 | 讓 DB 步驟失敗 → storage 內不得殘留該 blob |
| TC-UP-09 | 危險檔名 | L2 | 含 `/`、`\`、`\x00` 或 >512 字元 → 422，不得寫入 |
| TC-UP-10 | 批次完成狀態收斂 | L3 | 多檔上傳全部結束後，進度列消失、清單筆數正確 |

### 5.4 Preview（`/preview`，2 端點）— 事故熱區，加嚴

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-PREV-01 | **PDF 真的顯示得出來** | L3 | **禁止**只斷言 `<iframe>` 存在。必須確認 `/preview/{id}/content` 回 200、Content-Type 為 `application/pdf`、且回應 body 非空（`31c8b67` 事故本體） |
| TC-PREV-02 | 圖片預覽 | L3 | 取得 blob 且 `naturalWidth > 0`（真的解碼成功，非破圖） |
| TC-PREV-03 | **mime_type 為空的檔案** | L3 | 副檔名可判定時仍須正常預覽，不得誤判「不支援」（`edd8314`） |
| TC-PREV-04 | 預覽走 blob 而非裸 src | L1 | 見 TC-CONTRACT-05；不得出現 401 |
| TC-PREV-05 | 不支援的格式 | L2 | 明確顯示「不支援預覽」+ 提供下載，**不得空白畫面** |
| TC-PREV-06 | 下載端點的 mime fallback | L2 | Download 與 Preview 對同一檔案的 Content-Type 判定一致（`31c8b67`） |

### 5.5 Share（`/share`，8 端點）— 權限熱區，全數 L4

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-SHARE-01 | 分享給指定使用者 | L4 | **以對方帳號登入**，該項目出現在 shared-with-me |
| TC-SHARE-02 | 取消分享 | L4 | 對方重整後看不到，且直接打 API 也 403 |
| TC-SHARE-03 | **viewer 不能編輯** | L4 | 對方以 viewer 身分改名 → 403；UI 也不得提供編輯入口 |
| TC-SHARE-04 | **editor 真的能編輯** | L4 | 對方以 editor 身分改名、上傳、移動皆成功（`1c1a63e`：曾因只比對 owner 而失效） |
| TC-SHARE-05 | 建立公開連結 | L3 | 對話框顯示連結，且**無痕視窗開得起來** |
| TC-SHARE-06 | 複製連結按鈕 | L3 | 剪貼簿內容 == 實際可用的連結 |
| TC-SHARE-07 | **公開連結不可設 editor** | L2 | 回 422 而非 500（`0c84021`） |
| TC-SHARE-08 | 連結密碼 | L4 | 未帶密碼 401；帶正確密碼可存取 |
| TC-SHARE-09 | 連結到期 | L4 | 預設 7 天；過期後 403（`f4d1e78`） |
| TC-SHARE-10 | 右鍵 Share 開得起來 | L1 | 右鍵選單的 Share 必須開啟 ShareDialog（`28f1f78`） |
| TC-SHARE-11 | shared-by-me 列表 | L3 | 建立分享後該頁出現對應紀錄 |

### 5.6 Public Share（`/public`，13 端點）— 訪客身分

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-PUB-01 | 訪客瀏覽共享資料夾 | L4 | **未登入**狀態下清單載入成功 |
| TC-PUB-02 | 訪客下載 | L4 | 位元組一致 |
| TC-PUB-03 | 訪客預覽 | L4 | 同 TC-PREV-01 標準 |
| TC-PUB-04 | 訪客上傳（editor 連結） | L4 | 上傳後**擁有者端**看得到該檔 |
| TC-PUB-05 | 訪客建資料夾／改名／移動／丟垃圾桶 | L4 | 各自 reload 後狀態正確 |
| TC-PUB-06 | **viewer 連結不得有寫入入口** | L4 | UI 無上傳／改名按鈕，且直接打寫入 API → 403 |
| TC-PUB-07 | 打包下載選取項目 | L3 | `POST /public/archive` 帶 item_ids，zip 內含且僅含選取項 |
| TC-PUB-08 | 訪客頁版面與 My Drive 一致 | L3 | 檢查關鍵互動（框選、右鍵）在訪客頁同樣可用 |

### 5.7 Trash（`/trash`，5 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-TRASH-01 | 丟垃圾桶再還原 | L3 | 還原後**回到原本的父資料夾** |
| TC-TRASH-02 | 批次丟垃圾桶 | L3 | 選取數 == 垃圾桶新增數 |
| TC-TRASH-03 | **清空垃圾桶** | L3 | 不得 500。含曾有上傳 session 的項目（`c2952db`、`ff99cca` 外鍵事故） |
| TC-TRASH-04 | 永久刪除釋放配額 | L3 | quota used 精確下降 |
| TC-TRASH-05 | **永久刪除須 dedupe-aware** | L3 | 刪除被快照引用的檔案後，**快照仍還原得出來**（`f9459ce`） |
| TC-TRASH-06 | 父層在垃圾桶的孤兒項目 | L3 | 不得 500（`f4d1e78`） |

### 5.8 Search（`/search`，3 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-SEARCH-01 | 檔名搜尋 | L3 | 剛上傳的檔案搜得到 |
| TC-SEARCH-02 | **內容全文搜尋** | L3 | 用檔案內文字（非檔名）搜得到 |
| TC-SEARCH-03 | 含空白的查詢 | L2 | axios 把空白編為 `+`，後端須正確解析（用 `searchParams.get('q')` 驗） |
| TC-SEARCH-04 | 語意搜尋 | L3 | `EMBEDDING_ENABLED=true` 時回相關結果；關閉時**優雅降級不報錯** |
| TC-SEARCH-05 | 無結果 | L3 | 顯示空狀態，**不得空白頁或轉圈不停** |
| TC-SEARCH-06 | 搜尋結果僅限自己的檔案 | L4 | 他人檔案不得出現 |

### 5.9 File Version / Time Machine（`/drive/{id}/versions`、`/snapshots`）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-VER-01 | 覆寫產生新版本 | L3 | 版本數 +1，各版本內容可分別取回 |
| TC-SNAP-01 | 手動建立快照 | L3 | 時間軸出現該筆 |
| TC-SNAP-02 | **快照不複製 blob** | L3 | 建立快照前後 storage 總大小不變 |
| TC-SNAP-03 | 還原快照 | L3 | 檔案內容回到快照當時 |
| TC-SNAP-04 | 快照顯示「可回收空間」 | L3 | 顯示刪除後能回收多少，非涵蓋量（`d69851c`） |
| TC-SNAP-05 | 排程開關 | L3 | `SNAPSHOT_SCHEDULER_ENABLED=false` 時不產生快照且不報錯 |

### 5.10 Users / Settings（`/users`，5 + 4 端點）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-USER-01 | 改使用者名稱 | L3 | reload 後仍為新名稱 |
| TC-USER-02 | 改 email | L3 | reload 後生效；可用新 email 登入 |
| TC-USER-03 | email 衝突 | L2 | 409 + 錯誤訊息 |
| TC-USER-04 | email 格式錯誤 | L2 | 前端擋下，不發請求 |
| TC-USER-05 | 改密碼 | L4 | 舊密碼登入失敗、新密碼成功 |
| TC-USER-06 | 舊密碼錯誤 | L2 | 400/401 + 訊息 |
| TC-USER-07 | 配額顯示 | L3 | 與 `GET /users/me/quota` 數值一致 |
| TC-USER-08 | **外部模型憑證不回傳明文** | L2 | 回應為遮罩值；DB 內為 Fernet 密文 |

### 5.11 Assistant（`/assistant`，14 端點）

> 助理的**行為品質**由 `backend/eval/` 負責，不在此表。此表只驗**接線與governance**。

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-AI-01 | 對話回覆 | L3 | 回覆非空且無 503（`f42bef5`：gateway 回散文時曾誤報） |
| TC-AI-02 | 唯讀計畫自動執行 | L3 | 不需確認即完成，結果正確 |
| TC-AI-03 | **破壞性計畫必須等確認** | L3 | 未確認前**資料不得改變**（查 DB 確認） |
| TC-AI-04 | 取消計畫 | L3 | 資料完全未變動 |
| TC-AI-05 | 執行失敗誠實回報 | L3 | 回覆由 StepResult 重建，不得出現「已完成」等假陳述（`5f2d92d`） |
| TC-AI-06 | 根目錄哨兵 | L2 | `"root"` 不得炸 Invalid UUID（`99a1aef`） |
| TC-AI-07 | 模型殘骸不落地 | L3 | 帶位元組標記的參數須重新規劃，不得寫進檔名（`e1a3b5b`、`230d656`） |
| TC-AI-08 | 助理看得到垃圾桶項目 | L3 | 依名稱還原成功（`c4b32ba`） |
| TC-AI-09 | 助理關閉時 | L3 | `ASSISTANT_ENABLED=false` 時 UI 隱藏入口，不得出現錯誤 |

---

## 六、跨切面案例（最容易被三種測試都漏掉）

| ID | 場景 | 級 | 判定準則 |
|---|---|---|---|
| TC-X-01 | **每個列表頁的空狀態** | L3 | 全部 10 個受保護路由，新帳號進入皆須顯示空狀態，**無 console error、無無限轉圈** |
| TC-X-02 | **每個列表頁的載入與錯誤狀態** | L3 | 攔截 API 回 500 → 顯示錯誤訊息與重試，不得白畫面 |
| TC-X-03 | 深連結直達 | L3 | 直接輸入 `/drive/folder/{id}` 等 URL，內容正確載入（非導回首頁） |
| TC-X-04 | 404 路由 | L3 | 不存在的路徑顯示 NotFoundPage |
| TC-X-05 | 大清單效能 | L3 | 500 筆項目下捲動不卡死，無 console error |
| TC-X-06 | 同時開兩個分頁 | L4 | 一邊操作、另一邊重整後看得到變更 |

---

## 七、執行方式

```bash
# 後端 API 契約與整合（需 Postgres）
cd backend && uv run pytest tests/integration -v
```

```bash
# Playwright E2E（需先起 docker compose）
cd frontend && npm run test:e2e
```

```bash
# 只跑單一模組的 e2e
cd frontend && npx playwright test e2e/share.spec.ts --reporter=list
```

失敗時的 trace：

```bash
cd frontend && npx playwright show-trace test-results/**/trace.zip
```

---

## 八、維護規則

1. **新增功能必須先在本表補 case**，標明 ID 與驗證級別，才可開始寫程式（對齊 CLAUDE.md「文件先行」）。
2. **每修一個 bug，必須在對應模組表補一條 case**，並在判定準則標註 commit hash——本文件已標註的 hash 都是真實發生過的回歸點，不得刪除。
3. 判定準則出現 `toBeVisible()` 作為唯一斷言時，**視為未完成**。
4. 實測結果回填到 `doc/tasks/<module>.md`。

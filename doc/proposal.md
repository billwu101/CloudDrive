# 雲端硬碟系統需求文件

## 目錄

- [1. 文件目的](#1-文件目的)
- [2. 初版假設](#2-初版假設)
- [3. 待確認問題](#3-待確認問題)
- [4. 專案目標](#4-專案目標)
- [5. 功能範圍](#5-功能範圍)
- [6. 使用者使用情境](#6-使用者使用情境)
- [7. 系統架構](#7-系統架構)
- [8. 前端目錄結構](#8-前端目錄結構)
- [9. 前端頁面規劃](#9-前端頁面規劃)
- [10. 前端狀態管理](#10-前端狀態管理)
- [11. 後端目錄結構](#11-後端目錄結構)
- [12. 資料庫設計](#12-資料庫設計)
- [13. In-App AI Assistant（28 模組之後新增的核心功能）](#13-in-app-ai-assistant28-模組之後新增的核心功能)
- [14. 時光機（Snapshots，核心功能）](#14-時光機snapshots核心功能)
- [15. 權限模型](#15-權限模型)
- [16. API 設計](#16-api-設計)
- [17. 關鍵流程設計](#17-關鍵流程設計)
- [18. 安全性需求](#18-安全性需求)
- [19. 效能需求](#19-效能需求)
- [20. 錯誤處理](#20-錯誤處理)
- [21. 背景任務](#21-背景任務)
- [22. Docker 開發環境](#22-docker-開發環境)
- [23. 環境變數](#23-環境變數)
- [24. 測試計畫](#24-測試計畫)
- [25. 開發里程碑](#25-開發里程碑)
- [26. 驗收標準](#26-驗收標準)
- [27. 風險與對策](#27-風險與對策)
- [28. 結論](#28-結論)

## 1. 文件目的

本文件描述一個參考 Google Drive 與 OneDrive 的雲端硬碟系統**要解決的問題與需求**——功能範圍、使用者目標、使用情境、角色與限制。**實作方式（系統架構、資料庫設計、API 文件、目錄結構、部署細節）由 開發文檔 記錄，不屬本文件範圍。**


### 1.1 閱讀對象與用途

本文件主要供**開發團隊**與 **Claude（AI 協作開發）**參考：

| 對象 | 關注內容 | 文件用途 |
| --- | --- | --- |
| 開發團隊 | 模組邊界、設計取捨、資料一致性、安全模型、待辦與已知限制 | 後續維護、擴充與除錯依據 |
| Claude（AI 協作） | 同上 + 現況落點與檔案對應 | 理解專案現況、協助開發與文件對齊 |

> 交付方／審查者、部署／維運人員**另有專屬的需求與開發文件**，以該文件為主要依據；本文件不為其而寫。

因此，本文件不是一次定稿的早期需求書，而是**隨實作演進的現況式需求文件**：已交付的需求以現況描述，未完成或選用項目以狀態標籤標示，不把尚未交付的功能寫成已完成。

### 1.2 交付文件與內部紀錄分工

完整交付不建議只交一份 30 頁以上的單一檔案。較合理的交付套件如下：

| 文件 | 交付方是否需要 | 說明 |
| --- | --- | --- |
| 正式需求文件（本文件整理版） | 是 | 放功能範圍、使用者目標、使用情境、角色與限制 |
| API 文件、ERD、架構／部署／時序圖（**開發文件紀錄**） | 是 | 端點/request/response/錯誤碼、資料表與權限·搜尋·快照·助理、資料流與部署邊界；皆**由 `detailed-design.md` 與 OpenAPI 匯出／節錄**，供交付方審查 |
| 測試與 Assistant Eval Harness 報告 | 是 | 證明核心流程、E2E、AI agent 評測有被驗證 |

也就是說，`detailed-design.md`、`decisions.md`、`progress.md` 與 `tasks/*.md` 為**內部文件、不納入交付**；正式需求文件本身應能獨立說明系統需求。

### 1.3 文件維護方式

若所有內容都塞在單一檔案，交付時容易閱讀，但後續維護成本高；若全部拆散，審查時又不易理解。建議採用「主文件 + 附錄」：

1. 主文件：控制在可審閱的篇幅，放系統總覽、核心流程、API 摘要、ERD、部署、測試與限制。
2. 附錄：放完整 API 表、完整資料表欄位、環境變數、錯誤碼、路由對照、功能追蹤矩陣。
3. 內部文件：保留 `tasks/` 與原始設計決策，供開發團隊追溯。

## 2. 初版假設

以下是假設條件，若專案需求不同，後續可再調整：

1. 系統是一個多人使用的雲端硬碟，不是單機檔案管理器。
2. 使用者需要登入後才能管理自己的檔案。
3. PostgreSQL 只儲存使用者、檔案中繼資料、權限、分享紀錄、版本紀錄等資料，不直接儲存大型檔案二進位內容。
4. 檔案本體建議儲存在本機檔案系統、MinIO、AWS S3、Azure Blob Storage 或其他物件儲存服務中。
5. 初版可先使用本機儲存或 MinIO，之後再替換成正式雲端物件儲存。
6. 系統優先支援網頁版，不包含桌面同步程式與手機 App。
7. 初版使用帳號密碼登入，之後可擴充 Google、Microsoft OAuth 登入。
8. 初版支援檔案上傳、下載、預覽、資料夾、搜尋、分享連結、垃圾桶、星號標記與近期檔案。

## 3. 待確認問題

在正式開發前，建議先確認下列問題：

1. 使用者來源是否只有本系統帳號，或需要支援 Google、Microsoft、學校 SSO？
2. 檔案儲存位置要使用本機硬碟、MinIO、AWS S3、Azure Blob Storage，還是其他服務？
3. 是否需要多人協作編輯文件，或只需要檔案分享與下載？
4. 是否需要即時通知，例如他人分享檔案給我時跳出通知？
5. 是否需要管理員後台，用於查看使用者、容量、檔案統計與系統紀錄？
6. 單一檔案大小上限是多少？
7. 每位使用者容量上限是多少？
8. 是否需要防毒掃描、敏感檔案封鎖或內容審核？
9. 是否需要支援公開分享連結的密碼與到期時間？
10. 是否需要保留檔案版本紀錄？若需要，最多保留幾版？

## 4. 專案目標

### 4.1 核心目標

建立一個可上傳、分類、搜尋、分享與下載檔案的雲端硬碟系統。使用者可以像使用 Google Drive 或 OneDrive 一樣，透過資料夾階層管理自己的檔案，並能將檔案或資料夾分享給其他使用者或產生公開連結。此外提供兩項進階核心能力：**對話式 AI 助理**（以自然語言操作檔案、現場生成技能與工作流程）與**時光機**（時間點快照，可瀏覽並就地還原過去的硬碟狀態）。

### 4.2 使用者目標

使用者可以：

1. 註冊與登入帳號。
2. 上傳檔案。
3. 建立、重新命名、移動、複製、刪除資料夾與檔案。
4. 透過列表或格狀檢視瀏覽檔案。
5. 透過關鍵字搜尋檔名與檔案資訊。
6. 預覽圖片、PDF、文字檔與常見文件格式。
7. 將檔案標記星號。
8. 查看最近開啟或最近修改的檔案。
9. 把檔案移到垃圾桶，並可還原或永久刪除。
10. 分享檔案或資料夾給指定使用者。
11. 建立公開分享連結。
12. 查看自己的容量使用狀況。
13. 修改帳號設定（顯示名稱、登入 Email、密碼）。
14. 透過對話式 AI 助理，用自然語言操作檔案與執行批次任務。
15. 以時光機瀏覽並就地還原到過去某個時間點的硬碟狀態。

### 4.3 系統目標

系統需要：

1. 保護使用者檔案與權限。
2. 支援大型檔案上傳。
3. 支援可中斷續傳的上傳流程。
4. 維護檔案版本與操作紀錄。
5. 保持清楚的前後端分層。
6. 提供可擴充的儲存層抽象，讓本機儲存能在未來替換成物件儲存。
7. 具備可部署到 Docker 環境的架構。
8. 以本地模型優先執行 AI 助理，資料預設不外流，必要時才升級外部模型。

## 5. 功能範圍

### 5.1 必做功能

即第一版可展示與可使用的核心功能。

1. 使用者註冊、登入、登出。
2. JWT 存取權杖與刷新權杖。
3. 檔案上傳。
4. 檔案下載。
5. 建立資料夾。
6. 檔案與資料夾列表。
7. 檔案與資料夾重新命名。
8. 檔案與資料夾移動。
9. 檔案與資料夾刪除到垃圾桶。
10. 垃圾桶還原與永久刪除。
11. 檔案搜尋。
12. 檔案星號標記。
13. 最近檔案列表。
14. 檔案基本預覽。
15. 私人檔案權限檢查。
16. 容量統計。
17. 帳號設定：修改顯示名稱、登入 Email 與密碼。

### 5.2 第二階段功能

1. 分享給指定使用者。
2. 分享權限分級：可檢視、可下載、可編輯。
3. 公開分享連結。
4. 分享連結密碼。
5. 分享連結到期時間。
6. 檔案版本紀錄。
7. 上傳進度列表。
8. 大檔案分片上傳。
9. 上傳失敗後續傳。
10. 圖片縮圖。
11. PDF 預覽。
12. 操作紀錄。

### 5.3 第三階段功能

1. 管理員後台（系統統計、使用者列表、容量使用狀況、違規檔案處理紀錄）。
2. 使用者容量配額管理。
3. 團隊空間。
4. 共同資料夾。
5. 檔案留言。
6. 檔案標籤。
7. 全文檢索。
8. 防毒掃描。
9. 檔案加密。
10. OAuth 登入。
11. WebSocket 即時通知。
12. 桌面或手機同步客戶端。

### 5.4 In-App AI Assistant（核心）

28 模組之後新增的對話式 AI 助理（自然語言操作檔案、計畫確認、現場生成技能、技能管理、工作流程重用）。完整規格見 **§13**。

### 5.5 時光機（Snapshots，核心）

類 Apple Time Machine 的整碟時間點還原：定期/手動/助理操作前自動建快照，可瀏覽過去某時間點的硬碟並就地還原。完整規格見 **§14**。

### 5.6 暫不包含功能

初版不包含：

1. 線上 Office 文件共同編輯。
2. 桌面同步程式。
3. 手機 App。
4. 複雜企業組織權限。
5. 端對端加密。

## 6. 使用者使用情境

本節列舉**代表性**使用情境（含特殊互動或關鍵業務規則者，如框選、分享、AI 助理、時光機）；**完整功能清單見 §5 功能範圍**，不在此逐一對應。

### 6.1 上傳檔案

1. 使用者進入「我的硬碟」。
2. 使用者點擊上傳按鈕或拖曳檔案到頁面。
3. 前端顯示上傳進度。
4. 後端驗證使用者權限與容量限制。
5. 後端將檔案寫入儲存服務。
6. 後端將檔案中繼資料寫入 PostgreSQL。
7. 前端更新檔案列表。

### 6.2 建立資料夾

1. 使用者點擊新增資料夾。
2. 輸入資料夾名稱。
3. 後端檢查同層是否有重名項目。
4. 建立資料夾紀錄。
5. 前端刷新列表。

### 6.3 分享檔案

1. 使用者選取檔案。
2. 點擊分享。
3. 選擇分享給指定使用者或建立公開連結。
4. 設定權限。
5. 後端建立權限或分享連結紀錄。
6. 收到分享的使用者可以在「與我分享」頁面看到檔案。

### 6.4 框選檔案與資料夾

1. 使用者在「我的硬碟」檔案區空白處按住滑鼠左鍵。
2. 使用者拖曳出選取矩形，所有與矩形相交的檔案與資料夾即時進入選取狀態。
3. 框選只需要按住滑鼠左鍵拖曳，不需要搭配鍵盤按鍵；新的框選範圍會取代既有選取。
4. 在空白處單擊可清除目前選取，從檔案卡片或按鈕開始拖曳不會誤觸框選。

### 6.5 刪除與還原

1. 使用者刪除檔案或資料夾。
2. 系統不立即永久刪除，而是標記為已刪除並移入垃圾桶。
3. 使用者可從垃圾桶還原。
4. 使用者可永久刪除。
5. 系統可定期清除超過保留期限的垃圾桶項目。

### 6.6 管理帳號設定

1. 使用者從個人選單進入帳號設定頁。
2. 使用者可修改顯示名稱與登入 Email。
3. Email 必須是有效格式且不可與其他帳號重複。
4. 使用者輸入目前密碼後，可設定至少 8 個字元的新密碼。
5. 更新成功後，頁面與個人選單立即顯示最新資料。

### 6.7 用 AI 助理操作檔案

1. 使用者以自然語言向助理下指令（例如「把上週的報告搬到 Archive 資料夾」）。
2. 助理解析意圖，產生執行計畫並顯示給使用者確認。
3. 使用者確認後助理依計畫操作；唯讀或非破壞性操作可依權限自動執行。
4. 若缺對應技能，助理現場生成技能，經使用者核可後安裝再執行。
5. 常用流程可存成工作流程，之後一鍵重用。

（完整規格見 §13。）

### 6.8 用時光機瀏覽與還原

1. 系統定期、或使用者手動、或助理執行破壞性操作前，自動建立整碟快照。
2. 使用者開啟時光機，瀏覽過去某個時間點的硬碟狀態。
3. 使用者選定時間點，就地還原整個硬碟或特定項目。

（完整規格見 §14。）

## 7. 系統架構

### 7.1 架構總覽

**前後端分離**：React 前端 ──(HTTPS REST API)──> FastAPI 後端 ──(SQLAlchemy / asyncpg)──> PostgreSQL；檔案 binary 經 Storage Provider 存獨立儲存層（metadata 與 binary 分離，見 §7.5）。後端另內含 **AI 助理引擎**（本地 Gemma + 可選外部 GPT-5.5，見 §7.6）。完整架構圖與分層見 [detailed-design.md](./detailed-design.md) §5。

### 7.2 前端技術

核心：**React + TypeScript + Vite**；伺服器狀態用 TanStack Query、UI 狀態用 Zustand。其餘選型（路由、表單、驗證、樣式庫等）見 [detailed-design.md](./detailed-design.md) §9。

### 7.3 後端技術

核心：**FastAPI + Python 3.12+ + SQLAlchemy 2.x（async）+ PostgreSQL**；Alembic 管 migration、Pydantic 管 I/O 驗證。其餘選型（JWT／密碼雜湊套件、背景工作機制等）見 [detailed-design.md](./detailed-design.md) §6。

### 7.4 資料庫

以 PostgreSQL 儲存：使用者帳號、檔案/資料夾 metadata、權限、分享、檔案版本、上傳工作狀態、操作紀錄與容量統計（各表見 §12）。

### 7.5 儲存層

**設計理由**：檔案本體**不存 PostgreSQL**。DB 為結構化查詢與交易設計，存大型 binary 會使備份/複製肥大、佔用連線記憶體、不利串流，效能也隨檔案量劣化。因此採「metadata 與 binary 分離」：

- **DB 只存 metadata**：檔名、大小、權限、`storage_key`（檔案在儲存層的定位）。
- **檔案 binary 存獨立儲存層**（檔案系統或物件儲存）。
- **取檔流程**：先查 DB（驗權限 + 取 `storage_key`），再用 key 向儲存層取 binary——**權限與定位永遠經過 DB，binary 不經 DB**。
- 儲存層抽象為 **Storage Provider** 介面，底層可換（本地檔案系統／MinIO／S3／Azure Blob）而不動業務邏輯：開發用本地、正式可換物件儲存。

> Provider 介面方法與 `LocalStorageProvider` 實作見 [detailed-design.md](./detailed-design.md) §6.6。

### 7.6 AI 助理引擎

後端內含對話式 **AI 助理引擎**（HARNESS：while loop、context、skills/tools、sub-agents、沙箱、權限與安全）。預設以**本地 Gemma（Ollama）**為執行器，資料不外流；本地反覆失敗時可升級**外部 GPT-5.5**（Codex 訂閱優先、OpenAI key 備援，使用者自帶加密憑證）。驅動自然語言操作檔案、現場生成技能與工作流程重用。完整規格見 §13；引擎設計見 [detailed-design.md](./detailed-design.md) §6 與 [assistant-design.md](./assistant-design.md)。

## 8. 前端目錄結構

前端按職責分層：`api/`（axios 包裝）、`app/`（路由與守衛）、`pages/`、`components/`、`hooks/`（TanStack Query 包裝）、`stores/`（Zustand）。完整目錄見 [detailed-design.md](./detailed-design.md) §9（前端詳細）；實際以 `frontend/src/` 程式碼為準。

## 9. 前端頁面規劃

### 9.1 頁面

- **登入頁** / **註冊頁**：帳號登入、註冊（含表單驗證）。
- **主版面**：左側導覽（我的硬碟／與我分享／最近／星號／垃圾桶／儲存空間）、上方搜尋列、中央檔案區、右側詳細資訊面板。
- **我的硬碟頁**：麵包屑、新增/上傳（檔案/資料夾）、列表/格狀檢視、排序、多選、右鍵選單、拖曳上傳。

### 9.2 整體風格

介面以**實用、清楚、可快速操作**為主（高頻工作型產品，不過度裝飾）：淺色背景、左側固定導覽、上方全域搜尋、清楚的檔案列表、足夠留白、操作按鈕用圖示搭配 tooltip；重要操作（如刪除、永久刪除）需確認。

### 9.3 主要元件

`Sidebar`、`TopSearchBar`、`Breadcrumbs`、`FileToolbar`、`FileTable`、`FileGrid`、`ContextMenu`、`UploadDropzone`、`UploadQueue`、`PreviewDialog`、`ShareDialog`、`ConfirmDialog`、`StorageUsageBar`。

互動重點：上傳佇列含進度/速度/暫停/繼續/取消/重試；預覽支援圖片／PDF／文字／影片／音訊（不支援時顯示下載）；分享彈窗含搜尋使用者、設權限、建公開連結（到期/密碼）、複製、移除對象。

### 9.4 狀態設計

每個頁面都要設計：Loading、Empty、Error、Permission denied、Offline/retry 狀態。

> 各頁面/元件的詳細結構與 props 見 [detailed-design.md](./detailed-design.md) §9。

## 10. 前端狀態管理

建議狀態分工：

1. Auth state：登入狀態、token、目前使用者。
2. Drive query state：目前資料夾、排序、分頁、搜尋條件。
3. Upload state：上傳佇列與進度。
4. UI state：側邊欄、預覽窗、分享彈窗、右鍵選單。

建議：

1. 伺服器資料使用 TanStack Query。
2. UI 狀態使用 Zustand。
3. 表單使用 React Hook Form。
4. schema 驗證使用 Zod。

## 11. 後端目錄結構

後端按**模組**組織：每個 domain 為一個自足套件（`app/<module>/`，含 `router.py` / `service.py` / `repository.py` / `schemas.py`），模組之間只透過 service 注入互動、不互相 import 內部。

各層職責分明：

- **Router**：接收 HTTP request、驗證 request schema、呼叫 service、回傳 response。
- **Service**：商業邏輯、權限判斷、容量判斷、呼叫 repository 與 storage provider。
- **Repository**：資料庫查詢、transaction 管理、封裝 SQLAlchemy 操作。
- **Storage Provider**：儲存／讀取／刪除檔案、建立短效下載 URL。

**模組清單**（每個為 `app/<module>/` 套件）：

- **對外模組**（含 `router.py`）：`auth`、`drive`、`upload`、`download`、`file_version`、`share`、`search`、`trash`、`preview`、`users`、`assistant`、`snapshot`、`external_model`。
- **內部服務模組**（無對外 router，由其他 service 注入）：`activity_log`（操作紀錄）、`permission`（權限判斷）。
- **支撐層**：`core`（設定／JWT 安全／例外／錯誤碼／依賴注入）、`db`（session）、`models`（SQLAlchemy ORM）、`schemas`（共用回應型別）、`api/v1/router.py`（聚合各模組 router）、`storage`（StorageProvider 抽象：本地／物件儲存）、`email`（寄信抽象：console／SMTP）。

完整目錄與模組邊界見 [detailed-design.md](./detailed-design.md) §4（模組拆分原則）與 §6（後端核心）；實際以 `backend/app/` 程式碼為準。

## 12. 資料庫設計

### 12.0 欄位型別與長度原則

資料庫欄位使用 `varchar` 或 `text` 的原則如下：

| 類型 | 建議型別 | 依據 |
| --- | --- | --- |
| 枚舉狀態、短代碼 | `varchar(20~100)` | 例如 `status`、`permission`、`item_type`，長度有限且常用於索引或檢查 |
| Email、username、hash、token hash | `varchar(255)` | 255 是常見帳號識別欄位上限，可避免異常長字串 |
| 檔名 | `varchar(512)` | 檔案系統與瀏覽器上傳可能出現較長名稱，仍需上限防止濫用 |
| checksum | `varchar(64)` | SHA-256 hex 固定 64 字元 |
| MIME type | `varchar(255)` | MIME type 字串長度有限 |
| 使用者輸入長文、manifest code、storage key、URL、加密 secret | `text` | 長度不固定，不適合硬切；由 service 層與欄位用途控制 |
| 結構化流程、metadata | `jsonb` | 方便保存 workflow steps、activity metadata、manifest 等半結構化資料 |

長度選擇不是任意值：`50` 多用於狀態/類型，`100~200` 用於技能或 workflow 名稱，`255` 用於帳號、hash 或外部識別字，`512` 用於檔名。正式文件若列資料表欄位，應同時說明這些限制來自「業務意義 + 防止不受控輸入 + 索引效率」。

### 12.1 users

**需求**：儲存使用者帳號。`email` 為唯一登入識別；每位使用者有容量上限與已用量；需區分啟用狀態與管理員身分；密碼僅存雜湊、不存明文。

> 欄位、型別與索引（DDL）見 [detailed-design.md](./detailed-design.md) §7.1。

### 12.2 drive_items

**需求**：統一儲存檔案與資料夾，以 `item_type` 區分。同一資料夾下未刪除項目**不可同名**；上傳同名檔案時，MVP 預設保留兩者並自動命名 `filename (1).ext`，亦可改為取代並建新版本或由使用者選擇。支援星號、垃圾桶（軟刪除）、建立/修改者追蹤。

> 欄位、索引（含同資料夾不重名約束、名稱 trigram 搜尋）與資料夾樹策略見 [detailed-design.md](./detailed-design.md) §7.3。

### 12.2.1 user_item_preferences

**需求**：每位使用者對檔案項目的個人化偏好（目前主要是星號）。**星號以本表為準，不放在 `drive_items`**——分享檔案時每位使用者的星號應互不影響；若放在 `drive_items`，一人加星號會污染其他使用者看到的狀態。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.3.1。

### 12.3 file_versions

**需求**：儲存檔案的歷史版本，支援版本回溯。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.4。

### 12.4 shares

**需求**：對指定使用者的分享權限。權限分 `viewer`（檢視/預覽）、`downloader`（可下載）、`editor`（可改名/移動/上傳新版本）。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.5。

### 12.5 share_links

**需求**：公開分享連結，支援權限（`viewer`/`downloader`）、選用密碼、選用到期時間、啟用開關。**資料庫只存 token 與密碼的 hash，不存明文**；明文 token 僅在建立時回傳前端一次。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.6。

### 12.6 upload_sessions

**需求**：支援大型檔案分片上傳。session 狀態機：`pending` → `uploading` → `completed` / `failed` / `cancelled`；完成後建立對應的 `drive_item`。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.7。

### 12.7 upload_chunks

**需求**：記錄各分片（編號、暫存位置、大小、checksum），供完成時組裝與驗證。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.7。

### 12.8 activity_logs

**需求**：記錄使用者操作（`upload`/`download`/`rename`/`move`/`delete`/`restore`/`share`），含操作者、對象、metadata、IP、瀏覽器資訊，供稽核與「最近」功能。

> 欄位見 [detailed-design.md](./detailed-design.md) §7.8。

## 13. In-App AI Assistant（28 模組之後新增的核心功能）

原 28 模組完成後，於網頁應用內新增一個**可對話、可自我擴充的 AI 助理**。使用者用自然語言描述需求，助理把需求轉成**可檢視、可確認、可執行、可記錄的 Workflow**，以既有或現場生成的技能完成檔案／資料夾操作。完整設計見 [assistant-design.md](./assistant-design.md)，評測見 [assistant-eval-design.md](./assistant-eval-design.md)，決策見 [decisions.md](./decisions.md) 的 DEC-016～023。

### 13.1 功能範圍

- **對話操作**：登入後 CloudDrive shell 內的浮動聊天面板，用自然語言列檔／搜尋／整理／改名／移動／分享／壓縮解壓等。
- **計畫確認**：寫入/破壞性操作先產生計畫（步驟、權限層級、是否需確認），唯讀操作可 fast-path 自動執行；使用者確認後才執行，破壞性操作**絕不自動執行**。
- **現場生成新技能**：缺少的能力由助理現場生成（例如「做一個 7zip 解壓縮功能」），經 **codegen → 靜態驗證（codeguard）→ 使用者核可 → 受限沙箱執行**，產出檔案寫回 drive。
- **技能管理**：側欄 **Skills 頁（`/skills`）**檢視已安裝技能數量、編輯（描述/程式碼，改碼重跑 codeguard）、刪除。
- **工作流程重用**：計畫可命名儲存，之後一鍵重跑。
- **動態 UI**：已安裝技能依 manifest 動態掛到檔案右鍵選單；使用者訊息列提供複製鈕（前端全域禁止反白，故以按鈕程式複製）。
- **模型策略**：預設本地 Gemma（Ollama），達失敗上限且符合隱私條件時才條件式升級外部模型；隱私敏感且無法去識別化則不外送。

### 13.2 前端目錄（補充 §8）

```
src/components/assistant/  AssistantPanel MessageBubble WorkflowPlanCard
                           SkillApprovalCard SkillApprovalDialog SkillEditDialog
                           SavedWorkflowsPanel AssistantSkillResultDialog StepResultList
src/pages/SkillsPage.tsx           # 側欄 Skills 管理頁（/skills）
src/api/assistantApi.ts  src/hooks/useAssistant.ts
frontend/e2e/assistant/assistant-eval.spec.ts  frontend/playwright.eval.config.ts
```

### 13.3 後端目錄（補充 §11）

```
app/assistant/
  router.py service.py repository.py context.py schemas.py hooks.py
  planner.py workflow.py permissions.py subagent.py
  llm/      client.py ollama.py external.py router.py privacy.py
  skills/   registry.py manifest.py authoring.py sandbox.py codeguard.py builtin/
backend/eval/   schema.py runner.py inproc.py runner_browser.py verifier.py
                judge.py scoring.py baseline.py report.py state.py run.py cases/
```

### 13.4 前端頁面（補充 §9）

- **聊天面板**：浮動於各受保護頁；訊息泡泡、計畫確認卡、技能核可/程式碼審查、已存工作流程清單、使用者訊息複製鈕。
- **Skills 管理頁（`/skills`）**：已安裝技能列表（數量、描述、右鍵動作、更新時間）+ 編輯/刪除。

### 13.5 環境變數（補充 §23）

`ASSISTANT_ENABLED`、`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`ASSISTANT_MODEL`、`LLM_NUM_CTX`、`LLM_TIMEOUT_SECONDS`、`LLM_KEEP_ALIVE`、`ASSISTANT_MAX_TOOL_ITERATIONS`、`ASSISTANT_SANDBOX_TIMEOUT_SEC`、`EXTERNAL_LLM_ENABLED`、`MAX_LOCAL_ATTEMPTS`、`EXTERNAL_LLM_BASE_URL`/`EXTERNAL_MODEL`/`EXTERNAL_LLM_API_KEY`、`PRIVACY_DEFAULT`。設計建議模型為本地 Gemma 4 26B（`gemma4:26b`）；實際部署可用 `ASSISTANT_MODEL` 覆寫。

### 13.6 安全（補充 §18）

- 生成程式碼**絕不自動執行**：經 codeguard AST 靜態掃描（拒禁用 import/`eval`/dunder/錯誤簽章）→ 使用者核可 → 受限子行程沙箱（`python -I`、CPU/檔案 rlimit、`addaudithook` 封鎖網路/spawn/越界寫入）。編輯既有技能同樣重跑 codeguard。
- 沙箱檔案存取限該使用者 storage；所有動作可記入 activity_logs。詳見 DEC-019。

### 13.7 測試與評測（補充 §24）

- 前端 `components/assistant/*.test.tsx`、後端 `tests/assistant/`。
- 獨立評測 harness `backend/eval/`：YAML 案例 + 確定性斷言（workflow/state/safety）+ 可選 LLM judge；多次執行通過率/變異；baseline 回歸；三種 runner（in-process mock〔CI 預設、決定性〕、API〔`--llm real`〕、Browser〔Playwright〕）。

## 14. 時光機（Snapshots，核心功能）

類 Apple Time Machine 的整碟時間點還原。完整設計見 [time-machine-design.md](./time-machine-design.md)，決策見 DEC-024。**狀態：S1-S5 已實作並測試完成；仍有非阻擋限制：還原時硬配額檢查待補強。**

### 14.1 功能範圍

- **快照**：整個雲端硬碟在某時間點的狀態（哪些檔案/資料夾存在、名稱、位置、版本）。增量儲存——未變更檔案以 `checksum_sha256` 共用既有內容，不重複存。
- **三種觸發**：(1) 自動排程（使用者設定預設開啟、每小時；服務內建排程器由 `SNAPSHOT_SCHEDULER_ENABLED` 控制，compose 單 worker 預設開）；(2) 手動「立即建立快照」；(3) **助理執行寫入/破壞性 workflow 或生成式 skill 前自動建快照**（每個 workflow/skill 一個），可一鍵回到助理操作前。
- **時間軸瀏覽**：依時間列出快照，點任一快照唯讀瀏覽當時的硬碟。
- **就地還原**：把單檔／資料夾子樹／整碟還原到所選時間點，**覆蓋現況**（救回被刪檔、回復改名/搬移/內容）。子樹/整碟還原時可選 `keep_new`（保留現有新增）或 `exact_mirror`（精確鏡像）。還原前自動先建「還原前保命快照」，可再倒回；走 service 層套配額與權限。
- **保留與配額**：保留最近 N 個快照（預設 50，可設），釘選與保命快照豁免；快照空間**不計入檔案配額，另設獨立快照配額（預設為檔案配額的一半）**；刪快照的內容由背景 GC 回收。排程快照需設定開啟、距最近快照已達間隔且 drive 目前至少有一個 item；空碟不建立排程快照。
- **協作**：分享/協作項目僅擁有者可還原。

### 14.2 重用既有模組

建立在既有元件之上：`file_versions`（內容層）、`drive_items` 的名稱/父層/刪除旗標（可還原改名/搬移/刪除）、Trash（互補）、`activity_logs`（稽核）、Storage 的 checksum 去重、背景任務（排程與縮減）、Assistant（執行前快照）。

### 14.3 新增資料表

- 新表 `snapshots`、`snapshot_entries`、`snapshot_settings`（見設計文件 §7）。

### 14.4 前端頁面

側欄「時光機」入口（`/time-machine`）：快照時間軸、進入快照唯讀瀏覽、還原確認流程（明示覆蓋、已建保命快照、可選 subtree_mode）、保留數/排程/獨立快照配額設定。

## 15. 權限模型

### 15.1 權限類型

| 權限 | 說明 |
| --- | --- |
| owner | 擁有者，可執行所有操作 |
| editor | 可重新命名、移動、上傳新版本 |
| viewer | 可檢視與預覽 |
| downloader | 可檢視與下載 |

### 15.2 權限判斷順序

1. 若 user_id 等於 item.owner_id，擁有 owner 權限。
2. 若 item 透過 shares 分享給該使用者，依 shares.permission 判斷。
3. 若透過 share_links 存取，依 link.permission 判斷。
4. 若資料夾被分享，子項目應繼承資料夾權限。
5. 若以上皆不符合，拒絕存取。

### 15.3 權限注意事項

1. 後端每個檔案操作都必須檢查權限。
2. 前端隱藏按鈕只是使用者體驗，不能取代後端權限檢查。
3. 分享連結 token 不應直接儲存明文。
4. 資料夾權限繼承要避免查詢過慢，必要時可以建立 permission cache。

## 16. API 設計

API base path：`/api/v1`。下表為各端點對應的動作（介面需求）；**完整 request/response 規格見 OpenAPI 匯出（程式碼自動生成）** 與 [detailed-design.md](./detailed-design.md) §8（通用規則：統一錯誤格式、分頁、`DriveItemResponse`、API↔模組對應）。

### 16.1 Auth API

| 端點 | 動作 |
| --- | --- |
| `POST /auth/register` | 註冊使用者 |
| `POST /auth/login` | 登入（回 access token + refresh token） |
| `POST /auth/refresh` | 刷新 access token |
| `POST /auth/logout` | 登出並使 refresh token 失效 |
| `GET /auth/me` | 取得目前登入使用者 |

### 16.2 Drive API

| 端點 | 動作 |
| --- | --- |
| `GET /drive/items` | 取得指定資料夾底下的檔案與資料夾（支援 sort/order/分頁） |
| `POST /drive/folders` | 建立資料夾 |
| `PATCH /drive/items/{item_id}/name` | 重新命名 |
| `PATCH /drive/items/{item_id}/parent` | 移動檔案或資料夾 |
| `PUT /drive/items/{item_id}/star` | 設定星號 |
| `GET /drive/items/{item_id}/download` | 下載檔案（串流或短效下載 URL） |
| `GET /drive/items/{item_id}/preview` | 取得預覽資訊 |

### 16.3 Upload API

| 端點 | 動作 |
| --- | --- |
| `POST /upload/simple` | 小檔案直接上傳 |
| `POST /upload/sessions` | 建立分片上傳工作 |
| `PUT /upload/sessions/{session_id}/chunks/{chunk_index}` | 上傳單一分片 |
| `POST /upload/sessions/{session_id}/complete` | 合併分片並建立檔案紀錄 |
| `DELETE /upload/sessions/{session_id}` | 取消上傳 |

### 16.4 Search API

| 端點 | 動作 |
| --- | --- |
| `GET /search` | 搜尋檔案 |

### 16.5 Trash API

| 端點 | 動作 |
| --- | --- |
| `GET /trash` | 取得垃圾桶項目 |
| `PATCH /trash/{item_id}/restore` | 還原項目 |
| `DELETE /trash/{item_id}` | 永久刪除項目 |
| `DELETE /trash` | 清空垃圾桶 |

### 16.6 Share API

| 端點 | 動作 |
| --- | --- |
| `POST /share/items/{item_id}/users` | 分享給指定使用者 |
| `GET /share/shared-with-me` | 取得與我分享的檔案 |
| `POST /share/items/{item_id}/links` | 建立公開分享連結 |
| `DELETE /share/links/{link_id}` | 停用分享連結 |

### 16.7 Assistant API

前綴同 `/api/v1`；完整流程見 [assistant-design.md](./assistant-design.md)。

| Method | Path | 用途 |
|---|---|---|
| POST | `/assistant/chat` | 對話；回計畫或技能提案；記錄 session/訊息 |
| GET | `/assistant/sessions`、`/assistant/sessions/{id}/messages` | 對話歷史 |
| POST | `/assistant/workflows/{id}/confirm` · `/cancel` | 確認/取消 pending 計畫 |
| POST | `/assistant/workflows/save`、GET `/workflows/saved`、POST `/workflows/saved/{id}/rerun` | 命名儲存與一鍵重跑 |
| GET | `/assistant/skills?status=installed` | 列出已安裝技能 |
| POST | `/assistant/skills/{id}/approve` · `/execute` | 核可安裝 / 執行（生成技能於沙箱執行並寫回 drive） |
| PATCH | `/assistant/skills/{id}` | 編輯描述/程式碼（改碼重跑 codeguard） |
| DELETE | `/assistant/skills/{id}` | 刪除技能（連同右鍵動作）；回 204 |

### 16.8 Time Machine API

前綴同 `/api/v1`；完整設計見 [time-machine-design.md](./time-machine-design.md)、資料表見 §14.3。

| 端點 | 動作 |
| --- | --- |
| `POST /snapshots` | 建立快照 |
| `GET /snapshots` | 列出快照 |
| `GET /snapshots/{id}/items` | 瀏覽快照內容 |
| `POST /snapshots/{id}/restore` | 還原到所選快照 |
| `GET/PUT /snapshots/settings` | 讀取／更新快照設定 |

## 17. 關鍵流程設計

### 17.1 小檔案上傳流程

```text
User selects file
  -> Frontend sends multipart/form-data
  -> Backend checks auth
  -> Backend checks quota
  -> Backend saves file to storage
  -> Backend creates drive_items row
  -> Backend updates used_bytes
  -> Frontend refreshes file list
```

一致性處理：

1. storage key 由系統產生，不使用原始檔名，避免路徑穿越與重名衝突。
2. 上傳流程先寫入 storage，再建立 `drive_items` 與 `file_versions`；若資料庫流程失敗，service 會嘗試刪除剛寫入的 blob，避免留下孤兒檔案。
3. 永久刪除時先移除 metadata 與配額，再由 snapshot-aware GC 判斷 blob 是否仍被快照引用；不能確認安全刪除時保留 blob，交由後續 GC 回收。
4. PostgreSQL transaction 無法包住外部檔案系統，因此正式維運可加週期性 storage audit：找出「storage 有但 DB 無」與「DB 有但 storage 無」的差異並產生修復報告。

### 17.2 分片上傳流程

```text
User selects large file
  -> Frontend creates upload session
  -> Frontend splits file into chunks
  -> Frontend uploads chunks concurrently
  -> Backend records uploaded chunks
  -> Frontend calls complete
  -> Backend merges chunks or completes multipart upload
  -> Backend creates drive_items row
  -> Backend updates used_bytes
```

### 17.3 下載流程

```text
User clicks download
  -> Backend checks permission
  -> Backend logs download activity
  -> Backend streams file or returns temporary signed URL
  -> Browser downloads file
```

### 17.4 搜尋流程

```text
User enters keyword
  -> Frontend debounces input
  -> Frontend calls /search
  -> Backend filters accessible files
  -> PostgreSQL searches names and metadata
  -> Backend returns paginated result
```

### 17.5 垃圾桶流程

```text
Delete item
  -> Mark is_deleted = true
  -> Set deleted_at
  -> Hide from normal file list
  -> Show in trash

Restore item
  -> Check parent still exists
  -> Resolve naming conflict if needed
  -> Mark is_deleted = false

Permanent delete
  -> Delete file from storage
  -> Delete metadata or mark as purged
  -> Update quota
```

## 18. 安全性需求

### 18.1 身分驗證

1. 使用 access token 與 refresh token。
2. access token 有效時間建議 15 到 30 分鐘。
3. refresh token 有效時間建議 7 到 30 天。
4. refresh token 需可撤銷。
5. 密碼使用 bcrypt 或 argon2 雜湊。
6. access token 僅存於前端記憶體（不寫 localStorage／sessionStorage）、refresh token 存 HttpOnly cookie；頁面重整後以 **silent refresh**（app 啟動時呼叫 `POST /auth/refresh`）用 refresh cookie 續期維持登入，失敗則導向登入。實作見 [detailed-design.md](./detailed-design.md) §9.2.1。

### 18.2 權限安全

1. 所有檔案操作必須在後端檢查權限。
2. 使用者不得透過猜測 UUID 存取他人檔案。
3. 分享連結 token 需足夠長且不可預測。
4. 分享連結可設定失效。

### 18.3 上傳安全

1. 限制單檔大小。
2. 限制使用者總容量。
3. 檢查 MIME type。
4. 檢查副檔名。
5. 避免使用原始檔名作為 storage_key。
6. 對可疑檔案執行防毒掃描。
7. 禁止路徑穿越，例如 `../../secret.txt`。

### 18.4 API 安全

1. 啟用 CORS 白名單。
2. 限制登入嘗試頻率。
3. 對上傳 API 加上 rate limit。
4. 使用 HTTPS。
5. 避免在錯誤訊息洩漏內部路徑。
6. API response 不回傳 password_hash、token_hash 等敏感欄位。

## 19. 效能需求

### 19.1 前端效能

1. 檔案列表使用分頁或虛擬滾動。
2. 搜尋輸入使用 debounce。
3. 大量檔案上傳時避免造成 UI 卡頓。
4. 縮圖使用 lazy loading。
5. 預覽視窗按需載入。

### 19.2 後端效能

1. 檔案下載使用 streaming response 或 signed URL。
2. 大檔案使用分片上傳。
3. 搜尋欄位建立索引。
4. 熱門查詢可於後續引入 cache；目前版本不要求 Redis。
5. 縮圖產生放入背景任務。

### 19.3 資料庫效能

1. drive_items 依 owner_id、parent_id 建索引。
2. 搜尋名稱使用 pg_trgm。
3. activity_logs 可依時間分區。
4. 大型 JSON metadata 避免過度查詢。
5. 列表查詢只取必要欄位。

## 20. 錯誤處理

**需求**：API 採統一錯誤格式 `{ "error": { "code", "message", "details" } }`，前端依 `code` 顯示對應訊息——涵蓋未授權、權限不足、找不到、同層重名、容量不足、檔案過大、分享連結過期/停用等情境。

> 錯誤格式見 [detailed-design.md](./detailed-design.md) §8.1；完整錯誤碼表（含 HTTP 狀態碼）見 §11。

## 21. 背景任務

目前版本以同步 service 流程與內建 scheduler 處理必要背景工作；未來若工作量增加，可再外接 Celery/RQ。可能的背景工作包括：

1. 產生圖片縮圖。
2. 產生 PDF 預覽。
3. 清理失敗或過期的上傳分片。
4. 清理垃圾桶過期項目。
5. 統計使用者容量。
6. 防毒掃描。
7. 寄送分享通知 email。

## 22. Docker 開發環境

建議使用 docker-compose 管理本機開發環境。

```yaml
services:
  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL:-/api/v1}
    ports:
      - "${FRONTEND_PORT:-8088}:80"
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-cloud_drive}:${POSTGRES_PASSWORD:-cloud_drive_dev}@postgres:5432/${POSTGRES_DB:-cloud_drive}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-development-only-change-me}
      LOCAL_STORAGE_PATH: /app/storage
      SNAPSHOT_SCHEDULER_ENABLED: ${SNAPSHOT_SCHEDULER_ENABLED:-true}
      ASSISTANT_ENABLED: ${ASSISTANT_ENABLED:-true}
      EMBEDDING_ENABLED: ${EMBEDDING_ENABLED:-false}
    depends_on:
      - postgres
    volumes:
      - storage_data:/app/storage

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-cloud_drive}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cloud_drive_dev}
      POSTGRES_DB: ${POSTGRES_DB:-cloud_drive}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
  storage_data:
```

正式環境不建議使用 compose 裡的簡易密碼，應改用環境變數或 secret manager。

正式環境 port 暴露原則：

| 服務 | 本機開發 | 正式環境建議 |
| --- | --- | --- |
| frontend nginx | 對外開放 `80/443` 或目前展示用 `8088` | 唯一公開入口，終止 TLS，代理 `/api` |
| backend FastAPI | 可映射 `8000` 方便除錯 | 不直接對外，只允許 nginx 或內部網路存取 |
| postgres | 可映射 `5432` 方便本機測試 | 不對公網開放，只允許 backend 內網連線 |
| redis | 目前不使用 | 不需要開放；若未來引入 queue/cache，也應只留內網 |
| Ollama / LLM | 開發機可用 `11434` | 若使用本地模型，應限制在內網或主機 loopback，不直接暴露公網 |

## 23. 環境變數

後端建議環境變數：

| 名稱 | 說明 |
| --- | --- |
| APP_ENV | development、staging、production |
| DATABASE_URL | PostgreSQL 連線字串 |
| JWT_SECRET_KEY | JWT 簽章密鑰 |
| JWT_ALGORITHM | JWT 演算法 |
| ACCESS_TOKEN_EXPIRE_MINUTES | access token 有效時間 |
| REFRESH_TOKEN_EXPIRE_DAYS | refresh token 有效天數 |
| STORAGE_DRIVER | local、minio、s3、azure |
| LOCAL_STORAGE_PATH | 本機檔案儲存路徑 |
| MAX_UPLOAD_SIZE_BYTES | 單檔上限 |
| DEFAULT_USER_QUOTA_BYTES | 預設使用者容量 |
| CORS_ORIGINS | 前端允許來源 |
| EMAIL_PROVIDER / SMTP_* | Email provider 與 SMTP 寄信設定；正式環境需由 secret 管理 |
| ASSISTANT_ENABLED | 是否啟用 AI Assistant |
| LLM_BASE_URL / LLM_API_KEY / ASSISTANT_MODEL | 本地或相容 API 模型設定；若含密鑰不得提交版控 |
| EMBEDDING_ENABLED / EMBEDDING_MODEL | 語意搜尋設定 |
| CREDENTIAL_ENCRYPTION_KEY | 加密使用者外部模型憑證；正式環境必須由 secret manager 或受控環境注入 |
| EXTERNAL_API_BASE_URL / EXTERNAL_CHAT_MODEL | 外部模型升級設定 |

前端建議環境變數：

| 名稱 | 說明 |
| --- | --- |
| VITE_API_BASE_URL | 後端 API 位置 |
| VITE_APP_NAME | 應用名稱 |

secret 管理原則：

1. 本機開發：可由 `.env` 提供，`.env` 不進版控；`.env.example` 只放可啟動的示範值。
2. 正式環境：`JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、`SMTP_PASSWORD`、LLM API key、`CREDENTIAL_ENCRYPTION_KEY` 應由 secret manager、CI/CD secret 或受控環境變數注入。
3. 資料庫內不保存明文 refresh token、share token；只保存 hash。
4. 使用者外部模型憑證若啟用，保存於 `user_external_credentials.secret_encrypted`，只回傳遮罩提示，不回傳明文。

## 24. 測試計畫

### 24.1 前端測試

使用 Vitest 與 React Testing Library。

測試項目：

1. 登入表單驗證。
2. 檔案列表渲染。
3. 上傳進度顯示。
4. 右鍵選單。
5. 分享彈窗。
6. 搜尋輸入 debounce。
7. 錯誤訊息顯示。

### 24.2 後端測試

使用 pytest。

測試項目：

1. 註冊與登入。
2. JWT 驗證。
3. 建立資料夾。
4. 上傳檔案。
5. 下載檔案。
6. 權限拒絕。
7. 分享權限。
8. 搜尋。
9. 垃圾桶還原。
10. 容量限制。
11. 分片上傳。

### 24.3 E2E 測試

使用 Playwright。

測試情境：

1. 使用者登入。
2. 建立資料夾。
3. 上傳檔案。
4. 搜尋檔案。
5. 分享檔案。
6. 另一位使用者開啟分享檔案。
7. 刪除檔案並從垃圾桶還原。

### 24.4 回歸防護測試（補充，2026-06-14）

根據測試空白分析，以下區域缺乏保護，新增功能時容易造成無聲回歸，已補充對應測試：

#### 前端 Store 安全不變式

`authStore` 持有 access token，但沒有測試確保 token 只在記憶體中。若未來有人誤加了 `localStorage.setItem`，現有測試不會報錯。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `src/stores/authStore.test.ts` | 初始狀態 null、setToken/clearToken/clearAuth/setUser 狀態轉換、setToken 不寫入 localStorage 或 sessionStorage |

#### 前端元件行為

DriveToolbar 與 FileTable 是核心互動元件，但沒有對應元件測試。若 props 介面變更或條件渲染邏輯改變，目前沒有任何測試能捕捉。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `src/components/drive/DriveToolbar.test.tsx` | New Folder 永遠可見、Trash 按鈕僅在 selectedCount > 0 時出現、顯示正確數量、click handler 呼叫 |
| `src/components/drive/FileTable.test.tsx` | 渲染所有項目名稱、空陣列不渲染資料列、onItemClick/onItemDoubleClick 傳入正確項目 |

#### 前端 E2E 分享完整流程

目前 E2E 完全沒有覆蓋分享功能。分享涉及兩個使用者帳號、跨頁面操作，是最容易在前後端整合時出問題的流程。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `e2e/share.spec.ts` | 分享後對方在 shared-with-me 看到、移除分享後對方看不到、建立公開連結後連結出現在對話框 |

#### 後端 Router 層 HTTP 狀態碼轉換

Service 層已有單元測試驗證商業邏輯，但 Router 層負責將 Service 拋出的例外轉換為正確 HTTP 狀態碼。若 Router 漏接例外或錯誤使用 `status_code`，單元測試不會捕捉到。

補充項目：

| 檔案 | 端點覆蓋 |
| --- | --- |
| `tests/upload/test_router.py` | POST /upload/simple 201、未驗證 403、parent 不存在 404、quota 超出 413、parent_id 傳遞 |
| `tests/trash/test_router.py` | 移到垃圾桶 200、列表 200、還原 200、永久刪除 204、清空 204，各端點未驗證 403 |
| `tests/search/test_router.py` | 搜尋成功 200、空結果 200、未驗證 403、缺少 q 422、過濾參數傳遞 |
| `tests/share/test_router.py` | 分享 201/403/404、移除分享 204/403、shared-with-me 200/403、建立連結 201/403、驗證連結 200/404、停用連結 204/403 |

#### 後端整合：版本紀錄不變式

每次上傳必須自動建立版本記錄（`file_versions.version_no = 1`）。若 upload service 的版本建立邏輯被重構，整合測試才能抓到回歸。

補充項目：

| 檔案 | 覆蓋內容 |
| --- | --- |
| `tests/integration/test_file_version_flow.py` | 上傳自動產生 v1、size_bytes 正確記錄、未驗證 403、非擁有者無分享不能列版本、viewer 可列版本、兩次上傳同名各自有獨立 v1 |

## 25. 開發里程碑

以**四個階段（週）**推進，各階段即開發順序：

### 25.1 第一週：專案基礎與帳號

1. 建立 frontend 與 backend 專案、Docker Compose、PostgreSQL（pgvector image，供語意搜尋）。
2. FastAPI 基礎架構、React 基礎版面、lint／format／測試工具。
3. 使用者註冊、登入、JWT 驗證。
4. drive_items 資料表與 migration。

### 25.2 第二週：檔案核心（列表／上傳下載／管理）

1. 建立資料夾 API、檔案列表 API、前端我的硬碟頁。
2. 小檔案上傳、檔案下載、容量檢查、上傳進度 UI、檔案圖示與 MIME type 顯示、操作紀錄。
3. 重新命名、移動、星號、最近檔案、垃圾桶、搜尋、右鍵選單。

### 25.3 第三週：分享與預覽

1. 指定使用者分享、分享連結、與我分享頁面。
2. 圖片預覽、PDF 預覽、文字預覽。

### 25.4 第四週：強化與驗收

1. 分片上傳。
2. 測試補齊、權限測試、效能優化。
3. 錯誤處理優化。
4. 部署文件、Demo 準備。

## 26. 驗收標準

功能以 **§5 功能範圍**為基準——§5.1 列的必做功能均可正常操作，即達功能驗收（不在此逐條重述）。除功能完整外，需同時滿足以下品質門檻：

**安全與隔離**

1. 使用者只能存取自己的檔案；不能藉猜測 UUID 存取他人資源。
2. 未授權操作回傳正確錯誤碼（401/403），不洩漏資源是否存在。
3. 分享連結 token 不可預測、可設失效（見 §18）。

**品質與體驗**

4. 前端清楚呈現 loading / empty / error 三種狀態。
5. 容量超限、同名衝突等邊界情況有明確提示（見 §12.2、§20）。

**測試與部署**

6. §24 規劃的前端單元/E2E、後端單元/整合 測試通過。
7. Docker 開發環境可一鍵啟動。

## 27. 風險與對策

| 風險 | 影響 | 對策 |
| --- | --- | --- |
| 大檔案上傳失敗 | 使用體驗差 | 分片上傳與續傳 |
| 權限判斷錯誤 | 資料外洩 | 後端集中權限檢查與測試 |
| 檔案名稱衝突 | 使用者困惑 | 明確衝突策略 |
| 資料夾樹查詢慢 | 列表載入慢 | 索引、ltree 或 closure table |
| 儲存成本上升 | 維運成本高 | 容量限制、垃圾桶清理 |
| 預覽生成耗時 | 使用者等待 | 背景任務與快取 |
| 分享連結外流 | 資料風險 | 密碼、到期時間、撤銷機制 |

## 28. 結論

本專案的核心不是只做「檔案上傳」，而是要建立完整的檔案管理系統。因此設計上需同時考慮檔案本體儲存、資料庫中繼資料、權限、分享、搜尋、垃圾桶、容量限制與使用者體驗。

目前核心 MVP 與擴充模組已大致完成：登入、我的硬碟、資料夾、上傳、下載、搜尋、垃圾桶、容量統計、分享連結、檔案版本、預覽、In-App AI Assistant 與時光機（Snapshots）皆已有對應實作與測試紀錄。後續正式開發文件應把這些已完成能力整合成「使用者介面 → API → 資料表 → 時序圖 → 測試驗收」的交接文件，而不是停留在早期功能規劃。

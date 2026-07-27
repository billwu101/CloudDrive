# 雲端硬碟系統需求文件

## 目錄

- [1. 文件目的](#1-文件目的)
- [2. 初版假設](#2-初版假設)
- [3. 待確認問題](#3-待確認問題)
- [4. 專案目標](#4-專案目標)
- [5. 功能範圍](#5-功能範圍)
- [6. 使用者使用情境](#6-使用者使用情境)
- [7. 系統架構](#7-系統架構)
- [8. 技術選型](#8-技術選型)
- [9. 前端頁面與狀態管理](#9-前端頁面與狀態管理)
- [10. 後端目錄結構](#10-後端目錄結構)
- [11. 資料庫設計](#11-資料庫設計)
- [12. In-App AI Assistant](#12-in-app-ai-assistant)
- [13. 時光機（Snapshots，核心功能）](#13-時光機snapshots核心功能)
- [14. 權限模型](#14-權限模型)
- [15. API 設計](#15-api-設計)
- [16. 關鍵流程設計](#16-關鍵流程設計)
- [17. 安全性需求](#17-安全性需求)
- [18. 效能需求](#18-效能需求)
- [19. 錯誤處理](#19-錯誤處理)
- [20. Docker 開發環境](#20-docker-開發環境)
- [21. 環境變數](#21-環境變數)
- [22. 測試計畫](#22-測試計畫)
- [23. 開發里程碑](#23-開發里程碑)
- [24. 驗收標準](#24-驗收標準)
- [25. 風險與對策](#25-風險與對策)
- [26. 部署與維運計畫](#26-部署與維運計畫)
- [27. 大檔案分片續傳上傳](#27-大檔案分片續傳上傳)
- [28. 公開分享連結存取](#28-公開分享連結存取)
- [29. 我分享出去的項目（Shared by me）](#29-我分享出去的項目shared-by-me)
- [30. 結論](#30-結論)

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
| API 文件、ERD、架構／部署／時序圖（**開發文件紀錄**） | 是 | 端點/request/response/錯誤碼、資料表與權限·搜尋·快照·助理、資料流與部署邊界；皆**由 `detailed-design/` 與 OpenAPI 匯出／節錄**，供交付方審查 |
| 測試與 Assistant Eval Harness 報告 | 是 | 證明核心流程、E2E、AI agent 評測有被驗證 |

也就是說，`detailed-design/`（含附錄 A 架構決策紀錄）、`progress.md` 與 `tasks/*.md` 為**內部文件、不納入交付**；正式需求文件本身應能獨立說明系統需求。

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

1. 註冊、登入帳號，並可在忘記密碼時取得系統寄送的臨時密碼以重設。
2. 上傳檔案。
3. 建立、重新命名、移動、複製、刪除資料夾與檔案。
4. 透過列表或格狀檢視瀏覽檔案。
5. 透過關鍵字搜尋檔名與檔案內容（全文搜尋），另提供選用的語意搜尋。
6. 預覽圖片、PDF、文字檔、影片、音訊，以及 Word／Excel／PowerPoint 等 Office 文書檔與 Markdown；不支援的格式則提供下載。
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

1. 使用者註冊、登入、登出、忘記密碼（系統寄送臨時密碼）。
2. JWT 存取權杖與刷新權杖。
3. 檔案上傳。
4. 檔案下載（單檔下載；亦可多選多個檔案／資料夾打包成 zip 一次下載）。
5. 建立資料夾。
6. 檔案與資料夾列表。
7. 檔案與資料夾重新命名。
8. 檔案與資料夾移動。
9. 檔案與資料夾刪除到垃圾桶。
10. 垃圾桶還原與永久刪除。
11. 檔案搜尋（檔名與檔案內容全文搜尋；語意搜尋為選用，需開啟 embedding）。
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
13. Office 文書（Word／Excel／PowerPoint）與 Markdown 預覽。

### 5.3 第三階段功能

1. 管理員後台（系統統計、使用者列表、容量使用狀況、違規檔案處理紀錄）。
2. 使用者容量配額管理。
3. 團隊空間。
4. 共同資料夾。
5. 檔案留言。
6. 檔案標籤。
7. 防毒掃描。
8. 檔案加密。
9. OAuth 登入。
10. WebSocket 即時通知。
11. 桌面或手機同步客戶端。

### 5.4 In-App AI Assistant（核心）

對話式 AI 助理（自然語言操作檔案、計畫確認、現場生成技能、技能管理、工作流程重用）。完整規格見 **§12**。

### 5.5 時光機（Snapshots，核心）

類 Apple Time Machine 的整碟時間點還原：定期/手動/助理操作前自動建快照，可瀏覽過去某時間點的硬碟並就地還原。完整規格見 **§13**。

### 5.6 大檔案分片續傳上傳

把 §5.2 的「大檔案分片上傳／上傳失敗後續傳」落實為可執行規格：檔案切片上傳、可暫停／繼續／取消、關閉瀏覽器後仍可續傳。完整規格見 **§27**。

### 5.7 暫不包含功能

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

（完整規格見 §12。）

### 6.8 用時光機瀏覽與還原

1. 系統定期、或使用者手動、或助理執行破壞性操作前，自動建立整碟快照。
2. 使用者開啟時光機，瀏覽過去某個時間點的硬碟狀態。
3. 使用者選定時間點，就地還原整個硬碟或特定項目。

（完整規格見 §13。）

## 7. 系統架構

### 7.1 架構總覽

**前後端分離**：React 前端 ──(HTTPS REST API)──> FastAPI 後端 ──(SQLAlchemy / asyncpg)──> PostgreSQL；檔案 binary 經 Storage Provider 存獨立儲存層（metadata 與 binary 分離，見 §7.5）。後端另內含 **AI 助理引擎**（本地 Gemma + 可選外部 GPT-5.5，見 §7.6）。完整架構圖與分層見 [detailed-design/](./detailed-design/01-overview.md) §3。

### 7.2 前端技術

核心：**React + TypeScript + Vite**；伺服器狀態用 TanStack Query、UI 狀態用 Zustand。其餘選型（路由、表單、驗證、樣式庫等）見 [detailed-design/](./detailed-design/01-overview.md) §5。

### 7.3 後端技術

核心：**FastAPI + Python 3.12+ + SQLAlchemy 2.x（async）+ PostgreSQL**；Alembic 管 migration、Pydantic 管 I/O 驗證。其餘選型（JWT／密碼雜湊套件、背景工作機制等）見 [detailed-design/](./detailed-design/01-overview.md) §7。

### 7.4 資料庫

以 PostgreSQL 儲存：使用者帳號、檔案/資料夾 metadata、權限、分享、檔案版本、上傳工作狀態、操作紀錄與容量統計（各表見 §11）。

### 7.5 儲存層

**設計理由**：檔案本體**不存 PostgreSQL**。DB 為結構化查詢與交易設計，存大型 binary 會使備份/複製肥大、佔用連線記憶體、不利串流，效能也隨檔案量劣化。因此採「metadata 與 binary 分離」：

- **DB 只存 metadata**：檔名、大小、權限、`storage_key`（檔案在儲存層的定位）。
- **檔案 binary 存獨立儲存層**（檔案系統或物件儲存）。
- **取檔流程**：先查 DB（驗權限 + 取 `storage_key`），再用 key 向儲存層取 binary——**權限與定位永遠經過 DB，binary 不經 DB**。
- 儲存層抽象為 **Storage Provider** 介面，底層可換（本地檔案系統／MinIO／S3／Azure Blob）而不動業務邏輯：開發用本地、正式可換物件儲存。

> Provider 介面方法與 `LocalStorageProvider` 實作見 [detailed-design/](./detailed-design/01-overview.md) §7.6。

### 7.6 AI 助理引擎

後端內含對話式 **AI 助理引擎**（HARNESS：while loop、context、skills/tools、sub-agents、沙箱、權限與安全）。預設以**本地 Gemma（Ollama）**為執行器，資料不外流；本地反覆失敗時可升級**外部 GPT-5.5**（Codex 訂閱優先、OpenAI key 備援，使用者自帶加密憑證）。驅動自然語言操作檔案、現場生成技能與工作流程重用。完整規格見 §12；引擎設計見 [detailed-design/](./detailed-design/01-overview.md) §7 與 [detailed-design/ §9](./detailed-design/01-overview.md)。

## 8. 技術選型

各層採用的技術與理由（實際版本以 `backend/pyproject.toml`、`frontend/package.json` 為準）。

**前端**

| 技術 | 用途與選用理由 |
| --- | --- |
| React 19 + TypeScript + Vite | 元件化 UI、型別安全；Vite 提供快速開發與建置 |
| TanStack Query | 伺服器狀態：快取、失效與重取 API 資料 |
| Zustand | 輕量 UI／auth／上傳狀態管理，無樣板程式 |
| React Hook Form + Zod | 高效表單 + schema 驗證（`@hookform/resolvers` 串接） |
| React Router | SPA 路由與受保護頁面 |
| Tailwind CSS + shadcn／base-ui | 一致設計系統、可組合元件、快速開發 |
| axios | 統一 API 呼叫；攔截器處理 401／silent refresh |

**後端**

| 技術 | 用途與選用理由 |
| --- | --- |
| FastAPI + Python 3.12 | async 效能佳、原生型別、自動產生 OpenAPI |
| SQLAlchemy 2.x（async）+ asyncpg | async ORM + 高效 PostgreSQL 驅動 |
| Alembic | 資料庫 schema migration 版本管理 |
| Pydantic／pydantic-settings | request／response 驗證與設定管理 |
| PyJWT + pwdlib（Argon2） | JWT 存取／刷新權杖 + Argon2 密碼雜湊 |
| cryptography | 外部模型 API 憑證加密儲存（不存明文） |
| uvicorn + httpx | ASGI server + async HTTP client（呼叫 LLM） |
| Pillow／pypdf／py7zr／python-multipart | 圖片縮圖／PDF 預覽／壓縮技能／檔案上傳 |
| aiosmtplib | async SMTP 寄信（分享通知等） |

**資料、儲存與 AI**

| 技術 | 用途與選用理由 |
| --- | --- |
| PostgreSQL 16 + pgvector | 關聯式資料 + 交易一致性 + 向量檢索（語意搜尋） |
| 本地檔案系統（Storage Provider 抽象） | 開發用本地，可無痛換物件儲存（見 §7.5） |
| Ollama（本地 Gemma）+ OpenAI 相容外部模型 | 本地優先、資料不外流；反覆失敗時才升級外部 |

**維運與測試**

| 技術 | 用途與選用理由 |
| --- | --- |
| Docker + docker compose | 環境一致、一鍵啟動前後端與 DB |
| GitHub Actions + GHCR + self-hosted runner | CI 測試／建置、CD 部署（見 §26） |
| pytest · ruff · mypy | 後端測試、lint、型別檢查 |
| Vitest · Testing Library · MSW · Playwright | 前端單元測試、API mock、E2E |

## 9. 前端頁面與狀態管理

### 9.1 頁面

- **登入頁** / **註冊頁**：帳號登入、註冊（含表單驗證）。
- **主版面**：左側導覽（我的硬碟／與我分享／最近／星號／垃圾桶／儲存空間）、上方搜尋列、中央檔案區、右側詳細資訊面板。
- **我的硬碟頁**：麵包屑、新增/上傳（檔案/資料夾）、列表/格狀檢視、排序、多選、右鍵選單、拖曳上傳。

### 9.2 整體風格

介面以**實用、清楚、可快速操作**為主（高頻工作型產品，不過度裝飾）：淺色背景、左側固定導覽、上方全域搜尋、清楚的檔案列表、足夠留白、操作按鈕用圖示搭配 tooltip；重要操作（如刪除、永久刪除）需確認。

### 9.3 主要元件

`Sidebar`、`TopSearchBar`、`Breadcrumbs`、`FileToolbar`、`FileTable`、`FileGrid`、`ContextMenu`、`UploadDropzone`、`UploadQueue`、`PreviewDialog`、`ShareDialog`、`ConfirmDialog`、`StorageUsageBar`。

互動重點：上傳佇列含進度/速度/暫停/繼續/取消/重試；預覽支援圖片／PDF／文字／影片／音訊，以及 Word／Excel／PowerPoint 文書檔（伺服器轉 PDF 預覽）與 Markdown（渲染顯示），不支援時顯示下載；分享彈窗含搜尋使用者、設權限、建公開連結（到期/密碼）、複製、移除對象。

### 9.4 狀態設計

每個頁面都要設計：Loading、Empty、Error、Permission denied、Offline/retry 狀態。

### 9.5 狀態管理

狀態分工：

1. **Auth state**：登入狀態、token、目前使用者。
2. **Drive query state**：目前資料夾、排序、分頁、搜尋條件。
3. **Upload state**：上傳佇列與進度。
4. **UI state**：側邊欄、預覽窗、分享彈窗、右鍵選單。

技術選型：伺服器資料用 TanStack Query、UI 狀態用 Zustand、表單用 React Hook Form、schema 驗證用 Zod。

### 9.6 AI 助理相關頁面（AI Assistant）

> 屬 **In-App AI Assistant**（§12）功能。

- **聊天面板**：浮動於各受保護頁；訊息泡泡、計畫確認卡、技能核可/程式碼審查、已存工作流程清單、使用者訊息複製鈕。
- **Skills 管理頁（`/skills`）**：已安裝技能列表（數量、描述、右鍵動作、更新時間）+ 編輯/刪除。
- **外部模型連線設定（Settings）**：管理多組外部模型連線——連線列表、新增（含 Gemini／OpenAI／Ollama cloud／Codex presets，自動帶入對應 base_url）、刪除；顯示遮罩提示與連線狀態。

> 各頁面/元件的詳細結構與 props 見 [detailed-design/](./detailed-design/01-overview.md) §5。

## 10. 後端目錄結構

後端按**模組（domain）**組織，每個模組是一個自足套件、內部採**相同的分層**；模組之間只透過服務層注入互動，不互相 import 內部。模組內各層職責：

- **路由層**：接收 HTTP request、驗證輸入、呼叫服務層、組裝回應與狀態碼；不放商業邏輯。
- **服務層**：商業邏輯所在——權限判斷、容量檢查、協調資料層與儲存層，是模組對外的唯一介面。
- **資料層**：資料庫查詢與 transaction，封裝 ORM 操作；只被同模組的服務層呼叫。
- **結構層**：該模組的 request／response 型別與驗證規則。

跨模組的共用層：

- **儲存抽象層**：以介面封裝檔案存取（本地／物件儲存可替換），服務層透過它讀寫 binary，不直接碰檔案系統。
- **核心層**：設定、JWT 安全、例外與錯誤碼、依賴注入等全域基礎設施。
- **資料模型層**：ORM 模型與跨模組共用的回應型別。
- **基礎服務層**：操作紀錄、權限判斷、寄信等沒有對外路由、由其他服務層注入的內部能力。
- **API 聚合層**：彙整各模組路由為單一對外 API。

各層對應的實際模組清單、檔案與邊界見 [detailed-design/](./detailed-design/01-overview.md) §6（模組拆分原則）與 §6（後端核心）；實際以 `backend/app/` 程式碼為準。

## 11. 資料庫設計

下表為各資料表的需求；**欄位型別與長度原則、各表 DDL（欄位、型別、索引）見 [detailed-design/](./detailed-design/01-overview.md) §8**，對應小節列於最右欄。

| 資料表 | 需求 | DDL |
| --- | --- | --- |
| `users` | 使用者帳號；`email` 為唯一登入識別；有容量上限與已用量；區分啟用狀態與管理員身分；密碼僅存雜湊、不存明文。 | §7.1 |
| `drive_items` | 統一儲存檔案與資料夾（以 `item_type` 區分）；同層未刪除項目不可同名（同名上傳 MVP 自動命名 `filename (1).ext`，亦可取代建新版本或由使用者選）；支援星號、垃圾桶（軟刪除）、建立/修改者追蹤。 | §7.3 |
| `user_item_preferences` | 每位使用者對項目的個人化偏好（目前為星號）。星號以本表為準、不放 `drive_items`，以免分享時一人加星污染他人狀態。 | §7.3.1 |
| `file_versions` | 檔案歷史版本，支援版本回溯。 | §7.4 |
| `shares` | 對指定使用者的分享權限：`viewer`（檢視/預覽）、`downloader`（下載）、`editor`（改名/移動/上傳新版本）。 | §7.5 |
| `share_links` | 公開分享連結：權限（`viewer`/`downloader`）、選用密碼、選用到期、啟用開關。只存 token 與密碼 hash、不存明文；明文 token 僅建立時回傳一次。 | §7.6 |
| `upload_sessions` | 大型檔案分片上傳；狀態機 `pending`→`uploading`→`completed`/`failed`/`cancelled`；完成後建立對應 `drive_item`。 | §7.7 |
| `upload_chunks` | 各分片（編號、暫存位置、大小、checksum），供完成時組裝與驗證。 | §7.7 |
| `activity_logs` | 使用者操作紀錄（`upload`/`download`/`rename`/`move`/`delete`/`restore`/`share`），含操作者、對象、metadata、IP、瀏覽器；供稽核與「最近」。 | §7.8 |

## 12. In-App AI Assistant

於網頁應用內提供一個**可對話、可自我擴充的 AI 助理**。使用者用自然語言描述需求，助理把需求轉成**可檢視、可確認、可執行、可記錄的 Workflow**，以既有或現場生成的技能完成檔案／資料夾操作。完整設計見 [detailed-design/ §9](./detailed-design/01-overview.md)，評測見 [detailed-design/ §11](./detailed-design/01-overview.md)，決策見 [detailed-design/ 附錄 A](./detailed-design/01-overview.md) 的 DEC-016～023。

- **對話操作**：登入後 CloudDrive shell 內的浮動聊天面板，用自然語言列檔／搜尋／整理／改名／移動／分享／壓縮解壓等。
- **計畫確認**：寫入/破壞性操作先產生計畫（步驟、權限層級、是否需確認），唯讀操作可 fast-path 自動執行；使用者確認後才執行，破壞性操作**絕不自動執行**。
- **現場生成新技能**：缺少的能力由助理現場生成（例如「做一個 7zip 解壓縮功能」），經 **codegen → 靜態驗證（codeguard）→ 使用者核可 → 受限沙箱執行**，產出檔案寫回 drive。
- **自建技能用於對話（需逐個開啟）**：生成／自建技能預設只能透過右鍵對單一檔案執行；若要讓助理在對話中直接調用，須在 Skills 頁逐個開啟「允許在對話中使用」。開啟後助理可把該技能排進計畫，但因屬不可信程式碼，**一律需使用者確認、經沙盒執行、執行前自動快照**，不會自動執行。
- **勾選檔案帶入**：在對話中使用技能時，「要對哪些檔操作」由使用者在硬碟頁**勾選**帶入（對話框顯示已選檔、可單獨移除）；勾一個對該檔執行、**勾多個對每檔各跑一次**、未勾則提示先選檔——不靠 AI 猜檔名。
- **技能可對資料夾執行（不限單檔）**：生成/自建技能可對**資料夾**執行，型別由使用者選取的項目決定（選資料夾即對資料夾、選檔案即對檔案）。支援兩種：「對資料夾內每個檔各跑一次」與「把整個資料夾當一體處理（如壓成單一壓縮檔）」；資料夾攝取有檔數/大小上限保護。宣稱資料夾型別的技能會自動出現在資料夾的右鍵選單。
- **技能管理**：側欄 **Skills 頁（`/skills`）**檢視已安裝技能數量、編輯（描述/程式碼，改碼重跑 codeguard）、刪除、**逐個開關「允許在對話中使用」**。
- **工作流程重用**：計畫可命名儲存，之後一鍵重跑。
- **動態 UI**：已安裝技能依 manifest 動態掛到檔案右鍵選單；使用者訊息列提供複製鈕（前端全域禁止反白，故以按鈕程式複製）。
- **模型策略**：預設本地 Gemma（Ollama），達失敗上限且符合隱私條件時才條件式升級外部模型；隱私敏感且無法去識別化則不外送。
- **多組具名外部模型連線**：使用者可建立**多個**外部模型連線，每個自訂名稱、選類型（OpenAI 相容／Ollama／Codex 訂閱）並填 base_url + model + API key（取代「每 provider 一把」）。「OpenAI 相容」是**協定不是廠商**——同一介面可接 OpenAI／Gemini／Ollama cloud／Groq 等；Codex 為訂閱制特例。連線驗證失敗自動標記 invalid；憑證加密儲存、只回遮罩不回明文。**規劃中**再支援 Anthropic／Claude 連線。
- **模型選擇（對話內手動選、選定則無自動 fallback）**：助理面板下拉列出「本機 + 使用者已設定的外部模型連線」，每則訊息帶所選模型、可同一 session 中途更換；**選定即只用該模型、不自動退回其他模型**（上述自動升級僅適用於未指定模型的預設路徑）。所選模型失敗時**明確分類回報**（連不到／憑證被拒／額度或速率／其他）並**快速失敗**（本機連線逾時數秒、不卡分鐘級）；未設定的連線在選單停用。錯誤訊息只給分類與建議，不洩漏金鑰或內部細節。手動選外部**仍受隱私閘約束**（敏感且未去識別化 → 拒送並說明）。
- **對話記憶（多輪 context 回讀）**：助理在**同一對話 session** 內回讀最近數輪（預設約 6 輪）的訊息與工具執行結果，讓使用者能用指涉／省略延續操作（先列檔、下一句「把第一個改名為 X」，助理知道「第一個」是誰）。跨對話不記憶、無長期使用者畫像（v2 再議）；歷史與當前訊息走同一隱私閘。可用 `assistant_history_max_messages` 調整回讀則數（`0`=關閉、退回單輪）。實作見 [detailed-design/ §8.14](./detailed-design/01-overview.md)。

**HARNESS 引擎架構**：助理後端是一個 agent harness 引擎，由數個核心組件構成——

- **執行迴圈（while loop）**：驅動「送訊息 → 解析 → 執行工具 → 回填結果」直到完成或達迴圈上限。
- **情境管理（context）**：token 預算控制、超量裁切／摘要、大型工具輸出瘦身。
- **技能與工具（skills/tools）**：技能 registry + manifest，依相關性挑選可用技能；支援現場 author 新技能。
- **子代理（sub-agents）**：獨立 context 的子代理，主要用於 codegen 與有界平行子任務。
- **系統提示組裝**：動態組裝人設 + 安全規則 + 可用技能清單 + 當前語境（穩定前綴在前、無隨機／時間戳）。
- **生命週期 hooks**：在 session／tool／skill／code-exec／error 節點插入稽核、權限閘、計畫確認、安裝前驗證。
- **持久化**：session／訊息／技能／工作流程持久化，啟動時載入使用者已安裝技能與已存工作流程。
- **權限與安全**：`user_id` 多租戶綁定、分層權限（唯讀自動／破壞性確認／生成碼核可）、受限沙箱（資源／路徑／網路限制）、全程稽核。
- **模型路由**：本地 Gemma（Ollama）為主，達失敗上限且符合隱私條件時才升級外部模型（見上「模型策略」）。

各組件的職責與對應實作見 [detailed-design/ §9.7](./detailed-design/01-overview.md)（HARNESS 九大組件）。

## 13. 時光機（Snapshots，核心功能）

類 Apple Time Machine 的整碟時間點還原。完整設計見 [detailed-design/ §13](./detailed-design/01-overview.md)，決策見 DEC-024。**狀態：S1-S5 已實作並測試完成；仍有非阻擋限制：還原時硬配額檢查待補強。**

### 13.1 功能範圍

- **快照**：整個雲端硬碟在某時間點的狀態（哪些檔案/資料夾存在、名稱、位置、版本）。增量儲存——未變更檔案以 `checksum_sha256` 共用既有內容，不重複存。
- **三種觸發**：(1) 自動排程（使用者設定預設開啟、每小時；服務內建排程器由 `SNAPSHOT_SCHEDULER_ENABLED` 控制，compose 單 worker 預設開）；(2) 手動「立即建立快照」；(3) **助理執行寫入/破壞性 workflow 或生成式 skill 前自動建快照**（每個 workflow/skill 一個），可一鍵回到助理操作前。
- **時間軸瀏覽**：依時間列出快照，點任一快照唯讀瀏覽當時的硬碟。
- **就地還原**：把單檔／資料夾子樹／整碟還原到所選時間點，**覆蓋現況**（救回被刪檔、回復改名/搬移/內容）。子樹/整碟還原時可選 `keep_new`（保留現有新增）或 `exact_mirror`（精確鏡像）。還原前自動先建「還原前保命快照」，可再倒回；走 service 層套配額與權限。
- **保留與配額**：保留最近 N 個快照（預設 50，可設），釘選與保命快照豁免；快照空間**不計入檔案配額，另設獨立快照配額（預設為檔案配額的一半）**；刪快照的內容由背景 GC 回收。排程快照需設定開啟、距最近快照已達間隔且 drive 目前至少有一個 item；空碟不建立排程快照。
- **協作**：分享/協作項目僅擁有者可還原。

### 13.2 重用既有模組

建立在既有元件之上：`file_versions`（內容層）、`drive_items` 的名稱/父層/刪除旗標（可還原改名/搬移/刪除）、Trash（互補）、`activity_logs`（稽核）、Storage 的 checksum 去重、背景任務（排程與縮減）、Assistant（執行前快照）。

### 13.3 新增資料表

- 新表 `snapshots`、`snapshot_entries`、`snapshot_settings`（見設計文件 §7）。

### 13.4 前端頁面

側欄「時光機」入口（`/time-machine`）：快照時間軸、進入快照唯讀瀏覽、還原確認流程（明示覆蓋、已建保命快照、可選 subtree_mode）、保留數/排程/獨立快照配額設定。

## 14. 權限模型

### 14.1 權限類型

| 權限 | 說明 |
| --- | --- |
| owner | 擁有者，可執行所有操作 |
| editor | 可重新命名、移動、上傳新版本 |
| viewer | 可檢視與預覽 |
| downloader | 可檢視與下載 |

### 14.2 權限判斷順序

1. 若 user_id 等於 item.owner_id，擁有 owner 權限。
2. 若 item 透過 shares 分享給該使用者，依 shares.permission 判斷。
3. 若透過 share_links 存取，依 link.permission 判斷。
4. 若資料夾被分享，子項目應繼承資料夾權限。
5. 若以上皆不符合，拒絕存取。

### 14.3 權限注意事項

1. 後端每個檔案操作都必須檢查權限。
2. 前端隱藏按鈕只是使用者體驗，不能取代後端權限檢查。
3. 分享連結 token 不應直接儲存明文。
4. 資料夾權限繼承要避免查詢過慢，必要時可以建立 permission cache。

## 15. API 設計

API base path：`/api/v1`。下表為各端點對應的動作（介面需求）；**完整 request/response 規格見 OpenAPI 匯出（程式碼自動生成）** 與 [detailed-design/](./detailed-design/01-overview.md) §14（通用規則：統一錯誤格式、分頁、`DriveItemResponse`、API↔模組對應）。

### 15.1 Auth API

| 端點 | 動作 |
| --- | --- |
| `POST /auth/register` | 註冊使用者 |
| `POST /auth/login` | 登入（回 access token + refresh token） |
| `POST /auth/refresh` | 刷新 access token |
| `POST /auth/logout` | 登出並使 refresh token 失效 |
| `GET /auth/me` | 取得目前登入使用者 |

### 15.2 Drive API

| 端點 | 動作 |
| --- | --- |
| `GET /drive/items` | 取得指定資料夾底下的檔案與資料夾（支援 sort/order/分頁） |
| `POST /drive/folders` | 建立資料夾 |
| `PATCH /drive/items/{item_id}/name` | 重新命名 |
| `PATCH /drive/items/{item_id}/parent` | 移動檔案或資料夾 |
| `PUT /drive/items/{item_id}/star` | 設定星號 |
| `GET /drive/items/{item_id}/download` | 下載檔案（串流或短效下載 URL） |
| `POST /download/archive` | 多選打包下載為 zip（可含資料夾、遞迴保留結構；zip 以選取內容命名） |
| `GET /drive/items/{item_id}/preview` | 取得預覽資訊 |

### 15.3 Upload API

| 端點 | 動作 |
| --- | --- |
| `POST /upload/simple` | 小檔案直接上傳 |
| `POST /upload/sessions` | 建立分片上傳工作 |
| `PUT /upload/sessions/{session_id}/chunks/{chunk_index}` | 上傳單一分片 |
| `POST /upload/sessions/{session_id}/complete` | 合併分片並建立檔案紀錄 |
| `DELETE /upload/sessions/{session_id}` | 取消上傳 |

### 15.4 Search API

| 端點 | 動作 |
| --- | --- |
| `GET /search` | 搜尋檔案 |

### 15.5 Trash API

| 端點 | 動作 |
| --- | --- |
| `GET /trash` | 取得垃圾桶項目 |
| `PATCH /trash/{item_id}/restore` | 還原項目 |
| `DELETE /trash/{item_id}` | 永久刪除項目 |
| `DELETE /trash` | 清空垃圾桶 |

### 15.6 Share API

| 端點 | 動作 |
| --- | --- |
| `POST /share/items/{item_id}/users` | 分享給指定使用者 |
| `GET /share/shared-with-me` | 取得與我分享的檔案 |
| `POST /share/items/{item_id}/links` | 建立公開分享連結 |
| `DELETE /share/links/{link_id}` | 停用分享連結 |

### 15.7 Assistant API

前綴同 `/api/v1`；完整流程見 [detailed-design/ §9](./detailed-design/01-overview.md)。

| Method | Path | 用途 |
|---|---|---|
| POST | `/assistant/chat` | 對話；回計畫或技能提案；記錄 session/訊息；可帶 `selected_item_ids`（勾選檔，供自建技能帶入目標檔） |
| GET | `/assistant/models` | 列出可選模型目標（本機 + 使用者外部模型連線；含可用狀態） |
| GET | `/assistant/sessions`、`/assistant/sessions/{id}/messages` | 對話歷史 |
| POST | `/assistant/workflows/{id}/confirm` · `/cancel` | 確認/取消 pending 計畫 |
| POST | `/assistant/workflows/save`、GET `/workflows/saved`、POST `/workflows/saved/{id}/rerun` | 命名儲存與一鍵重跑 |
| GET | `/assistant/skills?status=installed` | 列出已安裝技能 |
| POST | `/assistant/skills/{id}/approve` · `/execute` | 核可安裝 / 執行（生成技能於沙箱執行並寫回 drive） |
| PATCH | `/assistant/skills/{id}` | 編輯描述/程式碼（改碼重跑 codeguard）；切換 `chat_enabled`（允許在對話中使用） |
| DELETE | `/assistant/skills/{id}` | 刪除技能（連同右鍵動作）；回 204 |
| GET/POST/PUT/DELETE | `/users/me/model-connections` | 多組具名外部模型連線 CRUD（憑證加密、只回遮罩；取代舊 `/external-credentials`） |

### 15.8 Time Machine API

前綴同 `/api/v1`；完整設計見 [detailed-design/ §13](./detailed-design/01-overview.md)、資料表見 §13.3。

| 端點 | 動作 |
| --- | --- |
| `POST /snapshots` | 建立快照 |
| `GET /snapshots` | 列出快照 |
| `GET /snapshots/{id}/items` | 瀏覽快照內容 |
| `POST /snapshots/{id}/restore` | 還原到所選快照 |
| `GET/PUT /snapshots/settings` | 讀取／更新快照設定 |

## 16. 關鍵流程設計

### 16.1 小檔案上傳流程

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

### 16.2 分片上傳流程

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

### 16.3 下載流程

```text
User clicks download
  -> Backend checks permission
  -> Backend logs download activity
  -> Backend streams file or returns temporary signed URL
  -> Browser downloads file
```

多選打包下載：使用者勾選多個檔案／資料夾後一次下載 → 後端逐項檢查下載權限、資料夾遞迴展開並保留目錄結構 → 打包成單一 zip 回傳；zip 以選取內容命名（單選用該資料夾／檔名，多選用「第一項 等 N 項」）。

### 16.4 搜尋流程

```text
User enters keyword
  -> Frontend debounces input
  -> Frontend calls /search
  -> Backend filters accessible files
  -> PostgreSQL searches names and metadata
  -> Backend returns paginated result
```

### 16.5 垃圾桶流程

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

## 17. 安全性需求

### 17.1 身分驗證

1. 使用 access token 與 refresh token。
2. access token 有效時間建議 15 到 30 分鐘。
3. refresh token 有效時間建議 7 到 30 天。
4. refresh token 需可撤銷。
5. 密碼使用 bcrypt 或 argon2 雜湊。
6. access token 僅存於前端記憶體（不寫 localStorage／sessionStorage）、refresh token 存 HttpOnly cookie；頁面重整後以 **silent refresh**（app 啟動時呼叫 `POST /auth/refresh`）用 refresh cookie 續期維持登入，失敗則導向登入。實作見 [detailed-design/](./detailed-design/01-overview.md) §5.2.1。

### 17.2 權限安全

1. 所有檔案操作必須在後端檢查權限。
2. 使用者不得透過猜測 UUID 存取他人檔案。
3. 分享連結 token 需足夠長且不可預測。
4. 分享連結可設定失效。

### 17.3 上傳安全

1. 限制單檔大小。
2. 限制使用者總容量。
3. 檢查 MIME type。
4. 檢查副檔名。
5. 避免使用原始檔名作為 storage_key。
6. 對可疑檔案執行防毒掃描。
7. 禁止路徑穿越，例如 `../../secret.txt`。

### 17.4 API 安全

1. 啟用 CORS 白名單。
2. 限制登入嘗試頻率。
3. 對上傳 API 加上 rate limit。
4. 使用 HTTPS。
5. 避免在錯誤訊息洩漏內部路徑。
6. API response 不回傳 password_hash、token_hash 等敏感欄位。

### 17.5 AI 助理安全（AI Assistant）

> 屬 **In-App AI Assistant**（§12）功能。

1. 生成程式碼**絕不自動執行**：經 codeguard AST 靜態掃描（拒禁用 import/`eval`/dunder/錯誤簽章）→ 使用者核可 → 受限子行程沙箱（`python -I`、CPU/檔案 rlimit、`addaudithook` 封鎖網路/spawn/越界寫入）。編輯既有技能同樣重跑 codeguard。
2. 沙箱檔案存取限該使用者 storage；所有動作可記入 `activity_logs`。詳見 DEC-019。

## 18. 效能需求

### 18.1 前端效能

1. 檔案列表使用分頁或虛擬滾動。
2. 搜尋輸入使用 debounce。
3. 大量檔案上傳時避免造成 UI 卡頓。
4. 縮圖使用 lazy loading。
5. 預覽視窗按需載入。

### 18.2 後端效能

1. 檔案下載使用 streaming response 或 signed URL。
2. 大檔案使用分片上傳。
3. 搜尋欄位建立索引。
4. 熱門查詢可於後續引入 cache；目前版本不要求 Redis。
5. 縮圖產生放入背景任務。

### 18.3 資料庫效能

1. drive_items 依 owner_id、parent_id 建索引。
2. 搜尋名稱使用 pg_trgm。
3. activity_logs 可依時間分區。
4. 大型 JSON metadata 避免過度查詢。
5. 列表查詢只取必要欄位。

## 19. 錯誤處理

**需求**：API 採統一錯誤格式 `{ "error": { "code", "message", "details" } }`，前端依 `code` 顯示對應訊息。

常見錯誤情境與 HTTP 狀態碼：

| HTTP 狀態 | 代表情境 |
| --- | --- |
| 400 | 參數／檔名／操作不合法（如 item type 不符、parent 不存在、不可移到子孫資料夾） |
| 401 | 未授權：未登入或 token 無效、帳號或密碼錯誤 |
| 403 | 權限不足、使用者停用、分享密碼錯誤 |
| 404 | 找不到：item、檔案本體或分享對象不存在 |
| 409 | 衝突：同層名稱重複、email 已存在、容量不足 |
| 410 | 分享連結已過期或停用 |
| 413 | 檔案過大 |

> 錯誤格式見 [detailed-design/](./detailed-design/01-overview.md) §14.1；完整錯誤碼表（`code` ↔ HTTP 狀態）見 [detailed-design/](./detailed-design/01-overview.md) §16。

## 20. Docker 開發環境

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

> 正式部署、CI/CD 與維運見 §26。

## 21. 環境變數

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
| EXTERNAL_API_BASE_URL / EXTERNAL_CHAT_MODEL | 舊自動升級路徑的外部模型設定；多組具名連線後每連線自帶 base_url/model（見 §12 多組具名外部模型連線） |

**AI Assistant 完整環境變數**（屬 §12 功能）：`ASSISTANT_ENABLED`、`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`ASSISTANT_MODEL`、`LLM_NUM_CTX`、`LLM_TIMEOUT_SECONDS`、`LLM_KEEP_ALIVE`、`ASSISTANT_MAX_TOOL_ITERATIONS`、`ASSISTANT_SANDBOX_TIMEOUT_SEC`、`EXTERNAL_LLM_ENABLED`、`MAX_LOCAL_ATTEMPTS`、`EXTERNAL_LLM_BASE_URL`/`EXTERNAL_MODEL`/`EXTERNAL_LLM_API_KEY`、`PRIVACY_DEFAULT`。設計建議模型為本地 Gemma 4 26B（`gemma4:26b`）；實際部署可用 `ASSISTANT_MODEL` 覆寫。

前端建議環境變數：

| 名稱 | 說明 |
| --- | --- |
| VITE_API_BASE_URL | 後端 API 位置 |
| VITE_APP_NAME | 應用名稱 |

secret 管理原則：

1. 本機開發：可由 `.env` 提供，`.env` 不進版控；`.env.example` 只放可啟動的示範值。
2. 正式環境：`JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、`SMTP_PASSWORD`、LLM API key、`CREDENTIAL_ENCRYPTION_KEY` 應由 secret manager、CI/CD secret 或受控環境變數注入。
3. 資料庫內不保存明文 refresh token、share token；只保存 hash。
4. 使用者外部模型連線憑證若啟用，保存於 `external_model_connections.secret_encrypted`（多組具名連線，取代舊 `user_external_credentials`），只回傳遮罩提示，不回傳明文。

## 22. 測試計畫

### 22.1 前端測試

使用 Vitest 與 React Testing Library。

測試項目：

1. 登入表單驗證。
2. 檔案列表渲染。
3. 上傳進度顯示。
4. 右鍵選單。
5. 分享彈窗。
6. 搜尋輸入 debounce。
7. 錯誤訊息顯示。
8. AI 助理面板元件（`components/assistant/*.test.tsx`，屬 §12 AI Assistant）。

### 22.2 後端測試

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
12. AI 助理 service／router（`tests/assistant/`，屬 §12 AI Assistant）。

此外，AI 助理另有**獨立評測 harness** `backend/eval/`（屬 §12 AI Assistant）：YAML 案例 + 確定性斷言（workflow/state/safety）+ 可選 LLM judge；多次執行通過率/變異、baseline 回歸；runner 含 in-process mock（CI 預設、決定性）與 API（`--llm real`），Browser runner 見 §22.3。

### 22.3 E2E 測試

使用 Playwright。

測試情境：

1. 使用者登入。
2. 建立資料夾。
3. 上傳檔案。
4. 搜尋檔案。
5. 分享檔案。
6. 另一位使用者開啟分享檔案。
7. 刪除檔案並從垃圾桶還原。
8. AI 助理 Browser 評測（eval harness 的 Playwright runner，屬 §12 AI Assistant）。

### 22.4 回歸防護測試（補充，2026-06-14）

**為什麼需要**：商業邏輯已有單元測試，但「測試空白分析」發現一批**介面與不變式**沒人守——它們不會在開發當下報錯，卻會在重構或加新功能時**無聲回歸**（例如 token 被誤寫進 `localStorage`、Router 漏接例外回錯狀態碼、分享流程斷掉）。因此針對下列高風險區補上「守不變式」的測試（細部覆蓋以實際測試碼為準）：

| 區域 | 防護的回歸風險 | 測試檔 |
| --- | --- | --- |
| 前端 Store 安全不變式 | access token 被誤寫入 `localStorage`／`sessionStorage`（應只在記憶體） | `stores/authStore.test.ts` |
| 前端核心元件行為 | `DriveToolbar`／`FileTable` 的 props 介面或條件渲染被改壞 | `components/drive/DriveToolbar.test.tsx`、`FileTable.test.tsx` |
| 前端 E2E 分享流程 | 兩帳號、跨頁的分享流程在前後端整合時斷掉 | `e2e/share.spec.ts` |
| 後端 Router HTTP 狀態碼 | Router 漏接 Service 例外或回錯 `status_code` | `tests/{upload,trash,search,share}/test_router.py` |
| 後端整合：版本不變式 | 上傳未自動建立 `file_versions` v1 記錄 | `tests/integration/test_file_version_flow.py` |

## 23. 開發里程碑

以**四個階段（週）**推進，各階段即開發順序：

### 23.1 第一週：專案基礎與帳號

1. 建立 frontend 與 backend 專案、Docker Compose、PostgreSQL（pgvector image，供語意搜尋）。
2. FastAPI 基礎架構、React 基礎版面、lint／format／測試工具。
3. 使用者註冊、登入、JWT 驗證。
4. drive_items 資料表與 migration。

### 23.2 第二週：檔案核心（列表／上傳下載／管理）

1. 建立資料夾 API、檔案列表 API、前端我的硬碟頁。
2. 小檔案上傳、檔案下載、容量檢查、上傳進度 UI、檔案圖示與 MIME type 顯示、操作紀錄。
3. 重新命名、移動、星號、最近檔案、垃圾桶、搜尋、右鍵選單。

### 23.3 第三週：分享與預覽

1. 指定使用者分享、分享連結、與我分享頁面。
2. 圖片預覽、PDF 預覽、文字預覽。

### 23.4 第四週：強化與驗收

1. 分片上傳。
2. 測試補齊、權限測試、效能優化。
3. 錯誤處理優化。
4. 部署文件、Demo 準備。

## 24. 驗收標準

功能以 **§5 功能範圍**為基準——§5.1 列的必做功能均可正常操作，即達功能驗收（不在此逐條重述）。除功能完整外，需同時滿足以下品質門檻：

**安全與隔離**

1. 使用者只能存取自己的檔案；不能藉猜測 UUID 存取他人資源。
2. 未授權操作回傳正確錯誤碼（401/403），不洩漏資源是否存在。
3. 分享連結 token 不可預測、可設失效（見 §17）。

**品質與體驗**

4. 前端清楚呈現 loading / empty / error 三種狀態。
5. 容量超限、同名衝突等邊界情況有明確提示（見 §11.2、§19）。

**測試與部署**

6. §22 規劃的前端單元/E2E、後端單元/整合 測試通過。
7. Docker 開發環境可一鍵啟動。

## 25. 風險與對策

| 風險 | 影響 | 對策 |
| --- | --- | --- |
| 大檔案上傳失敗 | 使用體驗差 | 分片上傳與續傳 |
| 權限判斷錯誤 | 資料外洩 | 後端集中權限檢查與測試 |
| 檔案名稱衝突 | 使用者困惑 | 明確衝突策略 |
| 資料夾樹查詢慢 | 列表載入慢 | 索引、ltree 或 closure table |
| 儲存成本上升 | 維運成本高 | 容量限制、垃圾桶清理 |
| 預覽生成耗時 | 使用者等待 | 背景任務與快取 |
| 分享連結外流 | 資料風險 | 密碼、到期時間、撤銷機制 |

## 26. 部署與維運計畫

### 26.1 CI/CD 架構

採 **GitHub Actions + 自架 Runner（self-hosted）**：

- **CI（GitHub 託管 Runner）**：每次 PR / push 執行後端 `pytest`·`ruff`·`mypy`、前端 lint·test·build、前後端 Docker build 檢查；通過且合併 `main` 後建置正式 image。
- **Image Registry（GHCR）**：CI 產出的 image 以 **Git commit SHA** 標記推送至 GHCR；正式 image **只由 CI 產生**，開發者不從本機直接推送。
- **CD（部署主機上的自架 Runner）**：以 `workflow_dispatch` **手動觸發**，自架 Runner 主動領取工作、登入 GHCR、執行固定部署腳本（`docker compose pull` → `up -d` → 健康檢查 → 失敗回滾）。
- 部署主機（家用／校內網路）**不需對外開放埠、不需讓 GitHub SSH 進入**；Runner 以 `systemd` 常駐並主動連線 GitHub。

### 26.2 元件職責

| 元件 | 職責 |
| --- | --- |
| 開發者 | 寫碼、commit、push、開 PR；不發布正式 image |
| GitHub 託管 Runner | 測試、檢查、建置、推送 image |
| GHCR | 儲存通過 CI 的 image（以 SHA 標記） |
| 自架 Runner | 只接收 CD 部署工作，不跑 PR 測試 |
| 部署腳本 | 固定的 pull / up / 健康檢查 / 回滾流程 |

### 26.3 部署流程

1. feature branch → push → PR → CI（GitHub 託管）通過 + review → 合併 `main`。
2. 合併後 CI 重跑測試、建前後端 image、以 commit SHA 推送 GHCR。
3. 於 GitHub Actions 手動觸發 Deploy，輸入要部署的 commit SHA。
4. 自架 Runner 領取 → 登入 GHCR → 部署腳本拉取該 SHA image → 啟動 → 健康檢查 → 成功或自動回滾。

### 26.4 維運

- **健康檢查**：部署後輪詢後端健康端點，連續失敗即判定部署失敗。
- **回滾**：部署失敗自動回到上一個可用的 image SHA（連同該 SHA 的 compose 拓撲一起回滾）。
- **設定隨程式碼同步**：部署時依要部署的 commit SHA，自動把 `compose.prod.yml` 與部署腳本本身（非機密）同步到主機——**部署拓撲改動（如新增服務）隨程式碼一起落地，不需手動上主機改檔**；**唯 `.env` 真密鑰不同步、只在主機**（缺鍵時部署會警告提醒補值）。前置安全：只允許部署 `main` 歷史上的 commit。
- **正式設定**：`.env`（DB 密碼、JWT secret 等）與正式 compose 設定**只存在部署主機、不進 GitHub**；主機記錄目前部署的 image SHA。正式環境的服務對外暴露原則見 §20。
- **備份與監控**：定期備份 PostgreSQL 資料與快照、監控 API 用量與容器健康狀態；以 `docker compose` 管理服務生命週期。

### 26.5 部署安全原則

- 自架 Runner **只用於 private repo、只跑 CD**；PR 一律使用 GitHub 託管 Runner。
- Runner **不以 root 執行、不加入 `docker` 群組**，只能經 `sudo` 執行單一固定部署腳本。
- 正式 image **只由 CI 建立**，部署一律使用**完整 commit SHA**（不用 `latest`）。
- `main` 分支保護：禁止直接 push、需 PR + review + CI 通過；workflow／Dockerfile／部署設定由 maintainer 審查（CODEOWNERS）。

> CI/CD workflow（`.github/workflows/ci.yml`·`deploy.yml`）、正式 compose 與部署腳本的實作見專案實際檔案與 [detailed-design/](./detailed-design/01-overview.md)。

### 26.6 正式環境對外曝露：Cloudflare Tunnel（僅 CD 端）

正式環境（CD）以 **Cloudflare Tunnel（cloudflared）** 作為對外曝露方式，讓網際網路使用者能經由固定網域安全連到 CloudDrive；**本機開發（dev）不使用**，維持既有的直接 port 存取。

- **需求**：使用者以 `https://<CloudDrive 網域>` 存取正式站台；連線由 Cloudflare 邊緣終止 TLS，經 Tunnel 轉到部署主機的前端（nginx）唯一入口。
- **動機（對應本專案環境）**：部署主機為家用／校內網路、**中華電信動態 IP**。Tunnel 由主機**主動向外**建立連線，因此**不需對主機開任何對外 port、不需固定 IP、不受動態 IP 變動影響**，並天然隱藏源站 IP。此與既有的 self-hosted Runner「主機不對外開埠、主動連 GitHub」原則一致（§26.1）。
- **範圍界定**：僅正式環境 compose 新增 `cloudflared` 服務；**dev 的 `docker-compose.yml` 不變**（開發者仍以 `localhost:8088` 等直接存取）。
- **安全**：Tunnel 憑證／token 屬機密，**只存部署主機 `.env`、不進 Git**（與 `JWT_SECRET_KEY` 等一致，§26.4）；`.env.prod.example` 只提供佔位示例。可選再疊 Cloudflare Access（Zero-Trust 登入閘）作為網路層前置驗證——**本次不含，列為後續**。
- **待確認事項**：① CloudDrive 正式站台的**網域名稱**（使用者稍後提供，暫以 `<CloudDrive 網域>` 佔位）；② 前端對外 port 是否仍保留 `8088` 映射，或改由 Tunnel 內部網路直達 `frontend:80`（實作面決定，見 detailed-design §21.9）。

實作（`cloudflared` 服務定義、ingress 路由、token 注入、部署整合）見 [detailed-design/ §21.9](./detailed-design/01-overview.md)。

## 27. 大檔案分片續傳上傳

把 §4.3「支援大型檔案上傳／可中斷續傳」與 §5.2 的分片、續傳項目落實為可開發規格。資料表見 §11（`upload_sessions`／`upload_chunks`）、API 見 §15、流程見 §16.2——**本節只補上述未涵蓋的需求面決策**，不重述。

### 27.1 背景與動機

現況只有單一請求上傳（`POST /upload/simple`，上限 100 MB）。實際使用時，一次拖曳 10 餘個檔案且含 1.93 GB 影片，出現整批失敗：大檔遠超上限、又佔滿瀏覽器對單一來源的連線，使排隊中的小檔一併逾時，前端只顯示無資訊量的 `Network error`。此外後端 simple upload 會把整檔讀進記憶體（記憶體用量 ≈ 檔案大小 ×2），大檔會有 OOM 風險。

### 27.2 功能需求

1. **分片上傳**：前端把檔案切片後逐片上傳；伺服器逐片落地，記憶體用量與檔案大小無關。
2. **續傳（跨工作階段）**：未完成的上傳保存在伺服器；**使用者關閉瀏覽器、重新登入後仍可從中斷處繼續**，不需重傳已完成分片。
3. **暫停／繼續／取消**：上傳清單每筆可手動暫停、繼續、取消；取消即釋放已暫存分片。
4. **真實進度**：以「已完成分片 ÷ 總分片」顯示百分比。
5. **上傳並行上限**：同時進行的檔案數設上限（**建議 3**，其餘排隊），避免多檔互相搶連線導致整批失敗。
6. **錯誤訊息分類**：至少區分**檔案超過上限**、**儲存配額不足**、**連線中斷／逾時**三類並給出對應建議，不再一律顯示 `Network error`。
7. **上傳前預檢**：送出前即以檔案大小比對上限與剩餘配額，超過者**立即標示失敗且不佔用連線**。

### 27.3 非功能需求與限制

- **單檔大小上限：5 GB**（超過即在前端預檢擋下）。
- 伺服器端**不得**將整檔載入記憶體；既有 `POST /upload/simple` 的記憶體累積寫法一併改為串流寫入。
- 對外入口（nginx）只需容納**單一分片**大小，不需放寬到單檔上限。
- 未完成上傳會佔用暫存空間，需有**保留期限與定期清理**（見待確認事項）。

### 27.4 安全與授權

- 上傳工作階段綁定 `user_id`；他人不得查詢、續傳、完成或取消。
- 完成合併時以整檔 checksum 驗證完整性；配額於**建立工作階段時預檢**、**完成時實扣**。
- 取消或過期清理必須一併刪除暫存分片，避免遺留孤兒檔（對應 §7.9 補償式一致性原則）。

### 27.5 不在範圍

- 分片的點對點加密、跨裝置同一上傳續傳（僅同使用者、任何裝置可續傳既有工作階段即可）。
- 物件儲存（S3 等）的原生 multipart upload：儲存層仍為 `LocalStorageProvider`，但介面設計須保留未來替換空間。

### 27.6 驗收標準

1. 5 GB 以內的檔案可成功上傳，且後端記憶體用量不隨檔案大小成長。
2. 上傳中關閉瀏覽器分頁、重新登入後，該檔案可從中斷處繼續，不重傳已完成分片。
3. 暫停後可繼續；取消後暫存分片被清除、配額未被佔用。
4. 一次選取 10 個以上檔案（含大檔）時，並行數受限且**不會**發生互相拖垮的整批失敗。
5. 超過上限或配額不足的檔案，於送出前即顯示明確原因。

### 27.7 已確認參數

| 參數 | 決定 | 說明 |
| --- | --- | --- |
| 未完成上傳保留期限 | **7 天** | 逾期由定期清理刪除工作階段與暫存分片；兼顧「隔天想續傳」與暫存空間。 |
| 分片大小 | **8 MB** | 5 GB 上限約 640 片。對外入口（nginx）因此只需容納單一分片（約 `10m`），**不必**放寬到 5 GB。 |
| 單一檔案的分片上傳方式 | **序列**（一片完成再送下一片） | 並行度只用在「檔案之間」（§27.2 第 5 點，建議 3）。序列的進度計算、重試與續傳最單純；代價是單一大檔無法靠多連線加速，屬已知取捨。 |

> 註：分片仍照常切片，「序列」只影響**傳送順序**，不影響是否分片、是否可續傳、或記憶體用量。若日後大檔上傳速度成為痛點，可改為分片並行，但**必須改用全域請求並行預算**（不分檔案內外統一計數），否則「檔案並行 × 分片並行」會重演連線耗盡問題。

## 28. 公開分享連結存取

### 28.1 背景與動機

分享功能目前只完成一半：使用者可在分享彈窗建立公開連結（可設權限、密碼、到期），但**任何人打開該連結都看不到檔案**——前端 `/s/<token>` 是一個佔位頁（顯示「Share link access will be implemented in Stage 10」），後端也沒有任何可用 token 取得檔案的端點：`/download/{id}` 與 `/preview/{id}` 一律要求登入。

亦即：連結建得出來、複製得走，但**收到連結的人永遠打不開**。已建立並發送出去的連結全部無效。本章補齊這條唯一「不需登入」的對外路徑。

### 28.2 功能需求

1. **開啟連結即可取用**：未登入的訪客開啟 `/s/<token>`，可看到被分享的項目並依權限取用內容。
2. **密碼保護（選填）**：密碼在建立連結時為可選項。未設密碼者開啟即直接取用；有設密碼者先要求輸入，通過後才顯示任何檔案資訊（含檔名）。
3. **權限分級**：沿用建立連結時所選權限——`viewer` 僅可線上預覽；`downloader`（含以上）另可下載原檔。
4. **資料夾分享**：連結指向資料夾時，可瀏覽該資料夾子樹（唯讀），並依權限預覽／下載其中檔案；`downloader` 以上另可**整包 zip 下載**整個子樹。
5. **失效處理**：連結已停用、已過期或 token 不存在時，一律顯示同一則「連結無效或已失效」訊息。
6. **不需帳號**：整段流程不得要求註冊或登入；已登入使用者開啟連結時行為一致。

### 28.3 非功能需求（安全，本章重點）

這是系統中**唯一對外公開、不需認證**的路徑，安全要求高於其他模組：

1. **不可枚舉**：token 需具足夠亂度；驗證失敗一律回同一種錯誤與狀態碼，不可因「token 不存在」與「密碼錯誤」而有可區分的回應或時間差。
2. **不洩漏存在性**：未通過驗證前，不得回傳檔名、大小、型別或任何項目中繼資料。
3. **密碼比對**：以雜湊儲存、常數時間比對；密碼不得出現在 URL、查詢字串或日誌。
4. **最小授權**：連結只授權「該項目及其子樹」，不得藉由 id 存取其他項目；權限不得高於連結所設層級，且不得因分享者本身是 owner 而被提升。
5. **每次存取都驗證**：停用／到期／密碼在**每一次**內容請求時重新驗證，不可只在第一次驗證後就長期放行。
6. **濫用防護**：需限制驗證嘗試頻率，避免成為密碼暴力破解或公開檔案託管的管道。

### 28.4 使用者流程

```text
收到連結 → 開啟 /s/<token>
  → 需要密碼？ → 是 → 輸入密碼 → 驗證失敗則顯示統一錯誤訊息
                 → 否 ↓
  → 顯示項目（檔案：名稱／大小／型別；資料夾：可瀏覽的唯讀清單）
  → viewer：線上預覽
  → downloader 以上：預覽 + 下載原檔
```

### 28.5 驗收標準

1. 未登入開啟有效連結，可看到項目並依權限預覽／下載。
2. 有密碼的連結，未輸入正確密碼前看不到任何項目資訊。
3. `viewer` 連結無法下載原檔；`downloader` 可以。
4. 連結停用或過期後，先前可用的連結立即失效。
5. 錯誤 token 與錯誤密碼回應無法區分。
6. 資料夾連結可瀏覽子樹，且無法藉此存取子樹以外的項目。
7. 未設密碼的連結不出現密碼輸入步驟，開啟即可取用。
8. 同一 token 每分鐘超過 5 次驗證嘗試後被暫時鎖定。
9. `downloader` 以上的資料夾連結可整包 zip 下載，且 zip 內容不含子樹以外的項目。

### 28.6 不在本章範圍

- 連結存取次數統計／稽核報表。
- 匿名訪客上傳（公開連結一律唯讀，不提供寫入權限）。
- 分享給站外使用者的 Email 通知。

### 28.7 已確認決策（2026-07-26）

1. **憑證形式：短效存取憑證**。訪客通過 token（必要時加密碼）驗證後，伺服器發一個**短期有效的存取憑證**，後續預覽／下載請求帶該憑證，而非反覆傳送密碼。理由：轉傳網址或瀏覽器歷史不會挾帶密碼；代價是需要一套憑證過期管理（有效期與續發規則於 detailed-design 定義）。
2. **速率限制：每個 token 每分鐘 5 次**驗證嘗試，超過後暫時鎖定（鎖定時長於 detailed-design 定義）。
3. **資料夾連結支援整包 zip 下載**：`downloader` 以上權限可將分享的資料夾子樹打包下載（沿用既有 `/download/archive` 的打包能力），不限逐檔。

**密碼為選填**：連結建立時密碼是可選的（UI 已標示 optional）。**未設密碼的連結直接開啟，不出現密碼輸入步驟**；僅在建立時設了密碼的連結才要求輸入。兩種情況都走同一套短效憑證機制。

## 29. 我分享出去的項目（Shared by me）

### 29.1 背景與動機

側邊欄現有「Shared with me」（**別人分享給我**的項目），但沒有反向的一覽：使用者**無法知道自己把哪些檔案／資料夾分享出去了**，也無法從單一位置檢視或收回這些分享。目前要確認某個項目是否已分享，只能逐一右鍵開啟分享彈窗查看，分享多了就等於失去掌控——這是隱私與安全上的缺口（可能有早已忘記的公開連結仍然有效）。

### 29.2 功能需求

1. **側邊欄新增「Shared by me」入口**，列出目前登入者**主動分享出去**的所有項目。
2. 每一列顯示：項目名稱／型別、**分享方式**（指定使用者／公開連結）、**權限層級**、建立時間；公開連結另顯示是否設密碼、到期時間、是否仍有效。
3. **同一項目可能同時有多種分享**（分享給數人＋一個公開連結），需能一併呈現。
4. **就地管理**：可直接移除某位使用者的分享、或停用某個公開連結，不必回到檔案列表。
4.1 **清除已失效的連結記錄**：已停用或已過期的公開連結會留在清單上（見第 2 點），必須能把這筆記錄刪掉，否則失效連結只會不斷累積成雜訊，反而蓋掉真正還有效的分享。
5. **主檔案列表標示**：在「My Drive」中，已被分享出去的項目應有可辨識的標記（例如分享圖示），讓使用者一眼看出哪些不是私有的。
6. 已刪除／已在垃圾桶的項目不列出（或明確標示為已刪除）。

### 29.3 驗收標準

1. 分享一個項目給某使用者後，該項目立即出現在「Shared by me」，並顯示對象與權限。
2. 建立公開連結後，該項目出現在清單並顯示連結狀態（密碼／到期／有效）。
3. 於清單中移除分享或停用連結後，對方立即失去存取權。
3.1 已失效的連結記錄可從清單中刪除，刪除後不再出現。
4. 同時有多種分享的項目只出現為一列，但可展開看到全部分享對象與連結。
5. 「My Drive」中已分享的項目有可辨識標記，未分享的沒有。

### 29.4 不在本章範圍

- 分享存取次數統計／稽核紀錄。
- 批次管理（一次收回多個項目的分享）。

### 29.5 已確認決策（2026-07-26）

1. **清單依項目分組**：一個項目一列，展開後才看到全部分享對象與公開連結（即 §29.3 驗收標準 4）。同一項目分享給 3 人不會佔 3 列。
2. **「My Drive」用兩種圖示分開標示**：「已分享給指定使用者」與「已建立公開連結」各自一個圖示，兩者都有就並列。理由：公開連結是唯一對外、不需登入的路徑（§28.3），風險等級與「分享給某個帳號」不同，必須一眼分辨得出來，不可混為同一個標記。
3. **不提供「一鍵收回此項目的所有分享」**：只做 §29.2 第 4 點的逐筆就地移除／停用。理由：收回是不可逆操作，一次砍掉全部分享的誤按代價過高，且本章已把「批次管理」列為不在範圍（§29.4）。
4. **「停用」與「刪除記錄」分成兩步**（2026-07-27 追加）：仍有效的連結只提供「停用」（切斷存取、保留記錄）；已失效的連結才提供「刪除」（清掉那筆記錄）。理由：這兩件事的後果完全不同——停用會立刻讓別人打不開，刪除只是整理自己的清單。合成一顆按鈕會讓「我只是想把這行清掉」變成「我不小心切斷了還在用的連結」。

## 30. 拖曳移動到資料夾

### 30.1 背景與動機

目前把檔案換位置只有一條路：右鍵 →「Move to」→ 在對話框裡挑目的地。整理大量檔案時每搬一個就要開一次對話框，而畫面上明明就看得到目的資料夾。所有主流雲端硬碟（OneDrive、Google Drive、Finder）都支援直接把項目拖到資料夾上，使用者也預期如此。

注意這與既有的兩種拖曳都不同，必須共存：**框選**（空白處拖曳圈選多個項目）與**拖曳上傳**（從桌面把檔案拖進來）。

### 30.2 功能需求

1. **拖曳單一項目到資料夾**：在檔案／資料夾上按住拖曳，放到某個資料夾上即移入該資料夾。
2. **拖曳多選項目**：若被拖曳的項目屬於目前的多選範圍，整批一起移動；若不屬於，只移動被拖的那一個。
3. **視覺回饋**：拖曳中的項目要有拖曳態；游標下方可放置的資料夾要明顯標示；不可放置處不得給出可放置的假象。
4. **兩種檢視都支援**：清單（FileTable）與格狀（FileGrid）行為一致。
5. **無效目標不接受**：放到檔案（非資料夾）、放到被拖曳項目自身、把資料夾放進自己的子樹，皆不執行移動。
6. **與既有拖曳互不干擾**：從項目上開始拖曳不得觸發框選；內部拖曳不得觸發「拖曳上傳」的全螢幕覆蓋層。
7. **失敗要說清楚**：批次移動時若部分項目失敗（例如目的地已有同名檔案），成功的照常完成，並明確告知哪些沒搬成功、原因為何。

### 30.3 驗收標準

1. 把一個檔案拖到資料夾上後放開，該檔案出現在該資料夾內、從原位置消失。
2. 勾選多個項目後拖曳其中之一，全部一起移入目的資料夾。
3. 拖曳一個未被選取的項目時，只有該項目被移動，既有選取不受影響。
4. 拖曳過程中，游標下的資料夾有明顯標示；移開後標示消失。
5. 把資料夾拖到自己身上或自己的子資料夾內，不會發生移動，並顯示錯誤說明。
6. 把項目拖到檔案上不會發生任何事。
7. 從項目上開始拖曳不會出現框選矩形；從空白處拖曳仍可框選。
8. 內部拖曳過程中不出現「Drop files or folders to upload」覆蓋層。
9. 批次移動中若有同名衝突，其餘項目仍成功移動，並列出失敗項目與原因。

### 30.4 不在本章範圍

- 拖到麵包屑或側邊欄（例如拖到「My Drive」回到根目錄）。
- 跨瀏覽器分頁／視窗的拖曳。
- 拖曳排序（本系統排序由欄位決定，非手動）。
- 拖曳複製（按住修飾鍵複製而非移動）。

### 30.5 已確認決策（2026-07-27）

1. **採用 HTML5 Drag and Drop API**，而非自行以 pointer events 實作。理由：可直接沿用瀏覽器原生的拖曳影像與游標回饋；更關鍵的是 `dataTransfer.types` 天然區分「內部項目拖曳」與「外部檔案拖入」，這正是需求 6 要的隔離，自幹 pointer 事件反而要另外想辦法辨識。
2. **拖曳未選取的項目時不改變既有選取**：只移動被拖的那一個。理由：拖曳是移動手勢，不是選取手勢；若順手清掉使用者辛苦選好的範圍，代價比省下一次點擊大得多。
3. **批次移動逐一送出、不整批回滾**：後端沒有批次移動端點，且部分失敗（同名衝突）是常態而非例外。已搬成功的不應該因為別人失敗而被搬回去。

## 31. 結論

本專案的核心不是只做「檔案上傳」，而是要建立完整的檔案管理系統。因此設計上需同時考慮檔案本體儲存、資料庫中繼資料、權限、分享、搜尋、垃圾桶、容量限制與使用者體驗。

目前核心 MVP 與擴充模組已大致完成：登入、我的硬碟、資料夾、上傳、下載、搜尋、垃圾桶、容量統計、分享連結、檔案版本、預覽、In-App AI Assistant 與時光機（Snapshots）皆已有對應實作與測試紀錄。後續正式開發文件應把這些已完成能力整合成「使用者介面 → API → 資料表 → 時序圖 → 測試驗收」的交接文件，而不是停留在早期功能規劃。

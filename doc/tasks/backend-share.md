# Backend Share 模組任務

## 完成定義

- owner 可分享給指定使用者、更新權限、移除分享。
- 被分享者可取得「與我分享」列表。
- 公開連結、密碼與到期時間具備第二階段實作。

## 指定使用者分享任務

- [x] 建立 `Share` SQLAlchemy model。
- [x] 建立 share permission enum。
- [x] 建立 share request/response schemas。
- [x] 建立 `ShareRepository`。
- [x] 實作依 item 與 target user 查詢 share。
- [x] 實作建立 share。
- [x] 實作更新 permission。
- [x] 實作刪除 share。
- [x] 實作列出 shared-with-me。
- [x] 建立 `ShareService`。
- [x] 驗證只有 owner 可分享。
- [x] 驗證不可分享給自己。
- [x] 依 email 查找 target user。
- [x] 重複分享時更新 permission。
- [x] 寫入 share activity log。
- [x] 寫入 unshare activity log。
- [x] 建立 share router。
- [x] 實作分享給使用者 endpoint。
- [x] 實作更新分享權限 endpoint。
- [x] 實作移除分享 endpoint。
- [x] 實作 `GET /share/shared-with-me`。

## 公開連結任務

- [x] 建立 `ShareLink` SQLAlchemy model。
- [x] 建立 `ShareLinkRepository`。
- [x] 建立安全隨機 share token。
- [x] 資料庫只保存 token hash。
- [x] 實作可選密碼 hash。
- [x] 實作可選 expires_at。
- [x] 實作 link 停用。
- [x] 建立 `ShareLinkService`。
- [x] 實作建立公開連結 endpoint。
- [x] 實作公開連結驗證 endpoint。
- [x] 實作停用公開連結 endpoint。
- [x] 驗證過期 link。
- [x] 驗證停用 link。
- [x] 驗證 link password。

## 測試任務

- [x] 測試 owner 建立分享。
- [x] 測試非 owner 不可分享。
- [x] 測試 target email 不存在。
- [x] 測試不可分享給自己。
- [x] 測試重複分享更新權限。
- [x] 測試移除分享。
- [x] 測試資料夾分享權限繼承。
- [x] 測試公開連結不保存明文 token。
- [x] 測試公開連結密碼。
- [x] 測試公開連結到期。
- [x] 測試公開連結停用。


---

## 階段 2 追加：公開連結免認證存取（proposal §28 / DEC-037）

**目標**：讓收到公開連結的訪客真的打得開檔案。目前 `/s/<token>` 無對應後端端點，已發出的連結全部無效。

**範圍**：新增 `app/public_share/` 套件與 `/api/v1/public/*` 端點、share 存取憑證、連結速率限制。
**不含範圍**：存取次數統計／稽核報表、匿名訪客上傳、Email 通知（proposal §28.6）。
**前置依賴**：無（既有 `share_links` 表與 `ShareLinkService` 已可用）。
**設計依據**：§6.12.8–§6.12.11、§7.6、§13。

### 子任務

- [x] `backend/app/core/security.py`：新增 `create_share_access_token()` / `decode_share_access_token()`（`type="share_access"`，claims 含 `sub`/`itm`/`prm`/`iss_at_chain`）。
- [x] `backend/app/core/config.py`：新增 `SHARE_ACCESS_TOKEN_EXPIRE_MINUTES`(15)、`SHARE_ACCESS_TOKEN_MAX_LIFETIME_MINUTES`(240)、`SHARE_LINK_ATTEMPT_LIMIT`(5)、`SHARE_LINK_LOCKOUT_MINUTES`(5)。
- [x] `backend/app/models/share_link.py`：新增 `attempt_window_start` / `attempt_count` / `locked_until`。
- [x] `backend/alembic/versions/0020_share_link_rate_limit.py`：對應 migration（接在 `0019` 之後）。
- [x] `backend/app/public_share/__init__.py`、`schemas.py`：`PublicSessionResult`、`PublicItemResponse` 等。
- [x] ~~`backend/app/public_share/repository.py`~~：不需要獨立檔案——連結查詢與速率限制欄位加在既有 `app/share/repository.py`（`get_by_id` / `update_attempt_state`），子樹判定在 service 以 `parent_id` 上溯（深度上限 64）而非遞迴 CTE。
- [x] `backend/app/public_share/service.py`：`open_session` / `refresh_session` / `get_item` / `list_children` / `open_content` / `build_archive`。
- [x] `backend/app/public_share/router.py`：7 個端點（§6.12.9），**不得依賴 `CurrentUserId`**。
- [x] `backend/app/api/v1/router.py`：掛載 `public_share` router。
- [x] 移除舊的 `POST /share/links/validate`（由 `POST /public/links/{token}/session` 取代），同步更新既有測試。

### 測試任務

- [x] 未設密碼的連結可直接換到憑證，回應含根項目中繼資料。
- [x] 密碼錯誤與 token 不存在的回應狀態碼／錯誤碼／訊息完全相同。
- [x] share 憑證無法通過 `get_current_user_id`（不可冒充使用者）。
- [x] 使用者 access token 無法存取 `/public/*`。
- [x] `viewer` 憑證下載原檔回 403；`downloader` 成功。
- [x] 以憑證存取子樹以外的 item id 回 404（非 403）。
- [x] 分享者停用連結後，尚未過期的憑證立即失效。
- [x] 第 6 次驗證嘗試被鎖定；鎖定期滿後恢復。
- [x] 續發不能突破總時長上限。
- [x] integration：`downloader` 資料夾連結可取得 zip，且 zip 內不含子樹以外項目。

### 追加（實作時發現，非原規劃）

- [x] `app/preview/service.py`：抽出 `content_for_item()` 與 `resolve_preview_type()`，讓公開路徑重用 Office 轉 PDF／文字截斷，不重寫一份。
- [x] `app/share/service.py`：公開連結密碼改用 `hash_password`（pwdlib），取代裸 SHA-256。
- [x] `app/share/service.py`：**修既有漏洞**——`deactivate_link` 從未驗證擁有權（舊註解宣稱 router 會做，router 沒做），任何登入者知道 link id 就能停用他人連結。已加 owner 檢查與回歸測試。

### 驗收條件

proposal §28.5 全部 9 項通過；`uv run pytest` / `mypy` / `ruff` 全綠。

**驗證結果（2026-07-26）**：單元 25 項（`tests/public_share/`）+ integration 7 項（`tests/integration/test_public_share_flow.py`，對真 Postgres）全過；後端全套 781 passed；`ruff` / `mypy` 全綠；migration `0020` 於全新 DB 跑完整條鏈並測過 downgrade。

### 風險

- 免認證路徑，任何權限判斷疏漏即為對外漏洞——子樹邊界與 `prm` 取值必須有測試守住，不可只靠 code review。
- 時間差不可區分：`pwdlib` 雜湊為主要耗時來源，token 查無時的 dummy 比對不可省略。

---

## 階段 2 追加：Shared by me（proposal §29 / DEC-038）

**目標**：讓使用者從單一位置看到自己分享出去了什麼，並就地收回。
**範圍**：`GET /share/shared-by-me` + `DriveItemResponse` 兩個標記欄位。
**不含範圍**：批次收回、存取統計（proposal §29.4、§29.5 決策 3）。
**設計依據**：§6.12.12。

### 子任務

- [x] `backend/app/share/schemas.py`：`SharedByMeUserShare` / `SharedByMeLink` / `SharedByMeEntry`。
- [x] `backend/app/share/repository.py`：以 owner 撈 `shares` + `share_links`，批次 join `drive_items`（排除 `is_deleted`）。
- [x] `backend/app/share/service.py`：`list_shared_by_me()`，以 `item_id` 聚合成一項目一列。
- [x] `backend/app/share/router.py`：`GET /share/shared-by-me`（分頁）。
- [x] `backend/app/schemas/`：`DriveItemResponse` 新增 `is_shared_with_users` / `has_active_public_link`。
- [x] `backend/app/drive/service.py`：`list_items` 以一次 `IN` 批次查詢填入兩欄位（不可 N+1）。

### 測試任務

- [x] 分享給使用者後該項目出現在 `shared-by-me`，含對象與權限。
- [x] 建立公開連結後該項目出現，`has_password` 正確且不回傳 hash。
- [x] 同一項目分享給 3 人 + 1 條連結 → 只回 1 個 entry，`user_shares` 長度 3。
- [x] 項目丟垃圾桶後不再列出。
- [x] 連結停用後仍列出但 `is_active=false`。
- [x] `list_items` 兩個標記欄位正確；非 owner 檢視時皆為 `false`。

### 驗收條件

proposal §29.3 全部 5 項通過（第 5 項需搭配前端）；三項品質檢查全綠。

**驗證結果（2026-07-26）**：單元 6 項（`tests/share/test_service.py`）+ 標記欄位 3 項（`tests/drive/test_service.py::TestShareBadges`，含「每頁一次查詢、不隨列數增加」）+ integration 2 項（真 Postgres 聚合查詢）；後端全套 **790 passed**；`ruff` / `mypy` 全綠。

### 追加（2026-07-27，使用者回報：失效連結無法清除）

- [x] `app/share/repository.py`：`AbstractShareLinkRepository.delete()` + SQL 實作。
- [x] `app/share/service.py`：`delete_link_record()`——驗證擁有權；連結仍有效時回 422 要求先停用。抽出 `_owned_link()` 供停用與刪除共用。
- [x] `app/share/router.py`：`DELETE /share/links/{link_id}/record`（路由順序須在 `/links/{link_id}` 之前）。
- [x] 測試：已停用可刪、已過期可刪、仍有效回 422、非 owner 回 403、integration 一輪完整流程。

### 修正（2026-07-29，使用者回報）：公開連結選 Editor 會 500

**症狀**：分享彈窗 Link 分頁把權限設為 Editor 後按「Create link」失敗。

**根因鏈**：`PermissionSelect` 是 People／Link 兩個分頁共用的元件，提供 viewer/downloader/editor 三級；`ShareLinkRequest.permission` 用通用的 `Permission`（四級全收）；資料庫 `ck_share_links_permission` 只允許 viewer/downloader → IntegrityError → 500。設計 §6.12.4 原本就寫 `create_link(permission: LinkPermission)`，屬實作與設計脫節。

- [x] `app/permission/permissions.py`：新增 `LinkPermission`（viewer/downloader）。
- [x] `app/share/schemas.py`：`ShareLinkRequest.permission` 改用 `LinkPermission` → 越界值在邊界回 422。
- [x] `app/share/service.py`：`create_link` 簽章同步。
- [x] `app/assistant/skills/builtin/write.py`：助理的 `share_item` 技能同為呼叫端（mypy 抓到），一併改用 `LinkPermission.VIEWER`。
- [x] `PermissionSelect` 新增 `allowed` prop；`ShareLinkPanel` 限制為 viewer/downloader。
- [x] 測試：後端「editor 回 422 且不呼叫 service」「viewer/downloader 仍為 201」；前端「Link 分頁只有兩級」「People 分頁仍有 editor」。

---

## 階段 2 追加：公開連結的臨時編輯權（proposal §33 / 設計 §6.12.11b）

**目標**：讓沒有帳號的外部人員憑連結修改被分享的內容，能力與登入 editor 相同，並有時效與稽核。
**不含範圍**：匿名者身分識別、即時協作、永久刪除、再分享（proposal §33.5）。
**前置依賴**：§28 公開連結存取（已完成）。

### 子任務

- [x] `alembic/versions/0021_share_link_editor.py`：`ck_share_links_permission` 放寬納入 `editor`（drop + recreate constraint）。
- [x] `app/permission/permissions.py`：`LinkPermission` 加 `EDITOR`。
- [x] `app/share/service.py`：`create_link` 於 `permission == editor` 且 `expires_at is None` 時回 422。
- [x] `app/public_share/service.py`：新增 `_assert_can_edit`（驗 `prm == editor`）；`create_folder` / `upload` / `rename` / `move` / `trash` 五個方法，一律先驗權限＋子樹再以 `root.owner_id` 呼叫下游。
- [x] `app/public_share/router.py`：對應五個端點；`Request` 取 `ip_address` / `user_agent` 傳入稽核。
- [x] 稽核：每筆寫入以 `ActivityLogService.log(actor_id=<連結建立者>, metadata={"via_share_link_id": ...}, ip_address=..., user_agent=...)`。
- [x] 前端 `PermissionSelect` 的 `allowed` 於 Link 分頁改為三級；選 editor 時到期欄位變必填並提示。

### 測試任務

- [x] editor 連結未帶到期時間 → 422；viewer/downloader 不受影響。
- [x] viewer / downloader 憑證呼叫寫入端點 → 403。
- [x] editor 憑證可上傳、覆寫（`file_versions` +1）、改名、移動、移到垃圾桶。
- [x] 子樹外的 item 寫入 → 404（非 403，避免確認 id 存在）。
- [x] 無法永久刪除、無法建立新連結。
- [x] 匿名上傳計入擁有者配額；不足時 413。
- [x] `activity_logs` 帶 `via_share_link_id`，`actor_id` 為連結建立者。
- [x] 連結被移除後既有憑證的寫入立即失敗。
- [x] integration：真 Postgres 跑一輪「建 editor 連結 → 訪客上傳 → 擁有者容量增加 → 稽核可追溯」。

### 驗收條件

proposal §33.4 全部 7 項通過；`uv run pytest` / `mypy` / `ruff` 全綠。

**驗證結果（2026-07-31）**：後端 **941 passed** + integration **62 passed**；前端 **338 passed**；四項檢查全綠。migration 0021 於全新 DB 跑完整條鏈，upgrade 後約束納入 editor、downgrade 後回到兩級（downgrade 會先清掉既有 editor 連結，否則舊約束會擋）。integration 實測「建 editor 連結 → 訪客上傳 → 檔案出現在擁有者資料夾 → 擁有者 used_bytes 增加」。

**實作時被守衛擋下的一次**：`PublicShareService` 對未接上的下游 service 會丟 `RuntimeError`，integration 第一次跑就抓到 router 工廠漏接 `upload_svc`/`trash_svc`/`drive_svc`——若當初讓它靜默為 None，這個漏洞會等到有人用才炸。

### 風險

- **下游以 owner 身分執行**：邊界完全靠 `PublicShareService` 自己擋，下游的權限檢查在此情境是 no-op。任何新增的訪客寫入端點都必須自行呼叫 `_assert_can_edit` + `_resolve_in_subtree`，漏掉即等於把 owner 權限交給匿名者。
- **無上傳上限**（proposal §33.6 決策 4）：外洩的連結可填滿擁有者配額並使其自身無法上傳。

---

## 階段 4 追加：訪客多選打包下載（proposal §34.4 / 設計 §6.12.8）

**背景**：訪客只能打包**整個分享根**（`GET /public/archive`）。§34 要求訪客頁的批次操作與 My Drive 一致，而 My Drive 的 `Download (N)` 走 `POST /download/archive` 收 `item_ids`——訪客端缺這個能力。

### 子任務

- [x] `app/public_share/service.py`：`archive()` 增加 `item_ids: list[UUID] | None = None`；`None` 維持整根打包，給定清單則**逐一** `_resolve_in_subtree` 後交給 `DownloadService.archive`。
- [x] `app/public_share/router.py`：新增 `POST /public/archive`（body `{item_ids}`），保留既有 `GET`。
- [x] 空清單回 422（不默默等同整根打包）。

### 測試任務

- [x] `downloader`／`editor` 憑證可打包指定項目；zip 內含所選檔案。
- [x] 任一 id 在子樹外 → **整個請求 404**，不做部分打包。
- [x] `viewer` → 403。
- [x] 空 `item_ids` → 422。
- [x] 既有 `GET /public/archive` 行為不變。

### 驗收條件

proposal §34.4 全部 4 點通過；`uv run pytest` / `mypy` / `ruff` 全綠。

### 驗證結果（2026-07-31）

後端 **1010 passed**（`tests/integration/test_assistant_flow.py` 的 5 項因本機未跑 Ollama 而 `ASSISTANT_UNAVAILABLE`，與本次改動無關，故排除）；ruff format／check、mypy 全綠。integration 實測「訪客只打包所選項目 → zip 內有 wanted.txt、沒有 skipped.txt」與「夾帶子樹外的 id → 整個請求 404」。

### 風險

- **部分打包是資訊洩漏管道**：若對子樹外的 id 採「略過並打包其餘」，訪客可用「zip 少了哪一個」推斷某 id 是否存在。因此設計上明訂為全有全無（§6.12.8）。

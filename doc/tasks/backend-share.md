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

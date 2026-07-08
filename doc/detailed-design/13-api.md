## 13. API 詳細設計

### 13.1 統一 Response 規則

成功時依 API 回傳資料。

錯誤時統一格式：

```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Storage quota exceeded",
    "details": {}
  }
}
```

### 13.2 分頁格式

列表 API 統一使用：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 50
}
```

### 13.3 DriveItemResponse

```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "parent_id": null,
  "item_type": "file",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "extension": "pdf",
  "size_bytes": 102400,
  "is_starred": false,
  "is_deleted": false,
  "created_at": "2026-06-11T14:00:00Z",
  "updated_at": "2026-06-11T14:00:00Z"
}
```

### 13.4 API 與模組對應

| API | Router | Service |
| --- | --- | --- |
| `/auth/*` | AuthRouter | AuthService |
| `/drive/items` | DriveRouter | DriveService |
| `/upload/simple` | UploadRouter | UploadService |
| `/drive/items/{id}/download` | DriveRouter | DownloadService |
| `/drive/items/{id}/preview` | DriveRouter | PreviewService |
| `/trash/*` | TrashRouter | TrashService |
| `/search` | SearchRouter | SearchService |
| `/share/*` | ShareRouter | ShareService / ShareLinkService |

### 13.5 完整端點清單

Base path：`/api/v1`。下表涵蓋全部 60 個端點；**逐欄位 request／response body、enum 值與校驗規則以 OpenAPI 自動生成為準**（執行時 `/docs`、`/openapi.json`），錯誤碼對照見 §15。認證欄：🔐 需 access token、🔓 公開。

**Auth（`/auth`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 註冊使用者 | 🔓 |
| POST | `/auth/login` | 登入（回 access token + 設 refresh cookie） | 🔓 |
| POST | `/auth/forgot-password` | 忘記密碼（隨機臨時密碼 + 防枚舉） | 🔓 |
| POST | `/auth/refresh` | 以 refresh cookie 換新 access token | 🔓（cookie） |
| POST | `/auth/logout` | 登出並撤銷 refresh token | 🔐 |
| GET | `/auth/me` | 取得目前登入使用者 | 🔐 |

**Users（`/users/me`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| GET | `/users/me` | 個人資料 | 🔐 |
| PATCH | `/users/me` | 更新顯示名稱 | 🔐 |
| PATCH | `/users/me/email` | 更新登入 Email | 🔐 |
| PATCH | `/users/me/password` | 更新密碼（驗目前密碼） | 🔐 |
| GET | `/users/me/quota` | 容量使用狀況 | 🔐 |

**Drive（`/drive`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| GET | `/drive/items` | 列出資料夾內容（sort/order/分頁） | 🔐 |
| GET | `/drive/items/{id}` | 取得單一項目 | 🔐 |
| POST | `/drive/folders` | 建立資料夾 | 🔐 |
| PATCH | `/drive/items/{id}/name` | 重新命名 | 🔐 |
| PATCH | `/drive/items/{id}/parent` | 移動 | 🔐 |
| PUT | `/drive/items/{id}/star` | 設定/取消星號 | 🔐 |
| GET | `/drive/items/{id}/ancestors` | 祖先路徑（麵包屑） | 🔐 |
| GET | `/drive/recent` | 最近項目 | 🔐 |

**Upload／Download／Preview／Version**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/upload/simple` | 小檔直接上傳 | 🔐 |
| GET | `/download/{item_id}` | 下載單一檔案（串流） | 🔐 |
| POST | `/download/archive` | 多選打包為 zip（`{item_ids}`，資料夾遞迴） | 🔐 |
| GET | `/preview/{item_id}` | 預覽資訊 | 🔐 |
| GET | `/preview/{item_id}/content` | 預覽內容 | 🔐 |
| GET | `/drive/items/{item_id}/versions` | 檔案版本列表 | 🔐 |

**Search（`/search`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| GET | `/search` | 檔名 + 全文內容搜尋 | 🔐 |
| GET | `/search/semantic` | 語意搜尋（pgvector，預設關） | 🔐 |
| POST | `/search/embeddings/backfill` | 舊檔 embedding 補建 | 🔐 |

**Share（`/share`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/share/items/{id}` | 分享給指定使用者 | 🔐 |
| DELETE | `/share/items/{id}/users/{target_user_id}` | 移除分享對象 | 🔐 |
| GET | `/share/shared-with-me` | 與我分享的項目 | 🔐 |
| POST | `/share/items/{id}/links` | 建立公開分享連結 | 🔐 |
| POST | `/share/links/validate` | 驗證公開連結（token/密碼） | 🔓 |
| DELETE | `/share/links/{link_id}` | 停用分享連結 | 🔐 |

**Trash（`/trash`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/trash/items/{id}` | 移到垃圾桶 | 🔐 |
| GET | `/trash` | 垃圾桶列表 | 🔐 |
| POST | `/trash/items/{id}/restore` | 還原 | 🔐 |
| DELETE | `/trash/items/{id}` | 永久刪除單項 | 🔐 |
| DELETE | `/trash` | 清空垃圾桶 | 🔐 |

**Assistant（`/assistant`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/assistant/chat` | 對話（回計畫或技能提案） | 🔐 |
| GET | `/assistant/sessions` | 對話列表 | 🔐 |
| GET | `/assistant/sessions/{id}/messages` | 對話訊息 | 🔐 |
| POST | `/assistant/workflows/{id}/confirm` | 確認 pending 計畫 | 🔐 |
| POST | `/assistant/workflows/{id}/cancel` | 取消 pending 計畫 | 🔐 |
| POST | `/assistant/workflows/save` | 命名儲存 workflow | 🔐 |
| GET | `/assistant/workflows/saved` | 已存 workflow | 🔐 |
| POST | `/assistant/workflows/saved/{id}/rerun` | 一鍵重跑 | 🔐 |
| GET | `/assistant/skills` | 已安裝技能列表 | 🔐 |
| POST | `/assistant/skills/{id}/approve` | 核可安裝技能 | 🔐 |
| PATCH | `/assistant/skills/{id}` | 編輯技能（改碼重跑 codeguard） | 🔐 |
| DELETE | `/assistant/skills/{id}` | 刪除技能 | 🔐 |
| POST | `/assistant/skills/{id}/execute` | 沙箱執行技能並寫回 drive | 🔐 |

**Snapshots／時光機（`/snapshots`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| POST | `/snapshots` | 手動建立快照 | 🔐 |
| GET | `/snapshots` | 快照時間軸列表 | 🔐 |
| GET | `/snapshots/{id}/items` | 瀏覽某快照內容 | 🔐 |
| POST | `/snapshots/{id}/restore` | 還原到所選快照 | 🔐 |
| GET | `/snapshots/settings` | 讀取快照設定 | 🔐 |
| PUT | `/snapshots/settings` | 更新快照設定 | 🔐 |

**External Model（`/users/me/external-credentials`）**

| Method | Path | 用途 | 認證 |
| --- | --- | --- | --- |
| GET | `/users/me/external-credentials` | 取得外部模型憑證（遮罩） | 🔐 |
| PUT | `/users/me/external-credentials` | 設定外部模型憑證（加密存） | 🔐 |
| DELETE | `/users/me/external-credentials/{provider}` | 刪除憑證 | 🔐 |

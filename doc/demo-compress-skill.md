# Demo 記錄：AI 助理現場生成「壓縮檔」技能

實機瀏覽器操作紀錄。對應設計 [detailed-design.md §9](./detailed-design.md)（AI 助理引擎）、決策 DEC-019（自我撰寫技能：核可→沙箱→稽核）。

## 環境

| 項目 | 值 |
|---|---|
| 應用 | docker-compose（前端 `:8088`、後端容器 `:8000`→主機 `:8001`、PostgreSQL `pgvector/pgvector:pg16`） |
| LLM | 內網 Ollama **Gemma 4 26B**（`gemma4:26b` @ `192.168.10.75:11434`，`LLM_PROVIDER=ollama`） |
| 帳號 | `sandboxdemo` |
| 瀏覽器 | Claude in Chrome |
| 產出 | `compress-skill-demo.gif`（30 frames，瀏覽器下載） |

## 下達的指令（自然語言）

> 請做一個把檔案壓縮成 zip 的技能，並用它把 scores.csv 和 data.json 壓縮成一個 zip 檔

## 完整流程（前端畫面 ↔ 後端 API ↔ 證據）

| # | 步驟 | 前端畫面 | 後端 / 證據 |
|---|---|---|---|
| 1 | 開啟助理 | 右下角 → 「CloudDrive Assistant」面板 | — |
| 2 | 送出指令 | 使用者訊息泡泡 → 助理顯示 **Thinking** | `POST /api/v1/assistant/chat` |
| 3 | **現場生成技能** | 助理回「我生成了一個技能『compress_to_zip』…核可後才會安裝；執行會在受限沙箱中進行」+ **Skill proposal 卡**（Review code / Dismiss / Approve） | Gemma codegen 產生程式碼 |
| 4 | 檢視程式碼 | 「Review generated skill」對話框：`import zipfile` / `from pathlib import Path` / `def run(input_path, output_dir, params)`，正確處理檔案與資料夾、`ZIP_DEFLATED`；底部註明「只在受限沙箱執行（無網路、無 shell、寫入受限），且需核可後才跑」 | **通過 codeguard 靜態檢查**（未被拒、可 Approve） |
| 5 | 核可安裝 | 點 **Approve & install** → 助理回「Installed Compress to ZIP.」 | `POST /api/v1/assistant/skills/{id}/approve` 200 |
| 6 | 動態右鍵選單 | 右鍵 `scores.csv` → 選單出現安裝的技能（含 **Compress to ZIP**），技能依 manifest 動態掛入 | — |
| 7 | **沙箱執行 + 寫回** | 點 Compress to ZIP → 結果對話框「zip_single_file produced 1 file(s) from scores.csv」<br>Produced Files: `["scores.csv.zip"]`<br>Summary: `{"status":"success","message":"Compressed scores.csv to scores.csv.zip","output_path":"/tmp/skill_sandbox_dn50bzg0/output/scores.csv.zip"}` | `POST /api/v1/assistant/skills/{id}/execute` 200；**`output_path` 在 `/tmp/skill_sandbox_*` ← 受限沙箱**；產物 ingest 回 Drive |
| 8 | 驗證 | Drive 搜尋可見 **`scores.csv.zip`** | 產物成功寫回 |

## 後端 API 軌跡（log 佐證）

```
POST /api/v1/assistant/chat                          200   # 現場生成技能提案
POST /api/v1/assistant/skills/{id}/approve           200   # 使用者核可安裝
POST /api/v1/assistant/skills/{id}/execute           200   # 受限沙箱執行 + 寫回
```

## 驗證到的關鍵設計點

- **現場生成（codegen）**：本地 Gemma 26B 從自然語言生成可用的 `zipfile` 壓縮程式碼。
- **codeguard 靜態檢查**：生成碼先過 AST 靜態掃描，通過才允許核可。
- **核可閘**：程式碼**絕不自動執行**——必經使用者 Review + Approve。
- **受限沙箱**：執行在 `/tmp/skill_sandbox_*`，無網路、無 shell、寫入受限於 output。
- **動態 UI**：安裝後技能依 manifest 動態掛入檔案右鍵選單。
- **產物 ingest**：沙箱 output 的 `scores.csv.zip` 寫回使用者 Drive。

> 註：此次以右鍵選單對單一檔案 `scores.csv` 執行，產出 `scores.csv.zip`；對多檔/資料夾壓縮同一技能亦適用（`run` 對 directory 會遞迴 `rglob` 打包）。

# Codex 訂閱憑證「跨機」可行性 demo

驗證一件事：**`codex login` 產生的憑證（`auth.json`，含 agent 私鑰）複製到「另一台機器（乾淨環境）」後，能不能直接拿來呼叫 + refresh？**

這對應 [`doc/external-model-integration.md`](../../doc/external-model-integration.md) §9 的核心問題：多使用者集中式要把使用者的 Codex 憑證搬到 server 端代呼叫，到底行不行。

> 與專案程式無關：本目錄是獨立實驗，不動 backend/frontend。

## ⚠️ 安全（務必先讀）

- `auth.json` **含 access token / agent 私鑰，等同密碼**。官方原話：*"Treat `~/.codex/auth.json` like a password."*
- 本 demo 的 `transfer/` 與所有 `auth.json` **已被 `.gitignore` 排除，絕不可進版控、不可貼到聊天/issue**。
- 跑完請 `docker compose down -v` 清掉 volume。

## 這個 demo 能 / 不能驗證什麼

| 能驗證 ✅ | 不能驗證 ❌ |
| --- | --- |
| `auth.json` 是否**自足可搬**（私鑰在不在裡面） | ChatGPT 端對「多地、多 IP」的**風控/濫用偵測**（兩容器在同一宿主、同一出口 IP） |
| 搬到**不同 hostname 的乾淨環境**能否呼叫成功（≈ 非原機） | 真實多使用者規模下的額度/限流 |
| access token 過期後能否在非原機 **refresh** | 是否違反服務條款（這是政策問題，非技術） |

換句話說：demo 證實/排除「**綁機（技術硬傷）**」；風控與合規仍需你自行權衡。

## 前置

1. 一個 **Codex / ChatGPT 訂閱帳號**。
2. 在 ChatGPT **Settings → Security 開啟 device code login**（admin 則在 workspace 權限），否則 `--device-auth` 會退回瀏覽器 callback。
3. Docker（含 compose）。

> 安裝名假設為 npm `@openai/codex`；若官方安裝方式不同，改 `Dockerfile` 那一行即可。

## 跑法

```bash
cd experiments/codex-cross-machine-demo
docker compose up -d --build          # 起 machine-a、machine-b 兩個不同 hostname 的容器

# 1) 在 machine-a 登入（device code：終端會給你 URL + 一次性碼，去瀏覽器完成）
docker compose exec machine-a /scripts/01-login-on-a.sh

# 2) 把 machine-a 的 auth.json 搬到 machine-b 的乾淨 CODEX_HOME，並檢查私鑰在不在
docker compose exec machine-a /scripts/02-export-from-a.sh
docker compose exec machine-b /scripts/02-import-to-b.sh

# 3) 在 machine-b（從未登入過）用搬來的憑證實際呼叫 + 測 refresh，輸出判定
docker compose exec machine-b /scripts/03-test-on-b.sh

docker compose down -v                # 清掉（含憑證 volume）
```

## 怎麼判讀結果

`03-test-on-b.sh` 會印出其一：

- **`RESULT: CROSS-MACHINE OK`** — machine-b 用搬來的 `auth.json` 成功呼叫（且必要時成功 refresh）。→ 跨機可行，多使用者集中式在「技術可搬性」這關過（風控仍另計，見上表）。
- **`RESULT: DEVICE-BOUND / FAILED`** — machine-b 被要求重新登入或呼叫失敗。→ 憑證綁原機，集中式訂閱制不可行，改走 API key。
- **`RESULT: PRIVATE KEY NOT IN auth.json`** — 私鑰在 OS keyring 而非 auth.json（`SecretAuthStorage` 模式）→ 無法只靠 auth.json 搬 → 對集中式判不可行。

把這段輸出貼回來（**只貼判定那幾行，不要貼 auth.json 內容**），我就能據此把 §9 結論定案。

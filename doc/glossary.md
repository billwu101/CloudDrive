# 代號對照表

> 專案裡有 9 套彼此獨立的代號體系。本表是**唯一的集中索引**——遇到看不懂的代號先查這裡，
> 不要憑字母猜。需求面規範見 [proposal §32](./proposal.md#32-代號命名規範)。

## 一覽

| 代號 | 範圍 | 意義 | 權威來源 |
| --- | --- | --- | --- |
| `DEC-nnn` | 001–038 | 架構決策紀錄（ADR） | [detailed-design/appendix-a-decisions.md](./detailed-design/appendix-a-decisions.md) |
| `M1`–`M4` | 4 級 | AI 助理引擎的**開發里程碑** | [tasks/backend-assistant.md](./tasks/backend-assistant.md) |
| `EC1`–`EC4` | 4 層 | 評測**案例分層**（每層 100 案） | [`backend/eval/generate_cases.py`](../backend/eval/generate_cases.py) |
| `E1`–`E8` | 8 階 | 評測 harness **自身**的開發階段 | [tasks/assistant-eval.md](./tasks/assistant-eval.md) |
| `EM1`–`EM3` | 3 階 | 外部模型接入的開發階段 | [tasks/external-model.md](./tasks/external-model.md) |
| `S1`–`S5` | 5 階 | 時光機（快照）的開發階段 | [tasks/time-machine.md](./tasks/time-machine.md) |
| `HARNESS 01`–`09` | 9 個 | 助理引擎的九大組件 | [detailed-design/08-assistant-engine.md](./detailed-design/08-assistant-engine.md) §8.7 |
| `Stage 0`–`15` | 16 階 | Codex 多代理編排的執行階段 | [prompt.md](./prompt.md) |
| `0001`–`0020` | 20 支 | Alembic migration revision | [detailed-design/07-database.md](./detailed-design/07-database.md) §7.12 |

## 最容易搞混的三組

### `M` 與 `EC`——里程碑 vs 案例分層

兩者**相關但不是同一件事**：每一層 EC 案例測的，正是對應里程碑交付的能力。曾經共用 `M`
字母，2026-07-27 起分開（proposal §32）。

| 里程碑（做了什麼） | 案例層（測什麼） |
| --- | --- |
| M1 引擎骨架（AgentLoop + 唯讀內建技能） | — 由手寫案例覆蓋，無生成分層 |
| M2 planner / workflow | **EC1** 唯讀多工具，自動執行 |
| M3 持久化 + 寫入型技能 | **EC2** 查詢脈絡 + 寫入，需確認 |
| M4 自我撰寫沙箱 | **EC3** 生成技能（100 種） |
| — 無對應里程碑 | **EC4** 多步驟 + 跨步引用 + 寫入 |

兩處不對稱是刻意的，不是漏寫：

- **M1 沒有 EC 層**——引擎骨架的唯讀行為由手寫案例（`eval/cases/*.yaml`，標籤 `read-only` 等）
  覆蓋，不需要再生成 100 個。
- **EC4 沒有里程碑**——跨步驟引用是評測額外加壓的一層，不對應任何開發階段。

### `E` 與 `EC`——做工具 vs 跑案例

- `E5`＝「幫 harness 加上執行驗證模式」這件開發工作。
- `EC4`＝一百個測試案例。

### `E` 與 `EM`

`EM` 從一開始就是為了避開 `E` 而取的兩字母前綴，
[tasks/external-model.md](./tasks/external-model.md) 開頭有明文註記。`EC` 沿用同一慣例。

## 新增代號時

1. **先查本表**，確認前綴沒被用過。
2. **避免單字母前綴**——`M`／`E`／`S` 已佔用，新體系一律用兩字母（如 `EM`、`EC`）。
3. 新增後回填本表與 proposal §32。

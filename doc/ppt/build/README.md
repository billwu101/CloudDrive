# 簡報產生器（v3.0）

`CloudDrive_專題報告_v3.0.pptx` 由本目錄的腳本產生，圖片取自 `doc/ppt/*.png`。

```bash
npm i pptxgenjs
node build.js "CloudDrive_專題報告_v3.0.pptx"
```

- `theme.js`　設計 token（配色、字級、版面常數）。內文字級下限 15pt。
- `helpers.js`　版面元件：頁首／資訊卡／統計格／表格／等比置圖／底部強調條。
- `build.js`　26 頁正片 + 1 頁附錄的內容與版面。

## 版本規則

`v3.0` 已定版並凍結於 `doc/ppt/_archive/`，不再修改。**之後任何改動一律輸出成 `v3.1`**：
改完 `build.js` 後把上面兩段指令與本檔的版號一併換成 `v3.1`，舊版留在 `_archive/` 供對照。

視覺驗收：

```bash
soffice --headless --convert-to pdf --outdir qa "CloudDrive_專題報告_v3.0.pptx"
pdftoppm -r 90 -png "qa/CloudDrive_專題報告_v3.0.pdf" qa/p
```

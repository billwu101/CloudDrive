# 簡報產生器（v2.0）

`CloudDrive_專題報告_v2.0.pptx` 由本目錄的腳本產生，圖片取自 `doc/ppt/*.png`。

```bash
npm i pptxgenjs
node build.js "CloudDrive_專題報告_v2.0.pptx"
```

- `theme.js`　設計 token（配色、字級、版面常數）。內文字級下限 15pt。
- `helpers.js`　版面元件：頁首／資訊卡／統計格／表格／等比置圖／底部強調條。
- `build.js`　22 頁正片 + 1 頁附錄的內容與版面。

視覺驗收：

```bash
soffice --headless --convert-to pdf --outdir qa "CloudDrive_專題報告_v2.0.pptx"
pdftoppm -r 90 -png "qa/CloudDrive_專題報告_v2.0.pdf" qa/p
```

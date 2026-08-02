"use strict";
const path = require("path");
const PptxGenJS = require("pptxgenjs");
const { C, FONT, FONT_NUM, W, H, M, CW, T } = require("./theme");
const { head, card, bullets, footnote, fitImage, statRow, table } = require("./helpers");

const IMG = "/Users/linyueying/Library/CloudStorage/OneDrive-Personal/NTUST/Mester0/CloudDrive/doc/ppt";
const R = {
  erdSlide: 2352 / 1821,
  erdFull: 2352 / 1629,
  deploy: 2352 / 1215,
  docker: 2352 / 1092,
  arch: 2352 / 327,
  chat: 2352 / 1032,
  boundary: 2352 / 1281,
  gateway: 2352 / 510,
};
const P = (n) => path.join(IMG, n);

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "billwu101";
pptx.company = "NTUST";
pptx.title = "CloudDrive 專題報告 v3.0";

const S = () => {
  const s = pptx.addSlide();
  s.background = { color: C.WHITE };
  return s;
};

/* ══════════════ 02 · 封面 ══════════════ */
{
  const s = S();
  s.addShape("rect", { x: 0, y: 0, w: 0.34, h: H, fill: { color: C.INK } });
  s.addShape("rect", { x: 0.34, y: 0, w: 0.07, h: H, fill: { color: C.AMBER } });

  s.addText("NTUST · 碩士專題報告", {
    x: 1.15, y: 1.65, w: 10.5, h: 0.36,
    fontFace: FONT_NUM, fontSize: 16, bold: true, color: C.BLUE,
    charSpacing: 2.4, valign: "middle",
  });
  s.addText("CloudDrive 雲端硬碟系統", {
    x: 1.15, y: 2.15, w: 11.0, h: 0.95,
    fontFace: FONT, fontSize: 50, bold: true, color: C.INK, valign: "middle",
  });
  s.addShape("rect", { x: 1.15, y: 3.24, w: 2.5, h: 0.045, fill: { color: C.AMBER } });
  s.addText("整合對話式 AI 助理與時光機還原的隱私導向私有雲", {
    x: 1.15, y: 3.52, w: 11.0, h: 0.42,
    fontFace: FONT, fontSize: 21, color: C.INK, valign: "middle",
  });
  s.addText("本地模型優先 · 可自架 · 全流程可測試", {
    x: 1.15, y: 4.0, w: 11.0, h: 0.36,
    fontFace: FONT, fontSize: 17, color: C.MUTED, valign: "middle",
  });

  const tags = ["React 19 + FastAPI", "PostgreSQL + pgvector", "本地 Gemma 4 26B", "Docker + CI/CD"];
  tags.forEach((t, i) => {
    const x = 1.15 + i * 2.80;
    s.addShape("roundRect", {
      x, y: 4.66, w: 2.64, h: 0.46, rectRadius: 0.05,
      fill: { color: C.TINT }, line: { color: C.LINE, width: 0.75 },
    });
    s.addText(t, {
      x: x + 0.06, y: 4.66, w: 2.52, h: 0.46,
      fontFace: FONT, fontSize: T.body, color: C.INK, align: "center", valign: "middle",
    });
  });

  s.addText([
    { text: "報告人　", options: { color: C.MUTED } },
    { text: "吳晉緯　·　沈威廷", options: { color: C.INK, bold: true } },
    { text: "　　　指導教授　", options: { color: C.MUTED } },
    { text: "呂政修 教授", options: { color: C.INK, bold: true } },
  ], {
    x: 1.15, y: 5.78, w: 11.0, h: 0.36,
    fontFace: FONT, fontSize: 17, valign: "middle",
  });
  s.addText("國立臺灣科技大學　·　2026 年 8 月", {
    x: 1.15, y: 6.2, w: 11.0, h: 0.32,
    fontFace: FONT, fontSize: 15, color: C.MUTED, valign: "middle",
  });
  s.addText("v3.0", {
    x: W - M - 1.2, y: 6.55, w: 1.2, h: 0.32,
    fontFace: FONT_NUM, fontSize: 14, color: C.LINE, align: "right", valign: "middle",
  });
}

/* ══════════════ 02 · 目錄導引 ══════════════ */
{
  const s = S();
  s.addText("CONTENTS", {
    x: M, y: 0.34, w: 7.4, h: 0.26,
    fontFace: FONT_NUM, fontSize: T.kicker, bold: true,
    color: C.BLUE, charSpacing: 2, valign: "middle",
  });
  s.addText("02", {
    x: W - M - 1.0, y: 0.3, w: 1.0, h: 0.34,
    fontFace: FONT_NUM, fontSize: T.pageno, color: C.MUTED,
    align: "right", valign: "middle",
  });
  s.addText("這份報告怎麼讀", {
    x: M, y: 0.6, w: CW - 1.1, h: 0.5,
    fontFace: FONT, fontSize: T.title, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("先看系統如何設計，再看 AI 助理如何被驗證，最後是部署、開發方法與個人回顧。", {
    x: M, y: 1.12, w: CW, h: 0.34,
    fontFace: FONT, fontSize: T.subtitle, color: C.MUTED, valign: "top",
  });
  s.addShape("rect", { x: M, y: 1.46, w: CW, h: 0.022, fill: { color: C.BLUE } });

  const parts = [
    ["1", "系統與設計", C.BLUE, "吳晉緯", [
      ["A", "專案概覽", "03 – 04", "問題定義 · 系統全貌"],
      ["B", "設計與資料", "05 – 06", "21 張表 · 後端模組化"],
    ]],
    ["2", "核心：AI 助理與驗證", C.VIOLET, "沈威廷", [
      ["C", "AI 助理與驗證", "07 – 13", "六元件 · 安全邊界 · 實測"],
      ["D", "模型服務層", "14 – 16", "Gemma4APIServer 獨立專案"],
    ]],
    ["3", "交付、方法與回顧", C.AMBER, "吳晉緯", [
      ["E", "部署", "17 – 20", "四節點 · CI-CD · 環境與實戰"],
      ["F", "定位", "21", "競品比較 · 完成度"],
      ["V", "Vibe Coding", "22 – 24", "兩次事故 · 規則體系 · 驗證"],
      ["G", "學習歷程", "25 – 26", "18 週軌跡 · 踩坑回顧"],
    ]],
  ];
  const cw = (CW - 0.44) / 3;
  parts.forEach(([n, t, col, who, rows], i) => {
    const x = M + i * (cw + 0.22);
    const yy = 1.72;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 4.62, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addShape("roundRect", {
      x: x + 0.2, y: yy + 0.22, w: 0.44, h: 0.44, rectRadius: 0.05, fill: { color: col },
    });
    s.addText(n, {
      x: x + 0.2, y: yy + 0.22, w: 0.44, h: 0.44,
      fontFace: FONT_NUM, fontSize: 18, bold: true, color: C.WHITE,
      align: "center", valign: "middle",
    });
    s.addText(t, {
      x: x + 0.76, y: yy + 0.22, w: cw - 0.96, h: 0.44,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText("報告　" + who, {
      x: x + 0.22, y: yy + 0.68, w: cw - 0.44, h: 0.3,
      fontFace: FONT, fontSize: T.body, color: col, valign: "middle",
    });
    let ry = yy + 1.06;
    rows.forEach(([k, name, pages, desc]) => {
      s.addText(k, {
        x: x + 0.22, y: ry, w: 0.32, h: 0.3,
        fontFace: FONT_NUM, fontSize: T.body, bold: true, color: col, valign: "middle",
      });
      s.addText(name, {
        x: x + 0.56, y: ry, w: cw - 1.7, h: 0.3,
        fontFace: FONT, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
      });
      s.addText(pages, {
        x: x + cw - 1.18, y: ry, w: 0.96, h: 0.3,
        fontFace: FONT_NUM, fontSize: T.body, color: col,
        align: "right", valign: "middle",
      });
      s.addText(desc, {
        x: x + 0.56, y: ry + 0.3, w: cw - 0.78, h: 0.34,
        fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "top",
      });
      ry += 0.86;
    });
  });
  footnote(s, "時間有限可直接看 P.12–13（穩定性三部曲與實測數據）與 P.22–24（Vibe Coding 開發方法）—— 這兩段是報告重心。附錄 P.27 為完整欄位 ERD，備 Q&A 使用。", { accent: C.BLUE, h: 0.66 });
}

/* ══════════════ 03 · A 問題與定位 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "A", no: 3, title: "要解決什麼問題",
    sub: "通用雲端硬碟把資料放在他人伺服器。要在自己掌控的儲存空間上，用自然語言完成檔案操作，目前沒有現成方案。",
  });
  const cw = (CW - 0.4) / 3;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 4.32, vcenter: true, accent: C.BLUE, num: 1, title: "完整檔案管理",
    items: ["資料夾樹、上傳下載、預覽", "垃圾桶軟刪除與還原", "檔名／全文／語意三種搜尋", "指定使用者分享與公開連結", "檔案版本與容量統計"],
  });
  card(s, {
    x: M + cw + 0.2, y: y + 0.16, w: cw, h: 4.32, vcenter: true, accent: C.VIOLET, num: 2, title: "對話式 AI 助理",
    items: ["自然語言操作檔案", "先出計畫，破壞性操作需確認", "可現場生成新技能並掛右鍵", "多輪對話記憶", "預設本地 Gemma 4 26B"],
  });
  card(s, {
    x: M + (cw + 0.2) * 2, y: y + 0.16, w: cw, h: 4.32, vcenter: true, accent: C.AMBER, num: 3, title: "時光機整碟還原",
    items: ["把整個硬碟倒帶到過去時間點", "排程／手動／助理操作前自動快照", "以 checksum 去重的增量儲存", "還原前自動建保命快照", "獨立配額，不吃檔案空間"],
  });
  footnote(s, "三者單獨都有現成產品，但「同時成立、而且能自架」的組合沒有 —— 這就是本專案的切入點。", { bold: true });
}

/* ══════════════ 04 · A 系統全貌（04-arch）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "A", no: 4, title: "系統全貌",
    sub: "nginx 為唯一入口，同源反代 /api；中繼資料進 PostgreSQL，檔案本體交 Storage Provider。",
  });
  fitImage(s, P("04-arch.png"), R.arch, { x: M, y: y + 0.22, w: CW, h: 1.85 });

  const yy = y + 2.32;
  const cw = (CW - 0.4) / 3;
  card(s, {
    x: M, y: yy, w: cw, h: 2.42, accent: C.BLUE, title: "nginx 唯一入口",
    body: "同源反代 /api → backend，零 CORS、換主機免重建前端。\n\n對外只有這一個入口，後端不直接曝露。",
  });
  card(s, {
    x: M + cw + 0.2, y: yy, w: cw, h: 2.42, accent: C.MOSS, title: "儲存層可抽換",
    body: "StorageProvider 為 Protocol 介面，本機實作可替換為物件儲存。\n\n中繼資料與檔案本體以 storage_key 關聯。",
  });
  card(s, {
    x: M + (cw + 0.2) * 2, y: yy, w: cw, h: 2.42, accent: C.VIOLET, title: "推論預設本地",
    body: "Ollama Gemma 4 26B；外送需經隱私閘，且預設關閉。\n\n沒有 Ollama 的環境仍可跑起核心功能。",
  });
  footnote(s, "28 個核心模組 + 3 個擴充系統（AI 助理 · 時光機 · 外部模型接入）；模組間只透過 service 層互相依賴。", { accent: C.BLUE });
}

/* ══════════════ 05 · B 資料模型（01-erd-slide）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "B", no: 5, title: "資料模型：21 張表、六個子系統",
  });
  fitImage(s, P("01-erd-slide.png"), R.erdSlide, { x: M, y: y + 0.12, w: 6.95, h: 4.95 });

  const bx = M + 7.25;
  const bw = CW - 7.25;
  const items = [
    ["drive_items 單表樹", "parent_id 自關聯，檔案與資料夾同表管理"],
    ["星號個人化", "user_item_preferences 為權威來源，分享互不污染"],
    ["憑證只存 hash", "refresh token 與分享連結 token 皆不存明文"],
    ["版本與去重", "file_versions + checksum 供時光機共用內容"],
  ];
  let by = y + 0.24;
  items.forEach(([t, d], i) => {
    s.addShape("rect", { x: bx, y: by, w: 0.05, h: 1.02, fill: { color: [C.BLUE, C.MOSS, C.ROSE, C.AMBER][i] } });
    s.addText(t, {
      x: bx + 0.18, y: by, w: bw - 0.2, h: 0.34,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x: bx + 0.18, y: by + 0.36, w: bw - 0.2, h: 0.64,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.2, valign: "top",
    });
    by += 1.2;
  });
  footnote(s, "完整欄位版 ER Diagram 見附錄。中文全文搜尋以 ILIKE 子字串比對補足 tsvector 的斷詞限制。", { accent: C.MOSS });
}

/* ══════════════ 06 · B 後端分層 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "B", no: 6, title: "後端模組化：每個 domain 是自足套件",
  });
  const cw = (CW - 0.3) / 2;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 2.55, accent: C.BLUE, title: "四檔案結構",
    items: ["router.py　路由，不直接碰資料庫", "service.py　商業邏輯與跨 repository 協調", "repository.py　只負責資料存取", "schemas.py　該模組的輸入輸出型別"],
  });
  card(s, {
    x: M + cw + 0.3, y: y + 0.16, w: cw, h: 2.55, accent: C.MOSS, title: "集中把關，不分散在 router",
    items: ["PermissionService　權限判斷唯一入口", "QuotaService　容量檢查唯一入口", "AppError 子類 → 一致的錯誤 JSON", "ActivityLogService　記錄失敗不影響主流程"],
  });

  const ly = y + 2.95;
  const layers = [
    ["Router", "接收請求\n回傳回應", C.BLUE],
    ["Service", "商業邏輯\n協調各方", C.MOSS],
    ["Repository ／\nStorageProvider", "資料存取\n檔案讀寫", C.ROSE],
    ["PostgreSQL ／\n檔案系統", "實際持久層", C.MUTED],
  ];
  const lw = (CW - 0.66) / 4;
  layers.forEach(([t, d, col], i) => {
    const x = M + i * (lw + 0.22);
    s.addShape("roundRect", {
      x, y: ly, w: lw, h: 1.45, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: col, width: 1.2 },
    });
    s.addText(t, {
      x: x + 0.08, y: ly + 0.12, w: lw - 0.16, h: 0.66,
      fontFace: FONT, fontSize: T.h, bold: true, color: col,
      align: "center", valign: "middle", lineSpacingMultiple: 1.1,
    });
    s.addText(d, {
      x: x + 0.08, y: ly + 0.82, w: lw - 0.16, h: 0.56,
      fontFace: FONT, fontSize: T.body, color: C.MUTED,
      align: "center", valign: "top", lineSpacingMultiple: 1.1,
    });
    if (i < 3) {
      s.addText("▶", {
        x: x + lw + 0.005, y: ly + 0.52, w: 0.21, h: 0.4,
        fontFace: FONT, fontSize: 14, color: C.LINE, align: "center", valign: "middle",
      });
    }
  });
  footnote(s, "依賴方向單向不可逆：Repository 不可呼叫 Service；StorageProvider 不可呼叫 Repository。", { accent: C.MOSS, bold: true });
}

/* ══════════════ 07 · C 助理能做什麼（05-chat）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 7, title: "In-App AI 助理：一次對話怎麼被完成",
    sub: "在網頁裡用自然語言操作自己的雲端硬碟；模型跑在本地，破壞性操作一定先出計畫、等使用者確認。",
  });
  fitImage(s, P("05-chat.png"), R.chat, { x: M, y: y + 0.14, w: CW, h: 3.86 });

  const yy = y + 4.14;
  const cw = (CW - 0.6) / 4;
  const four = [
    ["對話操作檔案", "一律經既有 service 層，天然沿用配額與權限", C.BLUE],
    ["計畫先行", "唯讀可自動執行，破壞性一定要確認", C.VIOLET],
    ["現場生成技能", "產碼 → 靜態檢查 → 核可 → 沙箱執行", C.ROSE],
    ["多輪記憶", "載入最近 N 則歷史，支援「第二個」這類指涉", C.MOSS],
  ];
  four.forEach(([t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    s.addShape("rect", { x, y: yy, w: cw, h: 0.04, fill: { color: col } });
    s.addText(t, {
      x, y: yy + 0.1, w: cw, h: 0.32,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x, y: yy + 0.44, w: cw, h: 0.72,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.2, valign: "top",
    });
  });
}

/* ══════════════ 08 · C HARNESS 六元件 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 8, title: "引擎架構：Agent Harness 六元件",
    sub: "把助理視為「LLM + 外部 harness」共同構成的系統。程式碼拆成九個實作模組，對外以文獻的六元件框架說明。",
  });
  const six = [
    ["E", "Execution Loop", "主迴圈驅動「送訊息 → 解析 → 執行 → 回填」；workflow 執行器處理步驟相依與錯誤策略", C.BLUE],
    ["T", "Tool / Skill Registry", "內建、自訂與現場生成的技能都是 registry 的來源；manifest 定義參數 schema 與權限標記", C.MOSS],
    ["C", "Context Manager", "token 預算、歷史裁切與摘要、工具輸出瘦身、技能清單注入與 prompt 組裝", C.VIOLET],
    ["S", "State Store", "sessions／messages／skills／workflows 全部持久化到資料庫，並一律依 user_id 隔離", C.ROSE],
    ["L", "Lifecycle Hooks", "治理層：權限分類、使用者核可、程式碼靜態檢查、沙箱與稽核，含對外傳送的隱私閘", C.AMBER],
    ["V", "Evaluation Interface", "離線開發者工具，從外部呼叫 /assistant/chat；確定性斷言為主、LLM judge 為輔", C.MUTED],
  ];
  const cw = (CW - 0.34) / 2;
  six.forEach(([k, t, d, col], i) => {
    const x = M + (i % 2) * (cw + 0.34);
    const yy = y + 0.18 + Math.floor(i / 2) * 1.58;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 1.4, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("roundRect", {
      x: x + 0.14, y: yy + 0.22, w: 0.54, h: 0.54, rectRadius: 0.06,
      fill: { color: col },
    });
    s.addText(k, {
      x: x + 0.14, y: yy + 0.22, w: 0.54, h: 0.54,
      fontFace: FONT_NUM, fontSize: 21, bold: true, color: C.WHITE,
      align: "center", valign: "middle",
    });
    s.addText(t, {
      x: x + 0.8, y: yy + 0.14, w: cw - 0.96, h: 0.32,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x: x + 0.8, y: yy + 0.48, w: cw - 0.96, h: 0.84,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.18, valign: "top",
    });
  });
  footnote(s, "V 不在使用者請求路徑上 —— 它從外部打 API，如同真實使用者，因此量測的是「模型 + harness 組態」整體。", { accent: C.VIOLET });
}

/* ══════════════ 09 · C 執行模型 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 9, title: "執行模型：計畫先行，失敗時誠實報告",
  });
  const cw = (CW - 0.4) / 3;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 4.3, vcenter: true, accent: C.VIOLET, title: "為什麼不用自由 tool 迴圈",
    items: ["權限模型依賴「完整計畫先行」", "逐步決策會讓「使用者核可了什麼」失去邊界", "本地小模型跑長程多輪容易漂移", "一次規劃 + 約束解碼 + 驗證，把弱模型鎖在能力範圍內"],
  });
  card(s, {
    x: M + cw + 0.2, y: y + 0.16, w: cw, h: 4.3, vcenter: true, accent: C.ROSE, title: "失敗時誠實報告",
    items: ["規劃時寫的回覆不能當執行結果用", "任何步驟失敗 → 改用程式組合的事實報告", "說明哪一步失敗、已完成哪些、其後未執行", "不經 LLM 潤飾，杜絕「沒做完卻說做完」"],
  });
  card(s, {
    x: M + (cw + 0.2) * 2, y: y + 0.16, w: cw, h: 4.3, vcenter: true, accent: C.MOSS, title: "有限度的重新規劃",
    items: ["僅 chat 快速路徑允許失敗後重規劃一次", "重規劃結果必須全為唯讀且可自動確認", "confirm／rerun 路徑只誠實回報，不偷換步驟"],
  });
  footnote(s, "DEC-029 · DEC-030　　授權是給規則，不是給那一份計畫。工作流維持串行——共用 AsyncSession 不允許並發，並行只省延遲卻引入配額競賽。", { accent: C.VIOLET });
}

/* ══════════════ 10 · C 安全邊界（06-boundary）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 10, title: "安全邊界：唯讀自動執行、寫入必須確認",
  });
  const cw9 = (CW - 0.4) / 3;
  card(s, {
    x: M, y: y + 0.16, w: cw9, h: 2.62, accent: C.AMBER, num: 1, title: "自我撰寫技能三道關卡",
    items: ["子代理產生程式碼，狀態停在 pending_approval", "使用者明確核可後才可執行", "受限子行程沙箱：限 CPU／記憶體／逾時，無對外網路"],
  });
  card(s, {
    x: M + cw9 + 0.2, y: y + 0.16, w: cw9, h: 2.62, accent: C.BLUE, num: 2, title: "零信任：不採信前端",
    items: ["user_id 一律從 JWT 取，不讀請求參數", "前端擋住不算數，端點本身必須擋", "四級權限全收斂在 PermissionService"],
  });
  card(s, {
    x: M + (cw9 + 0.2) * 2, y: y + 0.16, w: cw9, h: 2.62, accent: C.VIOLET, num: 3, title: "寫入前自動拍快照",
    items: ["hooks 掛在執行器的 before_execution", "助理的破壞性操作一律先建快照", "出錯可用時光機整碟倒帶回操作前"],
  });

  const ty9 = y + 3.02;
  s.addText("可驗證的隔離 —— 用測試證明，不用嘴巴保證", {
    x: M, y: ty9, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const steps9 = [
    ["1", "用 A 的 token 呼叫 API", "取得合法的 access token"],
    ["2", "指定 B 的資源 ID", "A 對該資源沒有任何權限"],
    ["3", "預期回傳 403 或 404", "且不透露該資源是否存在"],
    ["4", "納入自動化測試", "每次 CI 重跑，避免無聲回歸"],
  ];
  const sw9 = (CW - 0.6) / 4;
  steps9.forEach(([n, t, d], i) => {
    const x = M + i * (sw9 + 0.2);
    const yy = ty9 + 0.42;
    s.addShape("roundRect", {
      x, y: yy, w: sw9, h: 1.32, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addText(n, {
      x: x + 0.14, y: yy + 0.1, w: 0.34, h: 0.3,
      fontFace: FONT_NUM, fontSize: 18, bold: true, color: C.BLUE, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.5, y: yy + 0.1, w: sw9 - 0.66, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x: x + 0.14, y: yy + 0.46, w: sw9 - 0.28, h: 0.66,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
    });
  });
  footnote(s, "DEC-019 · DEC-023　　絕不自動執行未審核程式碼；涉私資料的任務限本地執行，去識別化失敗即禁止外送。", { accent: C.AMBER });
}

/* ══════════════ 11 · C 為什麼需要真實模型驗證 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 11, title: "為什麼需要真實模型驗證",
    sub: "單元測試中的 LLM 是 mock，通過只代表程式控制流程正確，驗不到真實模型在 workflow 規劃上的行為。",
  });
  const cw = (CW - 0.3) / 2;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 1.95, accent: C.MUTED, title: "單元測試驗不到的部分",
    items: ["真實模型的工具選擇是否穩定", "權限判定與多輪指涉是否正確", "規劃品質（寫入意圖是否遺漏）"],
  });
  card(s, {
    x: M + cw + 0.3, y: y + 0.16, w: cw, h: 1.95, accent: C.VIOLET, title: "因此建立獨立 eval harness",
    items: ["自外部呼叫 /assistant/chat，如同真實使用者", "確定性驗證器判定通過率，LLM judge 僅為輔", "相同回應必得相同判定，通過率可重現"],
  });

  const ty = y + 2.32;
  s.addText("量產案例分層：EC1 – EC4（依「任務複雜度 × 是否涉及寫入」遞增，各層為獨立案例集）", {
    x: M, y: ty, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  table(s, {
    x: M, y: ty + 0.38, w: CW, colW: [1.35, 6.6, 2.15, 1.96], accent: C.VIOLET,
    header: ["層級", "案例內容", "執行方式", "案例數"],
    rows: [
      ["EC1", "唯讀多工具（3 個以上查詢工具組合）", "自動執行", "100"],
      ["EC2", "查詢當脈絡 + 寫入／批次技能", "需確認", "120"],
      ["EC3", "自我撰寫生成（100 種不同技能）", "需核可", "100"],
      ["EC4", "多步驟 + 跨步驟引用前一步輸出 + 寫入", "需確認", "100"],
    ],
  });
  footnote(s, "DEC-039 代號分離：M 專指助理引擎的開發里程碑，EC 專指評測案例分層；先前共用 M 造成語境混淆。", { accent: C.VIOLET });
}

/* ══════════════ 12 · C 穩定性三部曲 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 12, title: "穩定性三部曲：把「請模型遵守」換成「使其不可違反」",
  });
  const trio = [
    ["DEC-031", "生成上限 + 非零溫度", "結構化請求把溫度釘 0，貪婪解碼在 thinking 段掉入決定性重複迴圈，吃滿 300 秒逾時。", "一律帶 num_predict 上限；結構化請求改用低而非零的溫度。", "以有界失敗取代長時間停滯，重試真正有效。", C.BLUE],
    ["DEC-032", "技能名以 enum 枚舉", "模型會捏造不存在的技能名，prompt 要求「只用清單內技能」沒有強制力。", "每次依當下 registry 動態組 schema，技能欄位以真實技能名做 enum。", "約束解碼在取樣時直接遮蔽，幻覺技能變成不可生成。", C.MOSS],
    ["DEC-033", "規劃預設關閉 thinking", "前兩道防線後，重複生成仍以約一至二成殘存，且只發生在 thinking 段。", "planner 呼叫預設 think:false，可用環境變數關回。", "重複生成歸零、延遲下降一個數量級。", C.AMBER],
  ];
  const cw = (CW - 0.4) / 3;
  trio.forEach(([code, name, prob, dec, eff, col], i) => {
    const x = M + i * (cw + 0.2);
    const yy = y + 0.16;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 4.32, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addText(code, {
      x: x + 0.18, y: yy + 0.14, w: cw - 0.36, h: 0.3,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: col, valign: "middle",
    });
    s.addText(name, {
      x: x + 0.18, y: yy + 0.44, w: cw - 0.36, h: 0.32,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    // 單一富文字塊：標籤與內文同流，不會互相疊字
    const lab = (t) => ({ text: t, options: { bold: true, color: col, breakLine: true } });
    const txt = (t, last) => ({ text: t, options: { color: C.MUTED, breakLine: true, paraSpaceAfter: last ? 0 : 8 } });
    s.addText(
      [lab("問題"), txt(prob), lab("決策"), txt(dec), lab("效果"), txt(eff, true)],
      {
        x: x + 0.18, y: yy + 0.86, w: cw - 0.36, h: 3.3,
        fontFace: FONT, fontSize: T.body, lineSpacingMultiple: 1.18, valign: "top",
      }
    );
  });
  footnote(s, "共同哲學：能用機制保證的事，就不要依賴模型自覺。三個決策都不是把 prompt 寫得更懇切，而是讓錯誤輸出在取樣層就無法產生、或在有界時間內必然停止。", { accent: C.AMBER });
}

/* ══════════════ 13 · C 實測結果 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 13, title: "實測結果：現行基準與多輪記憶",
  });
  statRow(s, {
    x: M, y: y + 0.16, w: CW, h: 1.45,
    stats: [
      { value: "387 / 420", label: "現行基準通過率\ngemma4:26b · runs=3", color: C.MOSS },
      { value: "95 / 120", label: "EC2 最弱一層\n寫入意圖仍是瓶頸", color: C.ROSE },
      { value: "45", label: "不穩定案例\n三次跑批有對有錯", color: C.AMBER },
      { value: "92.4s → 8.6s", label: "平均規劃延遲\n（關閉 thinking 後）", color: C.BLUE, size: 20 },
    ],
  });

  const ty = y + 1.9;
  s.addText("多輪記憶的可量測化", {
    x: M, y: ty, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  table(s, {
    x: M, y: ty + 0.4, w: CW, colW: [4.0, 5.4, 2.66], accent: C.VIOLET,
    header: ["案例 ID", "驗證內容", "結果"],
    rows: [
      ["multiturn-create-second", "從對話文字解析「第二個 = 2023」", "5 / 5"],
      ["multiturn-rename-first", "從結果摘要取得 item_id 執行改名（間接案例）", "5 / 5"],
      ["multiturn-recall-listed-names", "僅從對話報出全部三個名稱（嚴格回想案例）", "修復前 0 / 5 → 修復後 5 / 5"],
    ],
  });
  s.addText("「嚴格回想」案例的必要性：間接案例只證明模型用到了歷史中的某個 item_id，無法證明它真的記得內容——嚴格回想才揭露了記憶保真問題。", {
    x: M, y: ty + 2.3, w: CW, h: 0.42,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.2, valign: "top",
  });
  footnote(s, "基準取捨：2026-07-30 判分語意變更後舊通過率一律作廢，本頁採重建後的 387/420。另一份「400×3 逐 run 全過」的數據在未合併分支 eval/e9-objective-metrics，判分語意較寬，故不採用。", { accent: C.VIOLET });
}

/* ══════════════ 14 · D Gemma4APIServer（07-gateway）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 14, title: "模型服務層：Gemma4APIServer",
    sub: "獨立專案，不屬於 CloudDrive　·　github.com/billwu101/Gemma4APIServer",
  });
  fitImage(s, P("07-gateway.png"), R.gateway, { x: M, y: y + 0.2, w: CW, h: 2.35 });

  const yy = y + 2.78;
  const cw = (CW - 0.4) / 3;
  card(s, {
    x: M, y: yy, w: cw, h: 2.0, accent: C.ROSE, title: "雙協定相容",
    body: "同一個本地 Gemma 4 26B，同時以 OpenAI 相容與 Anthropic 相容 API 對外提供。",
  });
  card(s, {
    x: M + cw + 0.2, y: yy, w: cw, h: 2.0, accent: C.BLUE, title: "多金鑰 + 用量記錄",
    body: "每把金鑰獨立驗證，呼叫寫入 SQLite 用量記錄，可追溯誰用了多少。",
  });
  card(s, {
    x: M + (cw + 0.2) * 2, y: yy, w: cw, h: 2.0, accent: C.MOSS, title: "三個容器",
    body: "ollama / gateway / cloudflared；KEEP_ALIVE=-1 讓模型常駐記憶體。",
  });
  footnote(s, "/v1/* 相容路徑自動注入 think:false（對應 DEC-033）；原生 /api/* 保持透明轉發，不改寫請求。", { accent: C.ROSE });
}

/* ══════════════ 15 · D 為什麼拆成獨立專案 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 15, title: "為什麼把模型服務拆成獨立專案",
  });
  fitImage(s, P("06-boundary.png"), R.boundary, { x: M, y: y + 0.14, w: 6.15, h: 3.4 });

  const rx = M + 6.45;
  const rw = CW - 6.45;
  card(s, {
    x: rx, y: y + 0.16, w: rw, h: 1.9, accent: C.ROSE, title: "職責邊界",
    items: ["CloudDrive 是應用，不該內含 GPU 推論基礎設施", "GPU 主機是 Windows + WSL2 + NVIDIA，與部署主機不同"],
  });
  card(s, {
    x: rx, y: y + 2.2, w: rw, h: 1.34, accent: C.BLUE, title: "帶來的好處",
    items: ["其他專案也能共用同一台 GPU 主機", "金鑰與用量控管集中在 gateway，不散落各應用"],
  });

  const ly = y + 3.66;
  s.addText("CloudDrive 這一端只需要三個環境變數", {
    x: M, y: ly, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addShape("roundRect", {
    x: M, y: ly + 0.38, w: CW, h: 1.08, rectRadius: 0.05,
    fill: { color: C.INK },
  });
  s.addText(
    "LLM_PROVIDER=openai_compatible\nLLM_BASE_URL=https://<gateway>/v1\nLLM_API_KEY=<金鑰>",
    {
      x: M + 0.3, y: ly + 0.44, w: CW - 0.6, h: 0.96,
      fontFace: "Menlo", fontSize: T.body, color: "9FE8C0",
      lineSpacingMultiple: 1.24, valign: "top",
    }
  );
  footnote(s, "抽換成本因此趨近於零 —— 換模型、換供應商、退回本機 Ollama，都只是改這三行。", { y: 6.5, h: 0.6, accent: C.ROSE, bold: true });
}

/* ══════════════ 16 · D 營運監控儀表板 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 16, title: "營運監控：金鑰用量與即時日誌",
    sub: "gateway 附帶的終端儀表板，一眼看出 GPU 是否還活著、每把金鑰用了多少、請求是否正常。",
  });

  const px = M, pw = 8.32, py = y + 0.12, ph = 4.4;
  const MONO = "Menlo";
  const FS = 14;
  const NEON = { magenta: "E06BC0", cyan: "58C4DC", text: "D7DEE4",
                 dim: "8A97A2", green: "6BCF7F", red: "E0616B" };
  s.addShape("roundRect", { x: px, y: py, w: pw, h: ph, rectRadius: 0.05, fill: { color: "0F1519" } });
  const ix = px + 0.28, iw = pw - 0.56;

  s.addText([
    { text: "GEMMA4 API DASHBOARD", options: { color: NEON.magenta, bold: true } },
    { text: "    —    2026-08-01 10:50:58", options: { color: NEON.dim } },
  ], { x: ix, y: py + 0.16, w: iw, h: 0.3, fontFace: MONO, fontSize: FS, valign: "middle" });

  s.addText("SYSTEM", { x: ix, y: py + 0.56, w: 1.6, h: 0.28, fontFace: MONO, fontSize: FS, bold: true, color: NEON.cyan, valign: "middle" });
  const meters = [
    ["CPU", 0.099, "9.9%", NEON.green, "RAM", 0.349, "33.4 / 95.7 GB", NEON.green],
    ["GPU", 0.270, "27.0%", NEON.green, "VRAM", 0.875, "21.0 / 24.0 GB", NEON.red],
  ];
  meters.forEach((m, i) => {
    const ry = py + 0.9 + i * 0.34;
    s.addText(m[0], { x: ix, y: ry, w: 0.62, h: 0.26, fontFace: MONO, fontSize: FS, color: NEON.text, valign: "middle" });
    s.addShape("rect", { x: ix + 0.66, y: ry + 0.08, w: 1.3, h: 0.12, fill: { color: "22303A" } });
    s.addShape("rect", { x: ix + 0.66, y: ry + 0.08, w: 1.3 * m[1], h: 0.12, fill: { color: m[3] } });
    s.addText(m[2], { x: ix + 2.02, y: ry, w: 0.86, h: 0.26, fontFace: MONO, fontSize: FS, color: NEON.text, align: "right", valign: "middle" });
    s.addText(m[4], { x: ix + 3.02, y: ry, w: 0.82, h: 0.26, fontFace: MONO, fontSize: FS, color: NEON.text, valign: "middle" });
    s.addShape("rect", { x: ix + 3.88, y: ry + 0.08, w: 1.3, h: 0.12, fill: { color: "22303A" } });
    s.addShape("rect", { x: ix + 3.88, y: ry + 0.08, w: 1.3 * m[5], h: 0.12, fill: { color: m[7] } });
    s.addText(m[6], { x: ix + 5.24, y: ry, w: 2.5, h: 0.26, fontFace: MONO, fontSize: FS, color: NEON.text, align: "right", valign: "middle" });
  });
  s.addText("溫度 38°C   功耗 54 W   風扇 33%   模型 gemma4:26b · 100% GPU", {
    x: ix, y: py + 1.6, w: iw, h: 0.26, fontFace: MONO, fontSize: FS, color: NEON.dim, valign: "middle",
  });

  s.addText("TOKEN 使用量（每把金鑰）", { x: ix, y: py + 1.98, w: 4.2, h: 0.28, fontFace: MONO, fontSize: FS, bold: true, color: NEON.cyan, valign: "middle" });
  const cols = [[0, 1.5, "left"], [1.5, 1.35, "right"], [2.9, 1.5, "right"], [4.45, 1.35, "right"], [5.85, 1.9, "right"]];
  const trows = [
    [["金鑰", "請求", "prompt", "output", "總 token"], NEON.dim, false],
    [["alice", "16,598", "159,282", "14,583", "173,865"], NEON.text, false],
    [["dev_bill", "6", "8,773", "483", "9,256"], NEON.text, false],
    [["合計", "16,604", "168,055", "15,066", "183,121"], NEON.green, true],
  ];
  trows.forEach((r, ri) => {
    const ry = py + 2.3 + ri * 0.3;
    r[0].forEach((cell, ci) => {
      const c = cols[ci];
      s.addText(cell, {
        x: ix + c[0], y: ry, w: c[1], h: 0.28,
        fontFace: MONO, fontSize: FS, color: r[1], bold: r[2],
        align: c[2], valign: "middle",
      });
    });
  });

  s.addText("LOG   即時連線（2xx 綠 / 4xx 黃 / 5xx 紅）", { x: ix, y: py + 3.54, w: 5.4, h: 0.28, fontFace: MONO, fontSize: FS, bold: true, color: NEON.cyan, valign: "middle" });
  ["10:33:45", "10:45:55"].forEach((t, i) => {
    s.addText(t + "  INFO  POST /v1/chat/completions  200", {
      x: ix, y: py + 3.82 + i * 0.25, w: iw, h: 0.25,
      fontFace: MONO, fontSize: FS, color: NEON.green, valign: "middle",
    });
  });

  const rx = M + 8.56, rw = CW - 8.56;
  card(s, { x: rx, y: py, w: rw, h: 1.34, accent: C.ROSE, title: "為什麼要有面板",
    body: "GPU 與 VRAM 一眼可見，模型崩潰時能立刻判斷。" });
  card(s, { x: rx, y: py + 1.48, w: rw, h: 1.34, accent: C.BLUE, title: "每把金鑰獨立計量",
    body: "請求數與 token 寫入 SQLite，可追溯誰用了多少。" });
  card(s, { x: rx, y: py + 2.96, w: rw, h: 1.34, accent: C.MOSS, title: "日誌依狀態碼上色",
    body: "2xx 綠、4xx 黃、5xx 紅，掃一眼就知道有無異常。" });

  footnote(s, "VRAM 21.0 / 24.0 GB —— gemma4:26b 以 KEEP_ALIVE=-1 常駐，幾乎吃滿單張卡。這是「Ollama 單併發」限制的直接來源，也是 DEC-030 工作流不並行的實務理由之一。", { accent: C.ROSE });
}

/* ══════════════ 17 · E 系統部署（02-deploy）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 17, title: "系統部署：四個節點",
  });
  fitImage(s, P("02-deploy.png"), R.deploy, { x: M, y: y + 0.12, w: CW, h: 4.62 });

  const yy = y + 4.86;
  const cw = (CW - 0.4) / 3;
  const pts = [
    ["Tunnel 主動向外連線", "主機不需開放任何對外埠、不需固定 IP，天然隱藏源站位址", C.ROSE],
    ["nginx 為唯一入口", "同源反代 /api，沒有跨來源問題，換主機不需重建前端", C.BLUE],
    ["內網隔離", "後端只綁本機迴路位址，資料庫不對公網開放", C.MOSS],
  ];
  pts.forEach(([t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    s.addShape("rect", { x, y: yy, w: cw, h: 0.04, fill: { color: col } });
    s.addText(t, {
      x, y: yy + 0.1, w: cw, h: 0.3,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x, y: yy + 0.42, w: cw, h: 0.62,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.18, valign: "top",
    });
  });
}

/* ══════════════ 18 · E Docker 與 CI/CD（03-docker-wide）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 18, title: "Docker 與 CI/CD：從管線到容器",
  });
  fitImage(s, P("03-docker-wide.png"), R.docker, { x: M, y: y + 0.12, w: CW, h: 4.24 });

  const yy = y + 4.5;
  const cw = (CW - 0.6) / 4;
  const four = [
    ["映像只由 CI 建立", "以完整 commit SHA 標記，不使用 latest", C.BLUE],
    ["Runner 最小權限", "非 root、不加入 docker 群組，只能跑單一固定腳本", C.MOSS],
    ["部署可回滾", "健康檢查連續失敗即自動回到上一個可用版本", C.AMBER],
    ["密鑰只在主機", "正式環境設定不進版控，管線只做缺鍵警告", C.ROSE],
  ];
  four.forEach(([t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    s.addShape("rect", { x, y: yy, w: cw, h: 0.04, fill: { color: col } });
    s.addText(t, {
      x, y: yy + 0.1, w: cw, h: 0.32,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x, y: yy + 0.44, w: cw, h: 0.8,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.2, valign: "top",
    });
  });
}

/* ══════════════ 19 · E 三個環境的差異 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 19, title: "本機 · CI · 正式部署：三個環境差在哪",
    sub: "差異全部收斂在設定，不在程式碼——三份 .env 範本就是三個環境的規格書。",
  });
  table(s, {
    x: M, y: y + 0.18, w: CW, colW: [2.16, 3.34, 3.16, 3.40], accent: C.BLUE,
    header: ["", "本機開發", "CI（GitHub Actions）", "正式部署（CD）"],
    rows: [
      ["設定來源", "cp .env.example .env", "無 .env，直接寫在 ci.yml", "範本填真值放主機，不進 Git"],
      ["資料庫", "cloud_drive／弱密碼", "clouddrive_test（服務容器）", "高強度密碼，只走容器網路"],
      ["JWT 金鑰", "development-only-change-me", "不需要（測試自簽 token）", "openssl rand -hex 32"],
      ["AI 模型", "ollama → host.docker.internal", "不連模型，eval 走 mock", "openai_compatible → gateway"],
      ["對外曝露", "port 8088／8000／5432", "無", "Cloudflare Tunnel，零對外埠"],
      ["映像來源", "docker compose --build 本地建", "建置並推 GHCR（commit SHA）", "只拉 GHCR 的 SHA，不在主機建"],
    ],
  });

  const yy = y + 3.42;
  const pts = [
    ["範本進版控，真值不進", "範本本身就是可讀的規格；真 .env 只存部署主機（chmod 600），管線只做缺鍵警告。", C.BLUE],
    ["CI 根本不需要 .env", "它不跑完整系統，只跑測試——env 寫死在 workflow，無密鑰可外洩，也不會因誰的機器設定不同而變綠變紅。", C.MOSS],
    ["模型接法三邊都不同", "mock ／ 本機 Ollama ／ 遠端 gateway，程式碼一行沒改——這正是 LLMClient 抽象與 DEC-018 的價值。", C.ROSE],
  ];
  const cw = (CW - 0.4) / 3;
  pts.forEach(([t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    s.addShape("rect", { x, y: yy, w: cw, h: 0.04, fill: { color: col } });
    s.addText(t, {
      x, y: yy + 0.1, w: cw, h: 0.3,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d.replace(/`/g, ""), {
      x, y: yy + 0.44, w: cw, h: 1.04,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
    });
  });

  footnote(s, "唯一只出現在正式環境的變數是 TUNNEL_TOKEN —— 對外曝露是正式環境獨有的能力，本機與 CI 都不該擁有。", { accent: C.BLUE, h: 0.62 });
}

/* ══════════════ 20 · E 部署實戰與安全設計 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 20, title: "部署實戰：自架 runner 與最小權限設計",
    sub: "2026-07-11 首次上線　·　Ubuntu 24.04　·　CI 與 CD 刻意分離在兩種 runner 上。",
  });

  statRow(s, {
    x: M, y: y + 0.14, w: CW, h: 1.12,
    stats: [
      { value: "4", label: "正式環境容器", color: C.BLUE },
      { value: "60s", label: "健康檢查輪詢上限\n逾時自動回滾", color: C.MOSS },
      { value: "40", label: "字元 SHA 當映像 tag\n不使用 latest", color: C.VIOLET },
      { value: "1", label: "runner 可用的 sudo 指令\n且該腳本不可寫", color: C.ROSE },
    ],
  });

  const yy = y + 1.40;
  card(s, {
    x: M, y: yy, w: 7.3, h: 2.78, accent: C.BLUE, title: "deploy-cloud-drive 每次做的事",
    items: [
      "驗證參數是 40 字元 SHA，且該 SHA 在 main 歷史上",
      "自我同步：從 repo@SHA 取最新版腳本，原子替換後由新版接手",
      "同步 compose.prod.yml，部署拓撲隨程式碼落地",
      ".env 漂移檢查：只警告主機缺少的鍵，不同步值",
      "pull → up -d → 輪詢 /health；失敗自動回滾上一版",
    ],
  });
  card(s, {
    x: M + 7.5, y: yy, w: CW - 7.5, h: 2.78, accent: C.ROSE, title: "最小權限",
    items: [
      "專用非 root 帳號 gha-runner",
      "sudoers 只授權「呼叫」單一腳本",
      "腳本置於 /usr/local/sbin，runner 不可寫",
      ".env 為 root:root 600，永不進 Git",
      "能改 workspace 腳本的 PR ＝ 拿到主機 root",
    ],
  });

  const by = yy + 2.92;
  s.addShape("roundRect", {
    x: M, y: by, w: CW, h: 1.05, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: C.AMBER, width: 1.2 },
  });
  s.addText("踩過的坑：postgres 永遠 unhealthy，但容器內的環境變數其實是好的（PR #8）", {
    x: M + 0.26, y: by + 0.09, w: CW - 0.52, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("compose 的 --env-file 是「取代」預設插值來源而非疊加。腳本只傳了僅含 IMAGE_TAG 的狀態檔，healthcheck 的 ${POSTGRES_USER} 遂成空字串——容器內部由 env_file 注入的變數其實完全正常。修法：先帶 .env 再帶狀態檔。", {
    x: M + 0.26, y: by + 0.43, w: CW - 0.52, h: 0.66,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
  });
}

/* ══════════════ 21 · F 競品比較與定位 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "F", no: 21, title: "競品比較與定位",
  });
  table(s, {
    x: M, y: y + 0.2, w: CW, colW: [2.5, 3.05, 3.25, 3.26], accent: C.MOSS,
    header: ["比較維度", "Google Drive／OneDrive", "通用 AI 編碼工具 + 本機掛載", "CloudDrive"],
    rows: [
      ["資料存放位置", "服務商伺服器", "本機，但需掛載第三方雲端", "自架主機，完全自有"],
      ["AI 推論位置", "服務商雲端", "外部 API 為主", "本地模型優先，外送需經隱私閘"],
      ["對話式檔案操作", "有限，且綁定其生態", "可以，但需技術背景操作終端", "網頁內直接對話，一般使用者可用"],
      ["擴充新功能", "只能等官方或第三方外掛", "可寫腳本，但無核可與沙箱機制", "對話生成技能，經核可與沙箱後掛選單"],
      ["整碟時間點還原", "僅單檔版本歷史", "需自行搭配備份工具", "內建時光機，可整碟倒帶"],
    ],
  });
  statRow(s, {
    x: M, y: y + 3.18, w: CW, h: 1.28,
    stats: [
      { value: "28 / 28", label: "核心模組\n前後端與整合驗收", color: C.BLUE },
      { value: "3 / 3", label: "AI 助理\n引擎、面板、評測", color: C.VIOLET },
      { value: "1 / 1", label: "時光機\n資料層到前端五階段", color: C.AMBER },
      { value: "33 / 33", label: "模組總計\n對齊 progress.md", color: C.MOSS },
    ],
  });
  footnote(s, "定位：以隱私與資料主權為前提，把「完整檔案管理」與「可自我擴充的本地 AI 助理」放進同一個可自架的系統。", { y: H - 1.42, h: 0.6, accent: C.MOSS, bold: true });
  s.addText("已知限制：時光機還原硬配額檢查待補強（非阻擋）· 語意搜尋舊檔索引補建尚未背景自動化 · 評測結論綁定單一模型與硬體", {
    x: M, y: H - 0.68, w: CW, h: 0.4,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "middle",
  });
}

/* ══════════════ 22 · V 為什麼需要規則 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 22, title: "為什麼需要開發規則：兩次真實事故",
    sub: "用 AI 開發最常見的兩個失效模式，都不是「程式寫錯」，而是「看起來做完了」。",
  });
  const cw = (CW - 0.3) / 2;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 2.1, accent: C.ROSE, num: 1, title: "只驗表象，沒驗功能",
    items: ["PDF 預覽宣稱修好，實際只確認 <iframe> 有渲染", "打開仍然不能預覽"],
  });
  card(s, {
    x: M + cw + 0.3, y: y + 0.16, w: cw, h: 2.1, accent: C.ROSE, num: 2, title: "功能只做一半",
    items: ["proposal §33 後端完成，前端完全沒接", "editor 分享連結開起來與唯讀無異"],
  });

  s.addShape("roundRect", {
    x: M, y: y + 2.46, w: CW, h: 0.72, rectRadius: 0.05,
    fill: { color: C.INK },
  });
  s.addText("兩者的單元測試都是綠的。　測試綠 ≠ 功能可用。", {
    x: M + 0.3, y: y + 2.46, w: CW - 0.6, h: 0.72,
    fontFace: FONT, fontSize: 20, bold: true, color: C.WHITE, valign: "middle",
  });

  const ty = y + 3.4;
  s.addText("同類問題在 W18 一週內又抓到 18 個 —— 全部由實機操作發現，不是單元測試", {
    x: M, y: ty, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  table(s, {
    x: M, y: ty + 0.38, w: CW, colW: [1.9, 7.4, 2.76], accent: C.AMBER,
    header: ["commit", "問題", "性質"],
    rows: [
      ["1c1a63e", "editor 分享不能真的編輯——只比對 owner，沒走 PermissionService", "功能只做一半"],
      ["28f1f78", "右鍵 Share 沒接上既有的 ShareDialog", "前端沒接後端"],
      ["db5b2b7", "資料夾內的檔案加星後，星號清單看不到", "查詢範圍錯誤"],
    ],
  });
}

/* ══════════════ 23 · V 規則體系 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 23, title: "Vibe Coding：用 AI 協助，但不讓 AI 發散",
    sub: "核心原則：不猜測意圖、文件先行、任務最小化、結果可驗證。文件沒完成前不大量產生程式碼。",
  });
  const steps = [
    ["1", "需求", "proposal.md", "背景、角色、情境、功能與非功能需求、不在範圍、驗收標準", C.BLUE],
    ["2", "詳細設計", "detailed-design/", "模組劃分、依賴關係、資料結構、介面設計、錯誤處理、測試設計", C.MOSS],
    ["3", "任務拆分", "tasks/", "每模組一份任務文件，子任務 checklist 與驗收條件，標示依賴順序", C.VIOLET],
    ["4", "執行 Prompt", "prompt.md", "主／子代理責任、任務分派、平行規則、測試要求、禁止事項", C.ROSE],
  ];
  const cw = (CW - 0.66) / 4;
  steps.forEach(([n, t, f, d, col], i) => {
    const x = M + i * (cw + 0.22);
    const yy = y + 0.18;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 2.15, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addText(n, {
      x: x + 0.16, y: yy + 0.16, w: 0.4, h: 0.32,
      fontFace: FONT_NUM, fontSize: 20, bold: true, color: col, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.56, y: yy + 0.16, w: cw - 0.72, h: 0.32,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(f, {
      x: x + 0.16, y: yy + 0.54, w: cw - 0.32, h: 0.3,
      fontFace: "Menlo", fontSize: T.body, color: col, valign: "middle",
    });
    s.addText(d, {
      x: x + 0.16, y: yy + 0.9, w: cw - 0.32, h: 1.1,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.2, valign: "top",
    });
    if (i < 3) {
      s.addText("▶", {
        x: x + cw + 0.005, y: yy + 0.9, w: 0.21, h: 0.4,
        fontFace: FONT, fontSize: 14, color: C.LINE, align: "center", valign: "middle",
      });
    }
  });

  const by = y + 2.58;
  const cw2 = (CW - 0.3) / 2;
  card(s, {
    x: M, y: by, w: cw2, h: 1.95, accent: C.MOSS, title: "AI 實際幫上什麼",
    items: ["依任務文件實作模組並同時補測試", "生成 eval 案例與重現問題的最小測試", "協助定位重複生成與截斷類問題"],
  });
  card(s, {
    x: M + cw2 + 0.3, y: by, w: cw2, h: 1.95, accent: C.ROSE, title: "刻意設下的限制",
    items: ["不得在需求未確認時直接建立完整系統", "不得跳過測試換取速度、不得偽造測試結果", "文件與程式碼不一致時不得標記完成"],
  });
}

/* ══════════════ 24 · V 規則怎麼被驗證有效 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 24, title: "規則怎麼被驗證有效",
  });
  s.addShape("roundRect", {
    x: M, y: y + 0.16, w: CW, h: 1.34, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: C.AMBER, width: 1.2 },
  });
  s.addText("同一套「量化 → 修正 → 驗證」，用在流程本身，和 DEC-031/032/033 用在模型上，是同構的。", {
    x: M + 0.3, y: y + 0.26, w: CW - 0.6, h: 0.42,
    fontFace: FONT, fontSize: 19, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("模型端：發現跳針 → 加機制約束 → eval 量測歸零。　流程端：發現「測試綠但功能壞」→ 新增「使用者可見功能一律瀏覽器實測」硬規則 → 用 commit 紀錄驗證抓到的 bug 數。", {
    x: M + 0.3, y: y + 0.72, w: CW - 0.6, h: 0.66,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.24, valign: "top",
  });

  statRow(s, {
    x: M, y: y + 1.74, w: CW, h: 1.62,
    stats: [
      { value: "39", label: "條 DEC 決策紀錄\n每個決定可追溯、可質疑、可翻案", color: C.BLUE },
      { value: "1,389", label: "測試全綠\n後端 955+73 · 前端 361", color: C.MOSS },
      { value: "8", label: "項完成定義\n全數通過才算完成", color: C.VIOLET },
      { value: "18", label: "個 fix（W18 單週）\n全來自實機操作驗證", color: C.AMBER },
    ],
  });

  const by = y + 3.58;
  card(s, {
    x: M, y: by, w: CW, h: 1.4, accent: C.AMBER, title: "「完成」的定義（八項全過，缺一不可）",
    body: "功能實作　·　單元測試通過　·　型別檢查通過　·　Ruff 通過　·　使用者可見功能已瀏覽器實測　·　文件已更新　·　checklist 已更新　·　無未說明技術債",
  });
}

/* ══════════════ 25 · G 18 週訓練期軌跡 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "G", no: 25, title: "18 週訓練期軌跡（3/23 – 7/26）",
    sub: "前 10 週打底與找題目，後 8 週密集產出。",
  });
  const phases = [
    ["打底", "W1–3", "3/23 – 4/12", "VM + Ubuntu + SSH、Docker、Python 虛擬環境比較（conda・venv・pyenv・uv）、Git 與 GitHub；技術棧定案 React + FastAPI + PostgreSQL", C.BLUE],
    ["摸索", "W4–10", "4/13 – 5/31", "段考 2 週 + 專題方向討論 5 週；釐清前後端與資料庫的關係、整理 AI 輔助開發流程；題目從購物網站換到 CloudDrive", C.MOSS],
    ["起步", "W11–12", "6/1 – 6/14", "Caddy + Cloudflare DNS 憑證，打通 HTTPS 反向代理；6/13 一天建立 28 模組骨架，6/14 認證流程與批次選取", C.VIOLET],
    ["爆發", "W13–14", "6/15 – 6/28", "AI 助理 Harness（6/17 單日 46 commits）、時光機、全文與語意搜尋、外部模型 OpenAI／Codex 接入、文件重構 + CI/CD 落地", C.ROSE],
    ["收斂", "W15–18", "6/29 – 7/26", "harness 歸類文件與 CLAUDE.md 規則強化；detailed-design 拆模組、需求↔設計對齊；分片續傳、公開分享連結、CD 加 Tunnel；W18 單週 66 commits", C.AMBER],
  ];
  phases.forEach(([t, wk, dt, desc, col], i) => {
    const yy = y + 0.2 + i * 0.8;
    s.addShape("roundRect", {
      x: M, y: yy, w: CW, h: 0.7, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x: M, y: yy, w: 0.055, h: 0.7, fill: { color: col } });
    s.addText(t, {
      x: M + 0.22, y: yy, w: 0.86, h: 0.7,
      fontFace: FONT, fontSize: T.h, bold: true, color: col, valign: "middle",
    });
    s.addText(wk, {
      x: M + 1.05, y: yy, w: 1.16, h: 0.7,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(dt, {
      x: M + 2.26, y: yy, w: 1.46, h: 0.7,
      fontFace: FONT_NUM, fontSize: T.body, color: C.MUTED, valign: "middle",
    });
    s.addText(desc, {
      x: M + 3.76, y: yy + 0.02, w: CW - 3.98, h: 0.66,
      fontFace: FONT, fontSize: T.body, color: C.INK,
      lineSpacingMultiple: 1.12, valign: "middle",
    });
  });
  statRow(s, {
    x: M, y: y + 4.3, w: CW, h: 1.18,
    stats: [
      { value: "224", label: "commits / 9 天\n（6/13 – 6/21）", color: C.BLUE },
      { value: "46", label: "單日最高\n（6/17 · AI 助理）", color: C.ROSE },
      { value: "66", label: "W18 單週 commits\n18 feat · 18 fix · 13 docs", color: C.AMBER },
      { value: "28 + 3", label: "核心模組 + 擴充系統\n39 條 DEC 決策", color: C.MOSS },
    ],
  });
}

/* ══════════════ 26 · G 踩坑與結語 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "G", no: 26, title: "用 AI 開發踩到的坑，與這半年學到的事",
  });
  const cw = (CW - 0.3) / 2;
  card(s, {
    x: M, y: y + 0.16, w: cw, h: 2.5, accent: C.ROSE, title: "環境問題：AI 不會主動提的那一步",
    items: ["在 VM 裡開好 GPU 直通，卻始終抓不到裝置", "AI 給了完整設定步驟，唯獨沒說要重新開機", "教訓：AI 熟悉「怎麼設定」，但不熟悉「你的機器現在是什麼狀態」"],
  });
  card(s, {
    x: M + cw + 0.3, y: y + 0.16, w: cw, h: 2.5, accent: C.VIOLET, title: "驗證問題：功能常常只做一半",
    items: ["前端做出介面，後端完全找不到對應端點", "後端做完，前端沒接，功能等同不存在", "教訓：必須自己實際操作驗證，不能相信「已完成」的回報"],
  });

  const ly = y + 2.92;
  s.addText("從不會到會", {
    x: M, y: ly, w: CW, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const learn = [
    ["Git 與 GitHub", "分支、PR、衝突解決", C.BLUE],
    ["前後端與資料庫", "REST、ORM、非同步、migration", C.MOSS],
    ["測試與品質", "單元／整合／E2E 三層，型別與靜態檢查", C.VIOLET],
    ["Docker 與 CI/CD", "容器化、自架 Runner、可回滾部署", C.ROSE],
  ];
  const lw = (CW - 0.6) / 4;
  learn.forEach(([t, d, col], i) => {
    const x = M + i * (lw + 0.2);
    s.addShape("roundRect", {
      x, y: ly + 0.4, w: lw, h: 0.94, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: col, width: 1 },
    });
    s.addText(t, {
      x: x + 0.1, y: ly + 0.48, w: lw - 0.2, h: 0.3,
      fontFace: FONT, fontSize: T.h, bold: true, color: col, align: "center", valign: "middle",
    });
    s.addText(d, {
      x: x + 0.1, y: ly + 0.78, w: lw - 0.2, h: 0.5,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, align: "center", valign: "top",
    });
  });

  s.addShape("roundRect", {
    x: M, y: H - 1.25, w: CW, h: 0.86, rectRadius: 0.05, fill: { color: C.INK },
  });
  s.addText("專案的價值不在功能有多少，而在「一個小模型如何被工程機制馴服」的完整證據鏈。", {
    x: M + 0.3, y: H - 1.25, w: CW - 0.6, h: 0.86,
    fontFace: FONT, fontSize: 19, bold: true, color: C.WHITE, valign: "middle",
  });
}

/* ══════════════ 附錄 · 完整 ERD ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "B", no: 27, title: "附錄：完整欄位 ER Diagram",
    sub: "備 Q&A 使用，不在正式報告時間內。",
  });
  fitImage(s, P("01-erd.png"), R.erdFull, { x: M, y: y + 0.16, w: CW, h: H - y - 0.6 });
}

const OUT = process.argv[2] || "CloudDrive_專題報告_v2.0.pptx";
pptx.writeFile({ fileName: OUT }).then(() => console.log("✓ 產生完成：" + OUT));

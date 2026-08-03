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
  arch: 2352 / 351,
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
      ["C", "AI 助理與驗證", "07 – 16", "架構 · 受控流程 · 客觀評測"],
      ["D", "模型服務層", "17 – 19", "Gemma4APIServer 獨立專案"],
    ]],
    ["3", "交付、方法與回顧", C.AMBER, "吳晉緯", [
      ["E", "部署", "20 – 25", "四節點 · 儲存 · CI-CD · 環境與實戰"],
      ["F", "定位", "26", "競品比較 · 完成度"],
      ["G", "Vibe Coding", "27 – 29", "兩次事故 · 規則體系 · 驗證"],
      ["H", "學習歷程", "30 – 31", "18 週軌跡 · 踩坑回顧"],
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
  footnote(s, "時間有限可直接看 P.14–16（實測結果、效率指標與已知限制）與 P.27–29（Vibe Coding 開發方法）—— 這兩段是報告重心。附錄 P.34 為完整欄位 ERD，備 Q&A 使用。", { accent: C.BLUE, h: 0.66 });
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
    body: "程式只認相對 key，根目錄由 LOCAL_STORAGE_PATH 決定——「寫到哪」是部署決定的。\n\n未來換 S3 只要換一個 StorageProvider 實作。",
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

/* ══════════════ 07 · C Why Harness ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 7, title: "Why Harness：讓 AI 操作可控、可量測",
  });

  s.addShape("roundRect", {
    x: M, y: y + 0.14, w: CW, h: 0.86, rectRadius: 0.05, fill: { color: C.INK },
  });
  s.addText("CORE IDEA", {
    x: M + 0.3, y: y + 0.22, w: 2.0, h: 0.24,
    fontFace: FONT_NUM, fontSize: 13, bold: true, color: C.AMBER, charSpacing: 2, valign: "middle",
  });
  s.addText("先以結構化流程限制模型行為，再以真實模型與確定性驗證器量測可靠度。", {
    x: M + 0.3, y: y + 0.46, w: CW - 0.6, h: 0.38,
    fontFace: FONT, fontSize: 19, bold: true, color: C.WHITE, valign: "middle",
  });

  // ── 設計流程：五階段 ──
  s.addText("設計流程", {
    x: M, y: y + 1.14, w: 3.0, h: 0.28,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const fy = y + 1.48;
  const flow = [
    ["User Request", "自然語言需求", ["需求可能模糊", "不可直接操作資料"], C.AMBER],
    ["Structured\nWorkflow", "轉成可檢查的計畫", ["JSON plan", "Schema 驗證", "Registry 工具／技能"], C.BLUE],
    ["Permission\nReview", "權限與風險檢查", ["權限檢查", "高風險操作判定", "是否需要人工核可"], C.ROSE],
    ["Controlled\nExecution", "受控執行", ["只經授權後執行", "透過 Service Layer"], C.VIOLET],
    ["Objective\nEvaluation", "客觀量測可靠度", ["真實模型", "正式 API", "確定性 Verifier"], C.MOSS],
  ];
  const gap = 0.2;
  const fw = (CW - 4 * gap) / 5;
  flow.forEach(([t, d, items, col], i) => {
    const x = M + i * (fw + gap);
    s.addShape("roundRect", {
      x, y: fy, w: fw, h: 2.62, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: col, width: 1.3 },
    });
    s.addShape("rect", { x, y: fy, w: fw, h: 0.05, fill: { color: col } });
    s.addText(t, {
      x: x + 0.1, y: fy + 0.14, w: fw - 0.2, h: 0.56,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: col,
      align: "center", valign: "middle", lineSpacingMultiple: 1.06,
    });
    s.addText(d, {
      x: x + 0.1, y: fy + 0.72, w: fw - 0.2, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: C.INK,
      align: "center", valign: "middle",
    });
    s.addText(
      items.map((t2) => ({ text: t2, options: { bullet: { characterCode: "2022" }, breakLine: true } })),
      {
        x: x + 0.14, y: fy + 1.08, w: fw - 0.28, h: 1.44,
        fontFace: FONT, fontSize: T.body, color: C.MUTED,
        lineSpacingMultiple: 1.14, valign: "top",
      }
    );
    if (i < 4) {
      s.addText("▶", {
        x: x + fw + 0.01, y: fy + 0.98, w: gap - 0.02, h: 0.4,
        fontFace: FONT, fontSize: 13, color: C.LINE, align: "center", valign: "middle",
      });
    }
  });

  // ── 設計原則：三條 ──
  s.addText("設計原則", {
    x: M, y: fy + 2.78, w: 3.0, h: 0.28,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const cy = fy + 3.10;
  const cw = (CW - 0.4) / 3;
  const pts = [
    ["1", "Structure behavior", "限制輸出格式與合法技能，先形成完整計畫。", C.BLUE],
    ["2", "Govern execution", "唯讀自動；寫入與生成技能必須經權限與人工核可。", C.ROSE],
    ["3", "Measure reliability", "以真實模型、真實 fixture 與確定性 verifier 重複量測。", C.MOSS],
  ];
  pts.forEach(([n, t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    s.addShape("rect", { x, y: cy, w: cw, h: 0.04, fill: { color: col } });
    s.addText(n + "　" + t, {
      x, y: cy + 0.1, w: cw, h: 0.3,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x, y: cy + 0.42, w: cw, h: 0.62,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
    });
  });
}

/* ══════════════ 08 · C Harness 四層架構 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 8, title: "Harness 架構：四層分工與離線評測",
    sub: "Workflow Pipeline 定義要做什麼；Runtime 確保可靠執行；Service Layer 才真正操作資料。",
  });

  const lw = CW - 4.0;
  const layers = [
    ["1", "Workflow Pipeline", ["Parse", "Plan", "Validate", "Review", "Execute", "Log"], C.BLUE],
    ["2", "Agent Harness Runtime", ["Execution Loop", "Registry", "Context", "State", "Lifecycle"], C.VIOLET],
    ["3", "CloudDrive Service Layer", ["Drive Service", "Upload Service", "Assistant Skill Service"], C.MOSS],
    ["4", "DATA", ["PostgreSQL", "Object Storage"], C.MUTED],
  ];
  let ly = y + 0.18;
  layers.forEach(([n, t, chips, col]) => {
    s.addShape("roundRect", {
      x: M, y: ly, w: lw, h: 1.08, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x: M, y: ly, w: 0.055, h: 1.08, fill: { color: col } });
    s.addText(n + "　" + t, {
      x: M + 0.22, y: ly + 0.1, w: lw - 0.44, h: 0.3,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: col, valign: "middle",
    });
    const cwid = (lw - 0.44 - (chips.length - 1) * 0.12) / chips.length;
    chips.forEach((c, i) => {
      const cx = M + 0.22 + i * (cwid + 0.12);
      s.addShape("roundRect", {
        x: cx, y: ly + 0.44, w: cwid, h: 0.5, rectRadius: 0.04,
        fill: { color: C.WHITE }, line: { color: C.LINE, width: 0.7 },
      });
      s.addText(c, {
        x: cx + 0.04, y: ly + 0.44, w: cwid - 0.08, h: 0.5,
        fontFace: FONT_NUM, fontSize: T.body, color: C.INK, align: "center", valign: "middle",
      });
    });
    ly += 1.18;
  });

  const ex = M + lw + 0.28;
  const ew = CW - lw - 0.28;
  s.addShape("roundRect", {
    x: ex, y: y + 0.18, w: ew, h: 3.54, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: C.AMBER, width: 1.4, dashType: "dash" },
  });
  s.addText("Evaluation Interface", {
    x: ex + 0.2, y: y + 0.32, w: ew - 0.4, h: 0.32,
    fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("OFFLINE", {
    x: ex + 0.2, y: y + 0.66, w: ew - 0.4, h: 0.26,
    fontFace: FONT_NUM, fontSize: 13, bold: true, color: C.AMBER, charSpacing: 2, valign: "middle",
  });
  ["Case Schema", "Runner", "Verifier", "Scoring"].forEach((t, i) => {
    s.addShape("roundRect", {
      x: ex + 0.2, y: y + 1.02 + i * 0.5, w: ew - 0.4, h: 0.4, rectRadius: 0.04,
      fill: { color: C.WHITE }, line: { color: C.LINE, width: 0.7 },
    });
    s.addText(t, {
      x: ex + 0.24, y: y + 1.02 + i * 0.5, w: ew - 0.48, h: 0.4,
      fontFace: FONT_NUM, fontSize: T.body, color: C.INK, align: "center", valign: "middle",
    });
  });
  s.addText("not in request path", {
    x: ex + 0.2, y: y + 3.22, w: ew - 0.4, h: 0.3,
    fontFace: FONT, fontSize: T.body, bold: true, color: C.ROSE, align: "center", valign: "middle",
  });

  footnote(s, "評測介面刻意不在使用者請求路徑上——它從外部呼叫 Production API，如同真實使用者，因此量測的是「模型 + harness 組態」整體。", { accent: C.VIOLET, h: 0.62 });
}

/* ══════════════ 09 · C 六元件 × 九模組 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 9, title: "六核心元件 × 九實作模組",
    sub: "報告用的六元件框架，對應到程式碼裡實際存在的九個模組。",
  });
  table(s, {
    x: M, y: y + 0.18, w: CW, colW: [2.72, 3.1, 6.24], accent: C.VIOLET,
    header: ["核心元件", "實作模組", "職責"],
    rows: [
      ["E　Execution Loop", "Main Loop · Sub-agent", "控制任務執行流程；分派步驟給對應程序；處理每一步的結果回傳"],
      ["T　Tool / Skill Registry", "Registry · Built-in Skills", "管理可用工具與技能；提供名稱、功能與參數；內建與自建分開管理"],
      ["C　Context Manager", "Context Mgmt · Prompt Assembly", "整理需求、對話紀錄與任務；組成 system prompt；控制上下文長短與內容"],
      ["S　State Store", "Session Persistence", "保存 session／訊息／狀態；紀錄執行節點與結果；任務在多次請求間可延續"],
      ["L　Lifecycle Hooks", "Governance · Permissions & Safety", "執行前後做權限安全檢查；高風險操作要求確認；管理錯誤處理與執行紀錄"],
      ["V　Evaluation Interface", "Offline Evaluation", "建立測試案例；驗證規劃、執行結果與狀態；統計錯誤類型以分析"],
    ],
  });
  footnote(s, "六元件是文獻框架、九模組是可測試的實作切分——兩套命名並存是刻意的，報告講前者，程式碼與測試對後者。", { accent: C.VIOLET, h: 0.62 });
}

/* ══════════════ 10 · C Workflow Pipeline ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 10, title: "Workflow Pipeline：先形成完整計畫，再依權限分流",
  });

  const sy = y + 0.24;
  const steps = [
    ["Requirement\nParsing", C.BLUE],
    ["Structured\nPlanning", C.BLUE],
    ["Skill\nValidation", C.VIOLET],
    ["Permission &\nSafety Review", C.AMBER],
  ];
  const sw = 2.52;
  steps.forEach(([t, col], i) => {
    const x = M + i * (sw + 0.42);
    s.addShape("roundRect", {
      x, y: sy, w: sw, h: 0.92, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: col, width: 1.4 },
    });
    s.addText(t, {
      x: x + 0.08, y: sy, w: sw - 0.16, h: 0.92,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK,
      align: "center", valign: "middle", lineSpacingMultiple: 1.1,
    });
    if (i < 3) {
      s.addText("▶", {
        x: x + sw + 0.02, y: sy + 0.26, w: 0.38, h: 0.4,
        fontFace: FONT, fontSize: 15, color: C.LINE, align: "center", valign: "middle",
      });
    }
  });

  const by = sy + 1.24;
  const half = (CW - 0.36) / 2;
  s.addShape("roundRect", {
    x: M, y: by, w: half, h: 1.58, rectRadius: 0.05,
    fill: { color: C.TINT2 }, line: { color: C.MOSS, width: 1.4 },
  });
  s.addText("read-only", {
    x: M + 0.22, y: by + 0.14, w: half - 0.44, h: 0.3,
    fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.MOSS, valign: "middle",
  });
  s.addText("直接進入 Workflow Execution，不打斷使用者。", {
    x: M + 0.22, y: by + 0.5, w: half - 0.44, h: 0.9,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "top", lineSpacingMultiple: 1.18,
  });

  s.addShape("roundRect", {
    x: M + half + 0.36, y: by, w: half, h: 1.58, rectRadius: 0.05,
    fill: { color: C.TINT2 }, line: { color: C.ROSE, width: 1.4 },
  });
  s.addText("write", {
    x: M + half + 0.58, y: by + 0.14, w: half - 0.44, h: 0.3,
    fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.ROSE, valign: "middle",
  });
  s.addText("Plan Presentation → 使用者 approve 才執行；reject 即 Cancelled。", {
    x: M + half + 0.58, y: by + 0.5, w: half - 0.44, h: 0.9,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "top", lineSpacingMultiple: 1.18,
  });

  const ly = by + 1.82;
  s.addShape("roundRect", {
    x: M, y: ly, w: CW, h: 0.72, rectRadius: 0.05,
    fill: { color: C.INK },
  });
  s.addText("Execution Logging　·　Persistence + Governance Hooks　—　兩條路徑最後都寫進同一份稽核紀錄", {
    x: M + 0.3, y: ly, w: CW - 0.6, h: 0.72,
    fontFace: FONT, fontSize: T.body, bold: true, color: C.WHITE, valign: "middle",
  });

  footnote(s, "自我撰寫技能（skill-authoring）不走這條管線，另有獨立的 proposal 流程——見下一頁。", { accent: C.VIOLET, h: 0.6 });
}

/* ══════════════ 11 · C Generated Skill Lifecycle ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 11, title: "Generated Skill Lifecycle：核可後才執行",
  });
  const cw = (CW - 0.4) / 3;
  const phases = [
    ["1", "Generate & repair", ["Skill Requirement", "Codegen Sub-agent", "JSON / Manifest Validation", "CodeGuard"], "錯誤回饋給 codegen，最多 3 輪修復（共 4 次嘗試）", C.BLUE],
    ["2", "Human gate", ["Pending Proposal", "User Approval", "Approved？", "reject → Rejected / Cancelled"], "通過靜態驗證只建立 Pending Proposal，不會自動安裝", C.AMBER],
    ["3", "Execute after approval", ["Installed Skill", "Sandbox Execution", "Output Ingestion"], "核可後執行失敗不會自動重新生成", C.MOSS],
  ];
  phases.forEach(([n, t, chain, note, col], i) => {
    const x = M + i * (cw + 0.2);
    const yy = y + 0.18;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 4.34, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addText(n, {
      x: x + 0.2, y: yy + 0.16, w: 0.34, h: 0.32,
      fontFace: FONT_NUM, fontSize: 19, bold: true, color: col, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.56, y: yy + 0.16, w: cw - 0.76, h: 0.32,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    chain.forEach((c, j) => {
      const cy2 = yy + 0.62 + j * 0.62;
      s.addShape("roundRect", {
        x: x + 0.2, y: cy2, w: cw - 0.4, h: 0.44, rectRadius: 0.04,
        fill: { color: C.WHITE }, line: { color: C.LINE, width: 0.7 },
      });
      s.addText(c, {
        x: x + 0.24, y: cy2, w: cw - 0.48, h: 0.44,
        fontFace: FONT_NUM, fontSize: T.body, color: C.INK, align: "center", valign: "middle",
      });
      if (j < chain.length - 1) {
        s.addText("▼", {
          x: x + 0.2, y: cy2 + 0.44, w: cw - 0.4, h: 0.18,
          fontFace: FONT, fontSize: 9, color: C.LINE, align: "center", valign: "middle",
        });
      }
    });
    s.addText(note, {
      x: x + 0.2, y: yy + 3.52, w: cw - 0.4, h: 0.72,
      fontFace: FONT, fontSize: T.body, color: col, lineSpacingMultiple: 1.16, valign: "top",
    });
  });
  footnote(s, "一些限制：通過靜態驗證後只建立 Pending Proposal、使用者核可後才安裝才可進 Sandbox、核可後執行失敗不會自動重新生成——絕不自動執行未審核的程式碼。", { accent: C.AMBER, h: 0.62 });
}

/* ══════════════ 12 · C Why Evaluation ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 12, title: "Why Evaluation：用真實資料與確定性驗證器量測",
    sub: "Mock LLM 能防止程式管線退化，但不能證明真實模型的規劃與執行正確。",
  });

  const cw = (CW - 0.4) / 3;
  const tiers = [
    ["1", "Unit / integration", "Mock LLM；快速、CI 防退化", C.MUTED],
    ["2", "Production API", "與產品走同一條路徑", C.BLUE],
    ["3", "Deterministic verifier", "相同結果得到相同判定\nLLM judge = qualitative only", C.MOSS],
  ];
  tiers.forEach(([n, t, d, col], i) => {
    const x = M + i * (cw + 0.2);
    const yy = y + 0.14;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 1.14, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addText(n, {
      x: x + 0.18, y: yy + 0.12, w: 0.3, h: 0.3,
      fontFace: FONT_NUM, fontSize: 18, bold: true, color: col, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.5, y: yy + 0.12, w: cw - 0.68, h: 0.3,
      fontFace: FONT_NUM, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x: x + 0.18, y: yy + 0.48, w: cw - 0.36, h: 0.66,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.14, valign: "top",
    });
  });

  // ── 兩階段九步管線 ──
  const bw = (CW - 4 * 0.16) / 5;
  const drawPhase = (yy, label, labelColor, steps, startNo) => {
    s.addShape("rect", { x: M, y: yy, w: 0.05, h: 0.28, fill: { color: labelColor } });
    s.addText(label, {
      x: M + 0.16, y: yy - 0.01, w: 6.0, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: labelColor, valign: "middle",
    });
    steps.forEach(([t, d], i) => {
      const x = M + i * (bw + 0.16);
      const by = yy + 0.36;
      const isKey = t === "Deterministic\nVerifier";
      s.addShape("roundRect", {
        x, y: by, w: bw, h: 0.92, rectRadius: 0.05,
        fill: { color: isKey ? C.MOSS : C.TINT2 },
        line: { color: isKey ? C.MOSS : C.LINE, width: isKey ? 1.3 : 0.75 },
      });
      s.addText(String(startNo + i) + "　" + t.replace("\n", " "), {
        x: x + 0.08, y: by + 0.1, w: bw - 0.16, h: 0.42,
        fontFace: FONT_NUM, fontSize: T.body, bold: true,
        color: isKey ? C.WHITE : C.INK, align: "center", valign: "middle", lineSpacingMultiple: 1.05,
      });
      s.addText(d, {
        x: x + 0.08, y: by + 0.54, w: bw - 0.16, h: 0.32,
        fontFace: FONT, fontSize: T.body,
        color: isKey ? C.WHITE : C.MUTED, align: "center", valign: "middle",
      });
    });
  };

  drawPhase(y + 1.50, "Phase 1｜Run the case　執行測試", C.BLUE, [
    ["Case\nSchema", "定義測試案例"],
    ["Fixture\nBuilder", "建立真實資料"],
    ["Runner", "執行測試流程"],
    ["Production\nAPI", "正式產品路徑"],
    ["Approval\nHandling", "核可處理"],
  ], 1);

  drawPhase(y + 2.94, "Phase 2｜Verify the result　驗證結果", C.MOSS, [
    ["Result\nCollector", "搜集結果"],
    ["Deterministic\nVerifier", "固定規則驗證"],
    ["Scoring", "評分"],
    ["Report", "評測報告"],
  ], 6);

  s.addShape("roundRect", {
    x: M, y: y + 4.42, w: CW, h: 1.02, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: C.MOSS, width: 1.2 },
  });
  s.addText("Verifier 檢查七項", {
    x: M + 0.26, y: y + 4.48, w: 2.6, h: 0.3,
    fontFace: FONT, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("fixture/data · plan correctness · reference grounding · execution · final state · collateral damage · generated output", {
    x: M + 0.26, y: y + 4.78, w: CW - 0.52, h: 0.3,
    fontFace: FONT_NUM, fontSize: T.body, color: C.MUTED, valign: "middle",
  });
  s.addText("EC3 的生成程式碼另外在評測端沙箱實際執行——不只看它「產得出來」，還看它「跑起來對不對」。", {
    x: M + 0.26, y: y + 5.08, w: CW - 0.52, h: 0.3,
    fontFace: FONT, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
  });
}

/* ══════════════ 13 · C EC1–EC4 案例集 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 13, title: "EC1–EC4：四個獨立案例集",
    sub: "依「任務複雜度 × 是否涉及寫入」遞增；各層是獨立案例集，不是同一任務的四個階段。",
  });
  table(s, {
    x: M, y: y + 0.18, w: CW, colW: [1.5, 1.7, 5.5, 3.36], accent: C.VIOLET,
    header: ["層級", "案例數", "內容", "執行方式"],
    rows: [
      ["EC1", "100 cases", "唯讀多工具查詢", "自動執行"],
      ["EC2", "120 cases", "查詢作為脈絡 ＋ 寫入", "需使用者確認"],
      ["EC3", "100 cases", "生成技能 ＋ 執行側驗證", "需使用者核可"],
      ["EC4", "100 cases", "多步驟、跨步驟引用 ＋ 寫入", "需使用者確認"],
    ],
  });

  const gy = y + 2.4;
  s.addText("案例產生器：5 情境 × 20 主題 = 100 案，不是手工湊的", {
    x: M, y: gy, w: CW, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  fitImage(s, P("08-ec1-scenarios.png"), 1170 / 594, { x: M, y: gy + 0.38, w: 7.3, h: 2.42 });
  fitImage(s, P("09-ec1-topics.png"), 804 / 370, { x: M + 7.5, y: gy + 0.38, w: CW - 7.5, h: 2.42 });
}

/* ══════════════ 14 · C 實測結果 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 14, title: "實測結果：EC1–EC4 通過率",
    sub: "每個 case 跑 3 次；case-level 以至少 2/3 通過為門檻。",
  });
  statRow(s, {
    x: M, y: y + 0.16, w: CW, h: 1.24,
    stats: [
      { value: "389 / 420", label: "92.62% · Case threshold\ncase 以 ≥2/3 通過計", color: C.MOSS },
      { value: "1128 / 1260", label: "89.52%\nRun pass（全 run 計）", color: C.BLUE, size: 22 },
      { value: "337", label: "3/3 全過的案例\n佔 80.2%", color: C.VIOLET },
      { value: "65", label: "不穩定案例\n2/3：52　1/3：13", color: C.AMBER },
    ],
  });

  const ty = y + 1.62;
  const half = (CW - 0.36) / 2;
  s.addText("分層通過率", {
    x: M, y: ty, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const tiers = [["EC1", 94, 92], ["EC2", 90, 88], ["EC3", 87, 79], ["EC4", 100, 99.7]];
  tiers.forEach(([t, a, b], i) => {
    const yy = ty + 0.42 + i * 0.62;
    s.addText(t, {
      x: M, y: yy, w: 0.7, h: 0.5,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
    });
    const track = half - 2.35;
    [[a, C.MOSS, 0], [b, C.BLUE, 0.24]].forEach(([v, col, dy]) => {
      s.addShape("rect", { x: M + 0.72, y: yy + 0.06 + dy, w: track, h: 0.18, fill: { color: C.TINT } });
      s.addShape("rect", { x: M + 0.72, y: yy + 0.06 + dy, w: track * v / 100, h: 0.18, fill: { color: col } });
    });
    s.addText(a + "% / " + b + "%", {
      x: M + 0.8 + track, y: yy, w: 1.55, h: 0.5,
      fontFace: FONT_NUM, fontSize: T.body, color: C.MUTED, valign: "middle",
    });
  });
  s.addText([
    { text: "■ ", options: { color: C.MOSS } },
    { text: "Case threshold　", options: { color: C.MUTED } },
    { text: "■ ", options: { color: C.BLUE } },
    { text: "Run pass", options: { color: C.MUTED } },
  ], {
    x: M, y: ty + 2.96, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.body, valign: "middle",
  });

  const rx = M + half + 0.36;
  s.addText("三次跑批的穩定性分佈", {
    x: rx, y: ty, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const dist = [["3/3", 337, C.MOSS], ["2/3", 52, C.AMBER], ["1/3", 13, C.ROSE], ["0/3", 18, C.MUTED]];
  dist.forEach(([t, v, col], i) => {
    const yy = ty + 0.42 + i * 0.62;
    s.addShape("roundRect", {
      x: rx, y: yy, w: half, h: 0.5, rectRadius: 0.04,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.7 },
    });
    s.addShape("rect", { x: rx, y: yy, w: 0.05, h: 0.5, fill: { color: col } });
    s.addText(t, {
      x: rx + 0.2, y: yy, w: 0.9, h: 0.5,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: col, valign: "middle",
    });
    s.addShape("rect", { x: rx + 1.1, y: yy + 0.17, w: (half - 2.3) * v / 337, h: 0.16, fill: { color: col } });
    s.addText(String(v), {
      x: rx + half - 1.1, y: yy, w: 0.9, h: 0.5,
      fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK, align: "right", valign: "middle",
    });
  });
  s.addText("337 + 52 = 389 通過門檻；18 個三次全敗。", {
    x: rx, y: ty + 2.96, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "middle",
  });
}

/* ══════════════ 15 · C Token 與工具指標 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 15, title: "Token & Tool Uses：用量與工具呼叫指標",
    sub: "N = 960 runs　·　不依賴人為訂定的「標準步驟」，因此可跨案例與跨模型比較。",
  });
  statRow(s, {
    x: M, y: y + 0.16, w: CW, h: 1.16,
    stats: [
      { value: "2,043,273", label: "Input tokens total", color: C.BLUE, size: 22 },
      { value: "355,719", label: "Output tokens total", color: C.MOSS, size: 22 },
      { value: "2,398,992", label: "Total tokens", color: C.VIOLET, size: 22 },
      { value: "1,903.96", label: "Average tokens / run", color: C.AMBER, size: 22 },
    ],
  });

  const ty = y + 1.54;
  const half = (CW - 0.36) / 2;
  s.addText("Average tokens by EC tier", {
    x: M, y: ty, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const toks = [["EC1", 1987], ["EC2", 2087], ["EC3", 1447], ["EC4", 2058]];
  toks.forEach(([t, v], i) => {
    const yy = ty + 0.42 + i * 0.6;
    s.addText(t, { x: M, y: yy, w: 0.7, h: 0.46, fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK, valign: "middle" });
    const track = half - 2.0;
    s.addShape("rect", { x: M + 0.72, y: yy + 0.13, w: track, h: 0.2, fill: { color: C.TINT } });
    s.addShape("rect", { x: M + 0.72, y: yy + 0.13, w: track * v / 2087, h: 0.2, fill: { color: C.BLUE } });
    s.addText(String(v), { x: M + 0.76 + track, y: yy, w: 1.2, h: 0.46, fontFace: FONT_NUM, fontSize: T.body, color: C.MUTED, valign: "middle" });
  });

  const rx = M + half + 0.36;
  s.addText("Average tool uses（各層平均工具呼叫次數）", {
    x: rx, y: ty, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const tools = [["EC1", 4.92], ["EC2", 4.65], ["EC3", null], ["EC4", 4.14]];
  tools.forEach(([t, v], i) => {
    const yy = ty + 0.42 + i * 0.6;
    s.addText(t, { x: rx, y: yy, w: 0.7, h: 0.46, fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.INK, valign: "middle" });
    const track = half - 2.0;
    s.addShape("rect", { x: rx + 0.72, y: yy + 0.13, w: track, h: 0.2, fill: { color: C.TINT } });
    if (v !== null) {
      s.addShape("rect", { x: rx + 0.72, y: yy + 0.13, w: track * v / 4.92, h: 0.2, fill: { color: C.MOSS } });
    }
    s.addText(v === null ? "不適用" : String(v), {
      x: rx + 0.76 + track, y: yy, w: 1.2, h: 0.46,
      fontFace: FONT_NUM, fontSize: T.body, color: C.MUTED, valign: "middle",
    });
  });

  footnote(s, "EC3 為生成技能測試，不走工具呼叫路徑，故無工具次數；它的 token 也最低（1447），因為輸出是程式碼而非多輪工具規劃。", { accent: C.VIOLET, h: 0.62 });
}

/* ══════════════ 16 · C 缺陷、限制與未來 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "C", no: 16, title: "評測本身的缺陷、現行限制與未來工作",
  });

  s.addShape("roundRect", {
    x: M, y: y + 0.16, w: CW, h: 1.5, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: C.ROSE, width: 1.2 },
  });
  s.addText("評測深度：舊案例可能用空帳號、假 ID、根本沒真正執行就通過——只檢查了流程對不對", {
    x: M + 0.26, y: y + 0.26, w: CW - 0.52, h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const checks = ["fixture/data", "reference grounding", "plan correctness", "execution result", "final state", "collateral damage", "generated code output"];
  const cwid = (CW - 0.52 - 6 * 0.1) / 7;
  checks.forEach((t, i) => {
    const x = M + 0.26 + i * (cwid + 0.1);
    s.addShape("roundRect", {
      x, y: y + 0.68, w: cwid, h: 0.4, rectRadius: 0.04,
      fill: { color: C.MOSS }, line: { color: C.MOSS, width: 1 },
    });
    s.addText(t, {
      x: x + 0.03, y: y + 0.68, w: cwid - 0.06, h: 0.4,
      fontFace: FONT_NUM, fontSize: 12, color: C.WHITE, align: "center", valign: "middle",
    });
  });
  s.addText("新增的確定性檢查：確認資料真實有效 · 檢查計畫正確性 · 執行過程是否安全 · 驗證結果符合預期", {
    x: M + 0.26, y: y + 1.14, w: CW - 0.52, h: 0.32,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "middle",
  });

  const cy = y + 1.86;
  const half = (CW - 0.3) / 2;
  card(s, {
    x: M, y: cy, w: half, h: 2.6, accent: C.ROSE, title: "現行限制（誠實列出）",
    items: [
      "未真實對生成技能的執行效果做測試",
      "測試案例無紀錄 latency 資料",
      "記憶與長對話追蹤能力有限",
      "執行流程以串行為主",
      "LLM 生成計畫缺乏動態調整能力",
    ],
  });
  card(s, {
    x: M + half + 0.3, y: cy, w: half, h: 2.6, accent: C.MOSS, title: "未來工作",
    items: [
      "測試案例更多元化",
      "擴充 Playwright E2E 測試",
      "多元測試 generated skill runtime cases",
      "做不同模型的受控 A/B",
      "增加 tool-call effectiveness 指標",
    ],
  });
}

/* ══════════════ 17 · D Gemma4APIServer（07-gateway）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 17, title: "模型服務層：Gemma4APIServer",
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

/* ══════════════ 18 · D 為什麼拆成獨立專案 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 18, title: "為什麼把模型服務拆成獨立專案",
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

/* ══════════════ 19 · D 營運監控儀表板 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "D", no: 19, title: "營運監控：金鑰用量與即時日誌",
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

/* ══════════════ 20 · E 系統部署（02-deploy）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 20, title: "系統部署：四個節點",
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

/* ══════════════ 21 · E metadata 與 blob 分離 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 21, title: "metadata 與 blob：分開存，用 storage_key 接起來",
    sub: "中繼資料進 PostgreSQL、檔案本體交 StorageProvider——各自放在擅長的地方，一根字串接起來。",
  });

  const half = (CW - 0.34) / 2;
  const yy = y + 0.16;

  // ── metadata ──
  s.addShape("roundRect", {
    x: M, y: yy, w: half, h: 2.4, rectRadius: 0.05,
    fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
  });
  s.addShape("rect", { x: M, y: yy, w: half, h: 0.05, fill: { color: C.BLUE } });
  s.addText("Metadata（中繼資料）", {
    x: M + 0.22, y: yy + 0.14, w: half - 0.44, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("→　PostgreSQL 的 drive_items（16 欄）", {
    x: M + 0.22, y: yy + 0.46, w: half - 0.44, h: 0.3,
    fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.BLUE, valign: "middle",
  });
  s.addShape("roundRect", {
    x: M + 0.22, y: yy + 0.78, w: half - 0.44, h: 1.02, rectRadius: 0.04, fill: { color: C.INK },
  });
  s.addText("name「期末報告.pdf」   parent_id 樹狀結構\nowner_id   size_bytes   mime_type   is_deleted\nstorage_key  users/xxx/files/yyy/v1", {
    x: M + 0.34, y: yy + 0.84, w: half - 0.68, h: 0.92,
    fontFace: "Menlo", fontSize: 12.5, color: "9FE8C0", lineSpacingMultiple: 1.2, valign: "top",
  });
  s.addText("小、結構化、要被查詢——列資料夾、搜尋檔名、算容量都只碰這張表，一次 SQL 就回來。", {
    x: M + 0.22, y: yy + 1.86, w: half - 0.44, h: 0.44,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
  });

  // ── blob ──
  const bx = M + half + 0.34;
  s.addShape("roundRect", {
    x: bx, y: yy, w: half, h: 2.4, rectRadius: 0.05,
    fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
  });
  s.addShape("rect", { x: bx, y: yy, w: half, h: 0.05, fill: { color: C.MOSS } });
  s.addText("Blob（Binary Large Object）", {
    x: bx + 0.22, y: yy + 0.14, w: half - 0.44, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addText("→　檔案系統，經 StorageProvider 存取", {
    x: bx + 0.22, y: yy + 0.46, w: half - 0.44, h: 0.3,
    fontFace: FONT_NUM, fontSize: T.body, bold: true, color: C.MOSS, valign: "middle",
  });
  s.addShape("roundRect", {
    x: bx + 0.22, y: yy + 0.78, w: half - 0.44, h: 1.02, rectRadius: 0.04, fill: { color: C.INK },
  });
  s.addText("那個 PDF 真正的 12 MB 位元組\n\nDB 唯一知道的事：它在 storage_key 那個位置", {
    x: bx + 0.34, y: yy + 0.84, w: half - 0.68, h: 0.92,
    fontFace: "Menlo", fontSize: 12.5, color: "9FE8C0", lineSpacingMultiple: 1.2, valign: "top",
  });
  s.addText("大、無結構、只會整份讀寫——資料庫從來沒看過它的內容。", {
    x: bx + 0.22, y: yy + 1.86, w: half - 0.44, h: 0.44,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
  });

  // ── 分開之後的四個後果 ──
  const cy = yy + 2.6;
  s.addText("分開之後的四個實際後果", {
    x: M, y: cy, w: 4.0, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  const outs = [
    ["1", "改名／搬移零成本", "檔名只是 metadata。改名就是 UPDATE，磁碟上那個檔動都不用動。", C.BLUE],
    ["2", "blob 可被多筆指向", "版本與快照各自存 storage_key + checksum，做快照不複製任何位元組。", C.MOSS],
    ["3", "不在同一個交易裡", "上傳先寫 blob 再寫 DB，失敗即補刪；刪除先清 metadata，blob 交 GC。", C.ROSE],
    ["4", "blob 層可整個換掉", "上層只認 storage_key 與 StorageProvider，換 S3 metadata 一欄不改。", C.VIOLET],
  ];
  const ow = (CW - 0.6) / 4;
  outs.forEach(([n, t, d, col], i) => {
    const x = M + i * (ow + 0.2);
    const oy = cy + 0.36;
    s.addShape("rect", { x, y: oy, w: ow, h: 0.04, fill: { color: col } });
    s.addText(n + "　" + t, {
      x, y: oy + 0.1, w: ow, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: C.INK, valign: "middle",
    });
    s.addText(d, {
      x, y: oy + 0.42, w: ow, h: 1.06,
      fontFace: FONT, fontSize: T.body, color: C.MUTED, lineSpacingMultiple: 1.16, valign: "top",
    });
  });

  footnote(s, "「寧可多一個孤兒，也不要少一個本體」—— 上傳若先寫 DB，失敗會留下點開就壞的檔案；反過來最多留下沒人指向的 blob，只是浪費空間，功能仍正確，由 GC 算出全域被引用的 key 集合、60 分鐘寬限期後掃掉。", { accent: C.ROSE });
}

/* ══════════════ 22 · E 檔案實際落在哪裡 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 22, title: "檔案實際落在哪裡",
    sub: "程式碼裡一行絕對路徑都沒有——根目錄由 LOCAL_STORAGE_PATH 決定，「寫到哪」是部署決定的。",
  });

  const cw = (CW - 0.4) / 3;
  const cases = [
    ["1", "Docker（正常跑法）", "寫進 Docker volume", [
      "容器內 /app/storage，被 named volume 蓋住",
      "實際在 /var/lib/docker/volumes/…",
      "不在專案目錄與家目錄，macOS 還隔層 VM",
    ], C.BLUE],
    ["2", "直接跑 uvicorn", "落在 /tmp", [
      "未設環境變數時用 config.py 預設值",
      "/tmp/cloud-drive-storage",
      "開機會被清掉，只適合臨時試跑",
    ], C.AMBER],
    ["3", "從來不會寫到家目錄", "沒有任何路徑通到 ~", [
      "設成家目錄也一樣跳不出去",
      "key 帶 .. 或開頭 / → PathTraversalError",
      "resolve() 後再過 relative_to(root)",
    ], C.MOSS],
  ];
  cases.forEach(([n, t, sub2, items, col], i) => {
    const x = M + i * (cw + 0.2);
    const yy = y + 0.16;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 2.82, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addText(n, {
      x: x + 0.2, y: yy + 0.16, w: 0.32, h: 0.3,
      fontFace: FONT_NUM, fontSize: 19, bold: true, color: col, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.54, y: yy + 0.16, w: cw - 0.74, h: 0.3,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    s.addText("→　" + sub2, {
      x: x + 0.2, y: yy + 0.5, w: cw - 0.4, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: col, valign: "middle",
    });
    bullets(s, {
      x: x + 0.2, y: yy + 0.86, w: cw - 0.4, h: 1.84, items, color: C.MUTED,
    });
  });

  const vy = y + 3.16;
  const half = (CW - 0.3) / 2;
  s.addText("這台機器上真的存在的兩個 volume", {
    x: M, y: vy, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addShape("roundRect", {
    x: M, y: vy + 0.36, w: half, h: 1.0, rectRadius: 0.05, fill: { color: C.INK },
  });
  s.addText("clouddrive_storage_data     ← 本機開發\ncloud-drive_storage_data    ← 正式環境", {
    x: M + 0.26, y: vy + 0.44, w: half - 0.52, h: 0.84,
    fontFace: "Menlo", fontSize: T.body, color: "9FE8C0", lineSpacingMultiple: 1.24, valign: "top",
  });

  s.addText("要看內容只能穿進容器", {
    x: M + half + 0.3, y: vy, w: half, h: 0.3,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  s.addShape("roundRect", {
    x: M + half + 0.3, y: vy + 0.36, w: half, h: 1.0, rectRadius: 0.05, fill: { color: C.INK },
  });
  s.addText("docker compose exec backend \\\n  ls -R /app/storage/users", {
    x: M + half + 0.56, y: vy + 0.44, w: half - 0.52, h: 0.84,
    fontFace: "Menlo", fontSize: T.body, color: "9FE8C0", lineSpacingMultiple: 1.24, valign: "top",
  });

  footnote(s, "volume 生命週期與容器分開：rebuild、換映像 tag、docker compose down 都不掉檔案，只有 docker volume rm 或 down -v 才會消失。路徑寫在 compose 而非程式裡，換 S3 只要換一個 StorageProvider 實作。", { accent: C.BLUE });
}

/* ══════════════ 23 · E Docker 與 CI/CD（03-docker-wide）══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 23, title: "Docker 與 CI/CD：從管線到容器",
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

/* ══════════════ 24 · E 三個環境的差異 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 24, title: "本機 · CI · 正式部署：三個環境差在哪",
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

/* ══════════════ 25 · E 部署實戰與安全設計 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "E", no: 25, title: "部署實戰：自架 runner 與最小權限設計",
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

/* ══════════════ 26 · F 競品比較與定位 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "F", no: 26, title: "競品比較與定位",
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
      { value: "33 / 33", label: "模組總計\n另含外部模型接入 1 / 1", color: C.MOSS },
    ],
  });
  footnote(s, "定位：以隱私與資料主權為前提，把「完整檔案管理」與「可自我擴充的本地 AI 助理」放進同一個可自架的系統。", { y: H - 1.42, h: 0.6, accent: C.MOSS, bold: true });
  s.addText("已知限制：時光機還原硬配額檢查待補強（非阻擋）· 語意搜尋舊檔索引補建尚未背景自動化 · 評測結論綁定單一模型與硬體", {
    x: M, y: H - 0.68, w: CW, h: 0.4,
    fontFace: FONT, fontSize: T.body, color: C.MUTED, valign: "middle",
  });
}

/* ══════════════ 27 · V 為什麼需要規則 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 27, title: "為什麼需要開發規則：兩次真實事故",
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

/* ══════════════ 28 · V 規則體系 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 28, title: "Vibe Coding：用 AI 協助，但不讓 AI 發散",
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

/* ══════════════ 29 · V 規則怎麼被驗證有效 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "V", no: 29, title: "規則怎麼被驗證有效",
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

/* ══════════════ 30 · G 18 週訓練期軌跡 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "G", no: 30, title: "18 週訓練期軌跡（3/23 – 7/26）",
    sub: "前 10 週打底與找題目，後 8 週密集產出。",
  });
  const phases = [
    ["打底", "W1–3", "3/23 – 4/12", "VM + Ubuntu + SSH、Docker、Python 虛擬環境比較（conda・venv・pyenv・uv）、Git 與 GitHub；技術棧定案 React + FastAPI + PostgreSQL", C.BLUE],
    ["摸索", "W4–10", "4/13 – 5/31", "段考 2 週 + 專題方向討論 5 週；釐清前後端與資料庫的關係、整理 AI 輔助開發流程；題目從購物網站換到 CloudDrive", C.MOSS],
    ["起步", "W11–12", "6/1 – 6/14", "Caddy + Cloudflare DNS 憑證，打通 HTTPS 反向代理；6/13 一天建立 28 模組骨架，6/14 認證流程與批次選取", C.VIOLET],
    ["爆發", "W13–14", "6/15 – 6/28", "AI 助理 Harness（6/17 單日 46 commits）、時光機、全文與語意搜尋、外部模型接入、文件重構 + CI/CD 落地", C.ROSE],
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

/* ══════════════ 31 · G 踩坑與結語 ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "G", no: 31, title: "用 AI 開發踩到的坑，與這半年學到的事",
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

/* ══════════════ 32 · DEMO ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "H", no: 32, title: "Demo：現場操作",
    sub: "全部在自架環境上跑，模型是本機 gemma4:26b，沒有任何雲端 API。",
  });

  const cw = (CW - 0.6) / 4;
  const steps = [
    ["1", "檔案管理", ["登入 → 我的硬碟", "上傳、拖放、批次選取", "圖片／PDF／Office 預覽", "分享連結與權限"], C.BLUE],
    ["2", "搜尋", ["檔名搜尋", "全文內容搜尋", "語意搜尋（pgvector）"], C.MOSS],
    ["3", "AI 助理", ["一句話下多步驟指令", "先出計畫 → 使用者確認", "唯讀操作自動執行", "現場生成一個新技能"], C.VIOLET],
    ["4", "時光機", ["時間軸挑一個快照", "整碟倒帶還原", "還原前自動建保命快照"], C.AMBER],
  ];
  steps.forEach(([n, t, items, col], i) => {
    const x = M + i * (cw + 0.2);
    const yy = y + 0.18;
    s.addShape("roundRect", {
      x, y: yy, w: cw, h: 3.2, rectRadius: 0.05,
      fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
    });
    s.addShape("rect", { x, y: yy, w: cw, h: 0.05, fill: { color: col } });
    s.addShape("roundRect", {
      x: x + 0.2, y: yy + 0.22, w: 0.46, h: 0.46, rectRadius: 0.06, fill: { color: col },
    });
    s.addText(n, {
      x: x + 0.2, y: yy + 0.22, w: 0.46, h: 0.46,
      fontFace: FONT_NUM, fontSize: 19, bold: true, color: C.WHITE, align: "center", valign: "middle",
    });
    s.addText(t, {
      x: x + 0.78, y: yy + 0.22, w: cw - 0.98, h: 0.46,
      fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
    });
    bullets(s, {
      x: x + 0.2, y: yy + 0.86, w: cw - 0.4, h: 2.2, items, color: C.MUTED,
    });
  });

  footnote(s, "備援：模型伺服器若當下不可用，助理段改播事先錄好的操作影片；其餘功能不依賴模型，照常現場操作。", { accent: C.AMBER, h: 0.64 });
}

/* ══════════════ 33 · 感謝聆聽 ══════════════ */
{
  const s = S();
  s.background = { color: C.INK };
  s.addShape("rect", { x: 0, y: 0, w: 0.34, h: H, fill: { color: C.AMBER } });

  s.addText("THANK YOU", {
    x: 1.3, y: 1.9, w: 10.5, h: 0.36,
    fontFace: FONT_NUM, fontSize: 16, bold: true, color: C.AMBER, charSpacing: 3, valign: "middle",
  });
  s.addText("感謝聆聽", {
    x: 1.3, y: 2.4, w: 11.0, h: 1.0,
    fontFace: FONT, fontSize: 54, bold: true, color: C.WHITE, valign: "middle",
  });
  s.addShape("rect", { x: 1.3, y: 3.56, w: 2.5, h: 0.05, fill: { color: C.AMBER } });
  s.addText("Q & A", {
    x: 1.3, y: 3.86, w: 11.0, h: 0.44,
    fontFace: FONT_NUM, fontSize: 24, bold: true, color: "8FA6B8", valign: "middle",
  });
  s.addText("完整欄位 ER Diagram 與各模組設計文件備於附錄，歡迎指教。", {
    x: 1.3, y: 4.4, w: 11.0, h: 0.36,
    fontFace: FONT, fontSize: 17, color: "8FA6B8", valign: "middle",
  });

  const links = [
    ["CloudDrive", "github.com/billwu101/CloudDrive"],
    ["Gemma4APIServer", "github.com/billwu101/Gemma4APIServer"],
  ];
  links.forEach(([t, u], i) => {
    const x = 1.3 + i * 5.4;
    s.addShape("roundRect", {
      x, y: 5.16, w: 5.1, h: 0.86, rectRadius: 0.05,
      fill: { color: "1C2B36" }, line: { color: "35495A", width: 1 },
    });
    s.addText(t, {
      x: x + 0.24, y: 5.24, w: 4.6, h: 0.3,
      fontFace: FONT, fontSize: T.body, bold: true, color: C.AMBER, valign: "middle",
    });
    s.addText(u, {
      x: x + 0.24, y: 5.54, w: 4.6, h: 0.3,
      fontFace: FONT_NUM, fontSize: T.body, color: "8FA6B8", valign: "middle",
    });
  });

  s.addText("吳晉緯　·　沈威廷　　|　　指導教授　呂政修 教授　　|　　國立臺灣科技大學　2026 年 8 月", {
    x: 1.3, y: 6.36, w: 11.0, h: 0.36,
    fontFace: FONT, fontSize: 15, color: "6B7F8F", valign: "middle",
  });
}

/* ══════════════ 附錄 · 完整 ERD ══════════════ */
{
  const s = S();
  const y = head(s, {
    sec: "B", no: 34, title: "附錄：完整欄位 ER Diagram",
    sub: "備 Q&A 使用，不在正式報告時間內。",
  });
  fitImage(s, P("01-erd.png"), R.erdFull, { x: M, y: y + 0.16, w: CW, h: H - y - 0.6 });
}

const OUT = process.argv[2] || "CloudDrive_專題報告_v2.0.pptx";
pptx.writeFile({ fileName: OUT }).then(() => console.log("✓ 產生完成：" + OUT));

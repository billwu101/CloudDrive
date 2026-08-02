"use strict";
const { C, FONT, FONT_NUM, W, H, M, CW, T, SECTIONS } = require("./theme");

// ── 頁首：kicker + 標題 + 頁碼 + 分隔線 ─────────────────────────────
function head(s, { sec, title, sub, no }) {
  const meta = SECTIONS[sec] || SECTIONS.A;
  s.addText(meta.label, {
    x: M, y: 0.34, w: 7.4, h: 0.26,
    fontFace: FONT_NUM, fontSize: T.kicker, bold: true,
    color: meta.color, charSpacing: 2, valign: "middle",
  });
  s.addText(String(no).padStart(2, "0"), {
    x: W - M - 1.0, y: 0.3, w: 1.0, h: 0.34,
    fontFace: FONT_NUM, fontSize: T.pageno, color: C.MUTED,
    align: "right", valign: "middle",
  });
  s.addText(title, {
    x: M, y: 0.6, w: CW - 1.1, h: 0.5,
    fontFace: FONT, fontSize: T.title, bold: true,
    color: C.INK, valign: "middle",
  });
  let y = 1.18;
  if (sub) {
    s.addText(sub, {
      x: M, y: 1.12, w: CW, h: 0.34,
      fontFace: FONT, fontSize: T.subtitle, color: C.MUTED, valign: "top",
    });
    y = 1.56;
  }
  s.addShape("rect", {
    x: M, y: y - 0.1, w: CW, h: 0.022, fill: { color: meta.color },
  });
  return y + 0.06;
}

// ── 資訊卡：標題列 + 條列 ────────────────────────────────────────
function card(s, { x, y, w, h, accent, title, items, body, num, vcenter }) {
  s.addShape("roundRect", {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: C.TINT2 }, line: { color: C.LINE, width: 0.75 },
  });
  s.addShape("rect", { x, y, w: 0.055, h, fill: { color: accent } });

  let cy = y + 0.16;
  if (num) {
    s.addText(String(num), {
      x: x + 0.2, y: cy, w: 0.5, h: 0.32,
      fontFace: FONT_NUM, fontSize: 19, bold: true, color: accent, valign: "middle",
    });
  }
  s.addText(title, {
    x: x + (num ? 0.66 : 0.22), y: cy, w: w - (num ? 0.86 : 0.42), h: 0.32,
    fontFace: FONT, fontSize: T.h, bold: true, color: C.INK, valign: "middle",
  });
  cy += 0.44;
  if (body) {
    s.addText(body, {
      x: x + 0.22, y: cy, w: w - 0.44, h: h - (cy - y) - 0.14,
      fontFace: FONT, fontSize: T.body, color: C.MUTED,
      lineSpacingMultiple: 1.28, valign: "top",
    });
    return;
  }
  if (items && items.length) {
    s.addText(
      items.map((t) => ({
        text: t,
        options: { bullet: { characterCode: "2022" }, breakLine: true },
      })),
      {
        x: x + 0.22, y: cy, w: w - 0.44, h: h - (cy - y) - 0.14,
        fontFace: FONT, fontSize: T.body, color: C.INK,
        lineSpacingMultiple: 1.3, valign: vcenter ? "middle" : "top",
      }
    );
  }
}

// ── 純條列（無卡片框）────────────────────────────────────────────
function bullets(s, { x, y, w, h, items, color, size }) {
  s.addText(
    items.map((t) => ({
      text: t,
      options: { bullet: { characterCode: "2022" }, breakLine: true },
    })),
    {
      x, y, w, h,
      fontFace: FONT, fontSize: size || T.body, color: color || C.INK,
      lineSpacingMultiple: 1.32, valign: "top",
    }
  );
}

// ── 底部強調條 ──────────────────────────────────────────────────
function footnote(s, text, { y, accent, bold, h } = {}) {
  const hh = h || 0.78;
  const yy = y == null ? H - hh - 0.34 : y;
  const a = accent || C.AMBER;
  s.addShape("roundRect", {
    x: M, y: yy, w: CW, h: hh, rectRadius: 0.05,
    fill: { color: C.TINT }, line: { color: a, width: 1.1 },
  });
  s.addText(text, {
    x: M + 0.24, y: yy + 0.03, w: CW - 0.48, h: hh - 0.06,
    fontFace: FONT, fontSize: T.body, color: C.INK,
    bold: !!bold, lineSpacingMultiple: 1.16, valign: "middle",
  });
}

// ── 圖片：等比置中放進指定框 ────────────────────────────────────
function fitImage(s, path, ratio, box) {
  const boxRatio = box.w / box.h;
  let w, h;
  if (ratio >= boxRatio) { w = box.w; h = box.w / ratio; }
  else { h = box.h; w = box.h * ratio; }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  s.addImage({ path, x, y, w, h });
  return { x, y, w, h };
}

// ── 數字統計格 ──────────────────────────────────────────────────
function statRow(s, { x, y, w, h, stats }) {
  const gap = 0.16;
  const cw = (w - gap * (stats.length - 1)) / stats.length;
  stats.forEach((st, i) => {
    const cx = x + i * (cw + gap);
    s.addShape("roundRect", {
      x: cx, y, w: cw, h, rectRadius: 0.05,
      fill: { color: C.TINT }, line: { color: st.color || C.LINE, width: 1 },
    });
    s.addText(st.value, {
      x: cx + 0.08, y: y + 0.1, w: cw - 0.16, h: 0.46,
      fontFace: FONT_NUM, fontSize: st.size || 25, bold: true,
      color: st.color || C.BLUE, align: "center", valign: "middle",
    });
    s.addText(st.label, {
      x: cx + 0.08, y: y + 0.58, w: cw - 0.16, h: h - 0.68,
      fontFace: FONT, fontSize: T.small, color: C.MUTED,
      align: "center", valign: "top", lineSpacingMultiple: 1.14,
    });
  });
}

// ── 表格 ────────────────────────────────────────────────────────
function table(s, { x, y, w, colW, header, rows, accent }) {
  const a = accent || C.BLUE;
  const head = header.map((t) => ({
    text: t,
    options: {
      fill: { color: a }, color: C.WHITE, bold: true,
      fontFace: FONT, fontSize: T.body, valign: "middle",
    },
  }));
  const body = rows.map((r, ri) =>
    r.map((cell, ci) => ({
      text: typeof cell === "string" ? cell : cell.text,
      options: {
        fill: { color: ri % 2 ? C.TINT2 : C.WHITE },
        color: ci === 0 ? C.INK : C.MUTED,
        bold: ci === 0,
        fontFace: FONT, fontSize: T.body, valign: "middle",
      },
    }))
  );
  s.addTable([head, ...body], {
    x, y, w, colW,
    border: { type: "solid", color: C.LINE, pt: 0.75 },
    autoPage: false, rowH: 0.4,
    margin: [0.07, 0.11, 0.07, 0.11],
  });
}

module.exports = { head, card, bullets, footnote, fitImage, statRow, table };

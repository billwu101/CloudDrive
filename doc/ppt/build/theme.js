"use strict";
// ── 設計 token（沿用 30 頁版，字級全面提升到 15pt 下限）─────────────
const C = {
  INK: "13212A",
  BLUE: "2F6F8F",
  AMBER: "C9A94E",
  MOSS: "5E8F72",
  ROSE: "B06A66",
  VIOLET: "7E6DA8",
  TINT: "EFF3F6",
  TINT2: "F7F9FA",
  MUTED: "5B6470",
  LINE: "C9D3DA",
  WHITE: "FFFFFF",
};

const FONT = "PingFang TC";
const FONT_NUM = "Georgia";

// 版面常數（LAYOUT_WIDE = 13.3 x 7.5）
const W = 13.3;
const H = 7.5;
const M = 0.62; // 左右邊界
const CW = W - M * 2; // 內容寬 = 12.06

// 字級（學長要求：內文最小 15pt）
const T = {
  kicker: 13,
  pageno: 13,
  title: 30,
  subtitle: 16.5,
  h: 17,
  body: 15,
  small: 15,
  big: 44,
};

const SECTIONS = {
  A: { label: "OVERVIEW", color: C.BLUE },
  B: { label: "DESIGN & DATA", color: C.MOSS },
  C: { label: "AI ASSISTANT", color: C.VIOLET },
  D: { label: "MODEL SERVICE", color: C.ROSE },
  E: { label: "DEPLOYMENT", color: C.BLUE },
  F: { label: "POSITIONING", color: C.MOSS },
  V: { label: "VIBE CODING", color: C.AMBER },
  G: { label: "LEARNING", color: C.ROSE },
  H: { label: "CLOSING", color: C.INK },
};

module.exports = { C, FONT, FONT_NUM, W, H, M, CW, T, SECTIONS };

const {
  autoFontSize,
  calcTextBox,
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("../pptxgenjs_helpers");

const COLORS = {
  bg: "05111C",
  panel: "0D2031",
  panel2: "10283E",
  panel3: "132F48",
  border: "284763",
  text: "F7FBFF",
  muted: "B8CAD9",
  dim: "70859A",
  emerald: "2EE6A6",
  cyan: "38D2FF",
  amber: "FFC55C",
  red: "FF7A7A",
  white10: "173247",
  white20: "27435B",
  ink: "07111D",
};

const FONTS = {
  head: "Bahnschrift",
  body: "Segoe UI",
  mono: "Cascadia Code",
};

function configureDeck(pptx) {
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "Codex";
  pptx.company = "NeoFin AI";
  pptx.subject = "Young Financier 2026 presentation";
  pptx.title = "NeoFin AI — конкурсная презентация";
  pptx.lang = "ru-RU";
  pptx.theme = { headFontFace: FONTS.head, bodyFontFace: FONTS.body, lang: "ru-RU" };
}

function fitText(text, fontFace, opts) {
  return autoFontSize(text, fontFace, {
    minFontSize: opts.minFontSize || 10,
    maxFontSize: opts.maxFontSize || 28,
    fontSize: opts.fontSize || 16,
    margin: opts.margin ?? 0,
    valign: opts.valign || "mid",
    x: opts.x,
    y: opts.y,
    w: opts.w,
    h: opts.h,
    bold: opts.bold,
  });
}

function addBackground(slide, role = "main") {
  slide.background = { color: COLORS.bg };
  slide.addShape("rect", {
    x: 0.38, y: 0.32, w: 12.56, h: 6.88,
    line: { color: COLORS.border, transparency: role === "backup" ? 74 : 58, pt: 1 },
    fill: { color: COLORS.bg, transparency: 100 }, radius: 0.18,
  });
  slide.addShape("ellipse", {
    x: 9.06, y: 0.08, w: 3.82, h: 2.56,
    fill: { color: role === "backup" ? COLORS.white10 : COLORS.cyan, transparency: role === "backup" ? 84 : 88 },
    line: { color: COLORS.bg, transparency: 100 },
  });
  slide.addShape("ellipse", {
    x: 0.12, y: 5.34, w: 2.78, h: 1.92,
    fill: { color: role === "backup" ? COLORS.white20 : COLORS.emerald, transparency: role === "backup" ? 88 : 90 },
    line: { color: COLORS.bg, transparency: 100 },
  });
  slide.addShape("line", {
    x: 0.7, y: 0.62, w: 1.6, h: 0,
    line: { color: role === "backup" ? COLORS.cyan : COLORS.emerald, pt: 2.4 },
  });
}

function addAppendixFlag(slide) {
  slide.addText("ПРИЛОЖЕНИЕ / ОТВЕТЫ", {
    x: 10.42, y: 0.54, w: 2.02, h: 0.24,
    fontFace: FONTS.body, fontSize: 8.2, bold: true, color: COLORS.dim,
    margin: 0.04, align: "center", valign: "mid",
    fill: { color: COLORS.panel },
    line: { color: COLORS.border, transparency: 65, pt: 1 },
  });
}

function addFooter(slide, page, role = "main") {
  slide.addText(role === "backup" ? "NeoFin AI | приложение / ответы | 30.03.2026" : "NeoFin AI | основная история | 30.03.2026", {
    x: 0.78, y: 7.01, w: 5.6, h: 0.18,
    fontFace: FONTS.body, fontSize: 8.2, color: COLORS.dim, margin: 0,
  });
  slide.addText(String(page).padStart(2, "0"), {
    x: 12.02, y: 6.95, w: 0.48, h: 0.22,
    fontFace: FONTS.head, fontSize: 9.2, bold: true,
    color: role === "backup" ? COLORS.cyan : COLORS.emerald, margin: 0, align: "right",
  });
}

function addKicker(slide, text, options = {}) {
  slide.addText(text, {
    x: options.x || 0.82, y: options.y || 0.48, w: options.w || 2.25, h: 0.24,
    fontFace: FONTS.body, fontSize: 8.6, bold: true, color: options.color || COLORS.cyan,
    margin: 0.04, tracking: 0.35, align: "center", valign: "mid",
    fill: { color: options.fill || COLORS.panel2 },
    line: { color: COLORS.border, transparency: 58, pt: 1 },
  });
}

function addTitle(slide, title, subtitle, options = {}) {
  const titleBox = fitText(title, FONTS.head, {
    x: options.x || 0.82, y: options.y || 0.92,
    w: options.w || (options.role === "backup" ? 7.45 : 6.85),
    h: options.h || (options.role === "backup" ? 0.72 : 0.9),
    fontSize: options.fontSize || (options.role === "backup" ? 20 : 24),
    maxFontSize: options.maxFontSize || (options.role === "backup" ? 22 : 28),
    minFontSize: options.minFontSize || 16, margin: 0, bold: true,
  });
  slide.addText(title, { ...titleBox, fontFace: FONTS.head, bold: true, color: COLORS.text, margin: 0, breakLine: false });
  if (!subtitle) return;
  const subtitleY = titleBox.y + titleBox.h + (options.subtitleGap || 0.05);
  const box = fitText(subtitle, FONTS.body, {
    x: options.x || 0.82,
    y: subtitleY,
    w: options.w || (options.role === "backup" ? 7.45 : 6.85),
    h: options.subtitleHeight || 0.34,
    fontSize: options.subtitleFontSize || (options.role === "backup" ? 9.6 : 10.6),
    maxFontSize: options.subtitleMaxFontSize || 11.2,
    minFontSize: 8.8, margin: 0, valign: "top",
  });
  slide.addText(subtitle, { ...box, fontFace: FONTS.body, color: COLORS.muted, margin: 0, breakLine: false });
}

function addPanel(slide, cfg) {
  slide.addShape("roundRect", {
    x: cfg.x, y: cfg.y, w: cfg.w, h: cfg.h, rectRadius: cfg.radius || 0.06,
    fill: { color: cfg.fill || COLORS.panel },
    line: { color: cfg.line || COLORS.border, transparency: cfg.lineTransparency ?? 56, pt: cfg.linePt || 1 },
  });
  if (cfg.accent) {
    slide.addShape("roundRect", {
      x: cfg.x + 0.14, y: cfg.y + 0.12, w: cfg.w - 0.28, h: 0.05, rectRadius: 0.025,
      fill: { color: cfg.accent }, line: { color: cfg.accent, transparency: 100 },
    });
  }
  const contentX = cfg.x + 0.22;
  const contentW = cfg.w - 0.44;
  let cursorY = cfg.y + 0.24;
  if (cfg.title) {
    const titleBox = fitText(cfg.title, cfg.titleFontFace || FONTS.head, {
      x: contentX, y: cursorY, w: contentW, h: 0.34,
      fontSize: cfg.titleSize || 12, maxFontSize: cfg.titleMax || (cfg.titleSize || 12),
      minFontSize: cfg.titleMin || 8.6, margin: 0, bold: true, valign: "top",
    });
    slide.addText(cfg.title, {
      ...titleBox, fontFace: cfg.titleFontFace || FONTS.head, bold: true,
      color: cfg.titleColor || COLORS.text, margin: 0, breakLine: false,
    });
    cursorY += titleBox.h + 0.08;
  }
  if (!cfg.body) {
    return {
      contentX,
      contentW,
      bodyY: cursorY,
      innerBottom: cfg.y + cfg.h - 0.18,
    };
  }
  const bodyFont = cfg.mono ? FONTS.mono : FONTS.body;
  const bodyMeasure = calcTextBox(cfg.bodySize || 9.4, {
    text: cfg.body, w: contentW, fontFace: bodyFont,
    leading: cfg.leading || 1.12, margin: 0, padding: 0.02,
  });
  slide.addText(cfg.body, {
    x: contentX, y: cursorY, w: contentW,
    h: Math.min(cfg.h - (cursorY - cfg.y) - 0.18, bodyMeasure.h + 0.05),
    fontFace: bodyFont, fontSize: cfg.bodySize || 9.4,
    color: cfg.bodyColor || COLORS.muted, margin: 0,
    valign: cfg.bodyValign || "top", breakLine: false,
  });
  return {
    contentX,
    contentW,
    bodyY: cursorY,
    innerBottom: cfg.y + cfg.h - 0.18,
  };
}

function addBullets(slide, cfg) {
  let cursorY = cfg.y;
  cfg.items.forEach((item) => {
    slide.addShape("ellipse", {
      x: cfg.x, y: cursorY + 0.08, w: 0.09, h: 0.09,
      fill: { color: cfg.bulletColor || COLORS.emerald },
      line: { color: cfg.bulletColor || COLORS.emerald, transparency: 100 },
    });
    const box = calcTextBox(cfg.fontSize || 9.8, {
      text: item, w: cfg.w - 0.18, fontFace: FONTS.body,
      leading: cfg.leading || 1.15, margin: 0, padding: 0.04,
    });
    slide.addText(item, {
      x: cfg.x + 0.16, y: cursorY, w: cfg.w - 0.18, h: box.h + 0.02,
      fontFace: FONTS.body, fontSize: cfg.fontSize || 9.8,
      color: cfg.color || COLORS.muted, margin: 0, valign: "top", breakLine: false,
    });
    cursorY += box.h + (cfg.gap || 0.09);
  });
}

function addPillsRow(slide, cfg) {
  let cursor = cfg.x;
  cfg.items.forEach((item) => {
    const width = item.w || 1.75;
    slide.addShape("roundRect", {
      x: cursor, y: cfg.y, w: width, h: 0.34, rectRadius: 0.06,
      fill: { color: item.fill || COLORS.panel2 },
      line: { color: item.accent || COLORS.border, transparency: 55, pt: 1 },
    });
    slide.addText(item.text, {
      x: cursor + 0.12, y: cfg.y + 0.07, w: width - 0.24, h: 0.14,
      fontFace: FONTS.body, fontSize: 8.3, bold: true,
      color: item.color || COLORS.text, margin: 0, align: "center",
    });
    cursor += width + (cfg.gap || 0.16);
  });
}

function addStatTile(slide, cfg) {
  slide.addShape("roundRect", {
    x: cfg.x, y: cfg.y, w: cfg.w, h: cfg.h, rectRadius: 0.06,
    fill: { color: cfg.fill || COLORS.panel2 },
    line: { color: cfg.line || COLORS.border, transparency: 52, pt: 1 },
  });
  if (cfg.accent) {
    slide.addShape("line", {
      x: cfg.x + 0.16, y: cfg.y + 0.18, w: cfg.w - 0.32, h: 0,
      line: { color: cfg.accent, pt: 2.2 },
    });
  }
  slide.addText(cfg.value, {
    x: cfg.x + 0.18, y: cfg.y + 0.28, w: cfg.w - 0.36, h: 0.44,
    fontFace: FONTS.head, fontSize: cfg.valueSize || 22, bold: true,
    color: cfg.valueColor || COLORS.text, margin: 0,
    align: cfg.align || "left", valign: "mid",
  });
  slide.addText(cfg.label, {
    x: cfg.x + 0.18, y: cfg.y + cfg.h - 0.42, w: cfg.w - 0.36, h: 0.2,
    fontFace: FONTS.body, fontSize: cfg.labelSize || 8.8,
    color: cfg.labelColor || COLORS.dim, margin: 0, align: cfg.align || "left",
  });
}

function addCodePanel(slide, cfg) {
  addPanel(slide, { x: cfg.x, y: cfg.y, w: cfg.w, h: cfg.h, title: cfg.title, fill: COLORS.panel2, accent: cfg.accent || COLORS.cyan });
  slide.addShape("roundRect", {
    x: cfg.x + 0.22, y: cfg.y + 0.56, w: cfg.w - 0.44, h: cfg.h - 0.76, rectRadius: 0.04,
    fill: { color: COLORS.ink }, line: { color: COLORS.border, transparency: 30, pt: 1 },
  });
  slide.addText(cfg.code, {
    x: cfg.x + 0.38, y: cfg.y + 0.78, w: cfg.w - 0.76, h: cfg.h - 1.1,
    fontFace: FONTS.mono, fontSize: cfg.fontSize || 8.8,
    color: COLORS.text, margin: 0, valign: "top", breakLine: false,
  });
}

function finalizeSlide(slide, pptx) {
  warnIfSlideHasOverlaps(slide, pptx, { muteContainment: true, ignoreLines: true, ignoreDecorativeShapes: true });
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

module.exports = {
  COLORS, FONTS, configureDeck, addBackground, addAppendixFlag, addFooter, addKicker,
  addTitle, addPanel, addBullets, addPillsRow, addStatTile, addCodePanel, finalizeSlide,
};

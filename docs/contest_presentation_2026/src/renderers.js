const {
  COLORS,
  addBackground,
  addAppendixFlag,
  addFooter,
  addKicker,
  addTitle,
  addPanel,
  addBullets,
  addPillsRow,
  addStatTile,
  addCodePanel,
  finalizeSlide,
} = require("./theme");

function colorOf(key) {
  return COLORS[key] || COLORS.cyan;
}

function tagWidth(tag) {
  return Math.min(2.9, Math.max(1.15, 0.09 * tag.length + 0.55));
}

function renderBadgeRow(slide, badges) {
  if (!badges || !badges.length) return;
  const rows = [];
  const maxW = 5.78;
  const gap = 0.14;
  let currentRow = [];
  let currentWidth = 0;

  badges.forEach((badge) => {
    const width = badge.w || 1.75;
    const extra = currentRow.length ? gap : 0;
    if (currentRow.length && currentWidth + extra + width > maxW) {
      rows.push(currentRow);
      currentRow = [];
      currentWidth = 0;
    }
    currentRow.push({
      text: badge.text,
      w: width,
      accent: colorOf(badge.accent),
    });
    currentWidth += (currentRow.length > 1 ? gap : 0) + width;
  });

  if (currentRow.length) rows.push(currentRow);

  rows.forEach((items, idx) => {
    addPillsRow(slide, {
      x: 0.82,
      y: 5.05 + idx * 0.46,
      gap,
      items,
    });
  });
}

function renderStatsGrid(slide, stats, options = {}) {
  const items = stats || [];
  const cols = items.length === 4 ? 2 : items.length;
  const baseX = options.x || 7.28;
  const baseY = options.y || 2.12;
  const gapX = options.gapX || 0.22;
  const gapY = options.gapY || 0.22;
  const tileW = options.tileW || (cols === 2 ? 2.46 : 3.5);
  const tileH = options.tileH || 1.28;
  items.forEach((item, idx) => {
    const col = cols === 2 ? idx % 2 : idx;
    const row = cols === 2 ? Math.floor(idx / 2) : 0;
    const w = item.w || tileW;
    addStatTile(slide, {
      x: baseX + col * (tileW + gapX),
      y: baseY + row * (tileH + gapY),
      w,
      h: tileH,
      value: item.value,
      label: item.label,
      accent: colorOf(item.accent),
      valueSize: item.valueSize || (String(item.value).length > 10 ? 14 : 20),
      labelSize: 8.6,
      fill: row === 0 ? COLORS.panel2 : COLORS.panel,
    });
  });
}

function renderCardStack(slide, cards, cfg) {
  const items = cards || [];
  const cardH = cfg.cardH || 0.94;
  items.forEach((card, idx) => {
    addPanel(slide, {
      x: cfg.x,
      y: cfg.y + idx * (cardH + (cfg.gap || 0.16)),
      w: cfg.w,
      h: cardH,
      title: card.title,
      body: card.body,
      accent: colorOf(card.accent),
      titleSize: 10.0,
      bodySize: 8.8,
      fill: idx % 2 === 0 ? COLORS.panel : COLORS.panel2,
    });
  });
}

function renderHero(slide, spec) {
  addPanel(slide, {
    x: 0.82,
    y: 2.48,
    w: 5.95,
    h: 2.18,
    title: spec.statementTitle,
    body: spec.statement,
    accent: COLORS.emerald,
    fill: COLORS.panel2,
    bodySize: 10.1,
  });
  renderBadgeRow(slide, spec.badges);
  renderStatsGrid(slide, spec.stats, { x: 7.28, y: 2.08, tileW: 2.42, tileH: 1.26 });
  const sidePanel = addPanel(slide, {
    x: 7.28,
    y: 4.98,
    w: 5.16,
    h: 1.55,
    title: spec.sideTitle,
    accent: COLORS.cyan,
    fill: COLORS.panel2,
  });
  addBullets(slide, {
    x: sidePanel.contentX + 0.05,
    y: sidePanel.bodyY + 0.04,
    w: sidePanel.contentW - 0.06,
    items: spec.sideBullets,
    fontSize: 9.0,
    bulletColor: COLORS.cyan,
    gap: 0.1,
  });
  if (spec.bridge) {
    addPanel(slide, {
      x: 0.82,
      y: 6.42,
      w: 11.62,
      h: 0.34,
      body: spec.bridge,
      accent: COLORS.emerald,
      fill: COLORS.panel3,
      bodySize: 9.8,
      bodyColor: COLORS.text,
      bodyValign: "mid",
    });
  }
}

function renderSplit(slide, spec) {
  const leftPanel = addPanel(slide, {
    x: 0.82,
    y: 2.12,
    w: 5.48,
    h: 3.98,
    title: spec.leftTitle,
    accent: COLORS.emerald,
    fill: COLORS.panel2,
  });
  addBullets(slide, {
    x: leftPanel.contentX + 0.04,
    y: leftPanel.bodyY + 0.04,
    w: leftPanel.contentW - 0.04,
    items: spec.leftBullets,
    fontSize: 9.6,
    bulletColor: COLORS.emerald,
    gap: 0.12,
  });

  const rightPanel = addPanel(slide, {
    x: 6.82,
    y: 2.12,
    w: 5.6,
    h: 3.98,
    title: spec.rightTitle,
    accent: COLORS.cyan,
    fill: COLORS.panel2,
  });
  renderCardStack(slide, spec.rightCards, {
    x: rightPanel.contentX + 0.04,
    y: rightPanel.bodyY + 0.04,
    w: rightPanel.contentW - 0.04,
    cardH: 0.92,
    gap: 0.16,
  });

  if (spec.bridge) {
    addPanel(slide, {
      x: 0.82,
      y: 6.4,
      w: 11.62,
      h: 0.34,
      body: spec.bridge,
      accent: COLORS.cyan,
      fill: COLORS.panel3,
      bodySize: 9.6,
      bodyColor: COLORS.text,
      bodyValign: "mid",
    });
  }
}

function renderContrast(slide, spec) {
  const stats = spec.stats || [];
  const tileW = stats.length === 4 ? 2.72 : 3.55;
  const gap = stats.length === 4 ? 0.18 : 0.28;
  const totalW = stats.length * tileW + (stats.length - 1) * gap;
  let x = (13.33 - totalW) / 2;
  stats.forEach((item) => {
    addStatTile(slide, {
      x,
      y: 2.2,
      w: item.w || tileW,
      h: 1.42,
      value: item.value,
      label: item.label,
      accent: colorOf(item.accent),
      valueSize: String(item.value).length > 11 ? 14 : 22,
      fill: COLORS.panel2,
    });
    x += (item.w || tileW) + gap;
  });
  (spec.lowerPanels || []).forEach((panel, idx) => {
    addPanel(slide, {
      x: 0.92 + idx * 5.74,
      y: 4.48,
      w: 5.42,
      h: 1.78,
      title: panel.title,
      body: panel.body,
      accent: colorOf(panel.accent),
      fill: idx % 2 === 0 ? COLORS.panel : COLORS.panel2,
      bodySize: 9.5,
    });
  });
  if (spec.bridge) {
    addPanel(slide, {
      x: 0.92,
      y: 6.44,
      w: 11.5,
      h: 0.28,
      body: spec.bridge,
      accent: COLORS.emerald,
      fill: COLORS.panel3,
      bodySize: 9.6,
      bodyColor: COLORS.text,
      bodyValign: "mid",
    });
  }
}

function renderReference(slide, spec) {
  const columns = spec.columns || 2;
  const colW = columns === 3 ? 3.54 : 5.42;
  const gap = columns === 3 ? 0.28 : 0.34;
  const rowH = columns === 3 ? 1.52 : 1.45;
  (spec.sections || []).forEach((section, idx) => {
    const col = idx % columns;
    const row = Math.floor(idx / columns);
    addPanel(slide, {
      x: 0.92 + col * (colW + gap),
      y: 2.1 + row * (rowH + 0.18),
      w: colW,
      h: rowH,
      title: section.title,
      body: section.body,
      accent: colorOf(section.accent),
      fill: row % 2 === 0 ? COLORS.panel : COLORS.panel2,
      bodySize: section.mono ? 8.8 : 9.2,
      mono: section.mono,
    });
  });
  if (spec.bridge) {
    addPanel(slide, {
      x: 0.92,
      y: 6.35,
      w: 11.5,
      h: 0.36,
      body: spec.bridge,
      accent: COLORS.cyan,
      fill: COLORS.panel3,
      bodySize: 9.5,
      bodyColor: COLORS.text,
      bodyValign: "mid",
    });
  }
}

function renderCode(slide, spec) {
  (spec.sideSections || []).forEach((section, idx) => {
    addPanel(slide, {
      x: 0.92,
      y: 2.08 + idx * 1.52,
      w: 3.35,
      h: 1.24,
      title: section.title,
      body: section.body,
      accent: colorOf(section.accent),
      fill: idx % 2 === 0 ? COLORS.panel : COLORS.panel2,
      bodySize: 8.7,
      mono: section.mono,
    });
  });
  addCodePanel(slide, {
    x: 4.58,
    y: 2.08,
    w: 7.84,
    h: 4.98,
    title: spec.codeTitle,
    code: spec.code,
    accent: COLORS.cyan,
    fontSize: 8.6,
  });
  if (spec.bridge) {
    addPanel(slide, {
      x: 0.92,
      y: 6.35,
      w: 11.5,
      h: 0.36,
      body: spec.bridge,
      accent: COLORS.emerald,
      fill: COLORS.panel3,
      bodySize: 9.5,
      bodyColor: COLORS.text,
      bodyValign: "mid",
    });
  }
}

function renderThanks(slide, spec) {
  addBackground(slide, "main");
  addKicker(slide, spec.tag, { x: 5.4, y: 1.5, w: 1.6, color: COLORS.emerald });
  addTitle(slide, spec.title, spec.subtitle, {
    x: 1.25,
    y: 2.25,
    w: 10.8,
    h: 1.08,
    fontSize: 31,
    maxFontSize: 34,
    minFontSize: 24,
    subtitleOffset: 1.08,
    subtitleHeight: 0.34,
    subtitleFontSize: 11.8,
  });
  addPanel(slide, {
    x: 3.0,
    y: 5.25,
    w: 7.33,
    h: 0.46,
    body: spec.thanksLead,
    accent: COLORS.cyan,
    fill: COLORS.panel3,
    bodySize: 10.2,
    bodyColor: COLORS.text,
    bodyValign: "mid",
  });
}

function renderSlide(slide, spec, page, pptx) {
  if (spec.layout === "thanks") {
    renderThanks(slide, spec);
    finalizeSlide(slide, pptx);
    return;
  }

  addBackground(slide, spec.role);
  if (spec.role === "backup") addAppendixFlag(slide);
  addKicker(slide, spec.tag, { w: tagWidth(spec.tag) });
  addTitle(slide, spec.title, spec.subtitle, { role: spec.role });

  if (spec.layout === "hero") renderHero(slide, spec);
  if (spec.layout === "split") renderSplit(slide, spec);
  if (spec.layout === "contrast") renderContrast(slide, spec);
  if (spec.layout === "reference") renderReference(slide, spec);
  if (spec.layout === "code") renderCode(slide, spec);

  addFooter(slide, page, spec.role);
  finalizeSlide(slide, pptx);
}

function renderDeck(pptx, deck) {
  deck.forEach((spec, idx) => {
    const slide = pptx.addSlide();
    renderSlide(slide, spec, idx + 1, pptx);
  });
}

module.exports = {
  renderDeck,
};

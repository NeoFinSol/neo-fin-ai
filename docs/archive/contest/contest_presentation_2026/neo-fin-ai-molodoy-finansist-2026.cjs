const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");

const { configureDeck } = require("./src/theme");
const { DECK } = require("./src/content");
const { renderDeck } = require("./src/renderers");

const OUTPUT_FILE = path.join(
  __dirname,
  "neo-fin-ai-molodoy-finansist-2026.pptx"
);

async function main() {
  const pptx = new PptxGenJS();
  configureDeck(pptx);
  renderDeck(pptx, DECK);

  await pptx.writeFile({ fileName: OUTPUT_FILE });

  if (!fs.existsSync(OUTPUT_FILE)) {
    throw new Error(`Presentation file was not created: ${OUTPUT_FILE}`);
  }

  console.log(`Presentation created: ${OUTPUT_FILE}`);
  console.log(`Slides rendered: ${DECK.length}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

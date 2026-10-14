import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const BUILD_DIR = "C:\\Users\\Acer\\OneDrive\\Documents\\เป้าๆรวยๆๆๆ\\sleep_stage_reproduction\\slides_build";
const OUTPUT_DIR = path.join(BUILD_DIR, "output");
const VISUAL_PATH = path.join(BUILD_DIR, "eeg_sleep_visual.png");
const FINAL_PPTX = path.join(BUILD_DIR, "sleep_stage_classification_3slides.pptx");

const C = {
  navy: "#061528",
  navy2: "#0B2340",
  ink: "#10213A",
  slate: "#54657D",
  mist: "#F4F8FC",
  white: "#FFFFFF",
  cyan: "#44D6E8",
  teal: "#25B6A5",
  violet: "#8B7CF6",
  amber: "#F4B545",
  coral: "#F47B65",
  line: "#D7E2EE",
};

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function box(slide, geometry, left, top, width, height, fill = "none", lineFill = "none", lineWidth = 0, name) {
  return slide.shapes.add({
    geometry,
    ...(name ? { name } : {}),
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
  });
}

function text(slide, value, left, top, width, height, fontSize, color, bold = false, alignment = "left", name) {
  const shape = box(slide, "textbox", left, top, width, height, "none", "none", 0, name);
  shape.text = value;
  shape.text.style = { fontSize, color, bold, alignment };
  return shape;
}

function divider(slide, left, top, width, color = C.line, height = 2) {
  return box(slide, "rect", left, top, width, height, color, "none", 0);
}

function arrow(slide, left, top, width, height, color) {
  return box(slide, "rightArrow", left, top, width, height, color, "none", 0);
}

function addFooter(slide, sourceText, dark = false, page = "01 / 03") {
  divider(slide, 70, 680, 1140, dark ? "#36506E" : C.line, 1);
  text(slide, sourceText, 70, 690, 1030, 18, 13, dark ? "#A9BDD5" : "#687A91", false, "left");
  text(slide, page, 1110, 690, 100, 18, 13, dark ? "#A9BDD5" : "#687A91", true, "right");
}

function addNotes(slide, lines) {
  slide.speakerNotes.textFrame.setText(lines);
  slide.speakerNotes.setVisible(true);
}

async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const imageBytes = await fs.readFile(VISUAL_PATH);
  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  // Slide 1: opening claim and visual anchor.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.navy;
    slide.images.add({
      blob: imageBytes,
      contentType: "image/png",
      alt: "Abstract single-channel EEG signal transformed into sleep-stage bands",
      fit: "cover",
      position: { left: 0, top: 0, width: 1280, height: 720 },
    });
    // A quiet dark wash protects the left-side typography while preserving the visual.
    box(slide, "rect", 0, 0, 650, 720, { type: "solid", color: C.navy, transparency: 18 }, "none", 0);
    text(slide, "RESEARCH PROPOSAL", 76, 72, 330, 28, 16, C.cyan, true, "left");
    divider(slide, 76, 112, 86, C.cyan, 4);
    text(slide, "แยกประเภทการนอน\nจาก EEG ช่องเดียว", 76, 156, 570, 145, 50, C.white, true, "left");
    text(slide, "พัฒนาโมเดล Sleep Stage Classification\nด้วย SST + CNN + Contrastive Learning + GRU", 80, 330, 520, 80, 24, "#D7E7F8", false, "left");
    box(slide, "roundRect", 78, 462, 350, 86, { type: "solid", color: C.white, transparency: 8 }, "#8BB0D7", 1);
    text(slide, "1 ช่อง EEG  →  5 ระยะการนอน", 100, 486, 315, 30, 22, C.navy, true, "center");
    text(slide, "Wake · N1 · N2 · N3 · REM", 100, 521, 315, 22, 16, C.navy2, false, "center");
    text(slide, "จากสัญญาณดิบสู่การตัดสินใจที่อธิบายได้", 78, 608, 470, 30, 17, "#B9D0E9", false, "left");
    divider(slide, 70, 680, 1140, "#36506E", 1);
    text(slide, "แหล่งข้อมูล: Scientific Reports 2026 · PhysioNet Sleep-EDF", 70, 690, 850, 18, 13, "#A9BDD5", false, "left");
    text(slide, "01 / 03", 1110, 690, 100, 18, 13, "#A9BDD5", true, "right");
    addNotes(slide, [
      "เปิดด้วยคำถาม: เราสามารถลดจำนวน channel ของ EEG แต่ยังจำแนกระยะการนอนได้หรือไม่",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5 (งานวิจัยหลักและผลที่รายงาน)",
      "- https://physionet.org/content/sleep-edfx/1.0.0/ (ชุดข้อมูล Sleep-EDF)",
      "- ภาพประกอบสร้างด้วย OpenAI image generation เพื่อใช้ในสไลด์นี้",
    ]);
  }

  // Slide 2: the infographic pipeline.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.mist;
    text(slide, "โมเดลเปลี่ยนสัญญาณ EEG ให้เป็น sleep stage ได้อย่างไร", 70, 52, 1060, 56, 36, C.ink, true, "left");
    text(slide, "ใช้ทั้งรูปแบบเวลา–ความถี่ และบริบทของ epoch ที่ต่อเนื่องกัน", 72, 119, 840, 30, 20, C.slate, false, "left");
    box(slide, "roundRect", 950, 62, 260, 72, "#E3F7FA", "#9DDCE3", 1);
    text(slide, "30 วินาที\n3,000 samples / epoch", 968, 76, 224, 45, 18, C.navy2, true, "center");

    const nodes = [
      { x: 70, color: C.navy2, title: "EEG", body: "Fpz–Cz\nraw signal" },
      { x: 250, color: C.cyan, title: "SST", body: "T–F map" },
      { x: 430, color: C.violet, title: "CNN", body: "short-window\nfeatures" },
      { x: 610, color: C.teal, title: "Contrastive", body: "refine\nfeatures" },
      { x: 790, color: C.amber, title: "GRU × 2", body: "sequence\ncontext" },
      { x: 970, color: C.coral, title: "5 stages", body: "W · N1 · N2\nN3 · REM" },
    ];
    const nodeY = 268;
    const nodeW = 140;
    const nodeH = 150;
    // Arrows first so they stay behind the nodes.
    for (let i = 0; i < nodes.length - 1; i += 1) {
      arrow(slide, nodes[i].x + nodeW + 8, nodeY + 60, 28, 28, "#B5C5D6");
    }
    nodes.forEach((node) => {
      box(slide, "roundRect", node.x, nodeY, nodeW, nodeH, C.white, node.color, 3);
      box(slide, "roundRect", node.x, nodeY, nodeW, 12, node.color, "none", 0);
      text(slide, node.title, node.x + 12, nodeY + 32, nodeW - 24, 30, node.title === "Contrastive" ? 18 : 22, C.ink, true, "center");
      text(slide, node.body, node.x + 12, nodeY + 78, nodeW - 24, 54, 17, C.slate, false, "center");
    });

    text(slide, "สิ่งที่ทำให้แนวทางนี้ต่างจาก CNN ธรรมดา", 70, 478, 500, 30, 22, C.ink, true, "left");
    divider(slide, 70, 522, 510, C.line, 2);
    text(slide, "SST ช่วยรักษารายละเอียดของ EEG ในโดเมนเวลา–ความถี่\nขณะที่ GRU ใช้บริบทของลำดับ ไม่ตัดสินจาก epoch เดียวแบบโดด ๆ", 70, 546, 540, 70, 19, C.slate, false, "left");

    text(slide, "OUTPUT LABELS", 760, 478, 300, 24, 16, C.slate, true, "left");
    const stageItems = [
      ["W", C.navy2], ["N1", C.violet], ["N2", C.cyan], ["N3", C.teal], ["REM", C.amber],
    ];
    stageItems.forEach(([label, color], i) => {
      const x = 760 + i * 86;
      box(slide, "roundRect", x, 522, 70, 52, color, "none", 0);
      text(slide, label, x, 535, 70, 22, 17, C.white, true, "center");
    });
    text(slide, "เป้าหมาย: โมเดลที่แม่นขึ้นและตรวจสอบได้\nโดยไม่ให้ข้อมูลจากคนเดียวกันรั่วข้ามชุด", 760, 596, 430, 48, 18, C.ink, false, "left");
    addFooter(slide, "แหล่งข้อมูล: Nature Scientific Reports 2026 · protocol-level reproduction", false, "02 / 03");
    addNotes(slide, [
      "อธิบาย pipeline จากซ้ายไปขวา โดยเน้นว่าระบบไม่ได้ดูแค่ amplitude แต่สร้าง representation และใช้ sequence context",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5 (โครงสร้าง SST, CNN, contrastive learning และ GRU)",
      "- https://physionet.org/content/sleep-edfx/1.0.0/ (EEG และ hypnogram)",
    ]);
  }

  // Slide 3: evidence and next steps.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    text(slide, "pilot บอกอะไรเรา และต้องทำอะไรต่อ", 70, 52, 930, 56, 38, C.ink, true, "left");
    text(slide, "ผลรอบแรกยืนยันว่า pipeline ทำงาน แต่ข้อมูลและ compute ยังเป็นคอขวด", 72, 120, 930, 30, 20, C.slate, false, "left");
    box(slide, "roundRect", 70, 184, 650, 416, C.mist, C.line, 1);
    text(slide, "PILOT RESULT · 4 คืน · 588 epochs · CPU", 100, 214, 520, 24, 16, C.slate, true, "left");
    const chartLeft = 154;
    const chartBase = 532;
    const chartHeight = 240;
    divider(slide, chartLeft, chartBase, 485, "#AFC1D4", 2);
    [0, 25, 50, 75, 100].forEach((v) => {
      const y = chartBase - (chartHeight * v) / 100;
      divider(slide, chartLeft, y, 485, v === 0 ? "#AFC1D4" : "#E2EAF3", 1);
      text(slide, `${v}%`, 100, y - 10, 42, 20, 14, C.slate, false, "right");
    });
    const benchmarkY = chartBase - (chartHeight * 83) / 100;
    divider(slide, chartLeft, benchmarkY, 485, "#9AAEC4", 2);
    text(slide, "83% · paper reported\nfull protocol; not directly comparable", 410, benchmarkY - 42, 215, 36, 14, C.slate, false, "right");
    const bars = [
      { x: 270, value: 25, label: "unweighted", color: C.violet },
      { x: 500, value: 46.9, label: "class-weighted", color: C.teal },
    ];
    bars.forEach((bar) => {
      const h = (chartHeight * bar.value) / 100;
      box(slide, "roundRect", bar.x, chartBase - h, 120, h, bar.color, "none", 0);
      text(slide, `${bar.value}%`, bar.x, chartBase - h - 34, 120, 28, 24, C.ink, true, "center");
      text(slide, bar.label, bar.x - 18, chartBase + 20, 156, 28, 16, C.slate, true, "center");
    });
    text(slide, "+21.9 pp", 300, 574, 240, 30, 22, C.teal, true, "center");
    text(slide, "ดีขึ้นเมื่อชดเชย class imbalance", 260, 601, 320, 22, 15, C.slate, false, "center");

    box(slide, "roundRect", 770, 184, 440, 440, "#F8FBFE", C.line, 1);
    text(slide, "ข้อค้นพบสำคัญ", 805, 218, 340, 30, 24, C.ink, true, "left");
    const findings = [
      [C.teal, "โมเดลอ่านข้อมูลได้จริง", "โหลด EDF → train → evaluate ครบ"],
      [C.amber, "class imbalance สำคัญ", "N1 และ REM ยังถูกทำนายน้อย"],
      [C.violet, "ยังสรุปผลใหญ่ไม่ได้", "ต้องใช้ full dataset และ GPU"],
    ];
    findings.forEach(([color, head, body], i) => {
      const y = 286 + i * 78;
      box(slide, "ellipse", 808, y, 22, 22, color, "none", 0);
      text(slide, head, 846, y - 2, 320, 25, 19, C.ink, true, "left");
      text(slide, body, 846, y + 27, 320, 22, 16, C.slate, false, "left");
    });
    divider(slide, 805, 500, 350, C.line, 2);
    text(slide, "NEXT", 805, 520, 110, 22, 16, C.coral, true, "left");
    text(slide, "1  Full Sleep-EDF\n2  Train บน GPU\n3  Validate ข้าม dataset", 805, 548, 330, 62, 18, C.ink, true, "left");
    addFooter(slide, "ผล pilot จาก local reproduction · paper benchmark ใช้ protocol เต็มของผู้วิจัย", false, "03 / 03");
    addNotes(slide, [
      "ปิดด้วยความแตกต่างระหว่าง pilot กับ benchmark: 83% เป็นผลของ paper บน protocol เต็ม ไม่ใช่ตัวเลขที่นำมาเทียบตรง ๆ กับ subset นี้",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5 (83% ที่ paper รายงาน)",
      "- C:\\Users\\Acer\\OneDrive\\Documents\\เป้าๆรวยๆๆๆ\\sleep_stage_reproduction\\real_sst_gru_fullish_results.json (pilot unweighted)",
      "- C:\\Users\\Acer\\OneDrive\\Documents\\เป้าๆรวยๆๆๆ\\sleep_stage_reproduction\\real_sst_gru_weighted_results.json (pilot class-weighted)",
    ]);
  }

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(OUTPUT_DIR, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 2 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(OUTPUT_DIR, `${stem}.layout.json`), await layout.text(), "utf8");
  }
  await writeBlob(path.join(OUTPUT_DIR, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes", maxChars: 30000 });
  await fs.writeFile(path.join(OUTPUT_DIR, "inspect.ndjson"), inspect.ndjson, "utf8");
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

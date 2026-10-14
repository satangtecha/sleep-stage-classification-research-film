import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const BUILD_DIR = "C:\\Users\\Acer\\OneDrive\\Documents\\เป้าๆรวยๆๆๆ\\sleep_stage_reproduction\\pitch_deck_build";
const OUTPUT_DIR = path.join(BUILD_DIR, "output");
const FINAL_PPTX = path.join(BUILD_DIR, "sleep_stage_classification_pitch_EN.pptx");

const C = {
  navy: "#0B1220",
  navy2: "#14233A",
  ink: "#15263E",
  slate: "#5D6E84",
  mist: "#F5F8FC",
  white: "#FFFFFF",
  blue: "#38BDF8",
  cyan: "#24C6D9",
  mint: "#2DB7A3",
  violet: "#8A7CF4",
  amber: "#F3B545",
  coral: "#F27D69",
  line: "#D7E1EC",
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

function arrow(slide, left, top, width, height, color = "#B8C9DA") {
  return box(slide, "rightArrow", left, top, width, height, color, "none", 0);
}

function footer(slide, page, source, dark = false) {
  divider(slide, 70, 680, 1140, dark ? "#314A66" : C.line, 1);
  text(slide, source, 70, 690, 980, 18, 13, dark ? "#A9BCD2" : "#687A91", false, "left");
  text(slide, `${page} / 04`, 1110, 690, 100, 18, 13, dark ? "#A9BCD2" : "#687A91", true, "right");
}

function notes(slide, lines) {
  slide.speakerNotes.textFrame.setText(lines);
  slide.speakerNotes.setVisible(true);
}

async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  // Slide 1 — Problem and hook.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.navy;
    text(slide, "RESEARCH IDEA", 76, 64, 300, 24, 16, C.blue, true, "left");
    divider(slide, 76, 104, 84, C.blue, 4);
    text(slide, "Can one EEG channel\nclassify sleep stages?", 76, 150, 630, 150, 50, C.white, true, "left");
    text(slide, "A reproducible deep-learning pipeline for\nautomatic sleep staging", 80, 340, 520, 68, 24, "#D6E5F5", false, "left");
    text(slide, "SINGLE-CHANNEL EEG", 80, 470, 230, 22, 16, C.cyan, true, "left");
    text(slide, "5 SLEEP STAGES", 330, 470, 220, 22, 16, C.mint, true, "left");
    text(slide, "30-SECOND EPOCHS", 80, 510, 260, 22, 16, C.amber, true, "left");
    text(slide, "A simpler input, a transparent evaluation,\nand a research-ready prototype.", 80, 582, 520, 48, 19, "#AFC4DB", false, "left");

    // Visual anchor: one input channel expands into five outputs.
    box(slide, "roundRect", 760, 96, 420, 500, C.navy2, "#2D4865", 1);
    text(slide, "FROM ONE SIGNAL", 800, 130, 300, 22, 16, "#AFC4DB", true, "center");
    box(slide, "ellipse", 900, 218, 140, 140, C.blue, "none", 0);
    text(slide, "EEG", 900, 260, 140, 28, 27, C.navy, true, "center");
    text(slide, "Fpz-Cz", 900, 297, 140, 24, 17, C.navy, false, "center");
    // Connectors first.
    const outY = [410, 450, 490, 530, 570];
    outY.forEach((y, i) => arrow(slide, 1035, y - 11, 72, 22, [C.blue, C.violet, C.cyan, C.mint, C.amber][i]));
    const stageItems = [["Wake", C.blue], ["N1", C.violet], ["N2", C.cyan], ["N3", C.mint], ["REM", C.amber]];
    stageItems.forEach(([label, color], i) => {
      box(slide, "roundRect", 1110, outY[i] - 12, 54, 30, color, "none", 0);
      text(slide, label, 1110, outY[i] - 4, 54, 18, 14, C.white, true, "center");
    });
    text(slide, "one 30-second epoch", 845, 380, 250, 22, 17, "#D6E5F5", false, "center");
    footer(slide, "01", "Concept inspired by recent single-channel EEG sleep-staging research", true);
    notes(slide, [
      "Hello everyone. My project is about automatic sleep stage classification from EEG.",
      "The key idea is to investigate whether one EEG channel can provide enough information to classify five sleep stages automatically.",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5",
      "- https://physionet.org/content/sleep-edfx/1.0.0/",
    ]);
  }

  // Slide 2 — Idea and objectives.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.mist;
    text(slide, "The research idea is focused and testable", 70, 52, 930, 50, 37, C.ink, true, "left");
    text(slide, "Reduce the input, preserve the signal information, and evaluate generalization.", 72, 115, 900, 28, 20, C.slate, false, "left");

    box(slide, "roundRect", 70, 205, 340, 360, C.navy, "none", 0);
    text(slide, "CORE QUESTION", 105, 245, 260, 22, 16, C.blue, true, "left");
    text(slide, "Can one channel\nsupport reliable\nsleep staging?", 105, 300, 275, 130, 34, C.white, true, "left");
    text(slide, "without relying on a\nfull multi-sensor PSG setup", 105, 488, 245, 48, 18, "#B7C9DD", false, "left");

    // Objective path.
    text(slide, "PROJECT OBJECTIVES", 495, 205, 300, 22, 16, C.slate, true, "left");
    const objectives = [
      { y: 260, num: "01", color: C.blue, title: "Build", body: "A single-channel EEG sleep-staging pipeline" },
      { y: 370, num: "02", color: C.mint, title: "Compare", body: "Baseline CNN vs. the full representation + sequence model" },
      { y: 480, num: "03", color: C.amber, title: "Evaluate", body: "Class imbalance, unseen subjects, and per-stage performance" },
    ];
    objectives.forEach((item, i) => {
      if (i < objectives.length - 1) divider(slide, 536, item.y + 74, 2, C.line, 64);
      box(slide, "ellipse", 500, item.y, 56, 56, item.color, "none", 0);
      text(slide, item.num, 500, item.y + 17, 56, 20, 16, C.white, true, "center");
      text(slide, item.title, 590, item.y - 2, 220, 28, 24, C.ink, true, "left");
      text(slide, item.body, 590, item.y + 35, 510, 32, 18, C.slate, false, "left");
    });
    box(slide, "roundRect", 500, 590, 630, 45, "#E7F7F4", "#A5DFD5", 1);
    text(slide, "Research prototype — not a medical diagnostic device", 520, 603, 590, 20, 17, C.ink, true, "center");
    footer(slide, "02", "Research objective: reproducible modeling and honest evaluation");
    notes(slide, [
      "The core idea is simple: take a 30-second segment of single-channel EEG, learn its time-frequency patterns, and predict one of five sleep stages.",
      "The project objectives are to build the pipeline, compare model components, and evaluate generalization to unseen subjects.",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5",
      "- https://physionet.org/content/sleep-edfx/1.0.0/",
    ]);
  }

  // Slide 3 — Technical workflow.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    text(slide, "The proposed workflow turns EEG into five labels", 70, 52, 1000, 50, 37, C.ink, true, "left");
    text(slide, "Each step has a specific role: normalize, represent, learn, and classify.", 72, 115, 900, 28, 20, C.slate, false, "left");

    const nodes = [
      { x: 70, color: C.navy2, title: "30s EEG", body: "Fpz-Cz\n3,000 samples" },
      { x: 240, color: C.blue, title: "Normalize", body: "clean\nand scale" },
      { x: 410, color: C.violet, title: "SST map", body: "T–F\nmap" },
      { x: 580, color: C.cyan, title: "CNN", body: "local\nfeatures" },
      { x: 750, color: C.mint, title: "Contrastive", body: "robust\nfeatures" },
      { x: 920, color: C.amber, title: "GRU × 2", body: "ordered\ncontext" },
      { x: 1090, color: C.coral, title: "5 stages", body: "Wake · N1\nN2 · N3 · REM" },
    ];
    const nodeY = 275;
    const nodeW = 130;
    const nodeH = 146;
    for (let i = 0; i < nodes.length - 1; i += 1) arrow(slide, nodes[i].x + nodeW + 8, nodeY + 58, 24, 26);
    nodes.forEach((node) => {
      box(slide, "roundRect", node.x, nodeY, nodeW, nodeH, C.white, node.color, 3);
      box(slide, "roundRect", node.x, nodeY, nodeW, 11, node.color, "none", 0);
      text(slide, node.title, node.x + 8, nodeY + 34, nodeW - 16, 28, node.title === "Contrastive" ? 17 : 20, C.ink, true, "center");
      text(slide, node.body, node.x + 8, nodeY + 80, nodeW - 16, 50, 16, C.slate, false, "center");
    });

    text(slide, "WHY THIS COMBINATION?", 70, 500, 300, 22, 16, C.slate, true, "left");
    divider(slide, 70, 538, 540, C.line, 2);
    text(slide, "SST preserves time–frequency detail.\nCNN learns local patterns. GRU preserves the order of feature windows.", 70, 560, 600, 52, 19, C.ink, false, "left");
    box(slide, "roundRect", 770, 500, 410, 120, "#FFF5DE", "#F1D18A", 1);
    text(slide, "PRIMARY METRIC", 795, 520, 160, 22, 16, C.amber, true, "left");
    text(slide, "Macro-F1 + per-stage F1", 795, 556, 350, 26, 23, C.ink, true, "left");
    text(slide, "because the classes are imbalanced", 795, 588, 350, 20, 16, C.slate, false, "left");
    footer(slide, "03", "Model structure adapted from the selected recent research protocol");
    notes(slide, [
      "The workflow begins with a 30-second Fpz-Cz epoch, normalizes the signal, creates a time-frequency representation, and learns features with CNN.",
      "Contrastive learning improves robustness, and a two-layer GRU processes the ordered feature windows before predicting the five labels.",
      "Macro-F1 is the primary metric because the classes are imbalanced.",
      "[Sources]",
      "- https://www.nature.com/articles/s41598-026-62832-5",
      "- https://physionet.org/content/sleep-edfx/1.0.0/",
    ]);
  }

  // Slide 4 — Dataset, evaluation, and deliverables.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.mist;
    text(slide, "Data, evaluation, and expected contribution", 70, 52, 1000, 50, 37, C.ink, true, "left");
    text(slide, "The proposal ends with a reproducible experiment, not only a model score.", 72, 115, 900, 28, 20, C.slate, false, "left");

    box(slide, "roundRect", 70, 205, 480, 360, C.white, C.line, 1);
    text(slide, "DATASET", 105, 240, 220, 22, 16, C.blue, true, "left");
    text(slide, "Sleep-EDF Expanded", 105, 282, 370, 32, 27, C.ink, true, "left");
    text(slide, "197 whole-night PSG recordings\nEEG + expert-scored hypnograms", 105, 330, 360, 54, 19, C.slate, false, "left");
    divider(slide, 105, 420, 370, C.line, 2);
    const dataSteps = [
      [C.blue, "Input", "Fpz-Cz EEG"],
      [C.violet, "Labels", "Wake / N1 / N2 / N3 / REM"],
      [C.mint, "Split", "subject-wise train / test"],
    ];
    dataSteps.forEach(([color, label, value], i) => {
      const y = 452 + i * 38;
      box(slide, "ellipse", 106, y, 16, 16, color, "none", 0);
      text(slide, label, 140, y - 3, 80, 20, 16, C.ink, true, "left");
      text(slide, value, 240, y - 3, 250, 20, 16, C.slate, false, "left");
    });

    box(slide, "roundRect", 600, 205, 610, 360, C.navy, "none", 0);
    text(slide, "EVALUATION PLAN", 640, 240, 260, 22, 16, C.blue, true, "left");
    const evalItems = [
      ["01", "Baseline", "Majority class + CNN"],
      ["02", "Ablation", "SST / contrastive / GRU / class weighting"],
      ["03", "Metrics", "Accuracy, macro-F1, kappa, confusion matrix"],
      ["04", "Generalization", "Unseen subjects, then external dataset"],
    ];
    evalItems.forEach(([num, head, body], i) => {
      const y = 292 + i * 60;
      box(slide, "ellipse", 640, y, 36, 36, i === 0 ? C.blue : i === 1 ? C.violet : i === 2 ? C.mint : C.amber, "none", 0);
      text(slide, num, 640, y + 9, 36, 16, 13, C.navy, true, "center");
      text(slide, head, 700, y - 2, 160, 24, 19, C.white, true, "left");
      text(slide, body, 860, y - 2, 305, 24, 17, "#C8D7E7", false, "left");
    });
    box(slide, "roundRect", 70, 600, 1140, 45, "#E7F7F4", "#A5DFD5", 1);
    text(slide, "EXPECTED CONTRIBUTION: a transparent, reproducible single-channel EEG sleep-staging pipeline", 95, 613, 1090, 20, 18, C.ink, true, "center");
    footer(slide, "04", "Dataset: PhysioNet Sleep-EDF · evaluation designed for reproducibility");
    notes(slide, [
      "The primary dataset will be Sleep-EDF Expanded, which contains whole-night polysomnography recordings and expert-scored hypnograms.",
      "The final experiment will use subject-wise splits, compare baselines and ablations, and report both overall and per-stage metrics.",
      "The expected contribution is a reproducible research pipeline and an honest analysis of generalization.",
      "[Sources]",
      "- https://physionet.org/content/sleep-edfx/1.0.0/",
      "- https://www.nature.com/articles/s41598-026-62832-5",
    ]);
  }

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(OUTPUT_DIR, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 2 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(OUTPUT_DIR, `${stem}.layout.json`), await layout.text(), "utf8");
  }
  await writeBlob(path.join(OUTPUT_DIR, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await presentation.inspect({ kind: "slide,textbox,shape,notes", maxChars: 40000 });
  await fs.writeFile(path.join(OUTPUT_DIR, "inspect.ndjson"), inspect.ndjson, "utf8");
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

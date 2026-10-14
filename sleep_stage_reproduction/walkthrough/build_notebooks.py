"""Generate the Thai, evidence-backed VS Code walkthrough notebooks."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


HERE = Path(__file__).resolve().parent
NOTEBOOKS = HERE / "notebooks"


SETUP = """from pathlib import Path
import sys

ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "paper_faithful").is_dir())
sys.path.insert(0, str(ROOT / "walkthrough"))

import matplotlib.pyplot as plt
import numpy as np
from walkthrough_lib import *

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({"figure.dpi": 110, "axes.titleweight": "bold"})
print(f"Project root : {PROJECT_ROOT}")
print(f"Bulk artifacts: {BULK_ROOT}")
"""


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def notebook(title: str, cells: list):
    nb = nbf.v4.new_notebook(cells=[md(title), *cells])
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python (sleep-stage .venv)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
        "walkthrough": {"read_only_evidence": True, "launches_training": False},
    }
    return nb


def write(name: str, nb) -> None:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, NOTEBOOKS / name)


def build() -> None:
    write(
        "00_start_here.ipynb",
        notebook(
            """# 00 — เริ่มต้นที่นี่: เรากำลังทำอะไร และทำถึงไหนแล้ว

สมุดเล่มนี้เป็น **หน้าปกของการทดลองจริง** ไม่ใช่เว็บไซต์ประชาสัมพันธ์ และไม่ใช่การเทรนรอบใหม่

เมื่อกดรัน เซลล์จะอ่านหลักฐานที่มีอยู่แล้วจาก repository และ `E:\\blp\\sleep_stage_reproduction` เพื่อสรุปว่า

1. บทความต้นฉบับกำหนดอะไร
2. เราสร้างข้อมูลและรันอะไรจริงแล้ว
3. ผลใดเป็นเพียง pilot และยังเทียบกับบทความไม่ได้
4. ขั้นใดยังติด gate หรือยังไม่เริ่ม

> กติกาการอ่าน: สีเขียว = มีหลักฐานว่าสำเร็จ, สีเหลือง = เตรียมพร้อมบางส่วน, สีแดง = ถูก block/ล้มเหลว, สีเทา = ยังไม่เริ่ม""",
            [
                code(SETUP),
                md("""## 1. ตรวจว่าเครื่องนี้เห็นหลักฐานครบหรือไม่

เส้นทางต่อไปนี้เป็นแหล่งข้อมูลจริง เซลล์นี้ตรวจเฉพาะการมีอยู่ของไฟล์ ไม่แก้ไขไฟล์ใด ๆ"""),
                code("""health = path_health()
print_records(health, ["artifact", "exists", "path"])
assert health[0]["exists"], "เปิด notebook จาก repository ไม่ถูกตำแหน่ง"
"""),
                md("""## 2. ภาพรวมสถานะจากหลักฐานล่าสุด

`r19 cap128` หมายถึงใช้ไม่เกิน 128 epochs ต่อ split เพื่อพิสูจน์ว่า pipeline ทำงานได้ ไม่ใช่การรัน full numerical reproduction"""),
                code("""cohort = full_cohort_summary()
r19 = r19_runs()
gate = subject_gate_summary()

overview = [
    {"milestone": "Source/protocol lock", "status": "complete", "evidence": "PAPER_TEXT_V1 + source manifests"},
    {"milestone": "Full preprocessing", "status": cohort["status"], "evidence": f"{cohort['recordings']} records / {cohort['subjects']} subjects / {cohort['epochs']:,} epochs"},
    {"milestone": "Full SST cache", "status": "complete" if CACHE_ROOT.exists() else "missing", "evidence": "published cache manifest on E:"},
    {"milestone": "r19 cap128, two seeds", "status": "complete" if len(r19) == 2 and all(x['status'] == 'completed' for x in r19) else "prepared", "evidence": f"completed runs: {sum(x['status']=='completed' for x in r19)}/2"},
    {"milestone": "Subject-held-out pilot", "status": gate["status"], "evidence": gate["reason"]},
    {"milestone": "Full numerical reproduction", "status": "not_started", "evidence": "ยังไม่มีผลเต็มที่ตรวจรับแล้ว"},
]
print_records(overview, ["milestone", "status", "evidence"])

fig, ax = plt.subplots(figsize=(10, 4.5))
names = [row["milestone"] for row in overview]
colors = [STATUS_COLORS.get(row["status"], "#adb5bd") for row in overview]
ax.barh(range(len(names)), [1] * len(names), color=colors)
ax.set_yticks(range(len(names)), names)
ax.set_xlim(0, 1)
ax.set_xticks([])
ax.invert_yaxis()
ax.set_title("Project evidence map (not a percentage-complete estimate)")
for i, row in enumerate(overview):
    ax.text(0.02, i, status_badge(row["status"]), va="center", color="white", weight="bold")
plt.tight_layout()
plt.show()
"""),
                md("""## 3. เป้าหมายของบทความ เทียบกับสถานะของเรา

ตัวเลข 83% เป็นผลที่บทความรายงานจาก protocol เต็ม ส่วนผล r19 เป็น **pilot ที่ตัดข้อมูลเหลือ cap128** จึงวางไว้ให้เห็นระยะห่าง แต่ห้ามสรุปว่าโมเดลเราดีกว่าหรือแย่กว่าบทความจากกราฟเดียว"""),
                code("""protocol = paper_protocol()
comparison = [
    {"item": "Dataset", "paper": "Sleep-EDF full cohort", "ours": f"full cohort prepared: {cohort['subjects']} subjects"},
    {"item": "Input", "paper": "Fpz-Cz, 100 Hz, 30 s", "ours": f"{protocol['dataset']['signal']}, {protocol['dataset']['sampling_hz']} Hz"},
    {"item": "Reported accuracy", "paper": "83%", "ours": "ยังไม่มี full accepted result"},
    {"item": "Latest runnable evidence", "paper": "full experiment", "ours": "r19 cap128, 2 seeds completed"},
    {"item": "Subject-held-out", "paper": "not the 83% split", "ours": f"{gate['status']}; training_started={gate['training_started']}"},
]
print_records(comparison, ["item", "paper", "ours"])
"""),
                md("""## 4. อ่านเล่มต่อไปตามลำดับ

- `01_data_and_eeg.ipynb` — เห็นสัญญาณ EEG จริงและการกระจาย sleep stage
- `02_sst_representation.ipynb` — เห็น SST tensor จริงที่ป้อนโมเดล
- `03_model_and_protocol.ipynb` — เข้าใจ 3 ขั้นของการฝึกและจุดที่เราปรับให้เข้ากับฮาร์ดแวร์
- `04_results_and_next_steps.ipynb` — อ่านผลจริง confusion matrix ข้อจำกัด และงานถัดไป
- `05_embedding_and_transform_visuals.ipynb` — ดู sliding DFT/SST และ t-SNE จาก embedding จริงของ r19

ทุกเล่มสามารถกด **Run All** ได้อย่างปลอดภัย เพราะไม่มีเซลล์ launch training"""),
            ],
        ),
    )

    write(
        "01_data_and_eeg.ipynb",
        notebook(
            """# 01 — จากคนที่นอนหลับ สู่สัญญาณ EEG และป้ายกำกับ

บทนี้ตอบคำถามพื้นฐาน: ข้อมูลมาจากอะไร, หนึ่งตัวอย่างยาวเท่าไร, และแต่ละ sleep stage มีจำนวนเท่าใด

เราจะแยกสองชุดให้ชัด:

- `data/sleep-edf/` — สำเนา local ขนาด 6 คน/12 records สำหรับเปิดดูเร็ว
- full cohort บนไดรฟ์ E — 78 คน/153 records/194,655 epochs ที่ preprocess และตรวจ parity แล้ว""",
            [
                code(SETUP),
                md("""## 1. จำนวนข้อมูลที่มีจริง

หนึ่ง `epoch` ในงาน sleep staging คือช่วงสัญญาณ 30 วินาที ไม่ใช่ training epoch"""),
                code("""local = local_edf_inventory()
full = full_cohort_summary()

rows = [
    {"scope": "local files for demonstration", "subjects": local["subject_count"], "records": local["psg_files"], "epochs": "read on demand"},
    {"scope": "paper-faithful full cohort", "subjects": full["subjects"], "records": full["recordings"], "epochs": f"{full['epochs']:,}"},
]
print_records(rows, ["scope", "subjects", "records", "epochs"])
print("Local subject IDs:", ", ".join(local["subjects"]))
print("Full-cohort parity matches expected:", full["parity_matches_expected"])
"""),
                md("""## 2. ดูคลื่น Fpz–Cz จริง 30 วินาที

จุดวัด `Fpz–Cz` เป็นช่อง EEG เดียวตามบทความ เซลล์นี้อ่านเฉพาะ 3,000 samples (= 30 วินาที × 100 Hz) จาก EDF หนึ่งไฟล์"""),
                code("""import mne

edf_path = sorted((PROJECT_ROOT / "data" / "sleep-edf").glob("*-PSG.edf"))[0]
raw = mne.io.read_raw_edf(edf_path, preload=False, verbose="ERROR")
sfreq = float(raw.info["sfreq"])
samples = int(30 * sfreq)
signal_uv = raw.get_data(picks=["EEG Fpz-Cz"], start=0, stop=samples)[0] * 1e6
time_s = np.arange(samples) / sfreq

fig, axes = plt.subplots(2, 1, figsize=(11, 6))
axes[0].plot(time_s, signal_uv, lw=0.7, color="#264653")
axes[0].set(title=f"Actual Fpz-Cz EEG: {edf_path.name}", xlabel="Time (s)", ylabel="Amplitude (µV)")

window = np.hanning(len(signal_uv))
freq = np.fft.rfftfreq(len(signal_uv), d=1/sfreq)
power = np.abs(np.fft.rfft((signal_uv - signal_uv.mean()) * window)) ** 2
mask = (freq >= 0.5) & (freq <= 30)
axes[1].semilogy(freq[mask], power[mask] + 1e-12, color="#e76f51")
axes[1].set(title="Simple spectrum of the same 30-second epoch", xlabel="Frequency (Hz)", ylabel="Power (a.u.)")
plt.tight_layout()
plt.show()

print(f"Sampling rate: {sfreq:.0f} Hz | points shown: {samples:,} | duration: {samples/sfreq:.0f} s")
"""),
                md("""## 3. การกระจายของ 5 sleep stages ใน full cohort

คลาสไม่ได้มีจำนวนเท่ากัน โดยเฉพาะ N1 และ N3 มีน้อยกว่า W/N2 มาก ความไม่สมดุลนี้เป็นสาเหตุหนึ่งที่ต้องรายงาน **macro-F1** ควบคู่ accuracy"""),
                code("""counts = full["class_counts"]
values = [counts[label] for label in LABELS]

fig, ax = plt.subplots(figsize=(9, 4.5))
bars = ax.bar(LABELS, values, color=["#577590", "#f94144", "#43aa8b", "#277da1", "#f9c74f"])
ax.set(title="Full-cohort class distribution", xlabel="Sleep stage", ylabel="30-second epochs")
ax.bar_label(bars, labels=[f"{value:,}" for value in values], padding=3)
ax.set_ylim(0, max(values) * 1.15)
plt.tight_layout()
plt.show()

print("Label meaning: W=wake, N1=light sleep, N2=stable light sleep, N3=deep sleep, REM=rapid-eye-movement sleep")
"""),
                md("""## 4. สิ่งที่ preprocessing ทำ

1. เลือกช่อง `Fpz-Cz`
2. ใช้ sampling rate 100 Hz
3. แบ่งเป็นช่วงละ 30 วินาที (3,000 samples)
4. รวม stage 3 และ 4 แบบ R&K เป็น N3
5. ตัด movement/unknown และตัดช่วงตื่นไกลจากการนอนตามกติกา 30 นาที
6. บันทึก record, subject, hash และ class counts เพื่อ audit ย้อนกลับได้

บทถัดไปจะนำ epoch เหล่านี้ไปแปลงเป็นภาพเวลา–ความถี่แบบ SST"""),
            ],
        ),
    )

    write(
        "02_sst_representation.ipynb",
        notebook(
            """# 02 — SST: เปลี่ยนคลื่น 1 มิติให้เป็นภาพเวลา–ความถี่

Synchrosqueezed Transform (SST) ช่วยให้โมเดลเห็นว่า “พลังงานความถี่ใดเกิดขึ้นเมื่อไร” ภายใน epoch 30 วินาที

เซลล์ในบทนี้ **อ่าน tensor ที่สร้างจริงจาก cache** ไม่ได้วาดภาพจำลอง และเปิดไฟล์ด้วย memory-map เพื่อไม่ดึง cache ขนาดประมาณ 249 GiB เข้า RAM""",
            [
                code(SETUP),
                md("""## 1. ขนาดของ cache และ route ที่ใช้

Stage 1–2 ใช้ `PAPER_PRETRAIN_V1` (12 windows) ส่วน Stage 3 ใช้ `PAPER_STAGE3_V1` (15 windows)"""),
                code("""cache_manifest = load_json(CACHE_ROOT / "sst_full_cohort_run_manifest.json")
print("Full epochs represented:", f"{cache_manifest['capacity']['epochs']:,}")
print("Declared cache size:", f"{cache_manifest['capacity']['total_gib']:.3f} GiB")
print("Chunk size:", cache_manifest["chunk_epochs"], "epochs")
print("Routes:")
for route, size in cache_manifest["capacity"]["routes"].items():
    print(f"  {route:20s} {pretty_bytes(size)}")
"""),
                md("""## 2. เปิดตัวอย่างจริงหนึ่ง epoch

ค่าช่องสุดท้ายมี 2 channel คือ real และ imaginary component หลัง normalization"""),
                code("""pretrain, pre_meta, pre_path = load_sst_example("PAPER_PRETRAIN_V1")
stage3, stage3_meta, stage3_path = load_sst_example("PAPER_STAGE3_V1")

print("Pretraining sample:", pretrain.shape, pretrain.dtype, "from", pre_path.name)
print("Stage-3 sample     :", stage3.shape, stage3.dtype, "from", stage3_path.name)
print("Only these two single-epoch arrays were copied to RAM.")
"""),
                md("""## 3. ดูภาพ SST จริง

ภาพแต่ละแถวคือ window ต้น กลาง และท้ายของ epoch เดียวกัน คอลัมน์แสดง real, imaginary และ magnitude"""),
                code("""indices = [0, stage3.shape[0] // 2, stage3.shape[0] - 1]
fig, axes = plt.subplots(3, 3, figsize=(10, 9))
for row, index in enumerate(indices):
    real = stage3[index, :, :, 0]
    imag = stage3[index, :, :, 1]
    magnitude = np.sqrt(real**2 + imag**2)
    for col, (image, name) in enumerate(((real, "real"), (imag, "imaginary"), (magnitude, "magnitude"))):
        axes[row, col].imshow(image, origin="lower", aspect="auto", cmap="magma")
        axes[row, col].set_title(f"window {index + 1}: {name}")
        axes[row, col].set(xticks=[], yticks=[])
fig.suptitle("Actual PAPER_STAGE3_V1 SST tensor", y=1.01, fontsize=14, weight="bold")
plt.tight_layout()
plt.show()
"""),
                md("""## 4. ทำไมมี 12 กับ 15 windows

- บทความกำหนด 12 windows สำหรับการเรียนรู้ representation ใน Stage 1–2
- Stage 3 ใช้ sequence 15 windows เพื่อให้ GRU มองความต่อเนื่องตามเวลา
- ค่า overlap ของ Stage 3 ไม่ได้ระบุชัดในข้อความบทความ จึงใช้ 64 ตามโค้ดผู้เขียนและบันทึกว่าเป็น **inference** ไม่ใช่ข้อเท็จจริงจากข้อความ paper"""),
                code("""protocol = paper_protocol()
model = protocol["model"]
rows = [
    {"route": "PAPER_PRETRAIN_V1", "windows": model["pretraining_windows"], "width": model["width"], "overlap": model["overlap"], "provenance": "manuscript text"},
    {"route": "PAPER_STAGE3_V1", "windows": model["stage3_windows"], "width": model["width"], "overlap": model["stage3_overlap"], "provenance": "overlap inferred from author code"},
]
print_records(rows, ["route", "windows", "width", "overlap", "provenance"])

fig, ax = plt.subplots(figsize=(10, 2.5))
for i, row in enumerate(rows):
    count = row["windows"]
    for j in range(count):
        ax.add_patch(plt.Rectangle((j, i - 0.3), 0.8, 0.6, color="#2a9d8f" if i == 0 else "#457b9d", alpha=0.85))
    ax.text(-0.5, i, row["route"], ha="right", va="center")
ax.set_xlim(-5, 16)
ax.set_ylim(-0.8, 1.8)
ax.set_yticks([])
ax.set_xlabel("Ordered windows inside one 30-second epoch")
ax.set_title("Sequence lengths used by the two routes")
plt.tight_layout()
plt.show()
"""),
                md("""**สรุป:** เรามีทั้งข้อมูลเต็มที่ preprocess แล้วและ SST cache เต็มพร้อม hash/provenance การเปิดดูตัวอย่างนี้ไม่ใช่หลักฐานว่าโมเดลให้ผลดี แต่เป็นหลักฐานว่าท่อข้อมูลถึงจุดป้อนโมเดลทำงานและตรวจย้อนกลับได้"""),
            ],
        ),
    )

    write(
        "03_model_and_protocol.ipynb",
        notebook(
            """# 03 — โมเดลเรียนรู้อย่างไร และส่วนใดเหมือน/ต่างจากบทความ

โมเดลหลักมีแนวคิดสามขั้น:

1. **Stage 1 — Classification pretraining:** ให้ CNN เรียนรู้รูปแบบที่สัมพันธ์กับ sleep stage
2. **Stage 2 — Supervised contrastive learning:** ดึง representation ของคลาสเดียวกันให้ใกล้ และคลาสต่างกันให้ออกห่าง
3. **Stage 3 — Sequential classification:** ส่งลำดับ representation เข้า GRU สองชั้นเพื่อใช้บริบทตามเวลา

สมุดนี้อ่าน protocol และ metrics provenance ที่ r19 เขียนไว้จริง ไม่ build หรือ train TensorFlow model""",
            [
                code(SETUP),
                md("## 1. แผนภาพ pipeline"),
                code("""fig, ax = plt.subplots(figsize=(12, 4))
ax.axis("off")
boxes = [
    (0.02, "30-s Fpz-Cz\\nEEG"),
    (0.20, "SST windows\\n12 / 15"),
    (0.39, "CNN encoder\\nStage 1"),
    (0.58, "Contrastive\\nrepresentation\\nStage 2"),
    (0.78, "2-layer GRU\\n+ classifier\\nStage 3"),
]
for x, label in boxes:
    ax.add_patch(plt.Rectangle((x, 0.28), 0.14, 0.44, facecolor="#e9f5f2", edgecolor="#2a9d8f", linewidth=2))
    ax.text(x + 0.07, 0.5, label, ha="center", va="center", fontsize=10, weight="bold")
for (x1, _), (x2, _) in zip(boxes[:-1], boxes[1:]):
    ax.annotate("", xy=(x2, 0.5), xytext=(x1 + 0.14, 0.5), arrowprops=dict(arrowstyle="->", lw=2, color="#264653"))
ax.set_title("Paper-faithful learning pipeline", fontsize=15, pad=12)
plt.show()
"""),
                md("""## 2. Hyperparameters ที่ถูกบันทึกในผล r19

คอลัมน์ `paper_exact` บอกความตรงกับ protocol ในระดับ stage ไม่ได้แปลว่าผลรวมทั้ง run เป็น full reproduction"""),
                code("""specs = r19_stage_specs()
rows = []
for spec in specs:
    rows.append({
        "stage": spec["stage"],
        "epochs": spec["epochs"],
        "optimizer": spec["optimizer"],
        "learning_rate": spec["learning_rate"],
        "microbatch": spec["microbatch"],
        "effective_batch": spec["effective_batch"],
        "paper_exact": spec["paper_exact"],
    })
print_records(rows, ["stage", "epochs", "optimizer", "learning_rate", "microbatch", "effective_batch", "paper_exact"])
"""),
                md("""## 3. จุดดัดแปลงเพื่อให้รันบนเครื่องนี้ได้

Stage 3 ต้องการ batch 128 แต่ GPU/RAM ของเครื่องไม่พอเก็บทั้งหมดพร้อมกัน เราจึงใช้:

- microbatch = 1
- สะสม gradient 128 ครั้ง
- หารเฉลี่ยให้เทียบเท่า effective batch 128
- clip global norm ที่ 1.0 **หลังการเฉลี่ย** และก่อน optimizer step

วิธีนี้รักษาขนาด effective batch แต่เป็น numerical/hardware adaptation จึงต้องติดป้ายว่า `paper_exact = false`"""),
                code("""stage3 = next(spec for spec in specs if spec["stage"] == "stage3")
adaptation = {
    "adaptation_id": stage3["stage3_stability_adaptation_id"],
    "microbatch": stage3["microbatch"],
    "accumulation_steps": stage3["gradient_accumulation_steps"],
    "effective_batch": stage3["effective_batch"],
    "clip_norm": stage3["gradient_clip_norm"],
    "clip_when": stage3["gradient_clip_application"],
    "paper_exact": stage3["paper_exact"],
}
print_records([adaptation])
"""),
                md("""## 4. สิ่งที่ “เหมือนบทความ” กับสิ่งที่ยังไม่ควรกล่าวอ้าง

| ระดับ | สิ่งที่กล่าวได้ |
|---|---|
| Protocol | ใช้ dataset/channel/labels/3-stage design ตามข้อความบทความและแยก inference ไว้ |
| Data | full cohort preprocess และ class-count parity ผ่าน |
| Representation | SST cache เต็มถูกสร้างพร้อม hash และ route แยกชัด |
| Training pilot | r19 สอง seed จบครบ Stage 1–3 ภายใต้ cap128 |
| ยังกล่าวไม่ได้ | “ทำซ้ำ accuracy 83% สำเร็จ” หรือ “generalize ไปคนใหม่แล้ว” |

เหตุผลสำคัญคือ r19 จำกัดข้อมูลต่อ split เหลือ 128 epochs และ subject-held-out pilot ยังถูก block ก่อน training"""),
            ],
        ),
    )

    write(
        "04_results_and_next_steps.ipynb",
        notebook(
            """# 04 — ผลที่รันจริง ปัญหาที่เห็น และขั้นถัดไป

บทนี้ไม่เลือกเฉพาะ run ที่ดูดี แต่ค้นทุก run ใน bulk artifact directory แล้วอ่าน `execution.json` และ metrics ที่มีอยู่จริง

หลักการอ่านผล:

- Accuracy ตอบว่าเดาถูกกี่ตัวอย่างโดยรวม
- Macro-F1 ให้น้ำหนักแต่ละคลาสเท่ากัน จึงเปิดโปงปัญหาคลาสเล็กได้ดีกว่า
- Confusion matrix บอกว่าโมเดลสับสนคลาสใดกับคลาสใด
- ผล cap128 มีประโยชน์เป็น integration/pilot evidence แต่ยังไม่ใช่คำตอบสุดท้ายทางวิจัย""",
            [
                code(SETUP),
                md("## 1. Inventory ของ run ที่มี Stage 3 metrics"),
                code("""runs = discover_runs()
visible = []
for row in runs:
    visible.append({
        "revision": row["revision"],
        "seed": row["model_seed"],
        "status": row["status"],
        "cap": row["cap"],
        "accuracy": "—" if row["stage3_accuracy"] is None else f"{row['stage3_accuracy']:.3f}",
        "macro_f1": "—" if row["stage3_macro_f1"] is None else f"{row['stage3_macro_f1']:.3f}",
        "run_id": row["run_id"],
    })
print_records(visible, ["revision", "seed", "status", "cap", "accuracy", "macro_f1", "run_id"])
"""),
                md("""## 2. เปรียบเทียบผล Stage 3 ที่มีจริง

เส้น 83% แสดงตำแหน่งตัวเลขที่บทความรายงานเพื่อให้เห็นเป้าหมายเท่านั้น **แท่ง pilot เหล่านี้ห้ามใช้เป็น direct replication comparison** เพราะ cap และ execution conditions ต่างกัน"""),
                code("""completed = [row for row in runs if row["stage3_accuracy"] is not None]
labels = [f"{row['revision']}\\nseed {row['model_seed']}" for row in completed]
accuracy = [row["stage3_accuracy"] for row in completed]
macro_f1 = [row["stage3_macro_f1"] for row in completed]
x = np.arange(len(completed))

fig, ax = plt.subplots(figsize=(11, 5))
width = 0.36
ax.bar(x - width/2, accuracy, width, label="Accuracy", color="#457b9d")
ax.bar(x + width/2, macro_f1, width, label="Macro-F1", color="#e9c46a")
ax.axhline(0.83, color="#d62828", linestyle="--", label="Paper-reported accuracy (reference only)")
ax.set(xticks=x, xticklabels=labels, ylim=(0, 1), ylabel="Score", title="Existing Stage-3 test metrics")
ax.legend(loc="upper left", ncols=2)
plt.tight_layout()
plt.show()
"""),
                md("""## 3. เจาะ r19 สอง seed

r19 ทั้งสอง run จบครบ แต่ผลต่างกันและ macro-F1 ต่ำ แปลว่า pipeline ทำงานได้แต่โมเดลยังไม่จำแนกครบทุกคลาสใน pilot ขนาดเล็ก"""),
                code("""latest = r19_runs()
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, row in zip(axes, latest):
    metrics = stage_metrics(row["path"], "stage3")
    plot_confusion_matrix(metrics["confusion_matrix"], f"r19 seed {row['model_seed']} | acc={metrics['accuracy']:.3f}", ax=ax)
plt.tight_layout()
plt.show()

per_class = {label: [] for label in LABELS}
for row in latest:
    metrics = stage_metrics(row["path"], "stage3")
    for label in LABELS:
        per_class[label].append(metrics["per_class_f1"][label])

fig, ax = plt.subplots(figsize=(9, 4.5))
x = np.arange(len(LABELS))
for i, row in enumerate(latest):
    ax.bar(x + (i - 0.5) * 0.35, [per_class[label][i] for label in LABELS], 0.35, label=f"seed {row['model_seed']}")
ax.set(xticks=x, xticklabels=LABELS, ylim=(0, 1), ylabel="F1", title="r19 per-class F1")
ax.legend()
plt.tight_layout()
plt.show()
"""),
                md("""## 4. เหตุใด subject-generalization ยังไม่เริ่ม

เราเตรียม protocol 6 folds, test/review และ canonical gate แล้ว แต่ gate รอบล่าสุดตรวจพบ RAM ว่างต่ำกว่าเกณฑ์ 4,096 MB จึงปฏิเสธก่อนสร้าง production marker และก่อนเริ่ม training นี่เป็น failure แบบปลอดภัย ไม่ใช่ผลล้มเหลวของโมเดล"""),
                code("""gate = subject_gate_summary()
print_records([gate])

fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(["Available", "Required"], [gate["available_memory_mb"], gate["required_memory_mb"]], color=["#e76f51", "#2a9d8f"])
ax.bar_label(bars, fmt="%.1f MB", padding=3)
ax.set(title="Memory gate at the last subject-generalization attempt", ylabel="Physical memory (MB)")
ax.set_ylim(0, gate["required_memory_mb"] * 1.25)
plt.tight_layout()
plt.show()
"""),
                md("""## 5. แผนที่ควรทำต่อ

1. **รัน resource gate ใหม่เมื่อ RAM ว่างเพียงพอ** โดยใช้ fresh versioned run; ห้ามเปลี่ยนสถานะของหลักฐานเก่า
2. **ทำ subject-held-out pilot 6 folds** เพื่อวัดว่าทำนายคนที่ไม่เคยเห็นได้หรือไม่
3. **ตรวจแต่ละ fold แบบ standalone** แล้วรวมค่าเฉลี่ย/ส่วนเบี่ยงเบนพร้อม per-class F1
4. หาก pilot มีปัญหา ให้แยกว่าเกิดจาก data split, class imbalance, representation หรือ capacity ก่อนแก้
5. เมื่อ protocol และทรัพยากรนิ่ง จึงวางแผน **full numerical reproduction** ที่ไม่จำกัด cap128
6. รายงานสองคำถามแยกกัน: (ก) ทำซ้ำ protocol บทความได้แค่ไหน และ (ข) generalize ไปคนใหม่ได้แค่ไหน

### สถานะสั้นที่สุด

**ทำจริงมาแล้วมากกว่าตัวอย่างสาธิต:** full preprocessing + full SST cache + r19 สอง seed จบครบ แต่ผล cap128 ยังต่ำและ subject-held-out ยังไม่เริ่ม ดังนั้นโครงการ “เดินท่อครบแล้ว” แต่ยัง “ตอบคำถามวิจัยสุดท้ายไม่ครบ”"""),
            ],
        ),
    )

    write(
        "05_embedding_and_transform_visuals.ipynb",
        notebook(
            """# 05 — Visualization แบบในบทเรียน: sliding DFT/SST และ t-SNE embedding

บทนี้เพิ่มภาพสองชนิดตามตัวอย่างที่ต้องการ:

1. ภาพอธิบายว่าเรานำหน้าต่างเลื่อนไปบน EEG แล้วคำนวณ spectrum อย่างไร ก่อนเปรียบเทียบกับ SST จริง
2. t-SNE ของ **Stage-2 embeddings ที่อนุมานจาก checkpoint r19 จริง** สำหรับ seed 42 และ 43

ไฟล์ embedding ถูกสร้างด้วย CPU-only post-hoc inference จาก test split เดิม ไม่มีการฝึกต่อ ไม่มี optimizer step และไม่แก้ canonical run artifacts""",
            [
                code(SETUP),
                md("""## 1. จาก sliding DFT ไปสู่ SST

ด้านซ้ายใช้ EEG จริงจาก `SC4001E0-PSG.edf` เพื่อสาธิต windowing และ STFT/DFT ส่วนด้านขวาอ่าน SST tensor ที่สร้างจริงจาก cache รูปนี้จึงช่วยอธิบายแนวคิด แต่ไม่ได้กล่าวว่า STFT ด้านซ้ายเท่ากับ SST ด้านขวา"""),
                code("""import mne
from scipy import signal as scipy_signal

figures_dir = PROJECT_ROOT / "walkthrough" / "figures"
figures_dir.mkdir(parents=True, exist_ok=True)

edf_path = sorted((PROJECT_ROOT / "data" / "sleep-edf").glob("*-PSG.edf"))[0]
raw = mne.io.read_raw_edf(edf_path, preload=False, verbose="ERROR")
sfreq = float(raw.info["sfreq"])
eeg = raw.get_data(picks=["EEG Fpz-Cz"], start=0, stop=int(30 * sfreq))[0] * 1e6
time_s = np.arange(eeg.size) / sfreq

window_seconds = 2.56
window_samples = int(window_seconds * sfreq)
starts = [0, int(8 * sfreq), int(16 * sfreq)]
colors = ["#d000ff", "#00a6fb", "#f59e0b"]

fig = plt.figure(figsize=(14, 9), constrained_layout=True)
grid = fig.add_gridspec(3, 4, width_ratios=[1, 1, 1, 1.35])
ax_signal = fig.add_subplot(grid[0, :3])
ax_signal.plot(time_s, eeg, color="#264653", lw=0.7)
for start, color in zip(starts, colors):
    ax_signal.axvspan(start / sfreq, (start + window_samples) / sfreq, color=color, alpha=0.22)
ax_signal.set(title="Actual 30-second Fpz-Cz EEG with sliding analysis windows", xlabel="Time (s)", ylabel="Amplitude (µV)")

for column, (start, color) in enumerate(zip(starts, colors)):
    ax = fig.add_subplot(grid[1, column])
    segment = eeg[start : start + window_samples]
    local_time = np.arange(segment.size) / sfreq
    ax.plot(local_time, segment * np.hanning(segment.size), color=color, lw=0.9)
    ax.set(title=f"Window at {start/sfreq:.0f} s", xlabel="Local time (s)")
    if column == 0:
        ax.set_ylabel("Windowed EEG")

freq, times, zxx = scipy_signal.stft(eeg, fs=sfreq, window="hann", nperseg=256, noverlap=64, boundary=None)
mask = (freq >= 0.5) & (freq <= 30)
ax_stft = fig.add_subplot(grid[2, :3])
mesh = ax_stft.pcolormesh(times, freq[mask], 20 * np.log10(np.abs(zxx[mask]) + 1e-9), shading="auto", cmap="viridis")
ax_stft.set(title="Concatenated DFT columns (STFT explanation)", xlabel="Time (s)", ylabel="Frequency (Hz)")
fig.colorbar(mesh, ax=ax_stft, label="Magnitude (dB)")

stage3, _, _ = load_sst_example("PAPER_STAGE3_V1")
sst_magnitude = np.sqrt(stage3[:, :, :, 0] ** 2 + stage3[:, :, :, 1] ** 2).mean(axis=0)
ax_sst = fig.add_subplot(grid[:, 3])
image = ax_sst.imshow(sst_magnitude, origin="lower", aspect="auto", cmap="magma")
ax_sst.set(title="Actual cached SST\\n(mean magnitude across 15 windows)", xlabel="Time-frequency column", ylabel="Frequency bin")
fig.colorbar(image, ax=ax_sst, label="Normalized magnitude")

fig.suptitle("How a 1-D EEG epoch becomes a time-frequency representation", fontsize=16, weight="bold")
figure_path = figures_dir / "01_sliding_dft_and_actual_sst.png"
fig.savefig(figure_path, dpi=170, bbox_inches="tight")
plt.show()
print("Saved:", figure_path)
"""),
                md("""## 2. ตรวจ provenance ของ embedding

แต่ละไฟล์ต้องผูกกับ completed r19 run, test split hash และ Stage-2 checkpoint hash ก่อนนำไปวาด"""),
                code("""import hashlib

artifacts_dir = PROJECT_ROOT / "walkthrough" / "artifacts"
embedding_files = sorted(artifacts_dir.glob("r19_seed*_stage2_test_embeddings.npz"))
assert len(embedding_files) == 2, "ต้องมี embedding artifacts ของ r19 สอง seed"

provenance_rows = []
for path in embedding_files:
    provenance = load_json(path.with_suffix(".json"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == provenance["output_npz_sha256"]
    assert provenance["training_performed"] is False
    provenance_rows.append({
        "run_id": provenance["run_id"],
        "seed": provenance["model_seed"],
        "split": provenance["split"],
        "points": provenance["embedding_count"],
        "dimensions": provenance["embedding_dimensions"],
        "training": provenance["training_performed"],
    })
print_records(provenance_rows, ["seed", "split", "points", "dimensions", "training", "run_id"])
"""),
                md("""## 3. ลด 256 มิติเป็น 2 มิติด้วย t-SNE

ก่อน t-SNE เราทำ L2 normalization แบบเดียวกับ geometry ที่ contrastive loss ใช้ แล้วลดด้วย PCA เหลือ 50 มิติเพื่อให้เสถียรขึ้น สีคือ sleep stage จริงของแต่ละ window

> t-SNE ใช้ดูรูปทรงและการทับซ้อนของกลุ่มเท่านั้น ระยะและขนาดกลุ่มบนภาพไม่ใช่ accuracy และไม่ควรใช้แทนการประเมินบน test set"""),
                code("""from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import normalize

palette = {"W": "#7ad151", "N1": "#6c5ce7", "N2": "#3da5d9", "N3": "#4ee6a8", "REM": "#d6ff4b"}
fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharex=False, sharey=False)

for ax, path in zip(axes, embedding_files):
    artifact = np.load(path)
    embeddings = artifact["embeddings"].astype(np.float64)
    labels = artifact["labels"].astype(int)
    model_seed = int(artifact["model_seed"])
    unit = normalize(embeddings, norm="l2")
    reduced = PCA(n_components=50, random_state=42).fit_transform(unit)
    points = TSNE(
        n_components=2,
        perplexity=30,
        init="pca",
        learning_rate="auto",
        max_iter=1000,
        random_state=42,
    ).fit_transform(reduced)
    for class_index, label_name in enumerate(LABELS):
        selected = labels == class_index
        ax.scatter(points[selected, 0], points[selected, 1], s=7, alpha=0.65, c=palette[label_name], label=label_name, linewidths=0)
    ax.set(title=f"r19 Stage-2 embeddings — seed {model_seed}", xlabel="t-SNE component 1", ylabel="t-SNE component 2")

handles, legend_labels = axes[-1].get_legend_handles_labels()
fig.legend(handles, legend_labels, loc="center right", title="Sleep stage", markerscale=2)
fig.suptitle("Post-hoc t-SNE of actual r19 test embeddings", fontsize=16, weight="bold")
fig.tight_layout(rect=(0, 0, 0.93, 0.95))
tsne_path = figures_dir / "02_r19_stage2_tsne.png"
fig.savefig(tsne_path, dpi=180, bbox_inches="tight")
plt.show()
print("Saved:", tsne_path)
"""),
                md("""## 4. อ่านภาพอย่างไร

- ถ้าสีแต่ละสีแยกเป็นเกาะชัด representation จะมีโครงสร้างที่แยกคลาสได้ง่ายกว่า
- ถ้าสีทับกันมาก แสดงว่า Stage-2 embedding ยังแยก sleep stages ได้ไม่ดีใน pilot นี้
- ค่า silhouette test ของ r19 เป็นลบทั้งสอง seed (`-0.0818` และ `-0.0938`) ซึ่งสอดคล้องกับการทับซ้อนที่เห็น
- นี่เป็น **cap128 epoch-random pilot** ไม่ใช่ full-cohort result และไม่ใช่ subject-held-out result

ดังนั้นกราฟนี้ตอบว่า “representation ของ pilot มีรูปร่างอย่างไร” ไม่ได้ตอบว่า “โมเดลทำซ้ำ 83% สำเร็จหรือยัง”"""),
            ],
        ),
    )


if __name__ == "__main__":
    build()
    print(f"Generated notebooks in {NOTEBOOKS}")

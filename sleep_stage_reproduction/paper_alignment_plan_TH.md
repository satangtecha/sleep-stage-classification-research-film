# Lean-team plan: ทำ Sleep-stage reproduction ให้ใกล้ paper มากที่สุด

วันที่วางแผน: 19 สิงหาคม 2026  
สถานะ: `Phase 0 complete / Phase 1 Stage-1 gate passed` — ผู้ใช้อนุมัติด้วยคำว่า `proceed`; ยังไม่เริ่ม full dataset หรือ training

## 1. เป้าหมายที่วัดผลได้

สร้าง pipeline สามขั้นที่ใช้ Sleep-EDF Sleep Cassette, EEG Fpz-Cz, SST, CNN pretraining, supervised contrastive learning และ CNN-GRU ตาม paper/author artifact ให้ครบ พร้อมผลที่ตรวจย้อนกลับได้ และแยกผลออกเป็นสาม protocol อย่างชัดเจน:

1. `PAPER_TEXT_V1` — ตามรายละเอียดที่เขียนใน manuscript
2. `AUTHOR_CODE_V1` — ตาม Zenodo/GitHub release `v1.0`
3. `SUBJECT_GENERALIZATION_V1` — architecture เดียวกัน แต่ประเมินแบบ subject-wise เพื่อวัดการใช้กับคนใหม่อย่างถูกต้อง

การแยกสาม protocol จำเป็นเพราะ manuscript กับ source release ขัดกัน และ headline accuracy 83% มาจาก epoch-level split ซึ่งเปรียบเทียบตรงกับ subject-wise result ปัจจุบันไม่ได้

## 2. หลักฐานที่ล็อกไว้

- [Scientific Reports article](https://www.nature.com/articles/s41598-026-62832-5) — Fpz-Cz, 30 วินาที/3,000 samples, SST, CNN, contrastive learning, stacked GRU และรายงาน accuracy 83%
- [Accepted manuscript PDF](https://www.nature.com/articles/s41598-026-62832-5_reference.pdf) — 153 recordings จาก 78 subjects, 194,655 epochs, epoch-level 80/10/10 split seed 42, Stage 1/2/3 และ metrics
- [PhysioNet Sleep-EDF Expanded](https://physionet.org/content/sleep-edfx/1.0.0/) — dataset ทั้งหมด 8.1 GB; Sleep Cassette มี 153 recordings และ Fpz-Cz ที่ 100 Hz
- [Zenodo/DataCite record](https://api.datacite.org/dois/10.5281/zenodo.21302907) — ชี้ไปยัง author repository release `v1.0`
- [Author code v1.0](https://github.com/SadafAram/Sleep-Stage-Classification/tree/v1.0) — source ที่ใช้ตรวจ SST, windowing, model และ notebooks

## 3. ข้อจำกัดสำคัญ: ยังทำ exact replication 100% ไม่ได้

หลักฐานปัจจุบันไม่พอสำหรับคำว่า exact replication เพราะ:

- manuscript ระบุ 12 windows/epoch และ overlap 7 samples แต่ downstream code ใช้ 15 windows และ overlap 64
- Stage 3 ใน manuscript ระบุ 20 epochs แต่ notebook ใช้ 50 epochs
- Stage 1 code แบ่ง windows หลัง segmentation ขณะที่ downstream notebook แบ่ง epochs ก่อน ทำให้มี protocol split มากกว่าหนึ่งแบบ
- ไม่มี split-index files, checkpoints, training history หรือ hash ของโมเดลที่สร้าง Table 2
- `ssqueezepy` ไม่ pin version; ค่า default ของ SST จึงอาจต่างกันตาม version
- ลำดับ `os.listdir()` มีผลต่อ split แม้กำหนด seed 42

ดังนั้นสถานะที่ทำได้คือ:

- **Code-faithful reproduction:** ทำได้หลัง pin assumptions และซ่อม entry point
- **Paper-described reproduction:** ทำได้ในรูป sensitivity run โดยต้องบันทึก assumptions
- **Exact numerical replication:** blocked จนกว่าผู้เขียนให้ exact commit, split indices, `ssqueezepy` version/kwargs และ checkpoint hashes

## 4. Gap matrix: ปัจจุบันเทียบกับเป้าหมาย

| ส่วน | งานปัจจุบัน | Paper / author code | งานที่เหลือ |
|---|---|---|---|
| Dataset | 6 subjects, 12 records, 1,732 epochs | 78 subjects, 153 SC records, 194,655 epochs | ดาวน์โหลด SC cohort ครบและสร้าง checksum manifest |
| Wake trimming | จำกัดจำนวน epoch ต่อ record | เก็บ wake ก่อน/หลัง sleep ±30 นาที | ทำ preprocessing ให้ class counts ตรง Table 1 |
| Split | strict subject-wise; test SC402 | paper: epoch-level 80/10/10 seed 42 | สร้าง protocol manifests แยก paper/code/subject-wise |
| Windowing | 12 ช่วง ขนาด 256 และ pad | manuscript: 12/overlap 7; code downstream: 15/overlap 64 | implement ทั้งสองแบบและมี unit test start/end indices |
| SST | SciPy STFT reassignment แบบย่อ | `ssqueezepy.ssq_stft`, `n_fft=512`, real/imag, min-max ต่อ channel | pin version, สร้าง 256×256×2 regression fixture |
| CNN | 3 Conv blocks, embedding 32 | 6 blocks 16→512, AvgPool, BN, Dense 256→64, dropout .3 | implement architecture และตรวจ parameter count |
| Contrastive | self-supervised augmentation, symmetric loss | supervised contrastive, Dense 256, temperature .05, N-pairs | implement loss ตาม author source และเก็บ Stage-2 metrics |
| Sequence model | GRU 64×2, final state | GRU 256→128 + flattened encoder skip Dense 128 | implement time-distributed encoder, skip path และ freeze policy |
| Training | 2/1/5 epochs, AdamW 1e-3 | Stage 1 AdamW .05/20; Stage 2 SGD .1/20; Stage 3 SGD .1/20 paper หรือ 50 code | stage-specific runners, scheduler .2/1/min_lr .0001 |
| Metrics | accuracy, macro-F1, kappa, stage F1 | accuracy, macro/weighted P/R/F1, confusion matrix; Stage-2 silhouette | เพิ่ม metric schema และ provenance manifest |
| Evaluation | 3 model seeds บน test subject เดียว | headline 83% บน epoch split | รัน paper protocol และ subject-wise protocol แยกผล |

## 5. แผนดำเนินงานหลังได้รับ `proceed`

### Phase 0 — Protocol lock และ provenance

Owner: main agent + read-only explorer  
เวลาโดยประมาณ: 2–4 ชั่วโมง; ไม่มี training

งาน:

- archive/record exact author release tag `v1.0`, commit SHA และ file hashes
- สร้าง `protocol_manifest.paper_text.json`, `protocol_manifest.author_code_v1.json`, `protocol_manifest.subjectwise.json`
- บันทึกทุกความขัดแย้งเป็น decision log; ห้ามแก้ assumption แบบเงียบ ๆ
- เตรียมคำถามส่งผู้เขียน: exact Table-2 commit, split indices, SST version/kwargs, checkpoint hashes

Gate ผ่านเมื่อ:

- ทุก parameter ถูกระบุเป็น `source`, `assumption` หรือ `unknown`
- protocol ทั้งสามมี ID และห้ามผลลัพธ์คนละ ID รวมในตารางเดียวโดยไม่ระบุ

Stop condition: ถ้า source tag หรือ checksum เปลี่ยน ให้หยุดและ lock revision ใหม่

### Phase 1 — Environment และ hardware gate

Owner: implementer A; write scope เฉพาะ environment/lock files  
เวลา: 3–6 ชั่วโมง

งาน:

- สร้าง isolated reference environment สำหรับ TensorFlow/Keras author code
- pin Python, TensorFlow, TensorFlow Addons, NumPy, MNE และทดลอง `ssqueezepy` candidate versions
- ทดสอบ CUDA, deterministic seed และ one-batch forward/backward
- เก็บ `environment_manifest.json`, package lock และ `nvidia-smi`

Hardware ปัจจุบัน: i5-13420H, RAM 16 GB, RTX 3050 6 GB แต่ venv ปัจจุบันเป็น PyTorch CPU-only. เครื่องนี้เหมาะกับ preprocessing/pilot; full batch 128 ของ model 6-block อาจเกิน VRAM

Gate ผ่านเมื่อ:

- one-batch Stage 1/2/3 รันบน GPU และ rerun ด้วย seed เดิมให้ผล deterministic ภายใน tolerance
- ถ้า batch 128 OOM ต้องเลือก GPU ≥16 GB หรือบันทึก deviation; ห้ามใช้ gradient accumulation แล้วเรียกว่า exact batch เพราะ BatchNorm behavior ต่างกัน

### Phase 2 — Full Sleep-Cassette data parity

Owner: implementer A; files `paper_faithful/data/` และ manifests เท่านั้น  
เวลา: ดาวน์โหลด 2–8 ชั่วโมงตาม bandwidth; preprocess/QA 4–12 ชั่วโมง CPU

งาน:

- ดาวน์โหลด SC records ครบ 153 PSG + hypnogram พร้อม SHA-256
- Fpz-Cz 100 Hz, epoch 30 วินาที, map W/N1/N2/N3/REM, merge S3/S4, ตัด MOVEMENT/UNKNOWN
- ทำ wake trimming ±30 นาทีรอบ sleep period
- สร้าง deterministic record order ก่อน split

Gate ผ่านเมื่อ:

- 153 recordings / 78 subjects
- 194,655 epochs และ class counts W/N1/N2/N3/REM = 65,795 / 21,469 / 68,633 / 12,991 / 25,767
- ไม่มี checksum mismatch และไม่มี subject/record ที่หายโดยไม่ระบุ

Stop condition: ถ้า epoch/class counts ไม่ตรง Table 1 ให้หยุดก่อนสร้าง SST หรือ training

### Phase 3 — SST และ windowing parity

Owner: implementer A; one writer  
เวลา: engineering 4–8 ชั่วโมง; full transform 6–24 ชั่วโมงขึ้นกับ caching

งาน:

- ใช้ `ssq_stft(signal, n_fft=512)`; real/imag 256 bins; min-max แยก channel; resize 64×64 ใน model
- ทำ unit tests สำหรับ:
  - manuscript route: 12 windows, overlap 7
  - author route: 15 windows, width 256, overlap 64, starts 0..2688, ทิ้งท้าย 56 samples
- pin `ssqueezepy` version จาก regression comparison; ถ้ายืนยันไม่ได้ให้รัน candidate sensitivity

Storage gate:

- full float32 TFR cache ประมาณ 76 GB ซึ่งเกินพื้นที่ว่างที่ปลอดภัยของเครื่องนี้
- ใช้ sharded float16 cache, compressed cache หรือ streaming + embedding cache; รักษาพื้นที่ว่างอย่างน้อย 15 GB

Gate ผ่านเมื่อ:

- fixture เดิมให้ shape, min/max และ checksum คงที่
- ไม่มี train/validation/test leakage จาก epoch-derived windows ใน `PAPER_TEXT_V1` และ `SUBJECT_GENERALIZATION_V1`

### Phase 4 — Stage 1 CNN parity

Owner: implementer B; เริ่มหลัง Phase 3 ผ่าน  
เวลา: pilot 2–6 ชั่วโมง; full 20 epochs ประมาณ 12–48 GPU-hours บน GPU ที่เหมาะสม

งาน:

- 6 Conv2D blocks: 16/32/64/128/256/512, kernel 3×3, ReLU, AveragePool 2×2, BatchNorm
- Dense 256 → dropout .3 → Dense 64 → softmax 5 classes
- AdamW lr .05, categorical CE, batch 128, 20 epochs, ReduceLROnPlateau factor .2/patience 1/min_lr .0001

Gate ผ่านเมื่อ:

- architecture/parameter report ตรง author model
- Stage-1 test accuracy ใกล้ 0.69 และ macro-F1 ใกล้ 0.68; หากต่างเกิน 0.03 ให้หยุดตรวจ SST/split ก่อน Stage 2

### Phase 5 — Stage 2 supervised contrastive parity

Owner: implementer B  
เวลา: 8–36 GPU-hours สำหรับ 20 epochs

งาน:

- encoder cut-point `layers[20]`, Dense projection 256
- supervised contrastive/N-pairs loss, temperature .05
- SGD lr .1, batch 128, 20 epochs, scheduler เดียวกัน
- บันทึก contrastive loss, silhouette score และ embedding diagnostics ใน result artifact

Gate ผ่านเมื่อ:

- silhouette score เปลี่ยนจากประมาณ −0.02 ไปทาง 0.05 ตามรายงาน หรือมี root-cause report ก่อน Stage 3

### Phase 6 — Stage 3 CNN-GRU parity

Owner: implementer B  
เวลา: 4–24 GPU-hours ต่อ protocol

งาน:

- frozen time-distributed encoder
- GRU 256 return sequences → GRU 128
- flattened encoder skip → Dense 128; concatenate; dropout .3; Dense 128→64→5
- รันทั้ง `PAPER_TEXT_V1` (12 windows, 20 epochs) และ `AUTHOR_CODE_V1` (15 windows, 50 epochs)

Gate ผ่านเมื่อ:

- ทุก run เก็บ full config, seed, split membership, class counts, environment hash, checkpoint hash, history และ confusion matrix
- ไม่ overwrite checkpoints ระหว่าง protocol

### Phase 7 — Numerical comparison กับ paper

Owner: main agent; reviewer read-only  
เวลา: 2–4 ชั่วโมงหลัง runs เสร็จ

Paper targets:

- accuracy 0.83
- macro precision/recall/F1 = 0.78 / 0.75 / 0.76
- weighted precision/recall/F1 = 0.82 / 0.83 / 0.82
- F1 W/N1/N2/N3/REM = 0.94 / 0.42 / 0.85 / 0.76 / 0.80
- final model 3,340,885 parameters, 1,764,229 trainable, 0.75 GFLOPs

ระดับคำสรุป:

- `pipeline reproduced` เมื่อ full pipeline ผ่านครบและ artifact ตรวจย้อนกลับได้
- `numerically close` เมื่อ accuracy อยู่ 0.81–0.85 และ macro/weighted F1 ต่างไม่เกิน 0.03 ภายใต้ protocol ID เดียวกัน
- `exact replication` ใช้ได้เฉพาะเมื่อผู้เขียนให้ split/checkpoints/SST version และผลผูกกับ artifacts เหล่านั้นได้

### Phase 8 — Subject-wise scientific validation

Owner: implementer A สำหรับ split runner; main agentวิเคราะห์  
เวลา: 6-fold pilot 1–3 วันบน GPU; full LOSO หลาย seeds อาจใช้หลายสัปดาห์

งาน:

- ใช้ architecture ที่ล็อกจาก Phase 6
- GroupKFold/LOSO ตาม subject; ไม่มี subject overlap
- เริ่ม 6-subject LOSO เพื่อ smoke test แล้วขยายเป็น predetermined folds/full cohort
- รายงาน mean ± SD, confidence interval, per-stage metrics และ fold failures

ข้อห้าม: ผล Phase 8 ห้ามนำไปเทียบ 83% โดยตรง เพราะ evaluation protocol ต่างกัน

### Phase 9 — Ablation และ final report

Owner: main agent + reviewer  
เวลา: 1–3 วัน ขึ้นกับจำนวน runs

รันด้วย split/seeds/budget เดียวกัน:

1. raw CNN
2. SST-CNN
3. SST-CNN + supervised contrastive
4. SST-CNN + supervised contrastive + GRU

Gate ผ่านเมื่อ reviewer ยืนยันว่าแต่ละ ablation เปลี่ยนเพียงองค์ประกอบที่ตั้งใจ และไม่มี data leakage/provenance gap

## 6. Lean-team ownership หลัง `proceed`

| Role | Ownership | Concurrency |
|---|---|---:|
| Main agent | requirements, protocol decisions, integration, user updates, final claims | ตลอดงาน |
| Implementer A | environment, data manifest, preprocessing, SST/windowing, split runner | 1 writer |
| Implementer B | Stage 1/2/3 model and training files หลัง data contract freeze | 1 writer |
| Reviewer | read-only review หลังแต่ละ major phase | เรียกเมื่อมี integrated artifact |

เริ่มพร้อมกันไม่เกิน 2 workers และไม่ให้ writers สองคนแก้ไฟล์ชุดเดียวกัน

## 7. เวลาโดยรวมที่คาด

| ระดับ | เวลาโดยประมาณ |
|---|---:|
| Paper-faithful pilot บน 6 subjects | 1–2 วัน |
| Full preprocessing + Stage 1/2/3 บน GPU ≥16 GB | 3–10 วัน รวม machine time |
| ใช้ RTX 3050 6 GB โดยลด batch/ใช้ local cache | ประมาณ 1–3 สัปดาห์ และไม่ถือว่า batch-faithful |
| Subject-wise multi-fold validation | เพิ่ม 3 วันถึงหลายสัปดาห์ตาม folds/seeds |

ตัวเลขนี้เป็น planning range; หลัง Phase 1 one-batch benchmark จะปรับ ETA จาก throughput จริง

## 8. Approval gate

ผู้ใช้ตอบ `proceed` แล้ว จึงดำเนินการเฉพาะ **Phase 0 → Phase 1**: source/protocol lock ผ่าน และ Stage-1 GPU forward/backward smoke test ผ่าน รายละเอียดอยู่ใน `phase_0_1_report_TH.md` โดยยังไม่ดาวน์โหลด full dataset หรือเริ่ม full training จนกว่าจะอนุมัติ gate ถัดไป

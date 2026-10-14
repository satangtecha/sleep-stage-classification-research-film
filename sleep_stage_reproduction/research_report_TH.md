# Sleep-stage classification ด้วย EEG: รายงานการสำรวจและ reproduction

วันที่ตรวจสอบ: 19 สิงหาคม 2026

## สรุปผล

งานที่ใหม่ที่สุดที่พบและตรงกับโจทย์ EEG โดยตรงคือ **“Single-channel EEG sleep stage classification using synchrosqueezed transform and sequential representation learning”** ใน Scientific Reports เผยแพร่วันที่ 20 กรกฎาคม 2026 งานนี้ใช้ EEG ช่องเดียว Fpz-Cz จาก Sleep-EDF, แปลงสัญญาณด้วย synchrosqueezed transform, ให้ CNN เรียนรู้ representation ระดับช่วงสั้น, ปรับ representation ด้วย contrastive learning แล้วใช้ CNN แบบ time-distributed ต่อกับ GRU สองชั้นสำหรับลำดับ epoch โดยรายงาน accuracy **83%**.

แหล่งอ้างอิง: [บทความล่าสุด](https://www.nature.com/articles/s41598-026-62832-5), [Sleep-EDF Expanded ใน PhysioNet](https://physionet.org/content/sleep-edfx/1.0.0/)

ผมทำ reproduction ระดับ protocol ให้แล้วบนเครื่องนี้ โดยใช้ Sleep-EDF จริง 12 records จาก 6 subjects และรันได้ครบตั้งแต่โหลด EDF, อ่าน hypnogram, preprocess, train และประเมินผล รอบล่าสุดใช้ strict subject-wise split โดยไม่ให้ subject เดียวกันอยู่ข้าม train/validation/test ผลยังไม่เทียบเท่า 83% เพราะเป็น subset ขนาดเล็ก, train สั้นเพื่อให้รันบน CPU ได้ และรายละเอียด split/architecture/weights ของ paper ไม่ได้เปิดครบในหน้าเผยแพร่:

| การทดลอง | Accuracy | Macro-F1 | Cohen's kappa |
|---|---:|---:|---:|
| SST + CNN + contrastive + GRU, 2-subject pilot, ไม่ถ่วง class | 24.9% | 0.217 | 0.091 |
| 2-subject pilot + class-weighted ablation | 48.1% | 0.307 | 0.311 |
| SST + CNN + contrastive + GRU, 6-subject strict split | **53.1%** | **0.356** | **0.314** |
| 6-subject strict split + class-weighted ablation | 49.7% | 0.355 | 0.289 |
| Raw 1D-CNN baseline, class-weighted, 5 epochs | 45.0% | 0.292 | 0.211 |

ดังนั้นคำตอบคือ **ทำตามแนวทางล่าสุดได้และ pipeline ทำงานจริง** แต่ผลรอบนี้ยังเป็น reproduction ขนาดเล็ก ไม่ควรอ้างว่า reproduce ตัวเลข 83% แล้ว

## Dataset ที่พบ

| Dataset | ข้อมูล | เหมาะกับงานนี้อย่างไร |
|---|---|---|
| [Sleep-EDF Expanded](https://physionet.org/content/sleep-edfx/1.0.0/) | PSG 197 records มี EEG Fpz-Cz/Pz-Oz, EOG, chin EMG และ hypnogram ที่ผู้เชี่ยวชาญให้ label | แนะนำให้เริ่มที่นี่ เพราะเป็น dataset ที่ paper ล่าสุดใช้และดาวน์โหลดได้ผ่าน PhysioNet |
| [Dreem DOD-H/O](https://zenodo.org/records/15900394) | Full-night wearable EEG/PSG; DOD-H และ DOD-O มีไฟล์ขนาดหลายสิบ GB | เหมาะถ้าต้องการ single-channel/wearable และแนวทาง SleepPACNet; ใหญ่เกินกว่าจะใช้เป็นรอบแรกบนเครื่อง CPU |
| [ISRUC-Sleep](https://sleeptight.isr.uc.pt/?page_id=48) | EEG/EOG/EMG/PSG พร้อม expert scoring หลาย cohort | เหมาะสำหรับ external validation และดูความ generalize ข้าม dataset |
| [SHHS](https://sleepdata.org/datasets/shhs/pages) | PSG ขนาดใหญ่: Visit 1 จำนวน 6,441 คน และ Visit 2 จำนวน 3,295 คน | เหมาะเมื่อจะทำ benchmark ที่มีจำนวน subject มาก แต่ต้องลงทะเบียน/ขอ access |

งาน benchmark ที่ควรอ่านประกอบคือ [SLEEPYLAND](https://www.nature.com/articles/s41746-025-02237-2) ซึ่งเปรียบเทียบ U-Sleep, DeepResNet และ SleepTransformer บน EEG/EOG และมีทั้ง in-distribution กับ out-of-distribution evaluation และ [SleepPACNet](https://www.nature.com/articles/s41598-026-48881-w) ซึ่งใช้ Fp1-Fp2 จาก Dreem DOD-H และเน้น phase-amplitude coupling สำหรับ wearable EEG

## Protocol ที่ทำตาม

1. ใช้ช่อง EEG Fpz-Cz จาก Sleep-EDF และแบ่งเป็น epoch ละ 30 วินาที
2. อ่าน labels W, N1, N2, N3, REM; รวม R&K stage 3/4 เป็น N3 และตัด epoch ที่ไม่ทราบ label หรือ movement ออก
3. ทำ z-score ต่อ epoch และแบ่งสัญญาณ 3,000 samples เป็นช่วงย่อย 256 samples
4. คำนวณ SST-like time-frequency representation จาก STFT
5. Stage 1: pretrain CNN บนช่วง 256 samples
6. Stage 2: ใช้ contrastive refinement เพื่อให้ representation ของ augmentation เดียวกันใกล้กัน
7. Stage 3: ใช้ CNN แบบ time-distributed แล้วส่งลำดับ feature เข้า GRU สองชั้นเพื่อทำนาย sleep stage ของ epoch เต็ม
8. รวมคืนของ subject เดียวกันก่อน split และใช้ strict subject-wise split: train = SC404, SC400, SC405, SC403; validation = SC401; held-out test = SC402

การทดลอง strict ล่าสุดใช้ 1,732 scored epochs: train 1,127, validation 285 และ test 320 จาก 6 subjects. เป็นการจำกัดขนาดจาก full Sleep-EDF เพื่อให้รันได้บน CPU; ไม่ใช่ขนาดเต็มของ paper และ test ยังมีเพียงหนึ่ง held-out subject จึงควรเรียกว่า small strict benchmark ไม่ใช่ final benchmark

## ตีความผล

ใน strict benchmark โมเดล SST + CNN + contrastive + GRU ได้ accuracy 53.1%, macro-F1 0.356 และ kappa 0.314. N3 ทำได้ดีที่สุด (F1 0.689) แต่ REM ยังมี F1 = 0. การเพิ่ม class-weighted loss ช่วย W (F1 0.391) แต่ไม่ได้เพิ่มภาพรวม และยังไม่ใช่ configuration ที่ยืนยันว่าเป็นของ paper ล่าสุดโดยตรง เพราะ paper ไม่ได้เปิดรายละเอียด loss weighting ไว้ครบในหน้า HTML

raw 1D-CNN baseline ที่ใช้ class-weighted loss และ 5 epochs ได้ accuracy 45.0%, macro-F1 0.292 และ kappa 0.211 บน test subject เดียวกัน. ผลนี้สนับสนุนเบื้องต้นว่า SST representation และ sequence modeling อาจช่วยเหนือ raw-CNN ได้ แต่ยังเป็น ablation เชิงสำรวจ ไม่ใช่ข้อสรุปทั่วไป เพราะจำนวน subjects และ seeds ยังน้อย

## Robustness และการจัดการ class imbalance

เพื่อแยกผลของ random initialization ออกจากผลของการเปลี่ยน test subject ผมล็อก `split_seed=7` ไว้เหมือนกันทุกการทดลอง ทำให้ validation = `SC401` และ test = `SC402` คงที่ แล้วรัน model seeds `7, 19, 31`:

| Imbalance strategy | Accuracy | Macro-F1 | Kappa | W F1 | N1 F1 | REM F1 |
|---|---:|---:|---:|---:|---:|---:|
| None | 49.2% ± 3.9% | 0.302 ± 0.052 | 0.252 ± 0.063 | 0.051 | 0.499 | 0.000 |
| Full balanced sampler, power 1.0 | 49.3% ± 8.8% | **0.368 ± 0.099** | 0.279 ± 0.146 | **0.390** | 0.155 | **0.200** |
| Soft balanced sampler, power 0.5 | 46.8% ± 3.5% | 0.308 ± 0.046 | 0.228 ± 0.064 | 0.255 | 0.330 | 0.000 |

ค่าในตารางเป็น mean ± sample standard deviation จาก 3 seeds. Full balanced sampler ทำให้ REM เริ่มถูกทำนายได้และเพิ่ม macro-F1 เฉลี่ย แต่ variance สูงและ N1 ลดลงชัดเจน. Soft sampler รักษา N1 ได้ดีกว่า แต่ไม่ช่วย REM. ดังนั้นยังไม่มี imbalance strategy เดียวที่แก้ทั้ง REM และ N1 ได้อย่างเสถียรบนข้อมูล subset นี้ และไม่ควรเลือก full sampler เป็น final configuration โดยดูจาก macro-F1 เพียงอย่างเดียว

ผลนี้บอกได้สองอย่าง:

- โค้ดอ่าน dataset, label mapping, SST-like transform, CNN, contrastive stage และ GRU sequence stage ได้จริง
- strict split ลดความเสี่ยง leakage ระหว่างคน แต่ทำให้เห็น domain shift ระหว่าง subject ชัดขึ้น
- คอขวดรอบนี้คือข้อมูล/compute, class imbalance และ REM ที่มีจำนวนน้อย มากกว่าการพิสูจน์ว่าแนวคิดใช้ไม่ได้

## ไฟล์และคำสั่งที่รันได้

- [README_TH.md](README_TH.md) — วิธีติดตั้งและรัน
- [run_sst_gru.py](run_sst_gru.py) — reproduction ของแนวทาง paper ล่าสุด
- [download_sleepedf_subset.py](download_sleepedf_subset.py) — ดาวน์โหลด Sleep-EDF subset 12 records พร้อมตรวจความครบของไฟล์
- [run_raw_cnn_baseline.py](run_raw_cnn_baseline.py) — raw EEG 1D-CNN baseline
- [real_sst_gru_6subject.json](real_sst_gru_6subject.json) — strict benchmark ไม่ถ่วง class
- [real_sst_gru_6subject_weighted.json](real_sst_gru_6subject_weighted.json) — strict class-weighted ablation
- [raw_cnn_baseline_6subject_5ep.json](raw_cnn_baseline_6subject_5ep.json) — raw-CNN baseline 5 epochs
- `real_sst_gru_seed*_fixedsplit.json` — 3 model seeds, no sampler
- `real_sst_gru_balanced_seed*_fixedsplit.json` — 3 model seeds, full balanced sampler
- `real_sst_gru_softbalanced_seed*_fixedsplit.json` — 3 model seeds, inverse-square-root sampler
- [real_sst_gru_subject_pilot.json](real_sst_gru_subject_pilot.json) — ผล subject-held-out pilot ไม่ถ่วง class
- [real_sst_gru_subject_pilot_weighted.json](real_sst_gru_subject_pilot_weighted.json) — ผล subject-held-out class-weighted ablation
- [synthetic_sst_gru_results.json](synthetic_sst_gru_results.json) — smoke test ของ pipeline บนข้อมูลสังเคราะห์

คำสั่ง reproduction แบบสั้น:

```powershell
Set-Location "C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction"
.\.venv\Scripts\python.exe -u run_sst_gru.py `
  --data-dir data\sleep-edf `
  --max-subjects 6 `
  --max-epochs-per-subject 160 `
  --epochs-pretrain 2 `
  --epochs-contrastive 1 `
  --epochs-sequence 5 `
  --batch-size 64 `
  --split-seed 7 `
  --out real_sst_gru_6subject.json
```

ถ้าต้องการรอบที่สมดุลขึ้น:

```powershell
.\.venv\Scripts\python.exe -u run_sst_gru.py `
  --data-dir data\sleep-edf `
  --max-subjects 6 `
  --max-epochs-per-subject 160 `
  --epochs-pretrain 2 `
  --epochs-contrastive 1 `
  --epochs-sequence 5 `
  --batch-size 64 `
  --class-weighted `
  --out real_sst_gru_6subject_weighted.json
```

ถ้าต้องการ oversample minority stages:

```powershell
.\.venv\Scripts\python.exe -u run_sst_gru.py `
  --data-dir data\sleep-edf `
  --max-subjects 6 `
  --max-epochs-per-subject 160 `
  --epochs-pretrain 2 `
  --epochs-contrastive 1 `
  --epochs-sequence 5 `
  --batch-size 64 `
  --imbalance-mode balanced_sampler `
  --sampler-power 1.0 `
  --seed 7 `
  --split-seed 7 `
  --out real_sst_gru_balanced_seed7_fixedsplit.json
```

## ข้อจำกัดและรอบถัดไป

ตัวเลข 83% ของ paper เป็นผลบน protocol และขนาดข้อมูลของผู้วิจัย ไม่ใช่ baseline ที่นำมาเปรียบเทียบตรง ๆ กับผล subset นี้ การจะทดสอบให้ใกล้เคียงต้องเพิ่ม Sleep-EDF ให้ครบ, ใช้ split เดียวกับ paper หากผู้เขียนเปิดเผย, ปรับ sampling/augmentation/architecture ให้ตรง และ train หลาย epoch ด้วย GPU. ผล imbalance รอบนี้ชี้ว่าควรทำ targeted sampler/augmentation สำหรับ REM และ N1 แยกกัน ก่อนสรุป configuration สุดท้าย จากนั้นควรทดสอบ leave-one-subject-out และข้าม dataset บน ISRUC หรือ SHHS เพื่อวัดการ generalize

ไฟล์ใน `data\dodh` ที่เป็นไฟล์ดาวน์โหลดชั่วคราวไม่สมบูรณ์ไม่ได้ถูกใช้ในการทดลองนี้; ผลทั้งหมดใน report มาจาก Sleep-EDF subset ที่ดาวน์โหลดครบแล้ว

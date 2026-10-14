# Sleep stage classification: EEG protocol reproduction

> **สำหรับผู้ที่เพิ่งเข้ามาดูงาน:** เปิด [สมุดทดลองสำหรับ VS Code](walkthrough/README_TH.md) แล้วเริ่มจาก `00_start_here.ipynb` จะเห็น EEG จริง, SST จริง, pipeline, ผล r19, confusion matrix และงานที่ยังค้างตามลำดับ โดยไม่เริ่ม training ใหม่

> สถานะปรับปรุง 9 ก.ย. 2026: อ่าน [แผนและ audit 4 สัปดาห์](RECOVERY_PLAN_20260909_TH.md) ก่อน ข้อมูลส่วนล่างเป็นประวัติ prototype ขนาดเล็ก ไม่ใช่สถานะ full-cohort ปัจจุบัน `paper_faithful/` มี SST cache เต็มและ r19 cap128 สอง seeds ที่รันผ่าน แต่ **full numerical reproduction และ subject-held-out evaluation ยังไม่เสร็จ** คำว่า pipeline ผ่านไม่ได้หมายความว่าได้ accuracy ตาม paper

เริ่มอ่าน [research_report_TH.md](research_report_TH.md) เพื่อดู dataset, งานวิจัยล่าสุด, protocol และผลที่รันจริง โฟลเดอร์นี้มีทั้ง reproduction ของงาน EEG ล่าสุดปี 2026 (`run_sst_gru.py`) และ implementation สำรองของ SleepPACNet (`run_sleep_pacnet.py`)

## งานล่าสุดที่เลือกเป็นหลัก

งานหลักคือ `Single-channel EEG sleep stage classification using synchrosqueezed transform and sequential representation learning` (Scientific Reports, 20 ก.ค. 2026) ซึ่งใช้ Fpz-Cz จาก Sleep-EDF, SST, CNN, contrastive learning และ GRU สองชั้น รายงาน accuracy 83% บน protocol เต็มของผู้วิจัย

คำสั่ง smoke test:

```powershell
\.venv\Scripts\python.exe run_sst_gru.py --synthetic --epochs-pretrain 1 --epochs-contrastive 1 --epochs-sequence 1
```

เมื่อดาวน์โหลด Sleep-EDF subset แล้ว:

```powershell
\.venv\Scripts\python.exe run_sst_gru.py --data-dir data\sleep-edf --max-subjects 6 --max-epochs-per-subject 160 --epochs-pretrain 2 --epochs-contrastive 1 --epochs-sequence 5 --batch-size 64
```

`--max-subjects` จำกัดจำนวน unique subjects ไม่ใช่จำนวนคืน และโค้ดจะรวมหลายคืนของ subject เดียวกันก่อนทำ split ผล strict benchmark ล่าสุดที่รันบน CPU อยู่ใน `real_sst_gru_6subject.json` และ `real_sst_gru_6subject_weighted.json` ส่วน baseline อยู่ใน `raw_cnn_baseline_6subject_5ep.json`

ข้อมูล local ตอนนี้มี 6 subjects (12 records) และใช้ strict subject-wise split: train = SC404/SC400/SC405/SC403, validation = SC401, test = SC402. เป็น small strict benchmark; ยังไม่ใช่ final benchmark ของ paper เพราะใช้ subset, seed และ training budget จำกัด

สำหรับ robustness ให้ใช้ `--split-seed 7` คงที่ แล้วเปลี่ยน `--seed` เช่น `7, 19, 31` เพื่อวัดความแปรปรวนจากการ train โดยไม่เปลี่ยน held-out subject. สำหรับ class imbalance มีตัวเลือก `--imbalance-mode class_weighted` หรือ `balanced_sampler`; `--sampler-power 1.0` คือ inverse-frequency เต็มรูปแบบ และ `0.5` คือ inverse-square-root แบบนุ่มกว่า

## SleepPACNet เป็น implementation สำรอง

## สิ่งที่ทำตามงานต้นฉบับ

- สัญญาณ 30 วินาทีต่อ epoch, 250 Hz -> 100 Hz
- ใช้ EEG prefrontal bipolar `Fp1-Fp2` ที่สร้างจาก `Fp1-F3 - Fp2-F4 + F3-F4`
- PAC branch: bandpass 0.5–8 Hz + Hilbert transform และ bandpass 8–30 Hz
- CNN สองทาง: PAC feature branch + raw EEG branch
- weighted cross-entropy, AdamW, subject-wise split
- รายงาน Accuracy, macro-F1, Cohen's kappa และ F1 แยก stage

## ข้อควรระวัง

ผลจาก `--max-subjects` หรือจำนวน epoch ที่ลดลงเป็นเพียง smoke/sanity run ไม่ใช่ผลที่เทียบกับ paper ได้โดยตรง งานต้นฉบับใช้ Dreem Open Dataset-Healthy 25 คน, leave-one-subject-out, 100 epochs และรายงาน accuracy 75.7% บน Fp1-Fp2

ข้อมูล Dreem มีขนาดใหญ่และมีเงื่อนไขการใช้งานของเจ้าของข้อมูล ส่วน downloader ที่อยู่ในโฟลเดอร์นี้ดึงเฉพาะ record ที่เลือกจาก zip ได้ เพื่อไม่ต้องดาวน์โหลดทั้ง archive

## คำสั่งหลัก

```powershell
\.venv\Scripts\python.exe run_sleep_pacnet.py --help
\.venv\Scripts\python.exe run_sleep_pacnet.py --synthetic --epochs 2
```

เมื่อมีไฟล์ `.h5` ใน `data/dodh/` ให้รัน:

```powershell
\.venv\Scripts\python.exe run_sleep_pacnet.py --data-dir data/dodh --epochs 3 --max-subjects 5 --max-epochs-per-subject 400
```

ไฟล์ H5 ของ Dreem-learning ใช้ dataset `hypnogram` และ signal paths ใต้ `signals/`. ตัว loader จะค้นหา derivation ที่ชื่อใกล้เคียงกับ `Fp1_F3`, `Fp2_F4`, `F3_F4` ให้เองและบันทึก manifest ของ record ที่อ่านได้

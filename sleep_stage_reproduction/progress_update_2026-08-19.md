# Progress Update — 19 August 2026

## สิ่งที่ทำต่อจากจุดค้าง

1. แก้ `run_sst_gru.py` ให้ parse subject ID จากชื่อ Sleep-EDF และรวมหลายคืนของ subject เดียวกันก่อน split
2. เพิ่ม integrity guard เพื่อไม่ให้ไฟล์ PSG ที่ดาวน์โหลดไม่ครบถูกนำไป train
3. ขยายข้อมูลจาก 2 เป็น 6 unique subjects (`SC400`–`SC405`) รวม 12 PSG records และตรวจขนาดไฟล์ครบทุกไฟล์
4. รัน strict subject-wise benchmark ของ SST + CNN + contrastive refinement + GRU
5. รัน class-weighted ablation และ raw-CNN baseline ด้วย split เดียวกัน
6. เพิ่ม `split_seed` เพื่อแยกความแปรปรวนจาก model seed ออกจากความแตกต่างของ held-out subject
7. เพิ่ม balanced sampler แบบเต็มและแบบนุ่มสำหรับแก้ class imbalance

## Dataset และ split ล่าสุด

- Subjects: 6 คน
- Train subjects: `SC404`, `SC400`, `SC405`, `SC403`
- Validation subject: `SC401`
- Held-out test subject: `SC402`
- Train / validation / test epochs: 1,127 / 285 / 320
- Split type: `strict_subject_wise`

ไม่มี subject overlap ระหว่าง train, validation และ test ดังนั้นรอบนี้เป็น benchmark ที่ถูกต้องกว่า pilot 2-subject ก่อนหน้า แต่ยังเป็น subset ขนาดเล็กเมื่อเทียบกับ full Sleep-EDF

## Results ล่าสุด

| Experiment | Accuracy | Macro-F1 | Cohen's kappa | ข้อสังเกต |
|---|---:|---:|---:|---|
| SST + CNN + contrastive + GRU, unweighted | **53.1%** | **0.356** | **0.314** | N3 F1 = 0.689; REM F1 = 0 |
| SST + CNN + contrastive + GRU, class-weighted | 49.7% | 0.355 | 0.289 | W F1 ดีขึ้นเป็น 0.391 แต่ REM F1 ยัง = 0 |
| Raw 1D-CNN baseline, class-weighted, 5 epochs | 45.0% | 0.292 | 0.211 | ต่ำกว่า SST+GRU; N1/REM ยังยาก |

ผลบ่งชี้เบื้องต้นว่า representation แบบ SST และการใช้ลำดับด้วย GRU มีประโยชน์เมื่อเทียบกับ raw-CNN แต่ยังสรุปเชิงสถิติไม่ได้ เพราะใช้ seed เดียวและ test เป็น subject เดียว (`SC402`)

## Robustness: 3 seeds บน split เดียวกัน

ใช้ `split_seed=7` เหมือนกันทุกครั้ง จึงทดสอบ test subject เดิมคือ `SC402` และเปลี่ยนเฉพาะ model seed (`7, 19, 31`) โดยรายงานค่าเฉลี่ย ± sample standard deviation:

| Imbalance strategy | Accuracy | Macro-F1 | Kappa | REM F1 | N1 F1 |
|---|---:|---:|---:|---:|---:|
| None | 49.2% ± 3.9% | 0.302 ± 0.052 | 0.252 ± 0.063 | 0.000 | 0.499 |
| Full balanced sampler (`power=1.0`) | 49.3% ± 8.8% | **0.368 ± 0.099** | 0.279 ± 0.146 | **0.200** | 0.155 |
| Soft balanced sampler (`power=0.5`) | 46.8% ± 3.5% | 0.308 ± 0.046 | 0.228 ± 0.064 | 0.000 | 0.330 |

การตีความ: full sampler ช่วยให้โมเดลเริ่มทำนาย REM และ W ได้ แต่ทำให้ N1 ลดลงและผลแกว่งมาก; soft sampler รักษา N1 ได้ดีกว่าแต่ไม่ช่วย REM. จึงยังไม่มีวิธีเดียวที่แก้ทั้ง REM และ N1 ได้อย่างเสถียรบนข้อมูลชุดเล็กนี้

## Interpretation

- งานทำตาม pipeline หลักของ paper ได้จริงในระดับ protocol-level: single-channel EEG → SST-like representation → CNN pretraining → contrastive refinement → sequence model ด้วย GRU
- strict split ทำให้ผลลดความเสี่ยง data leakage จากการแบ่ง epoch ของคนเดียวกันข้ามชุด
- class weighting ช่วย W แต่ไม่ได้แก้ REM ใน test subject นี้; จึงยังต้องจัดการ class imbalance และ domain shift อย่างระมัดระวัง
- ยังไม่ควรอ้างว่าได้ reproduce accuracy 83% ของ paper เพราะรายละเอียด architecture/split/training ของ paper เปิดเผยไม่ครบ และการทดลองของเรายังใช้ epoch/seed/subjects น้อยกว่า

## Files

- `run_sst_gru.py` — โมเดล reproduction และ strict subject-wise split
- `run_raw_cnn_baseline.py` — raw EEG 1D-CNN baseline
- `download_sleepedf_subset.py` — downloader พร้อม resume และ file-integrity check
- `real_sst_gru_6subject.json` — strict benchmark ไม่ถ่วง class
- `real_sst_gru_6subject_weighted.json` — strict class-weighted ablation
- `raw_cnn_baseline_6subject_5ep.json` — raw-CNN baseline ที่ใช้ training budget ใกล้เคียงกัน
- `real_sst_gru_seed7_fixedsplit.json`, `real_sst_gru_seed19_fixedsplit.json`, `real_sst_gru_seed31_fixedsplit.json` — 3 model seeds แบบไม่ถ่วง class
- `real_sst_gru_balanced_seed*_fixedsplit.json` — 3 seeds ของ full balanced sampler
- `real_sst_gru_softbalanced_seed*_fixedsplit.json` — 3 seeds ของ inverse-square-root sampler
- `research_report_TH.md` — รายงานสรุปฉบับอัปเดต

## Next steps

1. ทำ leave-one-subject-out หรือเพิ่ม held-out subjects เพื่อไม่ให้ข้อสรุปขึ้นกับ `SC402` เพียงคนเดียว
2. ทำ targeted sampler/augmentation สำหรับ REM และ N1 แยกกัน เพราะ full balancing ช่วย REM แต่กด N1
3. เพิ่ม epochs และเปิด CUDA หากติดตั้ง PyTorch GPU ได้ เพื่อให้ใกล้ training budget ของ paper
4. ทำ ablation เพิ่ม: raw vs SST, no contrastive vs contrastive, no GRU vs GRU
5. ทดสอบ external validation บน ISRUC หรือ dataset อื่นเมื่อ pipeline หลักนิ่งแล้ว

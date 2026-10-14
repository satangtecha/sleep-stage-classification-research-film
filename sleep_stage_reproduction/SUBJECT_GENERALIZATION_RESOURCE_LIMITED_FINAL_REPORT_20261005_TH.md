# รายงานผลการทดสอบการจำแนกระยะการนอนหลับกับบุคคลที่ไม่เคยเห็นมาก่อน

วันที่สรุปผล: 5 ตุลาคม 2569  
สถานะ: **ดำเนินการครบและตรวจสอบหลักฐานผ่าน**  
Run: `subject-generalization-resource-limited-plan15-wait-drain-v1-cap32-e6-20261005`

## 1. ข้อสรุปสั้น

ระบบสามารถรันกระบวนการเรียนรู้ครบทั้ง 3 ขั้นกับการแบ่งข้อมูลแบบแยกบุคคลจำนวน 6 folds ได้สำเร็จ โดยแต่ละ fold กันบุคคลทดสอบออกจากข้อมูลฝึกอย่างชัดเจน ผลของทั้ง 6 folds ผ่านการตรวจซ้ำด้วย TensorFlow 2.4 ที่ล็อกเวอร์ชันไว้ และตัวควบคุมงานจบด้วย exit code 0 โดยถอด native cache ออกเรียบร้อย

อย่างไรก็ตาม ผลด้านความแม่นยำยังต่ำ: ค่า accuracy เฉลี่ยเท่ากับ **29.17% ± 14.88 จุดเปอร์เซ็นต์** และ macro-F1 เฉลี่ยเท่ากับ **0.1358 ± 0.0447** โมเดลมี N1 F1 เท่ากับศูนย์ทุก fold และ REM F1 เท่ากับศูนย์ใน 5 จาก 6 folds จึงสรุปได้ว่า **pipeline ทำงานครบและตรวจสอบซ้ำได้ แต่โมเดลรุ่น resource-limited นี้ยังจำแนกระยะการนอนของบุคคลใหม่ได้ไม่ดีพอ**

ผลนี้เป็น engineering pilot ที่ลดภาระให้เหมาะกับเครื่องปัจจุบัน ไม่ใช่การทำซ้ำงานวิจัยแบบ paper-exact และห้ามนำ accuracy นี้ไปเทียบตรงกับตัวเลขเด่นจากบทความที่ใช้วิธีแบ่งข้อมูลต่างกัน

## 2. ระเบียบวิธีที่รันจริง

- Evaluation protocol: `SUBJECT_GENERALIZATION_V1`
- Model protocol: `PAPER_TEXT_V1`
- Resource profile: `RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V11_MICROBATCH8_PER_STAGE_WAIT_DRAIN`
- Subjects: `SC433`, `SC449`, `SC408`, `SC430`, `SC448`, `SC437`
- การประเมิน: 6 sequential held-out-subject folds; แต่ละคนเป็น test หนึ่งครั้ง
- Validation subject: คนถัดไปตามลำดับแบบวนรอบ
- Training subjects: 4 คนที่เหลือภายใน cohort เดียวกัน
- Cap: 32 epochs ต่อ subject
- Epochs การฝึก: 6 epochs ต่อ stage
- Selection seed / model seed: 42 / 42
- Stage 1: microbatch 8, gradient accumulation 16, effective batch 128
- Stage 2: microbatch 128, effective batch 128
- Stage 3: microbatch 1, gradient accumulation 128, effective batch 128
- Stage 3 stability: global-norm clipping 1.0 หลังเฉลี่ย gradients ของ effective batch และก่อน optimizer step
- การจัดการหน่วยความจำ: เปิด TensorFlow 2.4 process ใหม่ทุก stage และทุก fold พร้อม bounded wait สูงสุด 120 วินาทีระหว่าง stages
- Protocol SHA-256: `cc418da7b8192d8effe4ef68fe83b285bb4709b469b9456761006b06867700f0`

## 3. ผลราย fold

| Fold | Test subject | n | Accuracy | Macro-F1 | Weighted-F1 | N1 F1 | REM F1 | Stage-2 silhouette |
|---:|:---|---:|---:|---:|---:|---:|---:|---:|
| 1 | SC433 | 32 | 0.4688 | 0.2051 | 0.4739 | 0.0000 | 0.0000 | -0.1202 |
| 2 | SC449 | 32 | 0.2813 | 0.1346 | 0.2460 | 0.0000 | 0.0000 | -0.0942 |
| 3 | SC408 | 32 | 0.1875 | 0.1150 | 0.1492 | 0.0000 | 0.0000 | -0.1569 |
| 4 | SC430 | 32 | 0.0625 | 0.0735 | 0.0492 | 0.0000 | 0.2500 | -0.0623 |
| 5 | SC448 | 32 | 0.4063 | 0.1238 | 0.3676 | 0.0000 | 0.0000 | -0.1579 |
| 6 | SC437 | 32 | 0.3438 | 0.1629 | 0.2946 | 0.0000 | 0.0000 | -0.1125 |

## 4. ผลรวม

| ตัวชี้วัด | ค่าเฉลี่ยข้าม folds | Sample SD | ต่ำสุด | สูงสุด |
|:---|---:|---:|---:|---:|
| Accuracy | 0.2917 | 0.1488 | 0.0625 | 0.4688 |
| Macro-F1 | 0.1358 | 0.0447 | 0.0735 | 0.2051 |
| Macro precision | 0.1301 | 0.0491 | 0.0600 | 0.2086 |
| Macro recall | 0.1586 | 0.0416 | 0.0952 | 0.2147 |
| Weighted-F1 | 0.2634 | 0.1519 | 0.0492 | 0.4739 |
| N1 F1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| REM F1 | 0.0417 | 0.1021 | 0.0000 | 0.2500 |
| Stage-2 silhouette | -0.1173 | 0.0369 | -0.1579 | -0.0623 |

มีตัวอย่างทดสอบรวม 192 ตัวอย่าง ทำนายถูก 56 ตัวอย่าง จึงได้ pooled accuracy 0.2917 ซึ่งเท่ากับค่าเฉลี่ย accuracy เพราะทุก fold มีขนาดเท่ากัน

Pooled confusion matrix โดยเรียง label เป็น `W, N1, N2, N3, REM`:

| จริง \ ทำนาย | W | N1 | N2 | N3 | REM |
|:---|---:|---:|---:|---:|---:|
| W | 39 | 8 | 22 | 1 | 4 |
| N1 | 13 | 0 | 7 | 0 | 2 |
| N2 | 34 | 10 | 16 | 0 | 3 |
| N3 | 11 | 0 | 2 | 0 | 1 |
| REM | 12 | 1 | 5 | 0 | 1 |

## 5. การตีความ

1. โมเดลเรียนรู้ W และ N2 ได้บางส่วน แต่ยังสับสนสองคลาสนี้สูงมาก
2. โมเดลไม่ทำนาย N1 ถูกเลยในชุดทดสอบทั้งหก folds และแทบไม่จำแนก REM ได้
3. คอลัมน์ N3 ใน pooled confusion matrix เป็นศูนย์ทั้งหมด แสดงว่าโมเดลไม่ทำนายตัวอย่างใดเป็น N3
4. Stage-2 silhouette ติดลบทุก fold หมายถึง representation ที่ได้ยังไม่แยกกลุ่มตาม sleep stage อย่างชัดเจนใน pilot นี้
5. ความแตกต่างของ accuracy ระหว่าง subjects สูงมาก (6.25% ถึง 46.88%) สะท้อนปัญหา subject variability และขนาด test ต่อ fold ที่เล็ก

ดังนั้นข้อสรุปที่รองรับโดยหลักฐานคือ “ระบบทำ subject-held-out training/evaluation ครบและตรวจสอบซ้ำได้” ไม่ใช่ “โมเดลทำซ้ำ accuracy ของบทความได้” หรือ “โมเดล generalize ได้ดีแล้ว”

## 6. หลักฐานการตรวจสอบ

- Parent terminal: `workload_completed`, exit code 0
- ระยะรัน: 2026-10-05 13:06:07Z ถึง 14:43:26Z (ประมาณ 1 ชั่วโมง 37 นาที)
- Native cache unmounted: true
- Windows host forced cleanup: false
- Summary status: `completed`, fold status `verified` ครบ 6 folds
- Locked verifier: `/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python`
- Standalone `verify_run`: ผ่านครบ 6 folds หลัง parent จบ โดย execution hashes ตรงกับ summary
- Terminal SHA-256: `f46e07c3f6232063ff3779ae2ecd54b2b68fa655879f81beb854f5300a4d700b`
- Summary SHA-256: `5dd07dd88dc003c2f1d83d35b5c62fc0a20ac13b9ef47f543fa261eba14fc828`
- Lifecycle SHA-256: `f518d7021c2ae9b1e57a0c753cfd1c1f44c0c922bc8000eaee040706e7545b2e`
- Final acceptance evidence: `E:/blp/sleep_stage_reproduction/runtime/reviews/plan15-final-acceptance-evidence-v1-20261005.json`
- Resource-admission procedural audit: `E:/blp/sleep_stage_reproduction/runtime/reviews/plan15-resource-admission-procedural-audit-v1-20261005.json`

## 7. ข้อจำกัด

- ใช้เพียง 6 subjects และเลือกเพียง 32 epochs ต่อ subject
- ฝึกเพียง 6 epochs ต่อ stage และใช้ seed เดียว
- test fold มี 32 ตัวอย่าง จึงอ่อนไหวต่อ class imbalance; บาง fold ไม่มี N3 หลัง deterministic cap
- Stage 1/2 ประเมิน 384 frame-level samples ต่อ held-out split แต่ Stage 3 ประเมิน 32 sequence-level samples จึงห้ามนำ accuracy ข้าม stage มาเปรียบเทียบกันโดยตรง
- Stage 1 และ Stage 3 ใช้ gradient accumulation ซึ่งเป็น hardware adaptation
- Stage 3 เพิ่ม global-norm clipping เพื่อควบคุม NaN จึงไม่ใช่ paper-exact
- ผลนี้ไม่ควรเทียบโดยตรงกับผลจาก epoch-random split หรือใช้สนับสนุนข้ออ้างทางคลินิก
- โค้ดตรวจ RAM/commit ก่อนโหลด cache ของทุก stage และทั้ง 18 stage workers จบด้วย exit code 0 แต่ V11 ไม่ได้บันทึกตัวเลขที่ “ผ่าน” ไว้ทุกครั้ง จึงไม่มี exact historical RAM snapshots ราย stage ข้อนี้บันทึกเป็น operational-audit deviation อย่างตรงไปตรงมาและไม่มีการสร้างตัวเลขย้อนหลัง

## 8. สถานะเป้าหมาย

ผลหลักของ resource-limited subject-generalization pilot ผ่านครบ: protocol ถูก version และ hash, fold แยกคนครบ 6 folds, parent จบสำเร็จ, cache cleanup สำเร็จ, ผลทุก foldผ่าน locked standalone verification และมี fold/aggregate metrics พร้อมขอบเขตการกล่าวอ้างชัดเจน ทั้งนี้รับผลโดยมี documented deviation ด้านการไม่เก็บตัวเลข RAM/commit ที่ผ่านในแต่ละ stage; ตัว gate ถูกบังคับใช้ตาม source และ worker สำเร็จครบ แต่ตรวจสอบค่าตัวเลขย้อนหลังไม่ได้

งานที่สมเหตุผลในระยะถัดไปคือปรับปรุงคุณภาพโมเดลเป็นการทดลองชุดใหม่ เช่น class-balanced sampling/loss, เพิ่ม cap และจำนวน subjects, ทำ multi-seed และ ablation โดยต้องสร้าง protocol/version ใหม่ ไม่แก้หรือนำ Plan 15 กลับมาใช้ซ้ำ

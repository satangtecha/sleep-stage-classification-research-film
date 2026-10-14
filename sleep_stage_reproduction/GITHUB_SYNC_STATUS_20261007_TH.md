# สถานะการซิงก์โครงการ Sleep-stage reproduction

วันที่บันทึก: 7 ตุลาคม 2026 (เวลาไทย)

## ขอบเขตของโครงการ

โครงการนี้พยายามทำซ้ำงานวิจัย **Single-channel EEG sleep stage classification using synchrosqueezed transform and sequential representation learning** (Scientific Reports, DOI: `10.1038/s41598-026-62832-5`) ซึ่งมีลำดับหลักเป็น

`EEG → Synchrosqueezed Transform (SST) → CNN representation → contrastive learning → GRU classifier`

งานต้นฉบับรายงาน accuracy ประมาณ 83% และ macro-F1 ประมาณ 76% บนการทดลองเต็มของผู้วิจัย (78 คน, 194,655 epochs, epoch-random 80/10/10, seed 42)

## สิ่งที่ทำไว้แล้ว

- มีตัวโหลดและ preprocessing ของ Sleep-EDF พร้อม manifest และ schema
- มี implementation ของ SST, windowing, CNN encoder, contrastive stage และ GRU classifier
- มี protocol/gate สำหรับแยกงานต้นฉบับ, pilot และ subject-generalization
- มี smoke tests, parity checks, locked TF2.4 verification และเอกสารอธิบายภาษาไทย
- มี baseline CNN และ CPU spectral baseline สำหรับใช้ตรวจว่าปัญหาอยู่ที่ข้อมูลหรือโมเดล
- มีผล pilot ที่ตรวจสอบได้ เช่น v17: accuracy `0.2526041667`, macro-F1 `0.2219642498`; CPU spectral baseline: accuracy `0.1692708333`, macro-F1 `0.1262186072`

## สถานะการทดลองล่าสุด

- งาน pilot ใช้ 6 subjects, cap64 ต่อคนต่อ split และ 6 subject-wise folds จึงยัง **ไม่ใช่ full replication** ของ paper
- v21 จบแล้ว และ standalone locked-TF2.4 verification ผ่านเมื่อใช้ source snapshot ที่ตรงกับ v21
- v37 ใช้ profile `QUALITY_BALANCED_CAP64_E12_V7_STAGE3_FOCAL_C10`; หยุดที่ Fold 5 Stage 2 เพราะ resource gate ของไดรฟ์ C: ไม่ผ่าน จึงไม่มีผลรวม final ที่ควรนำไปอ้างเป็นผลวิจัย
- v38 เป็นงานต่อเนื่องที่ยังไม่มีผล final และถูกหยุดตามคำสั่งให้หยุดทุก process ในวันที่ซิงก์นี้ จึงห้ามนำผลของ v38 ไปใช้สรุป
- ผลที่ได้จนถึงตอนนี้ยืนยันว่า pipeline และการตรวจสอบทำงานได้ แต่ยังยืนยันไม่ได้ว่า replicate accuracy ของ paper ได้

## สิ่งที่ไม่ใส่ใน GitHub

ข้อมูลดิบ, virtual environment, SST cache, runtime logs/checkpoints และไฟล์ไบนารีถูกเก็บไว้นอก repository โดยเฉพาะ bulk artifacts อยู่ที่ `E:\blp\sleep_stage_reproduction` ไฟล์เหล่านี้ถูกกันด้วย `.gitignore` เพื่อป้องกัน repo ใหญ่เกินจำเป็นและไม่เผยแพร่ข้อมูลดิบ

## ข้อสรุปเชิงวิจัย

โปรเจกต์อยู่ในระยะ **pilot reproduction ที่มีหลักฐานและโค้ดพร้อมตรวจสอบ** แต่ยังไม่ถึงเกณฑ์ full replication หรือการอ้างว่าได้ accuracy เท่ากับ paper สาเหตุหลักที่ต้องแยกให้ชัดคือจำนวน subjects/ข้อมูล, subject-wise split ที่ยากกว่า protocol ของ paper, resource-limited training budget และความแตกต่างของ preprocessing/parameter บางจุด

การทดลองถัดไปควรเลือก intervention เพียง 1–2 จุดต่อ fresh version, เก็บ protocol ก่อน dispatch, ตรวจ output/gradient parity และรายงาน validation/test แยกกัน โดยไม่ใช้ผล test เพื่อเลือก hyperparameter

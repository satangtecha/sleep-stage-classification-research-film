# แผนกู้และยกระดับงาน 4 สัปดาห์: 9 ก.ย. – 7 ต.ค. 2026

## สรุปตรง ๆ

โปรเจกต์ยังไปต่อได้ แต่ **ยังไม่ได้ reproduce ผลวิจัยเต็ม** และไม่มีหลักฐานพอจะรับประกันว่าได้ accuracy 83% ภายใน 4 สัปดาห์ สิ่งที่ทำได้จริงแล้วคือข้อมูล/แคช SST และ pipeline สามขั้นที่รันผ่านบนข้อมูลจำกัด ส่วนการฝึกเต็ม การประเมินกับคนที่ไม่เคยเห็น และรายงานเปรียบเทียบยังต้องทำ

คำอนุญาตล่าสุดวันที่ 9 ก.ย. ให้แก้โค้ดและลดพิธีการที่ไม่จำเป็นได้ ไม่ต้องขอให้ผู้ใช้คัดลอกประโยคยืนยันทุกเวอร์ชันอีก แต่ยังต้องเก็บผลล้มเหลว แยกข้อมูลฝึก/ทดสอบ ตรวจความถูกต้อง และไม่เขียนทับหลักฐานเดิม การใช้ cloud แบบมีค่าใช้จ่ายหรืออัปโหลดข้อมูลยังต้องตกลงงบและปลายทางก่อน

## สิ่งที่ยืนยันจากหลักฐานในเครื่อง

| งาน | สถานะจริง ณ การตรวจครั้งนี้ |
|---|---|
| งานวิจัยอ้างอิง | SST → CNN → supervised contrastive learning → GRU; ไม่เปลี่ยนเป้าไปตาม paper ใหม่ทุกสัปดาห์ |
| ข้อมูลและแคช | มี full-cohort manifest 194,655 epochs; 78 subjects ตาม cohort แต่มี 77 subjects ที่มี epoch ใช้งาน ต้องรายงานรายการที่เป็นศูนย์อย่างโปร่งใส |
| r19 seeds 42/43 | lifecycle `terminal_validated`, exit 0 และบันทึก verifier ผ่านทั้งสอง child |
| ขอบเขต r19 | `mode=pilot`, cap 128 ต่อ split ไม่ใช่การฝึกเต็ม และ verifier ผ่านไม่ได้แปลว่าได้คุณภาพตาม paper |
| Subject-held-out | มีแผน v1–v4 แต่ยังไม่มีหลักฐานการฝึกสำเร็จ ไม่ถือว่าเป็นผล generalization |
| สิ่งแวดล้อม | ใช้ Python 3.7 / TensorFlow 2.4 ที่ล็อกไว้; ต้องแยกจากคำกล่าวอ้าง paper-exact และระบุการปรับ batch/gradient clipping |
| เครื่องปัจจุบัน | RTX 3050 Laptop VRAM 6 GB; เวลา 19:13+07:00 วันที่ 9 ก.ย. RAM ว่างประมาณ 1,399 MiB, commit headroom 14,370 MiB; C ว่างประมาณ 22 GiB, E 361 GiB |

หลักฐานหลัก: `E:/blp/sleep_stage_reproduction/runtime/training-logs/paper-text-v1-multiseed-cap128-r19-20260905.lifecycle.jsonl` และ execution ของสอง child ใต้ `E:/blp/sleep_stage_reproduction/runs/` การตรวจนี้อ่านหลักฐานเดิม ไม่ได้ฝึกหรือ verify checkpoint ใหม่

## ปัญหาที่พบและการแก้รอบนี้

1. ตัวรอ GPU มี timeout/sleep หลุดออกนอก loop: เมื่อไม่มีคำตอบอาจวนไม่จบ แก้ตำแหน่งและทดสอบ timeout เดิมซ้ำ
2. Subject GPU admission ตรวจหลังสร้าง GPU context แต่ปฏิเสธทุก process จึงอาจปฏิเสธตัวเอง: ยอมรับ PID ของตัวเองเท่านั้น ปฏิเสธ PID อื่น/ข้อมูลอ่านไม่ได้ และไม่อ้างว่าการมองเห็น process ใน WSL รับประกัน GPU ว่างทั้งหมด
3. แผนแบบเบากับแผนตอนฝึกสร้างคนละ payload: รวมให้ได้ payload เดียวกัน บังคับใช้ SHA-256 ของแผนที่ตรวจแล้ว และให้ standalone verifier สร้าง split กลับมาตรวจเอง
4. หยิบแต่ epoch ต้น ๆ ของแต่ละคน: เพิ่ม `subject_balanced_seeded_temporal_sample_v2` ซึ่งสุ่มแบบไม่ใช้ label กระจายตลอด recordings โดยมี seed; ระบุชัดว่ายังเป็น smoke sample ไม่ใช่คะแนนแทนทั้งคืน
5. ตรวจทรัพยากรหลังอ่านแคชหนัก และยอมรับหลักฐานเก่า: ย้ายไปก่อนโหลดแคช ตรวจเวลาไม่เกิน 120 วินาที/exit code ของ probe และตรวจ RAM/commit/ไฟ/พื้นที่สดอีกหลัง scan และก่อนแต่ละ stage
6. ตัวโหลดเปิดไฟล์ซ้ำถี่และเช็ก finite ด้วยบัฟเฟอร์ขนาดทั้ง chunk: ใช้ bounded cache reuse/finite scan พร้อมทดสอบ view lifetime จาก review เพิ่มการอ่าน shard เป็น snapshot ที่ตรวจ hash ของ bytes ชุดเดียวกับที่ใช้จริง เพื่อไม่ให้ไฟล์ที่ถูกเปลี่ยนระหว่างตรวจไหลเข้า training; ดูผลตรวจจริงใน `RECOVERY_VALIDATION_20260909.md`
7. เพิ่มการตรวจอายุ receipt ซ้ำตรงก่อนโหลดแคช และบันทึก failure แม้เกิดระหว่างสร้าง markers ก่อนเริ่มฝึก ชื่อ namespace ที่เริ่มใช้แล้วไม่ถูกลบเพื่อให้ลองซ้ำอย่างคลุมเครือ

กฎที่ยังไม่ลดโดยเดา: RAM ขั้นต่ำ 4 GiB และ commit headroom 8 GiB เป็นค่าเผื่อแบบอนุรักษนิยม ไม่ใช่ข้อพิสูจน์ว่าพอแน่ ต้องวัด peak ของ workload หลังแก้ loader ก่อนปรับให้เหมาะสม ไม่ปิด NaN checks และไม่เปลี่ยน batch/SupCon objective โดยไม่ระบุ adaptation

## เกณฑ์จบภายใน 4 สัปดาห์

งานหลักที่ต้องมี: protocol ที่เลือกชัดเจน, full training อย่างน้อยหนึ่งเส้นทางพร้อม baseline, validation/test ไม่ปนกัน, ผลทดสอบคนที่ไม่อยู่ในชุดฝึก, confusion matrix และ F1 รายคลาส, ค่าเฉลี่ย/ความแปรปรวนจาก seeds 42/43/44 ในการทดลองหลักที่ตกลงไว้, คำสั่งรันซ้ำได้และรายงานข้อแตกต่างจาก paper ทั้งหมด ไม่ใช้ threshold 83% เป็นเหตุปรับโมเดลจากผล test

| ช่วง | งานสำคัญและจุดตัดสินใจ |
|---|---|
| 9–15 ก.ย. | ซ่อม/ทดสอบ/review; วัดเวลาต่อ batch, peak RAM/VRAM และ I/O ทั้งสาม stage; ทำ live canary; ล็อก primary protocol และชุด train/validation/test พร้อม class counts; ตัดสินเครื่องภายใน 11 ก.ย. |
| 16–22 ก.ย. | ฝึกเต็ม primary protocol และ baseline; checkpoint จาก validation เท่านั้น; เก็บเวลา/ทรัพยากร/ความล้มเหลวทุก run; ห้ามใช้ cap128 แทนผลเต็ม |
| 23–29 ก.ย. | ประเมิน subject-held-out ด้วยชุด test เต็มของคนที่กำหนดไว้ล่วงหน้า; ทำ seeds เพิ่มตาม budget และ ablation ที่ตอบคำถามสำคัญ เช่น ตัด SupCon ออก; ไม่ค้น hyperparameter บน test |
| 30 ก.ย.–6 ต.ค. | standalone verification, ตรวจ split/lineage/class support, สรุปความแปรปรวนระดับคน ไม่ปฏิบัติต่อ epoch ที่สัมพันธ์กันว่าเป็นคนอิสระ; ตารางเปรียบเทียบ/ข้อจำกัด/รายงาน/เดโม |
| 7 ต.ค. | ส่งมอบโค้ด คำสั่ง สภาพแวดล้อม ผลและรายงาน; ระบุการทดลองที่ไม่สำเร็จหรือไม่ทันจริง ๆ |

AUTHOR_CODE_V1 เต็มทุก seed, LOSO ทุกคน และ ablation ทุกแบบเป็นส่วนขยาย ไม่ควรขวางการส่งผลหลักที่เชื่อถือได้ หาก compute budget ไม่พอ ต้องปรับขอบเขตอย่างชัดเจนก่อนเปิดผล test ไม่ลดข้อมูลลับ ๆ แล้วเรียก full reproduction

## จะใช้ cloud หรือไม่

แนวทางที่เลือก: **เครื่องนี้ใช้พัฒนาและ smoke; เตรียมเส้นทาง cloud สำหรับการฝึกเต็มหาก benchmark ชี้ว่าไม่ทัน** ไม่ติดตั้ง/เช่า/อัปโหลดในรอบแก้โค้ดนี้

ตัวอย่างเตือนขนาดงานจาก r19: child43 อยู่ระหว่าง admission Stage1 16:40:53 ถึง Stage2 16:48:51, Stage2 ถึง Stage3 16:56:36 และ parent จบ 17:00:53 วันที่ 5 ก.ย. รวมราว 20 นาทีสำหรับ cap128 ตัวเลขนี้รวม overhead/ประเมินผล ไม่ใช่ pure training throughput ถ้าขยายเชิงเส้นด้วยสัดส่วน train ประมาณ 155,724/128 ≈ 1,217 เท่า จะได้ระดับหลายร้อยชั่วโมงต่อ seed จึงไม่ควรรับปากว่า local full research จะจบในไม่กี่ชั่วโมง การแก้ loader อาจช่วยมาก แต่ต้องวัดใหม่

เกณฑ์เลือกภายใน 48 ชั่วโมง:

- วัด warm-up แยกจาก steady-state อย่างน้อย 100 batches ต่อ stage แล้วคำนวณจำนวน batches จริง รวม validation/test, scan, จำนวน seeds/folds และเผื่อเวลา 2 เท่า
- ถ้าคิวทดลองที่จำเป็นเกิน 7 วันของเวลาที่เครื่องเปิดใช้งานได้จริง หรือ RAM/VRAM ไม่พอสำหรับ objective เดิม ให้ย้ายงานฝึกไปเครื่อง GPU ที่ benchmark ผ่าน ไม่เปลี่ยนวัตถุประสงค์ SupCon เพียงเพื่อให้ใส่ VRAM ได้
- ทดลองสภาพแวดล้อมกับ GPU ของ cloud ก่อนจ่ายงานยาว: TF2.4/CUDA เก่าอาจไม่ตรงกับเครื่องปลายทาง ต้องทดสอบจริงหรือบันทึก environment adaptation ไม่เปลี่ยนแล้วอ้าง exact
- คำนวณค่าใช้จ่ายจากราคาปัจจุบันและขอเพดานงบก่อนซื้อ; ตรวจสิทธิข้อมูล/ปลายทางและขนาดอัปโหลดจริง เทียบการสร้าง SST จาก raw บน cloud กับการส่งแคชทั้งหมด
- ถ้าไม่ใช้ cloud และ local benchmark ไม่ทัน ให้ส่งงาน replication study ที่ระบุขอบเขตและความคลาดเคลื่อนอย่างตรงไปตรงมา ไม่รับประกันความสำเร็จเทียม

แคชใน manifest มี payload 267,895,111,680 bytes ≈ 249.5 GiB; การสร้างแผนแบบไม่อ่าน tensors ที่วัดจริงวันที่ 9 ก.ย. ใช้ 11.888 วินาที และ peak Python allocations 17.551 MiB (วัดด้วย tracemalloc ไม่ใช่ RSS รวมของ process) ตัวเลขนี้เป็นการสร้างแผน ไม่ใช่ throughput ฝึกโมเดล

## ลดกฎที่เสียเวลาโดยไม่ลดความน่าเชื่อถือ

- ใช้แผนที่ตรวจแล้วและ digest ที่เครื่องตรวจได้ ไม่ใช้การพิมพ์ประโยคยืนยันยาวซ้ำ ๆ; agent ดำเนินงานในขอบเขตที่อนุญาตได้
- มี reviewer สำหรับจุดเสี่ยง ไม่ต้องสร้าง gate/review หลายสิบรุ่นสำหรับการเปลี่ยนข้อความ
- รักษา experiment ID + attempt ID; พิจารณา checkpoint recovery รุ่นใหม่ที่บันทึก model/optimizer/RNG/sampler และผ่าน interruption-equivalence test แทนห้าม resume ทุกกรณี แต่ **รอบนี้ยังไม่เปิด resume** และไม่ resume r1–r19
- มี resource admission และ timeout จริง; ใช้ heartbeat แจ้งเฉพาะความเปลี่ยนแปลง/ล้มเหลว/ต้องการผู้ใช้ ไม่ส่งสถานะเก่าซ้ำเป็นชั่วโมง
- การผิดจาก manuscript เช่น TF2.4, overlap inference, microbatch/BN semantics, clipping ต้องอยู่ใน deviation table เสมอ

## แหล่งความรู้และขอบเขตที่ใช้

งานหลักเป็นบทความ [Aram et al., Scientific Reports (20 กรกฎาคม 2026)](https://www.nature.com/articles/s41598-026-62832-5) ซึ่งอธิบาย pipeline สามขั้นและรายงาน accuracy 83%; appendix ระบุเลือก hyperparameter จาก validation ไม่ใช่ test โค้ดผู้เขียนแยกอ้างอิงที่ [release v1.0](https://github.com/SadafAram/Sleep-Stage-Classification/tree/v1.0) ความแตกต่างฉบับ manuscript/author code ในแผนเดิมต้องตรวจเทียบและระบุ ไม่ผสมแล้วเรียก exact

เปิดอ่าน BrainCode101 ผ่านคอร์ส [Week 6 – Signal Processing](https://braincode101.com/courses/h6ptp98TIiw4yUx93bMd) ที่ฝังบทเรียน [Sampling and Signal Averaging](https://course2026-braincodecamp.web.app/Fundamentals/SignalProcessing/signal_processing_part1_sampling_averaging.html) ได้แล้ว ใช้เป็นพื้นฐานการตรวจ sampling/time-frequency ไม่ใช้เป็นหลักฐานว่าโมเดลทำได้ตาม paper และไม่เปลี่ยน preprocessing เป็น averaging ข้ามช่วงการนอนเพียงเพราะบทเรียนมีตัวอย่าง averaging

## ขั้นถัดไปที่ยังต้องทำจริง

1. ใช้โค้ดที่ผ่าน review ทำ bounded live canary/throughput benchmark เมื่อมี RAM เพียงพอ พร้อมข้อมูล label coverage และคำสั่ง/ผลที่บันทึกได้
2. สรุป compute budget และตัดสิน local/cloud; ยังไม่มี ETA full study ที่วัดจาก workload เต็ม
3. ทำ runner สำหรับ **full held-out evaluation** แยกจาก smoke runner ปัจจุบัน และ freeze primary protocol ก่อนฝึกยาว

เอกสารนี้เป็นแผนส่งมอบและสถานะจริง ไม่ใช่หลักฐานว่า research สำเร็จแล้ว และไม่มี production training ถูกเปิดโดยรอบแก้โค้ดนี้

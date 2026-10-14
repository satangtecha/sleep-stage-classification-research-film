# ข้อเสนอโครงงานวิจัย

## ชื่อโครงงาน

**การจำแนกระยะการนอนหลับจากสัญญาณ EEG ช่องเดียวด้วย Synchrosqueezed Transform และการเรียนรู้ลำดับด้วย CNN–GRU**

ชื่อภาษาอังกฤษ: **Single-Channel EEG Sleep Stage Classification Using Synchrosqueezed Time–Frequency Representation and CNN–GRU Sequence Learning**

ผู้จัดทำ: ........................................................  
สาขา/หน่วยงาน: ....................................................  
อาจารย์ที่ปรึกษา: ..................................................

## 1. บทคัดย่อ

การจำแนกระยะการนอนหลับเป็นขั้นตอนสำคัญของการประเมินคุณภาพการนอนและการวิจัยด้าน sleep medicine โดยทั่วไปต้องใช้ polysomnography ซึ่งมีหลาย channel และต้องอาศัยผู้เชี่ยวชาญในการให้คะแนน sleep stage งานวิจัยนี้เสนอการพัฒนาโมเดลจำแนกระยะการนอนหลับ 5 ระยะ ได้แก่ Wake, N1, N2, N3 และ REM จาก EEG เพียงช่องเดียว โดยใช้ Fpz-Cz จากชุดข้อมูล Sleep-EDF

แนวทางหลักอ้างอิงงานล่าสุดที่ใช้ synchrosqueezed transform เพื่อสร้าง time–frequency representation, CNN เพื่อเรียนรู้คุณลักษณะของช่วงสัญญาณสั้น, contrastive learning เพื่อปรับปรุง representation และ GRU สองชั้นเพื่อเรียนรู้ความต่อเนื่องของลำดับ sleep epochs งานจะประเมินด้วย subject-wise split เพื่อป้องกันข้อมูลจากบุคคลเดียวกันรั่วข้ามชุด train/test และรายงาน accuracy, macro-F1, per-stage F1, balanced accuracy และ Cohen’s kappa ผล pilot บนข้อมูล Sleep-EDF 4 คืนสามารถรัน pipeline ได้ครบ โดยแบบไม่ถ่วง class ได้ accuracy 25.0% และแบบ class-weighted ได้ 46.9%; ผลดังกล่าวใช้เป็น preliminary result ไม่ใช่ผลสรุปของโครงการ

## 2. ที่มาและความสำคัญ

การนอนหลับประกอบด้วยระยะที่มีลักษณะทางสรีรวิทยาแตกต่างกัน การแบ่งเป็น Wake, N1, N2, N3 และ REM มักทำเป็น epoch ละ 30 วินาทีจากสัญญาณ EEG, EOG และ EMG อย่างไรก็ตาม การทำ scoring ด้วยผู้เชี่ยวชาญใช้เวลา มีต้นทุน และอาจมีความแตกต่างระหว่างผู้ประเมิน จึงมีความสนใจพัฒนา automated sleep staging จากสัญญาณที่มีจำนวน channel น้อยลง

งานล่าสุดใน Scientific Reports ใช้ EEG ช่องเดียว Fpz-Cz จาก Sleep-EDF และรายงาน accuracy 83% โดยประกอบด้วย synchrosqueezed transform, CNN pretraining, contrastive representation learning และ GRU สองชั้นสำหรับลำดับสัญญาณ ([บทความต้นฉบับ](https://www.nature.com/articles/s41598-026-62832-5)) แนวทางนี้เหมาะสำหรับนำมาทำซ้ำในโครงงาน เพราะมีโครงสร้างโมเดลที่เชื่อมโยงกับคุณสมบัติของ EEG ทั้งในโดเมนเวลา ความถี่ และบริบทของ epoch ก่อนหน้า

โครงการนี้จึงมุ่งสร้าง implementation ที่ตรวจสอบได้ ใช้ dataset สาธารณะ และประเมินอย่างถูกต้องในระดับ subject เพื่อเป็นพื้นฐานสำหรับงานต่อยอด เช่น wearable EEG, การทดสอบข้าม dataset และการตรวจสอบความน่าเชื่อถือของโมเดล

## 3. ปัญหาวิจัย

1. สามารถจำแนก sleep stage 5 ระยะจาก EEG ช่องเดียวได้ดีเพียงใด
2. การใช้ time–frequency representation และ sequence learning ช่วยเพิ่มผลลัพธ์เหนือ CNN ที่ดูแต่ epoch เดี่ยวหรือไม่
3. class imbalance โดยเฉพาะ N1 และ REM ส่งผลต่อผลลัพธ์มากเพียงใด และ class-weighted loss ช่วยได้หรือไม่
4. โมเดลที่พัฒนาสามารถ generalize ไปยัง subject ที่ไม่เคยเห็นระหว่างการฝึกได้หรือไม่

## 4. วัตถุประสงค์

### วัตถุประสงค์หลัก

พัฒนาและประเมินโมเดล deep learning สำหรับจำแนก sleep stage 5 ระยะจาก EEG ช่องเดียว โดยอ้างอิงแนวทาง SST–CNN–contrastive learning–GRU จากงานวิจัยล่าสุด

### วัตถุประสงค์ย่อย

1. เตรียมและตรวจสอบชุดข้อมูล Sleep-EDF พร้อม labels ที่สอดคล้องกัน
2. พัฒนา preprocessing และ synchrosqueezed time–frequency representation สำหรับ EEG epoch ละ 30 วินาที
3. เปรียบเทียบ CNN baseline กับโมเดลที่เพิ่ม contrastive learning และ GRU
4. วิเคราะห์ผลกระทบของ class weighting ต่อ N1, N2, N3 และ REM
5. ประเมินโมเดลด้วย subject-wise evaluation และจัดทำโค้ด/ผลการทดลองที่ทำซ้ำได้

## 5. สมมติฐานการวิจัย

1. โมเดล SST–CNN–GRU จะมี macro-F1 สูงกว่า CNN baseline ที่ใช้ epoch เดี่ยว
2. การใช้ sequence learning จะช่วยให้การจำแนก N1, N2 และ REM ดีขึ้น เนื่องจาก sleep stage มีความต่อเนื่องตามเวลา
3. class-weighted loss จะช่วยเพิ่ม macro-F1 และ per-stage F1 ของ class ที่มีจำนวนตัวอย่างน้อย โดยอาจแลกกับ accuracy ของ class ที่พบบ่อย
4. ผลลัพธ์จะลดลงเมื่อทดสอบกับ subject ที่ไม่อยู่ในชุด train แต่ยังควรสูงกว่า majority-class baseline อย่างมีนัยสำคัญเชิงปฏิบัติ

## 6. ขอบเขตการวิจัย

### ข้อมูล

ใช้ [Sleep-EDF Expanded](https://physionet.org/content/sleep-edfx/1.0.0/) เป็น dataset หลัก ซึ่งมี PSG หลาย channel และ hypnogram ที่ผู้เชี่ยวชาญให้ label งานนี้จะใช้ Fpz-Cz เป็น input หลัก และใช้ labels 5 classes ได้แก่ W, N1, N2, N3 และ REM โดยรวม R&K stage 3 และ 4 เป็น N3 และตัด epoch ที่เป็น unknown หรือ movement ออกจากการฝึก

ระยะ pilot ใช้ข้อมูลที่ดาวน์โหลดและตรวจสอบแล้ว 4 คืน จำนวน 588 scored epochs เพื่อยืนยัน pipeline ระยะหลักจะขยายไปยัง Sleep-EDF ตามทรัพยากรคอมพิวเตอร์และเวลาที่มี การแบ่ง train/validation/test จะทำระดับ subject ก่อนการแบ่ง epoch เพื่อป้องกัน data leakage

### โมเดล

โมเดลหลักประกอบด้วย:

1. EEG Fpz-Cz ความยาว 30 วินาที และ resample เป็น 100 Hz หรือ 3,000 samples ต่อ epoch
2. Synchrosqueezed transform เพื่อสร้าง representation ใน time–frequency domain
3. การแบ่ง representation เป็นช่วงย่อยขนาด 256 samples
4. CNN encoder สำหรับเรียนรู้ feature ของช่วงย่อย
5. Contrastive learning โดยใช้ amplitude scaling, masking และ perturbation ขนาดเล็กเป็น augmentation
6. Time-distributed CNN สำหรับรวม feature ของช่วงย่อยทั้งหมด
7. GRU 2 ชั้นสำหรับเรียนรู้ลำดับ feature และทำนาย sleep stage ของ epoch

### สิ่งที่อยู่นอกขอบเขต

โครงการนี้ไม่มุ่งสร้างอุปกรณ์ EEG ใหม่ ไม่วินิจฉัยโรค และไม่อ้างว่าโมเดลสามารถใช้แทนแพทย์หรือผู้เชี่ยวชาญได้ ผลลัพธ์เป็นงานวิจัยเชิง algorithmic validation จากข้อมูลสาธารณะ

## 7. วิธีดำเนินการวิจัย

### ขั้นที่ 1: เตรียมข้อมูล

1. ดาวน์โหลด EDF และ hypnogram จาก Sleep-EDF
2. อ่าน channel Fpz-Cz และตรวจสอบ sampling rate, missing values และความยาวสัญญาณ
3. แบ่งสัญญาณเป็น epoch ละ 30 วินาทีให้ตรงกับ hypnogram
4. resample เป็น 100 Hz, ทำ per-epoch z-score และจัดการ epoch ที่สั้นกว่าความยาวมาตรฐานด้วย padding ตามที่กำหนดไว้ล่วงหน้า
5. ทำ label mapping เป็น W/N1/N2/N3/REM
6. แบ่งข้อมูลเป็น train/validation/test ระดับ subject ก่อนทำ augmentation หรือสร้าง batch ใด ๆ

### ขั้นที่ 2: สร้าง baseline

จะสร้าง baseline อย่างน้อย 2 แบบ:

- majority-class baseline เพื่อดูผลจาก class imbalance
- CNN baseline ที่ใช้ time–frequency representation แต่ไม่ใช้ contrastive learning และ GRU

### ขั้นที่ 3: ฝึกโมเดลหลัก

ฝึกเป็น 3 stage:

1. pretrain CNN encoder ด้วยช่วงย่อย 256 samples
2. fine-tune encoder ด้วย contrastive learning
3. ฝึก CNN–GRU sequence classifier ด้วย labels ของ full epoch

จะเก็บ random seed, hyperparameters, data split, checkpoint และ log ทุกครั้ง เพื่อให้สามารถทำซ้ำและตรวจสอบความแตกต่างระหว่างการทดลองได้

### ขั้นที่ 4: Ablation study

เปรียบเทียบผลขององค์ประกอบสำคัญดังนี้:

1. CNN baseline เทียบกับ CNN + GRU
2. ไม่มี contrastive learning เทียบกับมี contrastive learning
3. unweighted cross-entropy เทียบกับ class-weighted cross-entropy
4. epoch เดี่ยวเทียบกับ sequence context

### ขั้นที่ 5: ประเมินผล

ตัวชี้วัดหลักคือ macro-F1 และ balanced accuracy เนื่องจากจำนวนตัวอย่างแต่ละ sleep stage ไม่เท่ากัน ตัวชี้วัดประกอบคือ accuracy, per-stage precision/recall/F1, Cohen’s kappa และ confusion matrix โดยจะรายงานค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐานเมื่อใช้หลาย subject-wise folds

## 8. เกณฑ์ความสำเร็จ

### เกณฑ์ด้านระบบ

- pipeline ตั้งแต่โหลดข้อมูลจนถึง evaluation ทำงานซ้ำได้จากคำสั่งเดียว
- ไม่มี subject เดียวกันอยู่ทั้ง train และ test
- มีผล baseline, ablation และ confusion matrix ครบ

### เกณฑ์ด้านผลลัพธ์

- โมเดลหลักมี macro-F1 สูงกว่า majority baseline และ CNN baseline
- class-weighted model เพิ่ม macro-F1 ของ class ที่มีจำนวนน้อยโดยไม่ทำให้ระบบล้มเหลวใน class อื่น
- เป้าหมายเชิงวิจัยคือเข้าใกล้ช่วง accuracy 75–83% บน full Sleep-EDF เมื่อใช้ protocol และทรัพยากรใกล้เคียงงานอ้างอิง ทั้งนี้เป็นเป้าหมาย ไม่ใช่ผลที่รับประกันล่วงหน้า

## 9. ผล pilot เบื้องต้น

การทดลองเบื้องต้นบน Sleep-EDF 4 คืน ใช้ train 2 คืน, validation 1 คืน และ test 1 คืน รวม 588 scored epochs ได้ผลดังนี้:

| Model | Accuracy | Macro-F1 | Kappa |
|---|---:|---:|---:|
| SST-like + CNN + contrastive + GRU | 25.0% | 0.219 | 0.102 |
| เพิ่ม class-weighted loss | 46.9% | 0.303 | 0.298 |

ผล pilot ยืนยันว่า implementation และ label pipeline ทำงานได้ แต่ยังไม่ใช่ผลสุดท้ายของโครงการ เนื่องจากใช้จำนวนคืนและจำนวน epoch จำกัด รวมถึงจำนวน training epochs ที่สั้นเพื่อให้รันบน CPU ได้

## 10. แผนการดำเนินงาน

| สัปดาห์ | งาน |
|---|---|
| 1 | ทบทวนวรรณกรรมและกำหนด protocol, label mapping และเกณฑ์ evaluation |
| 2 | ดาวน์โหลด ตรวจสอบ และจัดโครงสร้าง Sleep-EDF |
| 3 | สร้าง preprocessing, SST representation และ majority/CNN baselines |
| 4 | พัฒนา CNN encoder และ pretraining |
| 5 | เพิ่ม contrastive learning และ GRU sequence classifier |
| 6 | รัน full experiment และ class-weighted ablation |
| 7 | ทำ subject-wise evaluation, error analysis และ confusion matrix |
| 8 | สรุปผล จัดทำรายงาน โค้ด และ reproducibility package |

## 11. ความเสี่ยงและแนวทางลดความเสี่ยง

| ความเสี่ยง | ผลกระทบ | แนวทางรับมือ |
|---|---|---|
| GPU หรือเวลาไม่พอ | train full dataset ได้ช้า | เริ่มจาก pilot subset, cache features และลด batch/epoch อย่างมีบันทึก |
| class imbalance | N1/REM ถูกทำนายน้อย | ใช้ macro-F1, class weighting และรายงาน per-stage metrics |
| data leakage | ผลสูงเกินจริง | split ระดับ subject ก่อน preprocessing ที่เรียนรู้จากข้อมูลและก่อน augmentation |
| รายละเอียด paper ไม่เปิดครบ | ทำ exact replication ไม่ได้ | ระบุเป็น protocol-level reproduction และเปิดเผย implementation assumptions |
| ผลข้าม dataset ลดลง | generalization ต่ำ | เพิ่ม ISRUC หรือ SHHS เป็น external validation ในงานต่อยอด |

## 12. ประโยชน์ที่คาดว่าจะได้รับ

1. ได้ implementation สำหรับจำแนก sleep stage จาก EEG ช่องเดียวที่ทำซ้ำได้
2. ได้ความเข้าใจผลของ time–frequency representation, contrastive learning และ sequence modeling ต่อ sleep staging
3. ได้ baseline และ ablation ที่นำไปเปรียบเทียบกับงานวิจัยอื่นได้
4. ได้ code, configuration, metrics และผลการทดลองสำหรับต่อยอดไปยัง wearable EEG
5. ได้ข้อจำกัดที่ชัดเจนเกี่ยวกับ class imbalance, subject shift และการนำโมเดลไปใช้จริง

## 13. จริยธรรมและการใช้ข้อมูล

ใช้ข้อมูลสาธารณะที่ผ่านการ de-identification แล้ว และปฏิบัติตามเงื่อนไขการใช้งานของ dataset แต่ละแหล่ง ผลลัพธ์จะนำเสนอเพื่อการวิจัยเท่านั้น ไม่ใช้เป็นคำแนะนำทางการแพทย์หรือระบบวินิจฉัยผู้ป่วยโดยตรง

## 14. ผลส่งมอบ

- รายงานการทดลองและการวิเคราะห์ผล
- source code และ environment specification
- trained model/checkpoint ที่อนุญาตให้เผยแพร่
- ตาราง metrics, confusion matrix และ ablation study
- คู่มือ reproduction สำหรับผู้วิจัยคนอื่น

## 15. เอกสารอ้างอิงเบื้องต้น

1. [Single-channel EEG sleep stage classification using synchrosqueezed transform and sequential representation learning](https://www.nature.com/articles/s41598-026-62832-5), Scientific Reports, 2026.
2. [Sleep-EDF Expanded, PhysioNet](https://physionet.org/content/sleep-edfx/1.0.0/).
3. [SLEEPYLAND: a benchmark for sleep staging algorithms](https://www.nature.com/articles/s41746-025-02237-2), npj Digital Medicine, 2025.
4. [SleepPACNet](https://www.nature.com/articles/s41598-026-48881-w), Scientific Reports, 2026.
5. [ISRUC-Sleep Dataset](https://sleeptight.isr.uc.pt/?page_id=48).

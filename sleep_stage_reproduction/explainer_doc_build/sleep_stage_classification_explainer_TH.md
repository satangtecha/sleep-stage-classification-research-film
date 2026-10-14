# Sleep Stage Classification from Single-Channel EEG

เอกสารนี้อธิบายโครงงานตั้งแต่พื้นฐานจนถึงขั้นสูง: EEG, sleep stages, Sleep-EDF, preprocessing, SST, CNN, contrastive learning, GRU, evaluation และข้อจำกัด

## สรุปโครงงาน

เราจะใช้ EEG เพียงหนึ่ง channel จาก `Fpz-Cz` เพื่อจำแนก sleep stage เป็น 5 classes: Wake, N1, N2, N3 และ REM โดยใช้ Sleep-EDF Expanded เป็น dataset หลัก

Pipeline คือ:

`30-second EEG -> preprocessing -> SST time-frequency map -> CNN encoder -> contrastive refinement -> stacked GRU -> 5-stage prediction`

## 1. พื้นฐาน

### EEG และ BCI

EEG คือสัญญาณไฟฟ้าจากสมองที่วัดผ่าน electrodes บนหนังศีรษะ ส่วน BCI คือระบบที่ใช้สัญญาณสมองเพื่อสื่อสารหรือควบคุมอุปกรณ์ งานนี้เป็น automatic EEG sleep staging มากกว่าจะเป็น BCI สำหรับควบคุมอุปกรณ์โดยตรง

### Sleep stages

- `W`: Wake
- `N1`: ช่วงเปลี่ยนจากตื่นเข้าสู่หลับ มักจำแนกยาก
- `N2`: หลับตื้น มักมีจำนวนมาก
- `N3`: หลับลึก มี slow-wave/delta เด่น
- `REM`: Rapid Eye Movement

หนึ่ง epoch ยาว 30 วินาที หาก sampling rate เท่ากับ 100 Hz จะมี 3,000 samples

### EEG rhythms

- Delta: 0.5-4 Hz
- Theta: 4-8 Hz
- Alpha: 8-13 Hz
- Beta: 13-30 Hz
- Gamma: มากกว่า 30 Hz

## 2. Dataset

Dataset หลักคือ [Sleep-EDF Expanded](https://physionet.org/content/sleep-edfx/1.0.0/) จาก PhysioNet มี PSG, EEG, EOG, EMG และ hypnogram เราเลือกใช้ Fpz-Cz เพียง channel เดียว และใช้ hypnogram เป็น ground truth

Local pilot ที่มีอยู่: 4 คืนจาก 2 subjects, 588 scored epochs ใช้ตรวจ pipeline เท่านั้น ผล pilot ยังไม่ใช่ final result เพราะต้องแก้ subject-wise split

## 3. Objective

### Primary objective

พัฒนาและประเมินระบบ deep learning ที่จำแนก sleep stage 5 classes จาก single-channel EEG โดยใช้ subject-wise split

### Secondary objectives

1. ทดสอบ SST ว่าช่วยด้าน time-frequency feature หรือไม่
2. ทดสอบ contrastive learning ว่าช่วยแยก embedding หรือไม่
3. เปรียบเทียบกับ raw CNN และ CNN-GRU baseline
4. วิเคราะห์ per-class F1 และ confusion matrix

## 4. Model

### SST

SST เปลี่ยนสัญญาณ EEG จาก time domain ให้เป็น time-frequency representation และ reassign พลังงานไปยังความถี่ที่เหมาะสม เพื่อให้โครงสร้างของ oscillation คมขึ้น

### CNN

CNN ทำหน้าที่เรียนรู้ local pattern จาก short windows หรือ SST map และเปลี่ยนข้อมูลเป็น embedding

### Contrastive learning

ฝึกให้ embedding ของตัวอย่างที่ควรเหมือนกันอยู่ใกล้กัน และ embedding ของตัวอย่างต่าง class อยู่ห่างกัน

### GRU

GRU เรียนรู้ลำดับของ feature จาก short windows ภายใน epoch เดียว ใน implementation ปัจจุบันยังไม่ได้ model sequence ของทั้งคืนแบบ full-night context

## 5. Evaluation

ต้องใช้ subject-wise split เพื่อไม่ให้ subject เดียวกันอยู่หลายชุด และควรรายงาน:

- Accuracy
- Precision, Recall, F1-score
- Macro-F1
- Cohen's kappa
- Confusion matrix
- Per-class metrics

Baseline/ablation ที่แนะนำ:

1. Majority baseline
2. Raw CNN
3. CNN-GRU
4. SST-CNN
5. SST + contrastive learning
6. Full SST + CNN + contrastive + GRU

## 6. ข้อจำกัด

- ข้อมูลมีจำนวน subject จำกัด
- class imbalance โดยเฉพาะ N1
- single-channel ขาดข้อมูลจาก EOG/EMG
- dataset จากห้องแล็บอาจต่างจาก wearable/home setting
- implementation ปัจจุบันเป็น reproduction แบบใกล้เคียง ไม่ใช่การยืนยันว่าเหมือนต้นฉบับทุกจุด
- ผล accuracy ของ paper ต่าง ๆ เปรียบเทียบตรง ๆ ไม่ได้หาก protocol ต่างกัน
- งานนี้ไม่ใช่ระบบวินิจฉัยโรค

## 7. Paper หลักและแหล่งอ้างอิง

- [SST + sequential representation learning, Scientific Reports 2026](https://www.nature.com/articles/s41598-026-62832-5)
- [Rhythm representation and contrastive learning](https://www.sciencedirect.com/science/article/pii/S1746809425011346)
- [MultiScaleSleepNet](https://www.mdpi.com/1424-8220/25/20/6328)
- [SleepFocalNet](https://link.springer.com/article/10.1007/s10044-025-01475-0)
- [MNE-Python](https://mne.tools/stable/index.html)
- [PyTorch](https://pytorch.org/)

เอกสารอ้างอิงฉบับเต็มอยู่ใน [research_links.md](../research_links.md)

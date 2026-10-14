# Sleep Stage Classification Research Links

รวบรวมแหล่งข้อมูลและลิงก์ที่ใช้สำหรับโครงงาน **single-channel EEG sleep stage classification**

## 1. Main Dataset

### Sleep-EDF Expanded — PhysioNet

- Dataset page: <https://physionet.org/content/sleep-edfx/1.0.0/>
- Sleep Cassette directory: <https://physionet.org/content/sleep-edfx/1.0.0/sleep-cassette/>
- Official description: <https://physionet.org/content/sleep-edfx/1.0.0/#files-panel>

ข้อมูลที่ใช้ในโครงงานหลัก:

- EEG channel: `Fpz-Cz`
- Epoch length: 30 seconds
- Labels: Wake, N1, N2, N3, REM
- Data format: EDF/EDF+
- Reference annotations: hypnogram files

> หมายเหตุ: ไฟล์ Sleep-EDF ใช้รหัสชื่อที่บอก subject และ night ดังนั้นการแบ่ง train/validation/test ควรแบ่งตาม subject ไม่ใช่สุ่มแบ่ง epoch อย่างเดียว

## 2. Research Paper We Follow

### Single-channel EEG sleep stage classification using synchrosqueezed transform and sequential representation learning

- Article: <https://www.nature.com/articles/s41598-026-62832-5>
- DOI: <https://doi.org/10.1038/s41598-026-62832-5>
- Published in: *Scientific Reports*, 2026

วิธีการหลักของงานนี้:

1. ใช้ single-channel EEG จาก `Fpz-Cz`
2. แบ่ง EEG 30 วินาทีออกเป็นช่วงย่อย 256 samples
3. แปลงสัญญาณเป็น time-frequency representation ด้วย Synchrosqueezed Transform (SST)
4. ใช้ CNN เพื่อเรียนรู้ feature เบื้องต้น
5. ใช้ contrastive learning เพื่อทำให้ feature ของแต่ละ sleep stage แยกจากกันชัดขึ้น
6. ใช้ time-distributed CNN และ stacked GRU สำหรับการจำลอง temporal pattern
7. จำแนกเป็น 5 sleep stages

ผลที่รายงานในบทความ: accuracy ประมาณ 83% บน Sleep-EDF

## 3. Related Research for Comparison

### Rhythm representation and contrastive learning

- Single-channel EEG-based sleep staging with rhythm representation and contrastive learning: <https://www.sciencedirect.com/science/article/pii/S1746809425011346>
- DOI: <https://doi.org/10.1016/j.bspc.2025.108623>

แนวคิดสำคัญคือแยก rhythm ของ EEG เช่น delta, theta, alpha, beta และ gamma แล้วรวมกับ contrastive learning

รายงานผล accuracy 86.6% บน Sleep-EDF และ 87.2% บน MASS-SS3 แต่ protocol และ data split อาจแตกต่างจากงานหลัก จึงไม่ควรเปรียบเทียบตัวเลขโดยตรงโดยไม่ตรวจสอบรายละเอียด

### MultiScaleSleepNet

- Article: <https://www.mdpi.com/1424-8220/25/20/6328>
- DOI: <https://doi.org/10.3390/s25206328>

ใช้ hybrid architecture ประกอบด้วย CNN, BiLSTM และ Transformer เพื่อเรียนรู้ทั้ง temporal และ spectral feature จาก single-channel EEG

รายงานผล accuracy 88.6% บน Sleep-EDF และ 85.6% บน Sleep-EDF Expanded

### SleepFocalNet

- Article: <https://link.springer.com/article/10.1007/s10044-025-01475-0>
- DOI: <https://doi.org/10.1007/s10044-025-01475-0>

ใช้ temporal focal modulation network เพื่อประมวลผลลำดับ EEG ระยะยาวและจับ sleep-stage transition ตลอดทั้งคืน

รายงานผล accuracy 88.5% บน SleepEDF-20 และ 85.5% บน SleepEDF-78

### SleepMFormer

- Article: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12838882/>

เป็น efficient Transformer สำหรับ single-channel EEG และใช้ supervised contrastive learning เพื่อเพิ่มความทนทานของ feature

### MBSleepNet

- Article: <https://www.sciencedirect.com/science/article/pii/S1746809425000643>
- DOI: <https://doi.org/10.1016/j.bspc.2025.107553>

ใช้ multi-branch Transformer และ CNN เพื่อรวม time-domain, frequency-domain และ global feature จากข้อมูลหลาย channel

> งานกลุ่มนี้ใช้เป็น related work และ baseline comparison ไม่ได้หมายความว่าเป็นวิธีที่เหมาะกับโครงงานเราที่สุด เพราะบางงานใช้หลาย channel, transfer learning หรือ sequence ที่ยาวกว่า

## 4. Dataset Alternatives and Future Extensions

### Dreem Open Dataset — DOD-H/O

- Zenodo record: <https://zenodo.org/records/15900394>

เป็น dataset ขนาดใหญ่จากอุปกรณ์ wearable และ polysomnography เหมาะสำหรับการทดสอบ generalization ในอนาคต แต่ไม่จำเป็นสำหรับ prototype แรกของโครงงาน

### Sleep Heart Health Study — SHHS

- National Sleep Research Resource: <https://sleepdata.org/datasets/shhs>

เป็นอีก dataset ขนาดใหญ่ที่มีข้อมูล PSG และใช้ในงานวิจัย sleep staging หลายงาน

## 5. Signal Processing and Machine Learning Tools

### MNE-Python

- Official website: <https://mne.tools/stable/index.html>
- Reading EDF files: <https://mne.tools/stable/auto_tutorials/intro/10_overview.html>

ใช้สำหรับอ่านและตรวจสอบข้อมูล EEG/EDF รวมถึง signal preprocessing

### PyTorch

- Official website: <https://pytorch.org/>
- Documentation: <https://docs.pytorch.org/docs/stable/index.html>

ใช้สร้าง CNN, GRU, contrastive learning และ training pipeline

### WFDB Python

- Official documentation: <https://wfdb.readthedocs.io/en/latest/>
- PhysioNet WFDB package: <https://github.com/MIT-LCP/wfdb-python>

ใช้สำหรับจัดการข้อมูล waveform และ metadata จาก PhysioNet

### SciPy Signal Processing

- Documentation: <https://docs.scipy.org/doc/scipy/reference/signal.html>

ใช้สำหรับ filtering, STFT และการประมวลผลสัญญาณ EEG เบื้องต้น

## 6. Local Project Files

- [Research report](research_report_TH.md)
- [Thai proposal](sleep_stage_classification_proposal_TH.md)
- [Main reproduction script](run_sst_gru.py)
- [Thai presentation script](sleep_stage_pitch_script_TH.md)
- [English presentation script](sleep_stage_pitch_script_EN.md)
- [English pitch deck — PPTX](pitch_deck_build/sleep_stage_classification_pitch_EN.pptx)
- [English pitch deck — PDF](pitch_deck_build/output/pdf/sleep_stage_classification_pitch_EN.pdf)

## 7. Research Direction

### Project objective

พัฒนาและประเมินระบบที่จำแนก sleep stage จาก EEG เพียงหนึ่ง channel โดยศึกษาว่า time-frequency representation, contrastive learning และ sequential modeling ช่วยเพิ่มประสิทธิภาพเมื่อเทียบกับ baseline CNN/GRU ได้หรือไม่

### Recommended evaluation

- แบ่งข้อมูลแบบ subject-wise split
- รายงาน accuracy, macro-F1 และ Cohen's kappa
- แสดง confusion matrix และ per-stage F1-score
- ให้ความสำคัญกับ N1 เพราะเป็น class ที่มักจำแนกได้ยาก
- เปรียบเทียบกับ baseline ที่เรียบง่ายก่อนเพิ่ม SST และ contrastive learning

### Important interpretation

งานที่เลือกเป็นงานล่าสุดและเหมาะกับการทำซ้ำในทรัพยากรของเรา แต่ไม่ควรเรียกว่าเป็นวิธีที่มี accuracy สูงสุดโดยรวม เพราะงานอื่นรายงานตัวเลขสูงกว่า และแต่ละงานใช้ dataset, split, channel และ training protocol แตกต่างกัน


# สมุดทดลองสำหรับเปิดดูใน VS Code

ชุดนี้ทำหน้าที่เหมือน “ห้องทดลองที่เปิดดูย้อนหลังได้” และไม่เริ่ม training ใหม่ ทุก notebook อ่านข้อมูล/ผลลัพธ์จริงแบบ read-only แล้วสร้างกราฟให้คนที่เพิ่งเข้ามาเข้าใจโครงการตามลำดับ มีทั้งต้นฉบับ VS Code และหน้าอ่านผลใน Quant OS

## เปิดแบบเว็บไซต์ใน Quant OS

เปิด Quant OS เดิม แล้วเลือก **Research → Sleep Stage** หรือ [เปิดหน้าบทเรียน](http://127.0.0.1:8787/sleep-stage/index.html) / [เปิดใน dashboard](http://127.0.0.1:8787/#sleepstage)

- เรียง notebook 00–05 ต่อเนื่อง พร้อมสารบัญ โค้ด และ output ที่บันทึกไว้ทุกเซลล์
- คลิกกราฟเพื่อดูขนาดเต็ม กดซ่อนโค้ดเพื่ออ่านเฉพาะคำอธิบาย/ผล หรือดาวน์โหลด notebook กลับไปเปิดใน VS Code
- ธีมเริ่มต้นเป็นดำ–เทาและลิงก์สีฟ้า สลับเป็นโหมดสว่างได้ โค้ด Python แยกสีคำสั่ง/ชื่อ/ฟังก์ชัน/ข้อความ/ตัวเลข/คอมเมนต์ด้วย Pygments ขณะ export (ไม่ได้ execute โค้ด)
- หน้าเว็บเป็น snapshot ไม่ใช่ตัวรัน Python และไม่ใช่สถานะสด ไม่เทรนใหม่ ไม่ใช้ GPU และไม่เรียก API เทรด
- แต่ละบทมีชื่อไฟล์ต้นทาง เวลาแก้ไข และ SHA-256; รายการทั้งหมดอยู่ใน `strategy_lab/manager/sleep-stage/manifest.json`
- เวอร์ชันใน Quant OS ยังเป็น localhost; ฉบับสาธารณะแยกโฮสต์ตามหัวข้อด้านล่าง

หาก Quant OS ยังไม่เปิด ให้เรียก `strategy_lab\launch_manager_dashboard.ps1` จาก workspace หลัก

หลังอัปเดตและบันทึก output ของ notebook ให้สร้างเว็บใหม่ (ไม่ execute notebook):

```powershell
# เรียกจาก sleep_stage_reproduction
.\.venv\Scripts\python.exe .\walkthrough\build_course.py
.\.venv\Scripts\python.exe -m unittest discover -s .\walkthrough -p test_build_course.py
```

ตัว exporter ใช้ `mistune` และ `bleach` ตาม `requirements-walkthrough.txt`; template อยู่ใน `walkthrough/web/` และเขียนเฉพาะ static files ของตัวอ่านที่ `strategy_lab/manager/sleep-stage/` ไม่แก้ run/checkpoint หรือฐานข้อมูล Quant OS

## ฉบับสาธารณะ (17 กันยายน 2026)

[เปิด Sleep Stage Research Notebook](https://sleep-stage-research-notebook.satangtecha.chatgpt.site)

- ผู้มีลิงก์เปิดอ่านได้โดยไม่ล็อกอินและไม่ต้องเปิดคอมผู้วิจัยไว้ เผยแพร่เฉพาะ reader แบบ static ไม่เปิด Quant OS, ระบบเทรด, API, dataset หรือ checkpoint
- เป็น snapshot ของ notebook 00–05 ไม่อัปเดตผลจากเครื่องอัตโนมัติ ไม่รัน training
- `build_public_course.py` สร้างฉบับเผยแพร่โดยเปลี่ยนเส้นทางเฉพาะเครื่องเป็นตัวอย่าง คงตัวเลขและ PNG เดิม พร้อม hash ต้นฉบับและฉบับเผยแพร่แยกกันใน manifest
- notebook ที่ดาวน์โหลดเป็นฉบับเผยแพร่ ไม่ใช่แพ็กเกจพร้อมรัน: ยังต้องมีโค้ดประกอบและข้อมูลบนเครื่องตนเอง
- เพิ่มคำเตือนการตีความภาพบท 05: EEG/STFT กับ SST ตัวอย่างเป็นคนละช่วงเวลา ไม่ควรตีความเป็นภาพก่อน–หลังของ epoch เดียวกัน
- Site checkout แยกจาก Git workspace หลักที่ `E:\blp\sleep_stage_reproduction\public-reader-site`; ใช้ `.openai/hosting.json` ของที่นั่นสำหรับอัปเดต Site เดิม ห้ามสร้าง Site ซ้ำ
- ก่อนเผยแพร่รอบใหม่ให้ export ไปโฟลเดอร์ว่าง ตรวจ `validate_public()` และ `test_build_public_course.py` ก่อนเปลี่ยนชุด `dist/` เดิม ตัว exporter ปฏิเสธการเขียนทับ output ที่ไม่ว่างโดยตั้งใจ
- การตรวจรอบแรก: 18 tests ผ่าน, ตรวจทานอิสระและเพิ่ม guard สำหรับ path/PNG metadata, deploy สำเร็จ และ HTTP แบบไม่มี credentials เปิดหน้าและ manifest ได้

การแพ็กบน Windows ให้ใช้ Git Bash กับ `TAR_OPTIONS=--force-local` สำหรับ Sites helper (มิฉะนั้น WSL bash อาจอ่าน Windows path ไม่ได้ และ tar อาจตีความชื่อไดรฟ์เป็น remote host) ไม่ต้องเปลี่ยนการตั้งค่าระบบถาวร

## เปิดใช้งาน

1. เปิดโฟลเดอร์ `sleep_stage_reproduction` ใน VS Code
2. ติดตั้ง extension ที่ VS Code แนะนำ: Python และ Jupyter
3. เลือก interpreter `.venv\Scripts\python.exe`
4. เปิด [00_start_here.ipynb](notebooks/00_start_here.ipynb) แล้วกด **Run All**

ผลลัพธ์ถูก execute ไว้ล่วงหน้าแล้ว จึงอ่านกราฟได้ทันทีแม้ยังไม่กดรันใหม่

## ลำดับการอ่าน

1. [00_start_here.ipynb](notebooks/00_start_here.ipynb) — เป้าหมายและสถานะหลักฐาน
2. [01_data_and_eeg.ipynb](notebooks/01_data_and_eeg.ipynb) — EEG จริงและ class distribution
3. [02_sst_representation.ipynb](notebooks/02_sst_representation.ipynb) — SST tensor จริงจาก cache
4. [03_model_and_protocol.ipynb](notebooks/03_model_and_protocol.ipynb) — pipeline 3 stages และ hardware adaptation
5. [04_results_and_next_steps.ipynb](notebooks/04_results_and_next_steps.ipynb) — ผล r19, confusion matrix, blocker และงานถัดไป
6. [05_embedding_and_transform_visuals.ipynb](notebooks/05_embedding_and_transform_visuals.ipynb) — sliding DFT/SST และ t-SNE จาก embedding จริง

## ดูกราฟทันทีโดยไม่ต้องกด Run

เมื่อ execute notebook 05 แล้ว ภาพขนาดเต็มจะอยู่ที่:

- [Sliding DFT และ SST จริง](figures/01_sliding_dft_and_actual_sst.png)
- [t-SNE ของ r19 Stage-2 embeddings](figures/02_r19_stage2_tsne.png)

ภาพเหล่านี้สร้างจาก EEG/cache/checkpoint จริง ไม่ใช่ข้อมูลสุ่ม กราฟ t-SNE เป็น post-hoc visualization เท่านั้น และไม่เปลี่ยนสถานะผลวิจัยของ r19

## รันตรวจทุกเล่มอัตโนมัติ

```powershell
.\walkthrough\run_all.ps1
```

คำสั่งนี้รันเฉพาะเซลล์สาธิต ใช้ EEG 30 วินาที, SST ตัวอย่างหนึ่ง epoch, embedding visualization artifacts และ JSON metrics ที่มีอยู่แล้ว ไม่ใช้ TensorFlow/GPU และไม่สร้าง run/marker/checkpoint ใหม่

## ถ้าย้าย bulk artifacts ออกจากไดรฟ์ E

กำหนด environment variable ก่อนเปิด VS Code:

```powershell
$env:SLEEP_STAGE_BULK_ROOT = 'D:\path\to\sleep_stage_reproduction'
code .
```

## สำหรับผู้ดูแล notebook

ไฟล์ `.ipynb` สร้างจาก `build_notebooks.py` เพื่อให้ข้อความและโค้ดตรวจย้อนหลังได้:

```powershell
.\.venv\Scripts\python.exe .\walkthrough\build_notebooks.py
.\walkthrough\run_all.ps1
```

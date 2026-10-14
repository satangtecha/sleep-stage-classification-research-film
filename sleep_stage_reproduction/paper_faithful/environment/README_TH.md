# Reference environment — Phase 1

Environment นี้มีหน้าที่ตอบคำถามเดียวก่อนเริ่มงานใหญ่: โค้ด Stage 1 ของผู้วิจัยรัน forward, backward และ optimizer update หนึ่ง batch บนเครื่องนี้ได้หรือไม่

## เส้นทางที่เลือก

- ใช้ Ubuntu บน WSL2 เพราะมองเห็น NVIDIA RTX 3050 6 GB อยู่แล้ว
- ใช้ micromamba prefix แยกที่ `/home/techatat/.local/share/sleep-stage-paper/`
- ล็อก Python 3.7 + TensorFlow GPU 2.4 + TensorFlow Addons 0.12 ตาม `requirements.txt` ของผู้วิจัย
- ใช้ CUDA 11.0 + cuDNN 8.0 ใน environment ไม่แก้ CUDA ของ Windows
- ยังไม่ติดตั้ง `ssqueezepy` ใน Phase 1 เพราะผู้วิจัยไม่ได้ระบุเวอร์ชัน การเดาเวอร์ชันอาจเปลี่ยน SST input และทำให้คำว่า paper-faithful ไม่จริง

## สร้าง environment

```bash
MAMBA_ROOT_PREFIX=/home/techatat/.local/share/sleep-stage-paper/mamba-root \
  /home/techatat/.local/share/sleep-stage-paper/bin/micromamba create -y \
  -p /home/techatat/.local/share/sleep-stage-paper/envs/tf24 \
  -f legacy-tf24.yml
```

จากนั้นรัน `probe_environment.py` และ `smoke_stage1.py` โดยเพิ่ม `<env>/lib` กับ `/usr/lib/wsl/lib` ใน `LD_LIBRARY_PATH` ผลจริงจะถูกเก็บในโฟลเดอร์ `results/`

หลังสร้าง environment ให้ใช้ `requirements-resolved.txt` เพื่อล็อก transitive pip dependencies ให้ตรงกับ environment ที่ผ่าน smoke test แล้ว ส่วน `results/wsl_tf24_probe.json` เก็บทั้ง `pip freeze` และ conda package inventory จากการรันจริง

## ผล Phase 1

- TensorFlow 2.4.0 และ TensorFlow Addons 0.12.0 import ผ่าน
- TensorFlow เปิด CUDA 11.0/cuDNN 8 และเห็น RTX 3050 เป็น `/physical_device:GPU:0`
- author Stage-1 CNN รัน batch `(2, 256, 256, 2)` ไปเป็น output `(2, 5)` ได้
- backward ให้ gradient 30/30 ตัวและ finite ทั้งหมด พร้อม optimizer update
- seed เดิมรันซ้ำได้ loss เท่ากัน `2.414372682571411`
- ยังไม่พิสูจน์ batch 128, Stage 2/3, full training หรือ accuracy ใด ๆ

## ขอบเขตของผล

Smoke test ใช้ข้อมูลสุ่มรูปทรง `(2, 256, 256, 2)` เพื่อทดสอบ compatibility ของโมเดลเท่านั้น ไม่ได้วัด accuracy และห้ามนำไปเทียบกับผล 83% ในบทความ

# รายงานผล Phase 0–1: paper-aligned sleep-stage reproduction

วันที่ตรวจ: 19 สิงหาคม 2026  
สถานะ: ผ่าน Phase 0 และ Stage-1 environment gate ของ Phase 1  
ขอบเขต: ยังไม่ดาวน์โหลด Sleep-EDF เต็มชุดและยังไม่เริ่ม training

## ผลสรุป

เครื่องนี้รันโค้ด Stage-1 CNN จาก author repository `v1.0` บน RTX 3050 ผ่าน TensorFlow GPU 2.4 ได้จริงใน WSL2 โดยใช้ environment แยกจากโปรเจกต์เดิม Forward, backward และ optimizer update หนึ่ง batch ผ่าน และรันซ้ำด้วย seed เดิมได้ loss เท่ากัน

ผลนี้พิสูจน์เพียงว่า reference stack และ Stage-1 model executable บนเครื่องนี้ ไม่ได้พิสูจน์ accuracy 83%, full batch 128, Stage 2/3 หรือ exact numerical replication

## Phase 0 — Source และ protocol lock

Source ที่ล็อก:

- paper DOI: `10.1038/s41598-026-62832-5`
- author tag: `v1.0`
- author commit: `d99a312ce44844e7b782aa8bd0d9c498074434f1`
- author `requirements.txt` SHA-256: `c5c58e57fff710d5da9b490c9f3c268f5b6a34f81d19b7a5e2d1656810ea9abb`
- dataset release: PhysioNet Sleep-EDF Expanded `1.0.0`

Protocol ที่แยกไว้:

| Protocol | จุดประสงค์ | เทียบ 83% โดยตรง |
|---|---|---|
| `PAPER_TEXT_V1` | ตามรายละเอียดใน manuscript: epoch random split, 12 windows, overlap 7, 20/20/20 epochs | ได้เฉพาะภายใต้ protocol ID นี้และ assumptions ที่บันทึกไว้ |
| `AUTHOR_CODE_V1` | ตามโค้ด release: SST settings, downstream 15 windows, overlap 64, Stage 3 50 epochs | ต้องระบุว่าเป็น code route และรายงานความต่างจาก manuscript |
| `SUBJECT_GENERALIZATION_V1` | held-out subjects เพื่อวัดการใช้กับคนใหม่ | ห้ามเทียบโดยตรง เพราะ split คนละชนิด |

ยังเรียกงานนี้ว่า exact replication ไม่ได้ เพราะไม่มี split indices, checkpoints และเวอร์ชัน/kwargs ของ `ssqueezepy` ที่สร้างผลใน paper

## Phase 1 — Reference environment

เส้นทางที่ผ่าน:

- Ubuntu บน WSL2
- Python `3.7.12`
- TensorFlow GPU `2.4.0`
- TensorFlow Addons `0.12.0`
- CUDA toolkit `11.0.3`
- cuDNN `8.0.5.39`
- GPU: NVIDIA GeForce RTX 3050 6 GB Laptop GPU, driver `546.18`
- WSL RAM ที่มองเห็น: 7,980,240 KiB และ swap 2,097,152 KiB

การระบุ distro ยึด `/etc/os-release` ซึ่งรายงาน Ubuntu 24.04.4 LTS เป็นหลัก ส่วนข้อความ `debian-trixie-sid` จาก `platform.platform()` ของ Python 3.7 มาจาก `/etc/debian_version` และถูกเก็บไว้เพียง compatibility metadata ไม่ใช่ชื่อ OS

`ssqueezepy` ยังไม่ถูกเลือกใน Phase 1 เพราะ requirements ของผู้วิจัยไม่ pin version การเลือกเองจะเปลี่ยน SST input ได้ จึงเลื่อนไปเป็น Phase-2 preprocessing lock อย่างเปิดเผย

## One-batch Stage-1 test

ทดสอบกับไฟล์ `Source/model/model.py` จาก commit ที่ล็อกไว้โดยตรง:

- synthetic input: `(2, 256, 256, 2)`
- output: `(2, 5)`
- model parameters: 1,724,757
- trainable variables: 30
- non-null gradients: 30
- gradients finite: ผ่านทั้งหมด
- optimizer step: ใช้งานจริงหนึ่งครั้ง
- loss รอบแรก: `2.414372682571411`
- loss seed-repeat: `2.414372682571411`
- GPU device: `/physical_device:GPU:0`

ข้อสังเกต runtime:

- WSL ไม่มี NUMA sysfs entry; TensorFlow default ไป NUMA node 0 และงานผ่าน
- environment ไม่มี `ptxas`; TensorFlow ใช้ NVIDIA driver PTX JIT ทำให้ process แรกช้า แต่ไม่ทำให้ smoke test ผิด
- TensorFlow จอง GPU memory สูงสุดประมาณ 4,725 MB ใน log ดังนั้น batch 128 ยังมีความเสี่ยง OOM และยังถือว่าไม่ผ่านจนกว่าจะ benchmark แยก

## Verification ที่รัน

- manifest validator: ผ่าน 3 protocol manifests
- source verifier: remote/tag/commit/clean tree/requirements hash ผ่าน
- manifest unit tests: ผ่าน 7/7 รวม invalid protocol, Git SHA, provenance source, conflict protocol และ undeclared-field fixtures
- environment result validator: probe และ repeated Stage-1 smoke ผ่าน
- JSON/Python syntax checks: ผ่าน
- independent read-only review: แก้ findings เรื่อง OS provenance และ manifest-reference integrity แล้ว; reviewer ยืนยันว่าไม่มี blocker เหลือ

## Artifact หลัก

- `paper_faithful/manifests/source_manifest.json`
- `paper_faithful/manifests/source_lock.json`
- `paper_faithful/manifests/protocols/`
- `paper_faithful/environment/environment_spec.json`
- `paper_faithful/environment/requirements-resolved.txt`
- `paper_faithful/environment/results/wsl_tf24_probe.json`
- `paper_faithful/environment/results/stage1_one_batch.json`
- `paper_faithful/environment/results/stage1_one_batch_repeat.json`

## ขั้นถัดไปที่ยังไม่เริ่ม

Phase 2 คือ full Sleep-Cassette data parity: ดาวน์โหลด official SC cohort, ทำ checksum manifest, map labels/wake trimming และต้องได้ 153 recordings, 78 subjects, 194,655 epochs พร้อม class counts ตรง paper ก่อนอนุญาตให้สร้าง SST หรือเริ่ม training

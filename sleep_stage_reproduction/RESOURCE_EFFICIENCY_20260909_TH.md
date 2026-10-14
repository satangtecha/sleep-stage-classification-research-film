# ปรับเครื่องและ RAM — 9 กันยายน 2026

**ผลรอบนี้: ทดสอบ GPU บนข้อมูลจริงขนาดเล็กผ่านครบ Stage 1, 2, 3 แล้ว** จบด้วย exit 0 และหลักฐาน `status=pass` ทั้งสามงาน ไม่ใช่ full training และยังไม่ใช่ผลยืนยัน reproduction

หมายเหตุการตั้งค่าภายหลัง: เวลา21:53น. ผู้ใช้ขอเพิ่มพื้นที่ใช้RAMสำหรับงานเทรดร่วมด้วย จึงเพิ่มWSL ceilingจาก6เป็น8GBและตรวจbootแล้ว รายงานนี้คงตัวเลขprofile6GBซึ่งใช้ทดสอบจริงไว้เป็นหลักฐานเดิม ดูสถานะปัจจุบันที่ [RAM ร่วมสองโปรเจกต์](C:/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/SHARED_COMPUTE_MEMORY_20260909_TH.md) การเพิ่มเพดานไม่ใช่หลักฐานว่าทดสอบfull-load8GBแล้ว

## ขอบเขต

ผู้ใช้อนุญาตให้ปรับเครื่องและโค้ดเพื่อให้ทำงานได้ รอบนี้ใช้การแก้ที่ย้อนกลับได้ ไม่ปิดแอปผู้ใช้ ไม่ปิด antivirus ไม่แก้ pagefile Windows ไม่ repartition/ลง OS ใหม่ และไม่แก้ผล r1-r19 การทดสอบประสิทธิภาพไม่ใช่ผลวิจัยหรือ lineage ที่นำไปยืนยัน reproduction

## การตั้งค่าที่มีผลจริงแล้ว

ก่อนแก้ไม่มี `C:/Users/Acer/.wslconfig` และไม่มี WSL distribution ทำงาน จึงไม่ต้อง terminate งานใด

- WSL RAM สูงสุด 6 GiB: เป็นเพดาน ไม่ใช่การจองทั้งหมด และไม่รับประกัน Windows ว่างเสมอเมื่อเปิดแอปเพิ่ม
- vCPU 8 จาก 12 logical processors: เป็นค่าเริ่มต้นเพื่อเหลือกำลังให้ Windows ต้องวัด throughput ก่อนปรับต่อ
- WSL swap 4 GiB ที่ `E:/blp/sleep_stage_reproduction/runtime/resource-profile-20260909/wsl-swap.vhdx`; swap อยู่บนดิสก์ ช้ากว่า RAM และไม่ใช่ VRAM เพิ่ม
- `autoMemoryReclaim=gradual`: ค่อยคืน cached memory เมื่อ WSL ว่าง ไม่เรียก empty working sets หรือ flush cache ของ Windows

ตรวจหลังเปิด WSL: `free -m` รายงาน MemTotal 5,926 MiB, available 5,417 MiB, swap 4,096 MiB ใช้อยู่ 0; `nproc` รายงาน 8 มี swap backing file บน E จริง ไฟล์เริ่มต้นใช้ประมาณ 36 MiB แบบเติบโตได้ ไม่ได้เขียน 4 GiB ทันที

Profile SHA-256: `fdf658e7e0f42d303da8e3ab04f98d97e70eadafa0c4b7352a4d5e94759d1376`
หลักฐานก่อนเปลี่ยน: `E:/blp/sleep_stage_reproduction/runtime/resource-profile-20260909/before.json`

ตัวเลือกเหล่านี้ใช้กับ WSL2 ของผู้ใช้นี้ทั้งหมด ไม่ใช่เฉพาะโปรเจกต์ ผลจำกัดหน่วยความจำ/CPU อาจลด throughput บางงาน จึงไม่อ้างว่าเร็วขึ้นจากการตั้งค่าเพียงอย่างเดียว [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)

## การปรับโค้ด

`CacheSequence` เก็บจำนวน windows ครั้งเดียวและสร้าง batch buffer แบบ preallocation คัดลอกแต่ละ sample ทันที แทนเก็บ views ของทุก shard แล้วค่อย `np.stack` วิธีเดิมอาจเก็บ shard ขนาดใหญ่หลายไฟล์ไว้แม้ LRU cache จะมีเพดาน ส่วน `model.fit` กำหนด `workers=1`, `use_multiprocessing=False`, `max_queue_size=1` เพื่อลดคิว batch ค้าง หน่วยความจำทั้งหมดไม่ได้มีเพียง queue นี้: Keras/TF ยังมี buffers ภายใน จึงต้องวัด peak จริง

ไม่เปลี่ยน nominal batch, sample order, labels, optimizer, learning rate, objective, clipping หรือ precision

## การทดสอบ

- Host: input/execution/recovery 31 ผ่าน; regression ชุดกว้างก่อน final diagnostic delta 74 ข้อ ผ่าน73 ข้าม1ข้อที่ต้องใช้ WSL/E
- Locked WSL Python3.7/TF2.4: input/diagnostic/execution/recovery/scaffold 47 ผ่าน รวม CPU TensorFlow fixtures ภายใต้ `CUDA_VISIBLE_DEVICES=-1`
- ชุด input/diagnostic เวอร์ชันสุดท้าย: Host 12 ข้อ ผ่าน11 ข้าม1ข้อ POSIX signals; locked WSL 12/12 ผ่าน รวม actual SIGINT/SIGTERM ระหว่างเขียนผล
- PowerShell 5.1 parser ผ่าน; GNU timeout canary แบบ sleep ได้ exit124 ตามคาด โดยไม่แตะ training
- Live GPU ทั้งสาม mode ผ่านตามตารางด้านล่าง ไม่มี cgroup OOM และ weights finite
- Independent read-only review โดย Hypatia `01a08649-79da-7ca0-a16c-e6e0b92ec17b`: ไม่พบ material finding ที่ยังเปิดใน workflow launcher; ยังมีข้อจำกัดระดับต่ำของ direct CLI คือยอมรับ cgroup ที่เล็กกว่า2GiBและไม่บังคับ memory.high จึงอาจ OOM ถ้าผู้ใช้ประกอบคำสั่งเอง ให้ใช้ launcher ซึ่งตั้งทั้งสามค่า2GiBและตรวจจาก scope จริงแล้ว
- Skill `run-lean-team` ใช้แยกผู้แก้ input กับผู้รีวิวแบบ read-only และปิด worker เมื่อเสร็จ ไม่เปลี่ยนข้อกำหนดงานวิจัย

## Diagnostic ไม่ใช่ training งานวิจัย

`python -m paper_faithful.training.resource_diagnostic` ใช้ directory ใหม่ใต้ runtime profile เท่านั้น เขียน started/result แยกแต่ละ mode ไม่สร้าง checkpoint หรือแก้ production gate

- I/O: เปรียบเทียบ hash/decode/finite scan ของสี่ chunks บน `/mnt/e` กับสำเนาชั่วคราวใน Linux filesystem สลับลำดับ 4 รอบ เป็น **warm-cache** test ไม่ใช่ cold/random I/O ทั้ง cohort สำเนาชั่วคราวถูกลบโดยตัวทดสอบเมื่อจบ
- GPU: โมเดลใหม่ random initialization, stage2/3 ใช้ random parent ไม่ใช้ checkpoint วิจัย เลือกข้อมูลสี่ chunks ซ้ำเพื่อวัดขนาดงาน ไม่รายงาน accuracy; nominal batch128, stage3 microbatch1 และเฉลี่ย128ก่อน clip1.0 ตาม adaptation เดิม
- TensorFlow allocator จำกัด 3,072 MiB สำหรับ diagnostic เท่านั้น ไม่ใช่เพดาน GPU ของทุกแอปหรือค่า production ตั้ง CPU intra/inter threads4/2 และเผื่อ GPU headroom; ไม่อ้าง GPU exclusivity เมื่อแชร์ desktop [TensorFlow GPU memory controls](https://www.tensorflow.org/guide/gpu)
- Launcher ใหม่สร้าง systemd scope เฉพาะงาน ตั้ง `MemoryMax=2G`, `MemoryHigh=2G`, `MemorySwapMax=2G` แล้วลดสิทธิเป็นผู้ใช้ techatat ก่อนเรียก locked Python ไม่ปิด process ของแอปอื่น
- ปิด cuDNN convolution/RNN autotune และกำหนด convolution workspace limit256MiB เฉพาะ diagnostic ผ่าน environment; ไม่ได้เปลี่ยน precision หรือ scientific hyperparameters แต่การเลือก kernel อาจเปลี่ยน numerical rounding จึงต้องบันทึกและ validate ก่อนนำไปใช้ production ไม่รับประกัน bitwise-identical weights [TF2.4 autotune switches](https://raw.githubusercontent.com/tensorflow/tensorflow/v2.4.0/tensorflow/core/util/use_cudnn.cc), [TF2.4 convolution workspace](https://raw.githubusercontent.com/tensorflow/tensorflow/v2.4.0/tensorflow/core/kernels/conv_ops.cc)
- มี deadline600วินาทีภายใน Python และ GNU timeout ภายนอก ส่ง TERM แล้ว KILL หลังอีก15วินาทีเฉพาะ diagnostic มี memory/NaN checks และ external launch/exit receipts แยกจาก result; ถ้า PowerShell ถูก kill หรือเครื่องดับก็ยังรับประกัน exit receipt ไม่ได้
- Launcher รอ host RAM ว่าง3,072MiB สูงสุด60วินาทีก่อน dispatch เพราะ Windows อาจยังรับ RAM คืนจากงานก่อนหน้าไม่ทัน ถ้าไม่พร้อมจะไม่ dispatch และไม่ retry workload
- Compact diagnostic ตรวจ actual cgroup caps ไม่เชื่อ environment flag อย่างเดียว และต้องมี host RAM ตอนเริ่ม2,816MiB, ระหว่างงาน768MiB, commit4,096MiB, guestเริ่ม3,072MiB/ระหว่าง768MiB, AC online/noncritical และพื้นที่ E2GiB มี sampled peak RSS guard2,048MiB ทั้งหมดเป็นงบ diagnostic ไม่ได้ลด production gate
- cgroup2GiBคิดหน่วยความจำ process/file cache ไม่ได้รวม VRAMทั้งหมด และ driver อาจลงบัญชีต่างกัน; host reserve เป็นค่าที่สังเกต ไม่ใช่ RAM ที่จองไว้ Windowsอาจใช้เพิ่มระหว่าง samples ได้
- เมื่อ workload จบแล้ว ตัวทดสอบละเว้น SIGINT/SIGTERM ชั่วคราวเฉพาะช่วง cleanup/เขียนผล แล้วคืน handlers เดิม ถ้าถูกหยุดระหว่าง workload จะบันทึก failure; SIGKILL/ไฟดับยังทำให้ขาด result ได้ จึงมี started receipt แยกไว้

## ผลวัด I/O จริง

- `io-v1-2014/result.json`: ถูกปฏิเสธก่อนอ่านข้อมูล เพราะใช้เกณฑ์ RAM4GiB ของ production กับ diagnostic ขนาดเล็ก เก็บ failure ไว้ และแก้เป็นงบ diagnostic โดยเฉพาะ
- `io-v2-2017/result.json`: ผ่าน; peak process RSS71.38MiB, swap ใช้0 สี่ chunks ขนาดรวม48MiB/128epochs จาก SC4001 เท่านั้น
- median อ่าน+hash+decode+finite check: `/mnt/e` 1.0243วินาที; Linux ext4 0.1731วินาที ต่างประมาณ5.9เท่าในการอ่านซ้ำชุดเล็กนี้ ไม่ใช่ข้อสรุปว่าฝึกเต็มเร็วขึ้น5.9เท่า
- Ubuntu VHD อยู่ `E:/WSL/Ubuntu` อยู่แล้ว จึงเปรียบเทียบทางเข้าระบบไฟล์ ไม่ใช่คนละ SSD สำเนาทดสอบ48MiBใน Linuxถูกลบเมื่อจบ; original cache ไม่ถูกแก้หรือลบ
- ชุดเล็กนี้ไม่มี REM ไม่ครอบคลุมทุก subject/สภาพเลวร้ายสุด และยังไม่ได้ validate full cache หรือสร้าง accepted lineage

ผลทั้งหมดอยู่ `E:/blp/sleep_stage_reproduction/runtime/resource-profile-20260909/` แต่ละผลบันทึก code SHA ของเวอร์ชันที่รันจริง I/O v2 เกิดก่อนการแก้ signal-finalization ครั้งสุดท้าย ส่วน logic I/O ไม่ได้เปลี่ยน

## ผลวัด GPU จริง

ใช้ locked Python3.7.12 / TF2.4.0, RTX3050 Laptop6GiB; แต่ละ mode ใช้ fresh model แยกกัน ไม่ได้ส่ง checkpoint ต่อกัน ตัวเลขต่อ batch ด้านล่างไม่รวม host probes และเวลาสแกน/เตรียมข้อมูล

| ขั้น | ผล | วอร์มอัป | ค่ากลางต่อ nominal batch | Peak process RSS | Swap ของ scope ณ ท้ายงาน | Host RAM ต่ำสุดที่วัด |
|---|---|---:|---:|---:|---:|---:|
| Stage1 CNN | ผ่าน, 1 warmup+3 measured | 22.04s | 0.664s / 128 windows | 2030.46MiB | 1.636GiB | 1198.50MiB |
| Stage2 contrastive | ผ่าน, 1 warmup+3 measured | 33.64s | 0.840s / 128 windows | 2029.82MiB | 1.631GiB | 1242.79MiB |
| Stage3 CNN-GRU | ผ่าน, 1 warmup+2 measured | 31.12s | 6.320s / 128 epochs | 2031.02MiB | 1.804GiB | 1177.26MiB |

Stage3 microbatch1 จำนวน384 microbatches รวม warmup ทำ optimizer updates3 ครั้งจริง เฉลี่ย128 gradients ก่อน clip1.0; effective normสูงสุด0.61778 จึงไม่มี update ที่ต้อง clip ในตัวอย่างนี้ ผลนี้ยืนยัน execution path แต่ **ไม่ได้ทดสอบซ้ำ NaN failure เดิมของ seed43 และไม่ได้พิสูจน์ว่า clipping แก้ทุกกรณี**

GPUใช้รวมสูงสุดที่สังเกต4,308MiB (ประมาณ4.21GiB) รวม desktop/context/driver ไม่ขัดกับ TF tensor allocator cap3GiB ทั้งสาม scope มี `oom=0`, `oom_kill=0` แต่มี memory.max reclaim eventsจำนวนมากและใช้swapชัดเจน จึงยังเป็นโปรไฟล์ประหยัดRAMที่มีข้อแลกเปลี่ยน ไม่ใช่หลักฐานว่าหมด memory pressure

ผลวัดชุดเล็กใช้128epochsจาก SC4001 คนเดียว: W61,N1=4,N2=25,N3=38,REM0; stage1/2แบ่งเป็น windowsภายใน epoch30วินาที ส่วนstage3ใช้sequence15windowsต่อepoch ไม่ได้เพิ่มจำนวนคนหรือเปลี่ยนepochเป็น6–20วินาที

หลักฐาน canonical ที่อยู่ภายใต้ `E:/blp/sleep_stage_reproduction/runtime/resource-profile-20260909/`:

- `gpu-stage1-compact-20260909-205632-de43bbde/result.json` SHA `ef0b71089273ce96495a9a7b35909503c0f253c516770b33133dc0293109925f`
- `gpu-stage2-compact-20260909-205857-59146a73/result.json` SHA `1be8a094e11dbd8729f9f9cdb86f8417371c6d21a769de48f91ef3f9177a7158`
- `gpu-stage3-compact-20260909-210034-85a758ea/result.json` SHA `7b773ef0cd8292db092718d95305738259381991d29d4cdc6d4a893f98ac6ccb`
- ทุกงานมี sibling `.launch.json`/`.exit.json`, native exit0, wrapper success=true และ diagnostic codeSHA `89fe4940084f062ce438f4f59fd8c2439a17a4ecbdcc780f753fc4c42fc4048f`
- Launcherสุดท้าย SHA `32f9e44cb4cc8901084fc81ee55c04d7c12c416ed538040beda6722e99a88a0b`; Stage3ใช้เวอร์ชันที่เพิ่ม preparation wait/outer timeout แล้ว Stage1/2เกิดก่อนเพิ่มสองจุดนี้ โดย configurationGPU/cgroupเดียวกัน รายละเอียดคำสั่งจริงอยู่ใน launch receipt ของแต่ละงาน

## ครั้งที่ไม่ผ่าน — เก็บหลักฐานครบ ไม่เลือกเล่าเฉพาะผลดี

- `gpu-stage1-v1-2027`: ปฏิเสธ host RAM ก่อนสร้างโมเดล ไม่ใช่GPU OOM
- `gpu-stage1-compact-v1`: scope RAM1GiB/swap1GiB ไม่พอ เกิด kernel cgroup OOM, exit1, ไม่มี completed batch มี startedและexternal_failure ไม่กล่าวว่ามี terminalresult
- `gpu-stage1-compact-v2`: scope2GiB/2GiB/autotuneเดิม ผู้ช่วยหยุด exact diagnostic scopeเองเพื่อเปลี่ยนรูปแบบ startup; outputภายหลังแสดง warmup155.81sและอีกbatch0.780s แต่ไม่มีresult จึงไม่รับเป็น pass ห้ามเรียกว่า workloadล้มเองหรือใช้เปรียบเทียบspeedupแบบควบคุม
- `gpu-stage2-compact-20260909-205754-2e281dbc`: ปฏิเสธhost RAMหลังจบStage1เร็วเกินไป ต่อมารอระบบคืนRAMแล้วรันdirectoryใหม่ผ่าน นำไปสู่pre-dispatch waitในlauncher

โปรไฟล์ที่ผ่านปิด autotune/ลดworkspace พร้อมกับ cacheที่อุ่นขึ้น จึงยังแยกไม่ได้ว่าแต่ละการเปลี่ยนช่วยกี่เปอร์เซ็นต์ ไม่มีการ retry historical research run หรือเขียนทับ outputเดิม

## RAM ที่เหลือไปไหน / สถานะหลังจบ

เครื่องติดตั้ง16GiB Windowsเห็น15.71GiB ก่อนทดสอบพบ Edgeหลายprocess working-setรวมประมาณ2.63GiB, ChatGPT2.10GiB, Firefox1.51GiB, Memory Compression0.84GiB ยังมีระบบ/driver/pool/filecache อีก ค่าworking-setรวมมีsharedpagesนับซ้ำ ห้ามเอาไปบวกอ้างเป็นRAMจริงทั้งหมด

หลังจบ21:08น. Windowsว่าง3,894MiB, commitheadroom13,624MiB, GPUใช้268MiB/utilization0%, ไม่พบcompute appหรือdiagnostic scopeค้าง AConline/noncriticalแบต100% ไม่ได้ปิดbrowser/ChatGPT หรือflushWindowscacheเพื่อให้ผ่าน

## คำสั่งใช้งานที่รองรับ

ใช้ทีละคำสั่ง ไม่รันGPUพร้อมกัน เปิดPowerShellในโปรเจกต์ แล้วเรียกตามmodeที่ต้องการ (แต่ละ invocation เป็นdiagnosticใหม่ ไม่มีacceptedlineage):

```powershell
& 'C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction\paper_faithful\training\run_resource_diagnostic.ps1' -Mode stage1 -Steps 2
& 'C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction\paper_faithful\training\run_resource_diagnostic.ps1' -Mode stage2 -Steps 2
& 'C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction\paper_faithful\training\run_resource_diagnostic.ps1' -Mode stage3 -Steps 2
```

ให้ใช้wrapperนี้ ไม่ประกอบdirect `--compact` เอง หากresourcegateปฏิเสธให้อ่านเหตุผล ไม่ลดเกณฑ์หรือloopretryโดยอัตโนมัติ ชุดนี้ใช้cache/environmentที่มีในเครื่องอยู่แล้ว ไม่ต้องดาวน์โหลดข้อมูลเพิ่มหรือย้ายไปcloud

การย้าย full cache ประมาณ250GiB ยังไม่ได้ทำ Microsoft แนะนำให้ Linux workloads ใช้ Linux filesystem แต่ประโยชน์กับข้อมูลนี้ต้องวัดก่อนสร้าง replica ที่รักษา hash/provenance [Microsoft filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems)

## ย้อนกลับอย่างไร

เมื่อไม่มี training หรือ WSL งานอื่นทำงาน ให้ตรวจ hash ของ `C:/Users/Acer/.wslconfig` ว่ายังตรง profile นี้ แล้วเปลี่ยนชื่อไฟล์นี้เป็น `.wslconfig.sleep-resource-20260909.disabled` (ไม่เขียนทับไฟล์ชื่อดังกล่าวถ้ามีอยู่แล้ว) จากนั้นปิด/เปิด WSL ใหม่อย่างปลอดภัย จะกลับไปใช้ค่าปริยาย เพราะเดิมไม่มี config ไม่ต้องลบ swap VHD ระหว่างมี WSL ทำงาน ไฟล์นั้นเก็บไว้จนยืนยันว่าไม่ได้ถูกใช้งานก่อนจัดการพื้นที่ภายหลัง

การคืนโค้ดต้องคืนเฉพาะ CacheSequence และ fit queue ของรอบนี้ ไม่ใช้ git reset ทั้งโปรเจกต์ และไม่ยกเลิก recovery repairs ที่ทำก่อนหน้า

## ผลสรุป/ขั้นต่อไป

งานปรับทรัพยากรและbounded diagnosticรอบนี้เสร็จตามacceptanceแล้ว เครื่องเดิมรันGPUครบสามexecution pathsได้ ไม่จำเป็นต้องลงLinuxใหม่หรือซื้อcloudเพื่อผ่านขั้นนี้ แต่ยังไม่ถือว่าฝึกเต็มพร้อมหรือresearchเสร็จ

ขั้นที่เหมาะสมต่อไปคือทดสอบหลายsubject/ครบห้าclassesรวมseed43ด้วยbounded soakที่กำหนดไว้ล่วงหน้า วัดcold/data-loadingและend-to-end throughput แล้วค่อยใช้กำหนดงบ full runที่มีsplit/lineage/validationครบ หากswapทำให้เวลาเกินงบจึงเทียบทางเลือกเพิ่มRAM/ลดdesktopload/nativeLinux/cloudจากผลวัดจริง ไม่อนุมานETAทั้งcohortจากbatchซ้ำชุดเล็กนี้ และไม่ต้องรอexact approvalใหม่สำหรับdiagnosticในขอบเขตที่ผู้ใช้มอบหมาย

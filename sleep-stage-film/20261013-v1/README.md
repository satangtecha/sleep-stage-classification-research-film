# Sleep Stage Research: วิดีโอนำเสนอ 5 นาที

วิดีโอนี้เล่างาน CNN + BiGRU แบบย่อ โดยใช้คลิปที่แนบเป็นต้นแบบด้านสี กล้อง และจังหวะการเล่าเรื่องเท่านั้น ไม่ใช้ภาพ เสียง หรือข้อมูล Alzheimer's จากคลิปต้นแบบ ไม่ใช่การ replicate paper SST/contrastive และไม่อ้าง SOTA หรือความพร้อมใช้งานทางคลินิก

## ไฟล์ส่งมอบ

- `outputs/final/SleepStageResearch-5min-final.mp4`: วิดีโอ 1920×1080, 24 fps, เสียงสังเคราะห์ภาษาไทย Microsoft Pattara, คำบรรยายไทยฝังในภาพ และห้าบทใน metadata
- `outputs/final/presentation-final.html`: Manim Slides / RevealJS แบบฝังวิดีโอและ assets สำหรับเปิดนำเสนอในเบราว์เซอร์ ใช้ลูกศรเพื่อเปลี่ยนบท บางเบราว์เซอร์อาจต้องคลิกหน้า/เริ่มเล่นก่อนอนุญาตให้เล่นเสียง
- `slides/SleepStageFilmFinal.json`: รายการบทและ speaker notes สำหรับ Manim Slides
- `outputs/final/delivery-verification.json`: hash, stream durations, จำนวนเฟรม, source hashes และหลักฐานการจัดเวลาเสียง
- `story.json`, `facts.json`, `film.mjs`, `narrate.ps1`: บทบรรยาย ตัวเลขที่ freeze และ source ที่แก้ไขได้
- `manim-motion-project-verified.json`, `motion-export-verified.py`: โปรเจกต์กราฟผลสำหรับ Manim-Motion และ Python ที่ exporter ของ repo สร้างจริง

วิดีโอและเสียงมีระยะ 300 วินาทีตาม stream; container อาจยาวเกินเล็กน้อยประมาณหนึ่งในห้าสิบวินาทีจาก timestamp ของ MP4/AAC ให้ใช้ตัวเลขดิบใน verification ประกอบ ไม่ปัดไปอ้างว่า container เป็น 300.000 โดยไม่ได้วัด

| เวลา | เนื้อหา |
|---|---|
| 0:00–1:00 | โจทย์ sleep staging และข้อมูล 20 คน / 39 คืน |
| 1:00–2:00 | EEG, STFT, CNN + BiGRU และ subject-wise folds |
| 2:00–3:00 | ผลฐานและ R1 พร้อมข้อจำกัด post-hoc/transductive |
| 3:00–4:00 | Full-night sensitivity, CI และสาม validation pilots ที่ไม่ผ่าน |
| 4:00–5:00 | Metadata audit และสิ่งที่ยังต้องยืนยันอย่างอิสระ |

## ข้อเท็จจริงที่คงไว้

Primary MF1 คือค่าเฉลี่ย macro-F1 รายคน ส่วน accuracy รวมทุก epoch ทั้งสองไม่ใช่ metric เดียวกัน

| Historical test run | Subject-mean MF1 | Pooled accuracy |
|---|---:|---:|
| Base | 0.5642008634 | 0.6500106365 |
| R1 | 0.7485800654 | 0.8099368899 |
| Full-night | 0.7183630958 | 0.7909565793 |

R1 เป็น post-hoc และใช้สถิติจากสัญญาณคืน val/test เองแบบ offline/transductive ช่วง retained ของ R1 ยังเกี่ยวข้องกับ hypnogram trimming ส่วน full-night ใช้ PSG ทั้งคืนเพื่อคำนวณ stats การเปรียบเทียบฐานกับ R1 รวมทั้งโมเดลที่ฝึกใหม่และ normalization ที่เปลี่ยน ไม่ใช่หลักฐานของผลจากโมเดลอย่างเดียว

Full-night − R1 MF1 ต่างประมาณ −3.02 percentage points; paired subject bootstrap CI ประมาณ [−7.12, +1.22] pp คร่อมศูนย์ ไม่มีหลักฐานพอว่าต่างจาก R1 และไม่ได้พิสูจน์ว่าผลเท่ากัน เกณฑ์ sensitivity เกิดหลังเห็นฐาน/R1 จึงไม่ใช่ blind pre-registration เต็มรูปแบบ

สาม pilot ใช้ validation เท่านั้น ทั้งหมด rejected ไม่เปิด test ใหม่ Seed เดียวและประวัติความพยายามก่อน R1 ไม่ครบ ทำให้ CI ไม่ครอบคลุมความไม่แน่นอนจากการเลือกวิธีทั้งหมด

มี test สองคนต่อ fold และรวม 20 คนที่เป็น held-out คนละหนึ่งครั้ง: **Subject-wise protocol differs from the paper; test < 10 subjects per fold**

Metadata audit พบ 78 คน / 153 ชื่อไฟล์ PSG, 30 คนมีหลักฐาน development exposure, 48 คนยังมีประวัติใช้จริงไม่ครบ และศูนย์คนที่รับรองว่า independent การมี cache หรือหา receipt ไม่เจอไม่ได้พิสูจน์ว่าไม่เคยใช้

## GitHub ทั้งสามที่ทดลองจริง

เลือกสามรายการท้ายในข้อความที่แนบมา เพราะเป็นชุดที่ระบุว่าตรงกับคลิป

| Repo | สิ่งที่ทำจริง | ขอบเขต/ข้อจำกัด |
|---|---|---|
| [Manim-Motion](https://github.com/BlommeJan/Manim-Motion) | ทดสอบ engine 62 ผ่าน / 0 ล้มเหลว; เรียก exporter สร้าง Python และเรนเดอร์โปรเจกต์กราฟที่มี label จริง | ไม่เปิด full Docker stack เพราะเครื่องไม่มี Docker ใช้ exporter โดยตรงกับ Manim CE; ไม่ได้ทดสอบ editor UI ทุกเส้นทาง |
| [Manim Slides](https://github.com/jeertmans/manim-slides) | เรนเดอร์ `ThreeDSlide` ตัวอย่างสองช่วง และแปลงห้าบทที่สร้างแล้วเป็น HTML offline | ใช้ package 5.7.0 กับ Manim CE 0.19.0; CE 0.22.0 ทดลองแล้วไม่เข้ากัน (`write_to_movie` ไม่มี) ไม่มี reverse animations และไม่ได้ตรวจ Qt player |
| [ecmanim](https://github.com/johnhenry/ecmanim) | เครื่องมือหลัก: `Scene` timeline และ `ThreeDCamera` ฉาก 3 มิติ original, native canvas, FFmpeg | ใช้ npm 0.1.0; ตัววาด low-poly meshes/overlay เป็น code ของงานนี้ ไม่ได้อ้างว่าทุก upstream feature ผ่านการตรวจ |

Git revisions ที่ clone เพื่อศึกษา:

- ecmanim: `e16465ec4de78344f1fbcd993774ac9b20bb8793`
- Manim-Motion: `5d51316543db9dc9f489dc1e7bb52524645bffee`
- manim-slides: `df0f1f18f799cd38de0712b0abc4507d4d94b822`

npm/pip releases ที่ใช้ทำงานอาจไม่ใช่ source tree HEAD เหล่านี้ ดู package-lock และเวอร์ชันข้างต้น ไม่ได้ยืนยันว่า repo ใดเป็นเครื่องมือของเจ้าของคลิป ไม่ใช้คำกล่าวอ้าง stars/trending ในข้อความอ้างอิงเป็นหลักฐาน

## ทำซ้ำการสร้างวิดีโอ

ใช้ **โฟลเดอร์ build ใหม่**: scripts ปฏิเสธการเขียนทับ outputs เพื่อเก็บประวัติ ห้ามรันคำสั่งด้านล่างทับชุดส่งมอบนี้

ต้องมี Windows, Node ≥24, FFmpeg/FFprobe, PowerShell 7 ที่โหลด System.Speech ได้, ฟอนต์ Tahoma/Segoe UI และเสียง Microsoft Pattara ภาษไทย คำบรรยายและรูปทรงทั้งหมดเป็น original ไม่มี API key หรือบริการเสียงที่เสียเงิน

```powershell
npm ci --ignore-scripts --no-audit --no-fund
node build-facts.mjs       # อ่านเฉพาะ frozen aggregate reports จาก WSL ตาม hash
./narrate.ps1              # สร้างเสียง original ทุกฉาก รวมฉาก02ที่ผ่านรีวิว
node film.mjs render 1
node film.mjs render 2
node film.mjs render 3
node film.mjs render 4
node film.mjs render 5
node finish.mjs
node sync-audio.mjs        # ทำ PCM ให้ครบ20sต่อฉากด้วย zero padding เท่านั้น
node film.mjs render 5 60 credited
node deliver.mjs
npm test
```

`facts.json` ที่แนบ freeze ตัวเลขไว้แล้ว ถ้าไม่อยู่บนเครื่องที่มี source reports ตาม path เดิม ให้ใช้ facts นี้โดยไม่เรียก build-facts ใหม่ ไม่อ่าน raw EDF/hypnogram/features/model/predictions เพื่อสร้างภาพ

สำหรับ Manim Slides (ใช้ env แยกจาก env ของโมเดล):

```bash
/home/techatat/.venvs/sleep-stage-film/bin/python -m pip install manim==0.19.0 manim-slides==5.7.0
/home/techatat/.venvs/sleep-stage-film/bin/manim-slides convert \
  SleepStageFilmFinal outputs/final/presentation-final.html \
  --one-file --offline -ctitle="Sleep Stage Research" \
  -ccontrols=true -cprogress=true -cslide_number=true
```

HTML เป็นการเปิดวิดีโอทีละบท ไม่มี animation rewind สำหรับ Qt (`rev_file` อ้างถึงไฟล์เดียวกันเพื่อใช้กับ HTML export เท่านั้น) ใช้ MP4 เป็นไฟล์หลักสำหรับนำเสนอแบบเวลาแน่นอนห้านาที

## การตรวจที่ทำจริงและการเก็บร่าง

ตรวจห้าบท บทละ 1,440 เฟรม, รวม 7,200 เฟรม, 1080p/24fps มี video/audio streams และ chapter metadata ตรวจภาพแทนแต่ละฉากครบ15ฉาก แก้ฟอนต์ไทยที่แสดงเป็นกล่องและ label ที่ซ้อนวัตถุแล้ว ชุด tests ของงานนี้ 10 ผ่าน / 0 ล้มเหลว / 0 ข้าม รวมการรักษา PCM เดิมและ zero padding ให้ตรงเวลาฉาก

พบว่าการเตรียมเสียงผ่าน FFmpeg ครั้งแรกสั้นกว่า slot เล็กน้อย จึงอ่าน PCM แล้วเติมเฉพาะ zero samples หลังแต่ละฉาก ไม่มีการตัดคำพูดหรือแก้ค่าผลวิจัย ข้อมูลเสียงจริงและจำนวน sample อยู่ใน verification ไม่ได้อ้างว่าได้ฟังไฟล์เสียงครบหรือทดลอง HTML ในทุกเบราว์เซอร์

เก็บร่างก่อนแก้ฟอนต์และการตัด chapter แบบ seek ไว้ใน outputs/drafts และชุด intermediate อื่น ๆ ไม่ลบข้อมูล งานนี้ไม่แก้ archived model outputs/config/receipt/README/NOTES/PLAN/state/attempt counters ไม่เปิด timer ไม่ train/infer/evaluate test ไม่ commit/push/merge โปรเจกต์วิจัย

## แหล่งข้อมูลและเครดิต

- Frozen closeout report จาก branch `codex/simple-cnn-bigru`, result commit `25f93f893e5977a61c9aa9e6911e30b361184101`; audit source commit `5f5965d8a69627271651c80ddb6d6546f0006a51`
- [Sleep-EDF Expanded 1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/), Kemp et al. (2000); [PhysioNet, Goldberger et al. (2000)](https://pubmed.ncbi.nlm.nih.gov/10851218/); ODC-By 1.0 เครดิตอยู่ท้ายวิดีโอด้วย
- เครื่องมือ: ecmanim, Manim Community, Manim Slides, Manim-Motion, FFmpeg, @napi-rs/canvas
- รูป EEG/spectrum และ network edges เป็นภาพจำลอง ไม่ใช่ EEG ที่วัดจริง/learned weights ส่วน bars/CI/จำนวนคนอ้างจาก archived aggregate results
- ไม่แจกจ่ายคลิปต้นแบบหรือไฟล์ vendor ในไฟล์วิดีโอ/HTML

"""Export saved notebook cells/outputs to Quant OS. Never executes notebook code."""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import bleach
import mistune
from PIL import Image
from pygments.lexers import PythonLexer
from pygments.token import Comment, Error, Keyword, Name, Number, Operator, Punctuation, String

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT.parents[1] / "strategy_lab" / "manager" / "sleep-stage"
CHAPTERS = [
    ("00_start_here.ipynb", "เริ่มต้นและภาพรวม", "เป้าหมาย · หลักฐาน · สถานะโครงการ"),
    ("01_data_and_eeg.ipynb", "ข้อมูลและสัญญาณ EEG", "กลุ่มตัวอย่าง · สัญญาณจริง · Sleep stages"),
    ("02_sst_representation.ipynb", "จาก EEG สู่ภาพ SST", "Time–frequency · Tensor · Cache"),
    ("03_model_and_protocol.ipynb", "โมเดลและแผนการทดลอง", "CNN · Contrastive learning · GRU"),
    ("04_results_and_next_steps.ipynb", "ผลการทดลองและงานถัดไป", "Accuracy · Macro-F1 · Confusion matrix"),
    ("05_embedding_and_transform_visuals.ipynb", "มองเข้าไปใน Representation", "Sliding DFT · SST · t-SNE"),
]
TAGS = {"p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "del", "blockquote", "ul", "ol", "li", "pre", "code", "a", "table", "thead", "tbody", "tr", "th", "td", "span", "div", "sup", "sub"}
CLEANER = bleach.Cleaner(tags=TAGS, attributes={"a": ["href", "title"], "ol": ["start"], "td": ["colspan", "rowspan"], "th": ["colspan", "rowspan", "scope"]}, protocols={"http", "https", "mailto"}, strip=True)
MARKDOWN = mistune.create_markdown(escape=True, plugins=["table", "strikethrough"])
PYTHON_LEXER = PythonLexer()


def highlight_python(source):
    """Lex (never execute) Python, escaping each token and preserving original text."""
    tokens = list(PYTHON_LEXER.get_tokens_unprocessed(source))
    result = []
    for index, (_, token, value) in enumerate(tokens):
        kind = None
        if token in Comment:
            kind = "comment"
        elif token in String:
            kind = "string"
        elif token in Number:
            kind = "number"
        elif token in Keyword:
            kind = "keyword"
        elif token in Name.Function:
            kind = "function"
        elif token in Name.Class:
            kind = "class"
        elif token in Name.Decorator:
            kind = "decorator"
        elif token in Name.Builtin:
            kind = "builtin"
        elif token in Name:
            # Calls get the familiar editor function color, without evaluating names.
            following = next((v for _, _, v in tokens[index + 1:] if v.strip()), "")
            kind = "function" if following == "(" else "name"
        elif token in Operator:
            kind = "operator"
        elif token in Punctuation:
            kind = "punctuation"
        elif token in Error:
            kind = "error"
        escaped = html.escape(value)
        result.append(f'<span class="syntax-{kind}">{escaped}</span>' if kind else escaped)
    return "".join(result)


def joined(value):
    return "".join(value) if isinstance(value, list) else str(value)


def safe_html(value):
    value = CLEANER.clean(value)
    for filename, _, _ in CHAPTERS:
        value = value.replace(f'href="{filename}"', f'href="#chapter-{filename[:2]}"')
        value = value.replace(f'href="notebooks/{filename}"', f'href="#chapter-{filename[:2]}"')
    return value.replace("<table>", '<div class="table-scroll" tabindex="0" role="region" aria-label="ตารางผลลัพธ์ เลื่อนในแนวนอนได้"><table>').replace("</table>", "</table></div>")


def render_output(output, stem, cell_index, output_index, dest, heading):
    kind = output.get("output_type")
    if kind == "stream":
        return f'<pre class="text-output"><code>{html.escape(joined(output.get("text", "")))}</code></pre>', 0
    if kind == "error":
        # Errors are evidence too; display instead of silently treating as success.
        message = joined(output.get("traceback", [])) or f'{output.get("ename")}: {output.get("evalue")}'
        message = re.sub(r"\x1b\[[0-9;]*m", "", message)
        return f'<pre class="error-output">{html.escape(message)}</pre>', 0
    data = output.get("data", {})
    if "image/png" in data:
        raw = base64.b64decode(joined(data["image/png"]), validate=False)
        with Image.open(io.BytesIO(raw)) as picture:
            if picture.format != "PNG":
                raise ValueError("image/png output is not PNG")
            width, height = picture.size
            picture.verify()
        name = f"{stem}-cell{cell_index:02}-out{output_index:02}.png"
        (dest / "figures" / name).write_bytes(raw)
        caption = f"{heading} · เซลล์ {cell_index + 1}"
        return (f'<figure><a class="figure-link" href="figures/{name}" target="_blank" rel="noopener" aria-label="เปิดภาพขนาดเต็ม: {html.escape(caption, quote=True)}">'
                f'<img src="figures/{name}" width="{width}" height="{height}" loading="lazy" decoding="async" alt="กราฟจากผลรัน notebook: {html.escape(caption, quote=True)}"></a>'
                f'<figcaption>{html.escape(caption)} <span>คลิกภาพเพื่อดูขนาดเต็ม ↗</span></figcaption></figure>'), 1
    if "text/html" in data:
        return safe_html(joined(data["text/html"])), 0
    if "text/plain" in data:
        return f'<pre class="text-output"><code>{html.escape(joined(data["text/plain"]))}</code></pre>', 0
    # Never silently omit an unsupported MIME bundle.
    raise ValueError(f"Unsupported notebook output: {kind}, {list(data)}")


def build(notebooks=ROOT / "notebooks", dest=DESTINATION):
    dest = Path(dest)
    for directory in (dest, dest / "figures", dest / "notebooks"):
        directory.mkdir(parents=True, exist_ok=True)
    chapters, navigation, records = [], [], []
    for filename, title, subtitle in CHAPTERS:
        source = Path(notebooks) / filename
        raw = source.read_bytes()
        notebook = json.loads(raw)
        stem, number = source.stem, filename[:2]
        source_time = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        cells, image_count, code_count, output_count = [], 0, 0, 0
        heading = title
        for cell_index, cell in enumerate(notebook["cells"]):
            text = joined(cell.get("source", ""))
            cell_id = f"{number}-cell-{cell_index}"
            if cell["cell_type"] == "markdown":
                headings = re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
                if headings:
                    heading = headings[-1]
                # Website owns h1; preserve text while nesting original notebook headings.
                markdown = re.sub(r"^(#{1,5}) ", r"#\1 ", text, flags=re.MULTILINE)
                content = safe_html(MARKDOWN(markdown))
                cells.append(f'<section class="markdown-cell" id="{cell_id}" data-cell-type="markdown">{content}</section>')
            elif cell["cell_type"] == "code":
                code_count += 1
                execution = cell.get("execution_count")
                rendered_outputs = []
                for output_index, output in enumerate(cell.get("outputs", [])):
                    rendered, count = render_output(output, stem, cell_index, output_index, dest, heading)
                    rendered_outputs.append(f'<div data-output-index="{output_index}">{rendered}</div>')
                    image_count += count
                    output_count += 1
                result = "".join(rendered_outputs) or '<p class="no-output">เซลล์นี้ไม่มี output ที่บันทึกไว้</p>'
                cells.append(f'<section class="code-cell" id="{cell_id}" data-cell-type="code">'
                             f'<details class="source-code" open><summary><span>Python <b>In [{execution if execution is not None else " "}]</b></span><span>โค้ดต้นฉบับ</span></summary>'
                             f'<pre><code class="language-python">{highlight_python(text)}</code></pre></details>'
                             f'<div class="cell-output"><div class="output-label">SAVED OUTPUT · ผลที่บันทึกไว้</div>{result}</div></section>')
            else:
                cells.append(f'<pre id="{cell_id}" data-cell-type="raw">{html.escape(text)}</pre>')
        digest = hashlib.sha256(raw).hexdigest()
        (dest / "notebooks" / f"{stem}.json").write_bytes(raw)
        record = {"id": number, "source": filename, "sha256": digest, "source_modified_utc": source_time,
                  "cells": len(notebook["cells"]), "code_cells": code_count, "outputs": output_count, "figures": image_count,
                  "errors": sum(o.get("output_type") == "error" for c in notebook["cells"] for o in c.get("outputs", []))}
        records.append(record)
        navigation.append(f'<a href="#chapter-{number}" class="chapter-link"><span class="chapter-number">{number}</span><span>{title}<small>{subtitle}</small></span></a>')
        next_index = int(number) + 1
        next_link = (f'<a href="#chapter-{next_index:02}">บทถัดไป · {CHAPTERS[next_index][1]} <span aria-hidden="true">→</span></a>'
                     if next_index < len(CHAPTERS) else '<a href="#top">กลับไปภาพรวม ↑</a>')
        previous_link = f'<a href="#chapter-{int(number)-1:02}">← บทก่อนหน้า</a>' if int(number) else '<a href="#top">← ภาพรวม</a>'
        chapters.append(f'<article id="chapter-{number}" class="chapter" aria-labelledby="title-{number}">'
                        f'<header class="chapter-heading"><p class="eyebrow">CHAPTER {number} / 05</p><h2 id="title-{number}">{title}</h2><p>{subtitle}</p>'
                        f'<div class="chapter-meta"><span>{code_count} เซลล์โค้ด</span><span>{image_count} ภาพผลลัพธ์</span>'
                        f'<a href="notebooks/{stem}.json" download="{filename}">ดาวน์โหลด notebook ↗</a></div></header>'
                        f'{"".join(cells)}<details class="provenance"><summary>แหล่งที่มาและการตรวจสอบย้อนกลับ</summary>'
                        f'<p>ต้นฉบับ: <code>walkthrough/notebooks/{filename}</code></p><p>แก้ไขไฟล์ล่าสุด (UTC): {source_time}</p>'
                        f'<p>SHA-256: <code>{digest}</code></p><p>เว็บไซต์คัดลอกเซลล์และผลที่บันทึกไว้ ไม่มีการเรียก Python หรือเริ่ม training</p></details>'
                        f'<nav class="chapter-pagination" aria-label="ข้ามบท {number}">{previous_link}{next_link}</nav></article>')
    total_images = sum(r["figures"] for r in records)
    total_cells = sum(r["cells"] for r in records)
    manifest = {"schema": "sleep_stage_course_export_v1", "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "notebook_execution_performed": False, "training_performed": False, "chapters": records,
                "total_cells": total_cells, "total_figures": total_images}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    asset_version = hashlib.sha256((ROOT / "web" / "course.css").read_bytes() + (ROOT / "web" / "course.js").read_bytes()).hexdigest()[:12]
    page = f'''<!doctype html>
<html lang="th" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="description" content="บันทึกการทดลอง Sleep Stage: อ่านข้อมูล EEG, SST, โมเดล และผลที่รันจริง จาก notebook 00–05">
<title>Sleep Stage · Research Notebook | Quant OS</title><link rel="stylesheet" href="course.css?v={asset_version}"><script src="course.js?v={asset_version}" defer></script></head>
<body><a class="skip-link" href="#reading">ข้ามไปเนื้อหา</a>
<header class="topbar"><a class="brand" href="#top"><span class="brand-mark" aria-hidden="true">∿</span><span>SLEEP STAGE <small>RESEARCH NOTEBOOK</small></span></a>
<div class="top-actions"><a class="back-link" href="/#sleepstage" target="_top">Quant OS ↗</a><button id="themeToggle" type="button" aria-pressed="true">โหมดสว่าง</button><button id="menuToggle" type="button" aria-expanded="false" aria-controls="chapterNav">สารบัญ</button></div></header>
<div class="book-layout"><aside id="chapterNav" class="chapter-sidebar"><p class="sidebar-label">เส้นทางการทดลอง</p><nav aria-label="สารบัญบทเรียน">{"".join(navigation)}</nav>
<div class="sidebar-note"><span class="read-only-dot" aria-hidden="true"></span> อ่านผลที่รันไว้แล้ว<p>ไม่มีการใช้ GPU หรือเริ่มเทรนจากหน้านี้</p><a href="manifest.json" target="_blank" rel="noopener">ตรวจ export manifest ↗</a></div></aside>
<main id="reading" tabindex="-1"><section id="top" class="introduction"><p class="eyebrow">QUANT OS / RESEARCH LIBRARY</p>
<h1>จากสัญญาณสมอง<br>สู่การจำแนกระยะการนอนหลับ</h1><p class="intro-text">เปิดสมุดทดลองทีละขั้น ตั้งแต่ข้อมูล EEG และภาพ SST ไปจนถึงโมเดล ผลการทดลอง และสิ่งที่ยังต้องทำต่อ — พร้อมโค้ดและกราฟจริงจาก notebook 00–05</p>
<div class="overview-meta"><span><b>06</b> บทต่อเนื่อง</span><span><b>{total_cells}</b> เซลล์ต้นฉบับ</span><span><b>{total_images:02}</b> ภาพผลลัพธ์</span></div>
<div class="snapshot-note"><strong>นี่คือบันทึกผล ไม่ใช่หน้ารันสด</strong><p>ข้อมูลและสถานะด้านล่างเป็น snapshot จาก notebook ที่บันทึกไว้ วันสร้างเว็บไม่ได้หมายถึงวันรันการทดลองใหม่ ผล pilot ยังไม่ใช่ full reproduction หรือผลทดสอบกับบุคคลใหม่</p><p>ข้อความ “กด Run” ในต้นฉบับหมายถึงการเปิด notebook ใน VS Code ส่วนเว็บไซต์นี้ใช้สำหรับอ่านผลเท่านั้น</p></div>
<div class="reading-toolbar"><a class="start-link" href="#chapter-00">เริ่มอ่านบท 00 <span aria-hidden="true">→</span></a><button id="codeToggle" type="button" aria-pressed="true">ซ่อนโค้ดทั้งหมด</button></div></section>
{"".join(chapters)}<footer class="book-footer">Sleep Stage Research · เนื้อหาจาก notebook 00–05 โดยคงหลักฐานเดิม<br>ส่งออก {manifest["built_at_utc"]} · ไม่ได้รันการทดลองใหม่</footer></main></div></body></html>'''
    (dest / "index.html").write_text(page, encoding="utf-8")
    for asset in ("course.css", "course.js"):
        shutil.copyfile(ROOT / "web" / asset, dest / asset)
    return manifest


if __name__ == "__main__":
    report = build()
    print(json.dumps({"destination": str(DESTINATION), "chapters": len(report["chapters"]), "cells": report["total_cells"], "figures": report["total_figures"], "training_performed": False}, ensure_ascii=False))

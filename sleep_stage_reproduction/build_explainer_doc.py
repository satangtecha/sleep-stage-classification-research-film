from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "explainer_doc_build"
ASSET_DIR = OUT_DIR / "assets"
OUT_DIR.mkdir(exist_ok=True)
ASSET_DIR.mkdir(exist_ok=True)

DOCX_PATH = OUT_DIR / "sleep_stage_classification_explainer_TH.docx"
MD_PATH = OUT_DIR / "sleep_stage_classification_explainer_TH.md"
PIPELINE_PATH = ASSET_DIR / "sleep_stage_pipeline.png"


NAVY = "0B2545"
BLUE = "2E74B5"
BLUE_DARK = "1F4D78"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
CALLOUT = "F4F6F9"
GOLD = "A87400"
RED = "9B1C1C"
GREEN = "2F6B4F"
INK = "222222"
MUTED = "667085"
WHITE = "FFFFFF"


def rgb(hex_color):
    return RGBColor.from_string(hex_color)


def set_run_font(run, name="Tahoma", size=11, color=INK, bold=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = rgb(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_cell_border(cell, color="D0D5DD", size="6", val="single"):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), val)
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_table_geometry(table, widths_dxa, indent_dxa=120):
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths_dxa)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths_dxa[i]))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def mark_header_row(row):
    tr_pr = row._tr.get_or_add_trPr()
    header = tr_pr.find(qn("w:tblHeader"))
    if header is None:
        header = OxmlElement("w:tblHeader")
        tr_pr.append(header)
    header.set(qn("w:val"), "true")


def set_paragraph_spacing(paragraph, before=0, after=6, line=1.25):
    pf = paragraph.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)
    set_run_font(run, size=9, color=MUTED)


def add_hyperlink(paragraph, text, url, color=BLUE, underline=True):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), "Tahoma")
    r_fonts.set(qn("w:hAnsi"), "Tahoma")
    r_fonts.set(qn("w:eastAsia"), "Tahoma")
    r_pr.append(r_fonts)
    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), color)
    r_pr.append(color_el)
    if underline:
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        r_pr.append(u)
    new_run.append(r_pr)
    text_el = OxmlElement("w:t")
    text_el.text = text
    new_run.append(text_el)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_bullet(doc, text, level=0, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    set_paragraph_spacing(p, after=4, line=1.25)
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_run_font(r1, bold=True)
        r2 = p.add_run(text[len(bold_prefix):])
        set_run_font(r2)
    else:
        r = p.add_run(text)
        set_run_font(r)
    return p


def add_number(doc, text, level=0):
    p = doc.add_paragraph(style="List Number" if level == 0 else "List Number 2")
    set_paragraph_spacing(p, after=4, line=1.25)
    r = p.add_run(text)
    set_run_font(r)
    return p


def add_body(doc, text, after=6, bold_prefix=None):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, after=after, line=1.25)
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_run_font(r1, bold=True)
        r2 = p.add_run(text[len(bold_prefix):])
        set_run_font(r2)
    else:
        r = p.add_run(text)
        set_run_font(r)
    return p


def add_label_paragraph(doc, label, text, color=BLUE_DARK):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, after=4, line=1.25)
    r = p.add_run(label + " ")
    set_run_font(r, bold=True, color=color)
    r2 = p.add_run(text)
    set_run_font(r2)
    return p


def add_callout(doc, label, text, fill=CALLOUT, accent=BLUE):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360], indent_dxa=120)
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_border(cell, color=accent, size="12")
    p = cell.paragraphs[0]
    set_paragraph_spacing(p, after=2, line=1.2)
    r = p.add_run(label)
    set_run_font(r, size=10.5, bold=True, color=accent)
    p2 = cell.add_paragraph()
    set_paragraph_spacing(p2, after=0, line=1.2)
    r2 = p2.add_run(text)
    set_run_font(r2, size=10.5)
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, after=2, line=1.0)
    return table


def add_table(doc, headers, rows, widths, header_fill=LIGHT_BLUE, font_size=9.4):
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_geometry(table, widths, indent_dxa=120)
    mark_header_row(table.rows[0])
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, header_fill)
        set_cell_border(cell, color="B8C4D6", size="6")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_paragraph_spacing(p, after=0, line=1.1)
        r = p.add_run(header)
        set_run_font(r, size=font_size, bold=True, color=NAVY)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            set_cell_border(cells[i], color="D0D5DD", size="6")
            p = cells[i].paragraphs[0]
            set_paragraph_spacing(p, after=0, line=1.15)
            r = p.add_run(str(value))
            set_run_font(r, size=font_size)
    spacer = doc.add_paragraph()
    set_paragraph_spacing(spacer, after=2, line=1.0)
    return table


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    set_run_font(r, size={1: 16, 2: 13, 3: 12}[level], color={1: BLUE, 2: BLUE, 3: BLUE_DARK}[level], bold=True)
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, before=3, after=8, line=1.1)
    r = p.add_run(text)
    set_run_font(r, size=9.5, color=MUTED, italic=True)
    return p


def create_pipeline_image():
    W, H = 1800, 650
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    font_path = r"C:\Windows\Fonts\tahoma.ttf"
    bold_path = r"C:\Windows\Fonts\tahomabd.ttf"
    title = ImageFont.truetype(bold_path, 38)
    label = ImageFont.truetype(bold_path, 25)
    small = ImageFont.truetype(font_path, 20)
    draw.text((60, 35), "Single-Channel EEG Sleep Stage Classification Pipeline", font=title, fill="#0B2545")
    boxes = [
        ("EEG", "30 s / 3,000 samples", "#E8EEF5"),
        ("Preprocess", "filter + normalize", "#F2F4F7"),
        ("SST", "time-frequency map", "#FFF4D6"),
        ("CNN", "local features", "#E8EEF5"),
        ("Contrastive", "separate embeddings", "#F4F6F9"),
        ("2× GRU", "temporal pattern", "#E8EEF5"),
        ("5 stages", "W / N1 / N2 / N3 / REM", "#DDEFE5"),
    ]
    x0, y0 = 45, 205
    bw, bh, gap = 220, 185, 25
    for i, (top, bottom, fill) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        draw.rounded_rectangle((x, y0, x + bw, y0 + bh), radius=22, fill=fill, outline="#9AA9BC", width=3)
        top_box = draw.textbbox((0, 0), top, font=label)
        bottom_box = draw.multiline_textbbox((0, 0), bottom, font=small, spacing=5, align="center")
        draw.text((x + (bw - (top_box[2] - top_box[0])) / 2, y0 + 38), top, font=label, fill="#0B2545")
        draw.multiline_text((x + (bw - (bottom_box[2] - bottom_box[0])) / 2, y0 + 98), bottom, font=small, fill="#334155", spacing=5, align="center")
        if i < len(boxes) - 1:
            ax = x + bw + 5
            ay = y0 + bh / 2
            draw.line((ax, ay, ax + gap - 10, ay), fill="#2E74B5", width=5)
            draw.polygon([(ax + gap - 10, ay - 10), (ax + gap, ay), (ax + gap - 10, ay + 10)], fill="#2E74B5")
    draw.text((60, 470), "The model learns both local signal patterns and the sequence of short windows inside each 30-second epoch.", font=small, fill="#667085")
    img.save(PIPELINE_PATH)


def configure_document(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Tahoma"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Tahoma")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Tahoma")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Tahoma")
    normal.font.size = Pt(11)
    normal.font.color.rgb = rgb(INK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for level, size, color, before, after in [(1, 16, BLUE, 18, 10), (2, 13, BLUE, 14, 7), (3, 12, BLUE_DARK, 10, 5)]:
        style = styles[f"Heading {level}"]
        style.font.name = "Tahoma"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Tahoma")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = rgb(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.15
        style.paragraph_format.keep_with_next = True

    for name in ["List Bullet", "List Bullet 2", "List Number", "List Number 2"]:
        style = styles[name]
        style.font.name = "Tahoma"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Tahoma")
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.25

    for name, size, color, bold, italic in [
        ("Doc Kicker", 10.5, GOLD, True, False),
        ("Doc Title", 28, NAVY, True, False),
        ("Doc Subtitle", 14, MUTED, False, False),
        ("Doc Small", 9.5, MUTED, False, False),
    ]:
        if name in styles:
            style = styles[name]
        else:
            style = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = "Tahoma"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Tahoma")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Tahoma")
        style.font.size = Pt(size)
        style.font.color.rgb = rgb(color)
        style.font.bold = bold
        style.font.italic = italic

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_spacing(hp, after=0, line=1.0)
    hr = hp.add_run("Sleep Stage Classification  |  Research Guide")
    set_run_font(hr, size=8.5, color=MUTED, bold=True)
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_paragraph_spacing(fp, after=0, line=1.0)
    fr = fp.add_run("Page ")
    set_run_font(fr, size=9, color=MUTED)
    add_page_number(fp)


def add_cover(doc):
    for _ in range(5):
        p = doc.add_paragraph()
        set_paragraph_spacing(p, after=0, line=1.0)
    p = doc.add_paragraph(style="Doc Kicker")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=16, line=1.0)
    r = p.add_run("RESEARCH GUIDE")
    set_run_font(r, size=10.5, color=GOLD, bold=True)
    p = doc.add_paragraph(style="Doc Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=8, line=1.0)
    r = p.add_run("Sleep Stage Classification\nfrom Single-Channel EEG")
    set_run_font(r, size=27, color=NAVY, bold=True)
    p = doc.add_paragraph(style="Doc Subtitle")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=22, line=1.15)
    r = p.add_run("ปูพื้นฐานตั้งแต่ EEG, dataset และ sleep stages\nจนถึง SST, CNN, contrastive learning, GRU และการประเมินผล")
    set_run_font(r, size=14, color=MUTED)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=75, line=1.0)
    r = p.add_run("เอกสารอธิบายโครงงานสำหรับการทำความเข้าใจและการนำเสนอ")
    set_run_font(r, size=10.5, color=MUTED, italic=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=3, line=1.0)
    r = p.add_run("Project focus: Sleep-EDF Expanded + Fpz-Cz EEG")
    set_run_font(r, size=11, color=NAVY, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, after=0, line=1.0)
    r = p.add_run("Prepared: 19 August 2026")
    set_run_font(r, size=9.5, color=MUTED)
    doc.add_page_break()


def add_intro_and_map(doc):
    add_heading(doc, "เอกสารนี้ตอบคำถามอะไร", 1)
    add_body(doc, "โครงงานนี้ศึกษาว่าเราสามารถใช้สัญญาณไฟฟ้าจากสมองเพียงหนึ่งช่อง หรือ single-channel EEG เพื่อทำนายว่าคนกำลังอยู่ใน sleep stage ใดได้หรือไม่ โดยแบ่งการนอนออกเป็น 5 กลุ่ม ได้แก่ Wake, N1, N2, N3 และ REM")
    add_body(doc, "พูดให้สั้นที่สุด: เรารับ EEG 30 วินาทีเข้าโมเดล แปลงสัญญาณให้เห็นรูปแบบด้านเวลาและความถี่ เรียนรู้ feature ของสัญญาณ แล้วให้โมเดลตอบว่า epoch นั้นเป็น sleep stage ใด")
    add_callout(doc, "สรุปหนึ่งประโยค", "นี่เป็นงาน EEG-based sleep staging หรือการจำแนกช่วงการนอนจาก EEG ไม่ใช่ระบบวินิจฉัยโรค และไม่ใช่ BCI ที่สั่งงานอุปกรณ์โดยตรง")

    add_heading(doc, "วิธีอ่านเอกสาร", 1)
    add_body(doc, "เอกสารเรียงจากพื้นฐานไปหาขั้นสูง หากยังไม่คุ้นกับ EEG ให้อ่านหัวข้อ 1-4 ก่อน จากนั้นจึงอ่านหัวข้อ 5-9 เพื่อเข้าใจวิธีทำโครงงานและการประเมินผล")
    add_table(doc, ["ส่วน", "เนื้อหา", "ระดับ"], [
        ("1-2", "ปัญหา, sleep stages, EEG และ BCI", "พื้นฐาน"),
        ("3-4", "dataset, labels, preprocessing และการแบ่งข้อมูล", "พื้นฐาน-กลาง"),
        ("5-7", "SST, CNN, contrastive learning, GRU และ pipeline", "กลาง-สูง"),
        ("8-9", "metrics, experiment design, leakage และข้อจำกัด", "สูง"),
        ("10", "glossary และแผนการทำงานต่อไป", "ทบทวน"),
    ], [1450, 6200, 1710])

    add_heading(doc, "คำตอบสั้นสำหรับการนำเสนอ", 1)
    add_body(doc, "เราจะพัฒนาระบบที่ใช้ EEG เพียงหนึ่ง channel จาก Sleep-EDF เพื่อจำแนก sleep stage แบบ 5 classes โดยใช้ Synchrosqueezed Transform สร้าง time-frequency representation จากนั้นใช้ CNN เรียนรู้ pattern ระยะสั้น ใช้ contrastive learning ช่วยแยก feature ของแต่ละ stage และใช้ GRU เรียนรู้ลำดับของสัญญาณย่อยภายใน epoch ก่อนวัดผลด้วย accuracy, macro-F1, Cohen's kappa และ confusion matrix")


def add_foundations(doc):
    add_heading(doc, "1. ปัญหาที่เรากำลังแก้", 1)
    add_body(doc, "โดยปกติการแบ่ง sleep stage ทำโดยผู้เชี่ยวชาญตรวจ polysomnography หรือ PSG ซึ่งประกอบด้วย EEG, EOG, EMG และสัญญาณอื่น ๆ แล้วให้ label ทุกช่วงเวลา 30 วินาที วิธีนี้มีคุณค่าในทางคลินิก แต่ใช้แรงงานมากและต้องใช้อุปกรณ์หลายชนิด")
    add_body(doc, "โจทย์ของเราจึงคือการศึกษาว่า EEG เพียงช่องเดียวจะให้ข้อมูลเพียงพอสำหรับการแบ่ง sleep stage อัตโนมัติหรือไม่ หากทำได้ ระบบจะมีความซับซ้อนน้อยลงและอาจนำไปต่อยอดกับ wearable หรือ home monitoring ได้ง่ายขึ้น")

    add_heading(doc, "1.1 งานนี้เกี่ยวกับ BCI หรือ EEG กันแน่", 2)
    add_body(doc, "EEG คือสัญญาณที่วัดความต่างศักย์ไฟฟ้าบนหนังศีรษะ ส่วน BCI หรือ Brain-Computer Interface คือระบบที่นำสัญญาณสมองไปถอดรหัสเพื่อสั่งงานหรือสื่อสารกับอุปกรณ์ เช่น ควบคุม cursor, wheelchair หรือระบบสื่อสาร")
    add_body(doc, "โครงงานของเราใช้ EEG เป็นข้อมูลหลักและอยู่ในกลุ่ม neurotechnology หรือ BCI-related signal processing ได้ แต่ output ของเราเป็น sleep-stage label ไม่ใช่คำสั่งควบคุมอุปกรณ์ ดังนั้นคำเรียกที่แม่นยำที่สุดคือ automatic EEG sleep staging")

    add_heading(doc, "1.2 Sleep stage คืออะไร", 2)
    add_body(doc, "การนอนเป็นกระบวนการที่สมองและร่างกายเปลี่ยนสถานะตลอดคืน เราแบ่งช่วงการนอนเป็น epoch ละ 30 วินาที แล้วกำหนด label ให้แต่ละ epoch")
    add_table(doc, ["Class", "ชื่อเต็ม", "ภาพรวมเชิงสรีรวิทยา", "ความท้าทาย"], [
        ("W", "Wake", "ตื่นหรือมีการทำงานของสมองแบบตื่นตัว", "อาจสับสนกับ REM"),
        ("N1", "Non-REM 1", "ช่วงเปลี่ยนจากตื่นเข้าสู่หลับ เริ่มมี theta", "เป็น class ที่ยากที่สุดและมักมีจำนวนน้อย"),
        ("N2", "Non-REM 2", "หลับตื้น มี sleep spindle และ K-complex", "อาจสับสนกับ N1 หรือ N3"),
        ("N3", "Non-REM 3", "หลับลึก มี slow-wave หรือ delta เด่น", "อาจมีข้อมูลน้อยและมี class imbalance"),
        ("REM", "Rapid Eye Movement", "สมอง active คล้ายตื่น แต่กล้ามเนื้อส่วนใหญ่ผ่อนคลาย", "อาจสับสนกับ W และ N2"),
    ], [850, 1750, 4050, 2710])
    add_callout(doc, "จำง่าย", "N1 มักยากที่สุด เพราะเป็นช่วงเปลี่ยนผ่าน ส่วน N2 มักมีจำนวนมากที่สุดในข้อมูล sleep staging จึงต้องดู macro-F1 และผลราย class ไม่ใช่ดู accuracy อย่างเดียว", fill="FFF8E8", accent=GOLD)

    add_heading(doc, "1.3 Epoch และ hypnogram", 2)
    add_body(doc, "Epoch คือช่วงเวลาคงที่ที่ใช้เป็นหน่วยการจำแนก ในโครงงานนี้หนึ่ง epoch ยาว 30 วินาที ถ้า sampling rate เท่ากับ 100 Hz จะมีตัวอย่างสัญญาณ 100 x 30 = 3,000 samples")
    add_body(doc, "Hypnogram คือกราฟที่แสดงลำดับ sleep stage ตลอดทั้งคืน เช่น W -> N1 -> N2 -> N3 -> N2 -> REM การเห็นลำดับนี้สำคัญ เพราะ sleep stage ไม่ได้เกิดแบบสุ่ม แต่มี transition และบริบทตามเวลา")

    add_heading(doc, "1.4 EEG แบบเข้าใจง่าย", 2)
    add_body(doc, "EEG หรือ electroencephalography คือ time series ของแรงดันไฟฟ้าที่วัดจาก electrodes บนหนังศีรษะ สัญญาณจะเปลี่ยนแปลงตามกิจกรรมของเซลล์ประสาทและถูกบันทึกเป็น amplitude ตามเวลา")
    add_table(doc, ["คำศัพท์", "ความหมาย", "ตัวอย่างในงานนี้"], [
        ("Amplitude", "ขนาดของแรงดันในขณะนั้น", "หน่วยมักเป็น microvolt"),
        ("Sampling rate", "จำนวนจุดข้อมูลต่อวินาที", "100 Hz"),
        ("Frequency", "จำนวนรอบการสั่นต่อวินาที", "หน่วย Hz"),
        ("Channel", "เส้นสัญญาณจาก electrode หรือ derivation หนึ่งชุด", "Fpz-Cz"),
        ("Montage", "วิธีอ้างอิงความต่างศักย์ระหว่าง electrodes", "Fpz-Cz เป็น bipolar derivation"),
        ("Artifact", "สัญญาณรบกวนที่ไม่ใช่กิจกรรมสมองที่ต้องการ", "movement, electrode noise, muscle"),
    ], [1700, 4800, 2860])

    add_heading(doc, "1.5 Time domain และ frequency domain", 2)
    add_body(doc, "Time domain บอกว่าสัญญาณขึ้นลงอย่างไรตามเวลา ส่วน frequency domain บอกว่าสัญญาณประกอบด้วยความถี่ใดมากน้อยเพียงใด Sleep stage หลายกลุ่มมีรูปแบบความถี่ที่ต่างกัน ดังนั้นการมองทั้งสองมุมจึงมีประโยชน์")
    add_table(doc, ["Rhythm", "ช่วงความถี่โดยประมาณ", "ความหมายแบบง่าย"], [
        ("Delta", "0.5-4 Hz", "เด่นใน N3 หรือ deep sleep"),
        ("Theta", "4-8 Hz", "พบมากขึ้นใน N1 และ sleep transition"),
        ("Alpha", "8-13 Hz", "มักสัมพันธ์กับ relaxed wakefulness"),
        ("Beta", "13-30 Hz", "กิจกรรมความถี่สูงและความตื่นตัว"),
        ("Gamma", ">30 Hz", "ความถี่สูง แต่ไวต่อ noise และไม่ใช่แกนหลักของ baseline นี้"),
    ], [1700, 2600, 5060])


def add_data(doc):
    add_heading(doc, "2. Data: เราใช้ข้อมูลอะไร", 1)
    add_body(doc, "Dataset หลักคือ Sleep-EDF Expanded จาก PhysioNet ซึ่งเป็นฐานข้อมูล PSG ที่มี EEG, EOG, chin EMG และ hypnogram ที่ผู้เชี่ยวชาญทำ annotation ไว้ เราจะเลือกใช้ EEG เพียง channel เดียวคือ Fpz-Cz เพื่อให้ตรงกับโจทย์ single-channel")
    add_label_paragraph(doc, "Dataset link:", "Sleep-EDF Expanded — https://physionet.org/content/sleep-edfx/1.0.0/")
    add_table(doc, ["องค์ประกอบ", "สิ่งที่ใช้ในโครงงาน", "เหตุผล"], [
        ("Raw signal", "EEG Fpz-Cz", "ลดความซับซ้อนและศึกษาความพอเพียงของ EEG ช่องเดียว"),
        ("Annotation", "Hypnogram", "ใช้เป็น ground truth หรือคำตอบอ้างอิง"),
        ("Unit", "30-second epoch", "สอดคล้องกับมาตรฐานการ sleep scoring"),
        ("Classes", "W, N1, N2, N3, REM", "เป็น 5-class sleep staging target"),
        ("File format", "EDF/EDF+", "รูปแบบมาตรฐานของ physiological waveform"),
    ], [1800, 3100, 4460])

    add_heading(doc, "2.1 ไฟล์ PSG และ hypnogram", 2)
    add_body(doc, "โดยทั่วไปข้อมูลหนึ่งคืนจะมีไฟล์ PSG ที่เก็บสัญญาณต่อเนื่อง และไฟล์ hypnogram ที่เก็บ annotation ของแต่ละช่วงเวลา ชื่อไฟล์จะมีรหัสของ subject และ night จึงต้องอ่าน metadata ให้ถูกต้องก่อนแบ่งข้อมูล")
    add_body(doc, "ตัวอย่างเชิงแนวคิด: ไฟล์ PSG ให้ข้อมูลสัญญาณ EEG ในทุก sample ส่วน hypnogram บอกว่าเวลาเริ่มต้นของ epoch นั้นมี label เป็น W, N1, N2, N3 หรือ REM การเตรียมข้อมูลต้อง align สองส่วนนี้ให้ตรงกัน")

    add_heading(doc, "2.2 ข้อมูลที่เรามีอยู่ตอนนี้", 2)
    add_table(doc, ["รายการ", "สถานะปัจจุบัน", "คำแปลในการวิจัย"], [
        ("Local records", "4 คืน: SC4001E0, SC4002E0, SC4011E0, SC4012E0", "เป็น pilot subset"),
        ("Participants", "2 subjects x 2 nights", "ยังไม่พอสำหรับ claim เรื่อง generalization"),
        ("Scored epochs", "588 epochs", "ใช้ตรวจ pipeline และ debug"),
        ("Current split", "ยังต้องแก้ให้ subject-wise", "ผล pilot เดิมยังไม่ใช่ final evaluation"),
    ], [2200, 3800, 3360])
    add_callout(doc, "ข้อควรจำ", "ตัวเลขจาก pilot 4 คืนใช้ดูว่าโค้ดและ pipeline ทำงานหรือไม่ ไม่ควรนำไปอ้างว่าเป็นประสิทธิภาพจริงของโมเดล เพราะข้อมูลน้อยและ subject อาจปรากฏทั้งใน train และ test", fill="FFF1F2", accent=RED)

    add_heading(doc, "2.3 Data preprocessing", 2)
    add_body(doc, "ก่อนส่งเข้าโมเดล เราต้องทำให้สัญญาณและ label อยู่ในรูปแบบที่สม่ำเสมอ ขั้นตอนหลักมีดังนี้")
    for text in [
        "อ่านสัญญาณ EEG และตรวจ channel name, sampling rate และจำนวน sample",
        "อ่าน hypnogram และแปลง annotation ให้เป็น 5 classes ที่ใช้",
        "ตัด epoch ที่ไม่มี label, unknown, movement หรือไม่มีข้อมูลเพียงพอ",
        "ปรับ sampling rate ให้ตรงกับ pipeline หากจำเป็น",
        "ทำ filtering หรือ detrending ตาม protocol ที่กำหนด",
        "ทำ normalization โดย fit จาก training data เท่านั้น",
        "เก็บข้อมูลเป็นคู่ (epoch_signal, label, subject_id, record_id)",
    ]:
        add_number(doc, text)

    add_heading(doc, "2.4 ทำไมต้องแบ่งข้อมูลแบบ subject-wise", 2)
    add_body(doc, "ถ้าเราแบ่งแบบสุ่มระดับ epoch คนเดียวกันอาจมี epoch บางส่วนอยู่ใน training และบางส่วนอยู่ใน test โมเดลอาจจำลักษณะเฉพาะของคนหรือ recording ได้ ทำให้คะแนนดูสูงกว่าความสามารถในการนำไปใช้กับคนใหม่")
    add_body(doc, "การแบ่งแบบ subject-wise หมายความว่า subject เดียวกันต้องอยู่ในชุดใดชุดหนึ่งเท่านั้น เช่น train subjects, validation subjects และ test subjects ไม่ซ้ำกัน แม้ subject เดียวกันจะมีหลายคืนก็ต้องอยู่กลุ่มเดียวกัน")
    add_table(doc, ["การแบ่ง", "ถูกต้องหรือไม่", "ผลกระทบ"], [
        ("Random epoch split", "ไม่เหมาะสำหรับ final result", "เสี่ยง data leakage และ optimistic score"),
        ("Record/night split", "ดีกว่า แต่ยังไม่พอถ้ามีหลายคืนต่อ subject", "คนเดียวกันอาจอยู่หลายชุด"),
        ("Subject-wise split", "แนะนำ", "วัดการ generalize ไปยังคนใหม่ได้ดีกว่า"),
        ("Cross-dataset test", "แข็งแรงที่สุดในระดับหนึ่ง", "ทดสอบ domain shift จาก dataset อื่น"),
    ], [2100, 2300, 4960])


def add_objectives(doc):
    add_heading(doc, "3. วัตถุประสงค์และสมมติฐาน", 1)
    add_heading(doc, "3.1 Primary objective", 2)
    add_body(doc, "พัฒนาและประเมินระบบ deep learning ที่จำแนก sleep stage 5 classes จาก single-channel EEG Fpz-Cz โดยใช้ข้อมูล Sleep-EDF Expanded และประเมินด้วย subject-wise split")
    add_heading(doc, "3.2 Secondary objectives", 2)
    for text in [
        "ศึกษาว่า time-frequency representation แบบ SST ช่วยให้โมเดลเห็นรูปแบบของ EEG ชัดขึ้นหรือไม่",
        "ศึกษาว่า contrastive learning ช่วยแยก embedding ของ sleep stages โดยเฉพาะ stage ที่สับสนกันได้หรือไม่",
        "เปรียบเทียบโมเดลเต็มกับ baseline ที่เรียบง่าย เช่น CNN และ CNN-GRU",
        "วิเคราะห์ว่า class ใดทำได้ดีและ class ใดเป็น bottleneck โดยใช้ per-class F1 และ confusion matrix",
        "ประเมินความเป็นไปได้ในการรันบนคอมพิวเตอร์ที่มีทรัพยากรจำกัด",
    ]:
        add_bullet(doc, text)
    add_heading(doc, "3.3 Hypotheses", 2)
    add_table(doc, ["สมมติฐาน", "สิ่งที่คาดว่าจะเห็น"], [
        ("H1: SST ช่วยเรื่อง feature", "โมเดลที่ใช้ SST จะมี macro-F1 สูงกว่า raw-signal baseline"),
        ("H2: Contrastive learning ช่วย representation", "embedding ของ class จะแยกได้ดีขึ้นและ confusion ลดลงบางคู่"),
        ("H3: GRU ช่วยลำดับสัญญาณ", "โมเดลที่มี sequence model จะจับ pattern ของ subwindows ได้ดีกว่า CNN อย่างเดียว"),
        ("H4: Subject-wise score ต่ำกว่า random split", "คะแนนจะลดลง แต่เป็นตัวแทนของ generalization ที่น่าเชื่อถือกว่า"),
    ], [3900, 5460])


def add_method(doc):
    add_heading(doc, "4. วิธีการของเรา: จากสัญญาณไปสู่คำตอบ", 1)
    doc.add_picture(str(PIPELINE_PATH), width=Inches(6.5))
    picture = doc.inline_shapes[-1]
    picture._inline.docPr.set("descr", "Pipeline diagram showing EEG preprocessing, SST, CNN, contrastive learning, GRU and five sleep-stage outputs")
    picture._inline.docPr.set("title", "Sleep stage classification pipeline")
    add_caption(doc, "ภาพรวม pipeline ของระบบ: 30-second EEG epoch -> feature representation -> sequence model -> sleep-stage prediction")

    add_heading(doc, "4.1 ภาพรวม pipeline", 2)
    for text in [
        "รับ EEG 30 วินาทีจาก Fpz-Cz",
        "ทำ preprocessing และ normalization",
        "แบ่ง epoch เป็น short segments ขนาด 256 samples",
        "สร้าง time-frequency representation ด้วย SST-like transform",
        "ใช้ CNN เรียนรู้ local pattern ของแต่ละ segment",
        "ใช้ contrastive learning ปรับ embedding ให้แยก class ได้ดีขึ้น",
        "ส่ง feature ของหลาย segment เข้า stacked GRU",
        "ใช้ classifier ทำนาย W, N1, N2, N3 หรือ REM",
    ]:
        add_number(doc, text)

    add_heading(doc, "4.2 ทำไมต้องแบ่ง 30 วินาทีเป็นช่วงย่อย", 2)
    add_body(doc, "EEG 30 วินาทีที่ sampling rate 100 Hz มี 3,000 samples หากป้อนเข้า CNN ตรง ๆ อาจมีมิติยาวและเรียนรู้ยาก งานหลักจึงแบ่งเป็น window สั้น 256 samples เพื่อให้ CNN เรียนรู้ local waveform และ local spectral pattern ได้ง่ายขึ้น")
    add_body(doc, "หลัง CNN แปลงแต่ละ window เป็น feature vector แล้ว feature เหล่านั้นจะถูกมองเป็นลำดับ เช่น window 1, window 2, ... โมเดล GRU จึงเรียนรู้ว่าลำดับของ pattern เหล่านี้ช่วยบอก sleep stage อย่างไร")

    add_heading(doc, "4.3 Synchrosqueezed Transform หรือ SST", 2)
    add_body(doc, "SST เป็นวิธีสร้าง time-frequency representation โดยเริ่มจากการดูว่าสัญญาณมีพลังงานอยู่ที่เวลาและความถี่ใด แล้ว reassign พลังงานให้ไปอยู่บริเวณความถี่ที่สอดคล้องกับ instantaneous frequency มากขึ้น ผลคือภาพ time-frequency ที่คมและอ่านโครงสร้างของ oscillation ได้ชัดกว่า representation ที่กระจายกว้าง")
    add_label_paragraph(doc, "STFT แบบแนวคิด:", "นำหน้าต่างสั้น ๆ เลื่อนไปตามเวลา แล้วคำนวณความถี่ของสัญญาณในแต่ละตำแหน่ง")
    add_label_paragraph(doc, "SST แบบแนวคิด:", "นำ coefficient ของ STFT ไปจัดวางใหม่ตามความถี่จริงที่ประเมินจาก phase change")
    add_callout(doc, "ไม่ต้องจำสูตรทั้งหมดตอนนำเสนอ", "ให้จำว่า SST เปลี่ยน EEG จากคลื่นเส้นเดียวใน time domain ให้เป็นแผนที่ที่บอกว่าแต่ละช่วงเวลามีพลังงานอยู่ในความถี่ใด จากนั้น CNN จะอ่านแผนที่นี้เหมือนอ่านภาพ feature", fill="FFF8E8", accent=GOLD)

    add_heading(doc, "4.4 CNN: เรียนรู้ local feature", 2)
    add_body(doc, "CNN หรือ Convolutional Neural Network ใช้ filter ขนาดเล็กเลื่อนบน input เพื่อจับ pattern ที่เกิดเฉพาะบริเวณ เช่น waveform, edge ของพลังงาน หรือโครงสร้างบางช่วงของ time-frequency map")
    add_body(doc, "ในงานนี้ CNN ไม่ได้ทำหน้าที่แค่จำแนกโดยตรง แต่ทำหน้าที่เป็น encoder เปลี่ยนข้อมูลดิบหรือ SST map ให้เป็น embedding ที่กะทัดรัดและมีข้อมูลสำคัญสำหรับ sleep stage")
    add_table(doc, ["องค์ประกอบ CNN", "หน้าที่"], [
        ("Convolution", "ตรวจ local pattern ด้วย learnable filters"),
        ("Activation", "เพิ่มความไม่เป็นเชิงเส้นให้โมเดลเรียนรู้รูปแบบซับซ้อนได้"),
        ("Pooling/stride", "ลดขนาดและเพิ่ม receptive field"),
        ("Normalization", "ช่วยให้การ train เสถียรขึ้น"),
        ("Embedding", "ตัวแทน feature ที่ส่งต่อไปยัง contrastive loss และ GRU"),
    ], [2600, 6760])

    add_heading(doc, "4.5 Contrastive learning: เรียนรู้ว่าอะไรควรใกล้หรือไกล", 2)
    add_body(doc, "Contrastive learning ไม่ได้สอนโมเดลด้วยการบอกคำตอบเพียงอย่างเดียว แต่สอนให้ representation ของตัวอย่างที่ควรเหมือนกันอยู่ใกล้กัน และ representation ของตัวอย่างต่าง class อยู่ห่างกัน")
    add_body(doc, "ตัวอย่างเชิงแนวคิด: หาก epoch สองอันเป็น N2 โมเดลควรสร้าง embedding ที่คล้ายกัน แม้ถูกทำ augmentation ต่างกันเล็กน้อย แต่ embedding ของ N2 ควรแยกจาก N3 หรือ REM ให้ชัดขึ้น")
    add_table(doc, ["คำศัพท์", "ความหมาย"], [
        ("Anchor", "ตัวอย่างหลักที่กำลังพิจารณา"),
        ("Positive", "ตัวอย่างหรือ augmented view ที่ควรอยู่ใกล้ anchor"),
        ("Negative", "ตัวอย่างที่ควรแยกออกจาก anchor"),
        ("Embedding", "เวกเตอร์ feature ที่โมเดลสร้างขึ้น"),
        ("Temperature", "ตัวควบคุมความคมของการเปรียบเทียบ similarity"),
    ], [2400, 6960])

    add_heading(doc, "4.6 GRU: เรียนรู้ลำดับ", 2)
    add_body(doc, "GRU หรือ Gated Recurrent Unit เป็น recurrent neural network ที่ใช้ gates ควบคุมว่าจะเก็บหรือลืมข้อมูลจากเวลาเดิมอย่างไร เหมาะกับข้อมูลที่เป็น sequence และมักเบากว่า LSTM ในจำนวนพารามิเตอร์")
    add_body(doc, "ในโครงงานนี้ GRU รับลำดับของ feature จาก short windows ภายใน epoch เดียว จึงควรอธิบายให้ตรงว่าเป็น sequential modeling ภายใน 30-second epoch ไม่ใช่การ model hypnogram ทั้งคืนแบบเต็มรูปแบบ")

    add_heading(doc, "4.7 Classifier และ output", 2)
    add_body(doc, "หลัง GRU จะมี classification head เช่น linear layer ที่ให้คะแนน 5 classes แล้วใช้ softmax แปลงคะแนนเป็นความน่าจะเป็นของ W, N1, N2, N3 และ REM class ที่มี probability สูงสุดจะเป็น prediction")
    add_body(doc, "ใน training จะใช้ loss เช่น cross-entropy เพื่อทำให้ probability ของ class ที่ถูกต้องสูงขึ้น หากข้อมูล imbalance มาก อาจใช้ class-weighted loss หรือ focal loss แต่ต้องระบุ protocol ให้ชัดเจน")

    add_heading(doc, "4.8 สิ่งที่ implementation ปัจจุบันทำและยังไม่ใช่", 2)
    add_table(doc, ["หัวข้อ", "สถานะปัจจุบัน", "ความหมาย"], [
        ("SST", "ใช้ SST-like reassignment จาก STFT", "เป็น reproduction เชิงวิศวกรรม ไม่ใช่การรับรองว่าเหมือน implementation ต้นฉบับทุกจุด"),
        ("CNN pretraining", "มีใน pipeline", "ใช้สร้าง feature encoder เริ่มต้น"),
        ("Contrastive stage", "มีใน pipeline", "ใช้ refine embedding ก่อน classification"),
        ("GRU", "ใช้ 2-layer sequence model", "รับ feature ของ subwindows ภายใน epoch"),
        ("Full-night temporal context", "ยังไม่มีใน version นี้", "ยังไม่ได้ใช้ epoch ข้างเคียงเป็น sequence เดียวกัน"),
        ("Final evaluation", "ยังต้องแก้ subject-wise split", "ผลปัจจุบันเป็น diagnostic pilot"),
    ], [2700, 2600, 4060])


def add_evaluation(doc):
    add_heading(doc, "5. วิธีประเมินผล", 1)
    add_body(doc, "การประเมินผลไม่ใช่แค่รันโมเดลแล้วดู accuracy แต่ต้องออกแบบการทดลองให้ตอบได้ว่าโมเดล generalize ไปยัง subject ใหม่ได้จริงหรือไม่ และรู้ว่าโมเดลพลาดใน sleep stage ใด")

    add_heading(doc, "5.1 Metrics หลัก", 2)
    add_table(doc, ["Metric", "ความหมาย", "ควรใช้เมื่อใด"], [
        ("Accuracy", "สัดส่วน prediction ที่ถูกทั้งหมด", "ดูภาพรวม แต่ไวต่อ class imbalance"),
        ("Precision", "เมื่อโมเดลทายเป็น class นี้ ถูกจริงกี่ครั้ง", "ดู false positive"),
        ("Recall", "ตัวอย่างจริงของ class นี้ โมเดลจับได้กี่เปอร์เซ็นต์", "ดู false negative"),
        ("F1-score", "ค่าเฉลี่ยเชิงสมดุลระหว่าง precision และ recall", "เหมาะกับ class ที่ไม่สมดุล"),
        ("Macro-F1", "เฉลี่ย F1 ของทุก class โดยให้น้ำหนักเท่ากัน", "ตัวชี้วัดสำคัญเมื่อ N1 มีน้อย"),
        ("Cohen's kappa", "วัด agreement หลังหัก agreement ที่เกิดโดยบังเอิญ", "ใช้เสริม accuracy สำหรับ multiclass"),
    ], [1800, 4700, 2860])
    add_label_paragraph(doc, "ตัวอย่างสูตร:", "Accuracy = จำนวนที่ทายถูก / จำนวนตัวอย่างทั้งหมด")
    add_label_paragraph(doc, "ตัวอย่างสูตร:", "F1 = 2 x (Precision x Recall) / (Precision + Recall)")
    add_label_paragraph(doc, "Macro-F1:", "นำ F1 ของ W, N1, N2, N3 และ REM มาเฉลี่ย โดยไม่ปล่อยให้ N2 ที่มีจำนวนมากกลบ class อื่น")

    add_heading(doc, "5.2 Confusion matrix และ per-class analysis", 2)
    add_body(doc, "Confusion matrix แสดงว่า true label อยู่แถวใดและ prediction ไปตกคอลัมน์ใด หาก N1 ถูกทายเป็น N2 บ่อย แปลว่าโมเดลแยก transition ระหว่าง sleep stage ได้ยาก การรายงานเมทริกซ์นี้ช่วยให้เห็นปัญหาที่ accuracy เดียวซ่อนไว้")
    add_body(doc, "ควรรายงาน F1, precision และ recall แยกตาม W, N1, N2, N3 และ REM พร้อมตัวอย่าง hypnogram หรือ sequence prediction เพื่อดูว่าโมเดลสร้าง transition ที่สมเหตุผลหรือไม่")

    add_heading(doc, "5.3 Baseline และ ablation study", 2)
    add_body(doc, "เพื่อพิสูจน์ว่าส่วนประกอบของโมเดลช่วยจริง เราควรเพิ่มทีละส่วนและเปรียบเทียบภายใต้ split และ training budget เดียวกัน")
    add_table(doc, ["Experiment", "องค์ประกอบ", "คำถามที่ตอบ"], [
        ("B0: Majority baseline", "ทาย class ที่มีจำนวนมากที่สุด", "โมเดลเรียนรู้อะไรได้เกินกว่าการเดาง่าย ๆ หรือไม่"),
        ("B1: Raw CNN", "raw EEG + CNN", "CNN จาก signal ดิบทำได้แค่ไหน"),
        ("B2: CNN-GRU", "raw EEG + CNN + GRU", "sequence model ช่วยหรือไม่"),
        ("A1: SST-CNN", "SST + CNN", "time-frequency representation ช่วยหรือไม่"),
        ("A2: SST + contrastive", "SST + CNN + contrastive", "contrastive learning ช่วย representation หรือไม่"),
        ("Full model", "SST + CNN + contrastive + 2-layer GRU", "pipeline เต็มดีขึ้นหรือไม่"),
    ], [2000, 3500, 3860])

    add_heading(doc, "5.4 Experiment protocol ที่ควรใช้", 2)
    for text in [
        "แยก subject เป็น train, validation และ test โดยไม่มี subject ซ้ำกัน",
        "fit normalization, class weights และ augmentation policy จาก training data เท่านั้น",
        "ใช้ validation สำหรับเลือก hyperparameters และหยุดการ train",
        "ล็อก random seed และบันทึก configuration เพื่อทำซ้ำได้",
        "รายงาน mean และ standard deviation หากใช้หลาย folds หรือหลาย seeds",
        "เก็บ confusion matrix, per-class metrics และเวลาการ train",
        "เปรียบเทียบทุก baseline ภายใต้ test split เดียวกัน",
    ]:
        add_number(doc, text)

    add_callout(doc, "เกณฑ์สำเร็จที่แนะนำ", "โมเดลเต็มควรดีกว่า raw CNN ใน macro-F1 และไม่ทำให้ N1 recall แย่ลงอย่างมีนัยสำคัญ พร้อมทั้งมี subject-wise test protocol ที่ตรวจสอบได้", fill="EAF5EE", accent=GREEN)


def add_limitations(doc):
    add_heading(doc, "6. ข้อจำกัดและความเสี่ยง", 1)
    add_table(doc, ["ข้อจำกัด", "ทำไมสำคัญ", "วิธีรับมือ"], [
        ("ข้อมูลมีจำนวน subject จำกัด", "model อาจจำคนมากกว่าจำ pattern ของ sleep", "ใช้ subject-wise split และเพิ่มหลาย subject"),
        ("Class imbalance", "N2 หรือ W อาจกลบ N1", "ใช้ macro-F1, class weights และ per-class analysis"),
        ("N1 เป็น transition stage", "ลักษณะคล้าย W/N2 และ label agreement ต่ำกว่า", "เน้น N1 recall/F1 และดู confusion matrix"),
        ("Artifact และ noise", "movement หรือ muscle อาจถูกโมเดลเรียนเป็น sleep feature", "quality check, filtering และ artifact analysis"),
        ("ข้อมูลจากห้องแล็บ", "อาจไม่เหมือน EEG จาก wearable หรือบ้าน", "ทดสอบ cross-dataset เมื่อมีโอกาส"),
        ("Single-channel มีข้อมูลจำกัด", "ขาด EOG/EMG ที่ช่วยแยก REM และ movement", "รายงาน scope อย่างตรงไปตรงมา"),
        ("Paper protocol ไม่เหมือนกัน", "accuracy ข้ามงานเปรียบเทียบตรง ๆ ไม่ได้", "ระบุ dataset, split, channel และ metric ทุกครั้ง"),
        ("Implementation ไม่ตรงต้นฉบับทุกจุด", "ผล reproduction อาจต่างจาก paper", "บันทึก approximation และทำ ablation"),
    ], [2300, 3550, 3510])

    add_heading(doc, "6.1 สิ่งที่งานนี้ยังไม่สามารถอ้างได้", 2)
    for text in [
        "ยังไม่สามารถอ้างว่าโมเดลใช้วินิจฉัยโรคหรือแทน sleep technician ได้",
        "ยังไม่สามารถอ้างว่าใช้ได้กับประชากรทุกกลุ่มหรือกับ wearable ทุกชนิด",
        "ยังไม่สามารถอ้างว่าเป็นวิธีที่มี accuracy สูงสุดโดยรวม เพียงเพราะเป็นงานล่าสุด",
        "ยังไม่ควรใช้ผล pilot 4 คืนเป็นผลลัพธ์หลักของงานวิจัย",
        "ยังไม่ควรเปรียบเทียบคะแนนที่ได้กับ paper อื่น หาก protocol ต่างกัน",
    ]:
        add_bullet(doc, text)

    add_heading(doc, "6.2 ความเสี่ยงด้าน data leakage", 2)
    add_body(doc, "Data leakage คือการที่ข้อมูลจาก test แอบส่งอิทธิพลเข้าไปใน training หรือ model selection ทำให้คะแนนสูงเกินจริง ตัวอย่างที่ต้องระวังคือการสุ่ม epoch จาก subject เดียวกันไปหลายชุด, การ normalize โดยใช้ค่าเฉลี่ยของทั้ง dataset และการเลือก hyperparameter จาก test score")


def add_plan(doc):
    add_heading(doc, "7. แผนการทำงานต่อไป", 1)
    add_table(doc, ["ระยะ", "งาน", "ผลลัพธ์ที่ต้องได้"], [
        ("Phase 0", "ตรวจไฟล์, channel, annotation, subject IDs", "data inventory และ quality report"),
        ("Phase 1", "แก้ subject-wise split และทำ baseline", "valid baseline metrics"),
        ("Phase 2", "ทำ preprocessing และ SST", "SST examples + ablation"),
        ("Phase 3", "train CNN encoder และ contrastive stage", "embedding diagnostics"),
        ("Phase 4", "ต่อ stacked GRU และ classifier", "full-model metrics"),
        ("Phase 5", "หลาย seed/fold และ error analysis", "robustness report"),
        ("Phase 6", "สรุป proposal/report/presentation", "final research package"),
    ], [1300, 4900, 3160])

    add_heading(doc, "7.1 ลำดับที่แนะนำสำหรับคอมของเรา", 2)
    for text in [
        "เริ่มจาก subset ขนาดเล็กเพื่อทดสอบว่า subject-wise split ถูกต้อง",
        "รัน raw CNN baseline ก่อน เพื่อมีตัวเลขอ้างอิง",
        "เพิ่ม SST แล้วตรวจว่า input และ label alignment ไม่พัง",
        "เพิ่ม contrastive stage และตรวจ embedding / loss curve",
        "เพิ่ม GRU และประเมินด้วย metrics ครบชุด",
        "ค่อยขยายไป Sleep-EDF ที่มี subject มากขึ้น",
        "หากต้องการลดเวลา train ให้เปิดใช้ CUDA กับ RTX 3050 และใช้ checkpoint",
    ]:
        add_number(doc, text)

    add_heading(doc, "7.2 ข้อความสำหรับอธิบายกับอาจารย์", 2)
    add_callout(doc, "พูดแบบสั้นและถูกต้อง", "โครงงานนี้เป็นการทำ automatic sleep staging จาก single-channel EEG โดยใช้ Sleep-EDF เป็น dataset เราจะทดสอบว่า time-frequency representation แบบ SST, CNN feature extraction, contrastive learning และ GRU sequence modeling ช่วยจำแนก W, N1, N2, N3 และ REM ได้ดีขึ้นหรือไม่ การประเมินจะใช้ subject-wise split เพื่อวัดการ generalize ไปยังคนที่โมเดลไม่เคยเห็น", fill="EAF5EE", accent=GREEN)


def add_glossary(doc):
    add_heading(doc, "8. Glossary: คำศัพท์ที่ควรรู้", 1)
    glossary = [
        ("EEG", "Electroencephalography; การวัดสัญญาณไฟฟ้าจากสมองผ่าน electrodes บนหนังศีรษะ"),
        ("BCI", "Brain-Computer Interface; ระบบถอดรหัสสัญญาณสมองเพื่อสื่อสารหรือควบคุมอุปกรณ์"),
        ("PSG", "Polysomnography; การบันทึกหลายสัญญาณระหว่างนอน เช่น EEG, EOG และ EMG"),
        ("Fpz-Cz", "EEG bipolar derivation ที่ใช้เป็น single channel ในโครงงานนี้"),
        ("Epoch", "ช่วงเวลาคงที่ที่ใช้เป็นหน่วยวิเคราะห์; งานนี้ใช้ 30 วินาที"),
        ("Hypnogram", "กราฟหรือ annotation ที่แสดง sleep stage ตามเวลา"),
        ("Sampling rate", "จำนวน sample ต่อวินาที เช่น 100 Hz หมายถึง 100 จุดต่อวินาที"),
        ("Artifact", "สัญญาณรบกวนหรือสิ่งที่ไม่ใช่ brain activity ที่ต้องการ"),
        ("STFT", "Short-Time Fourier Transform; แปลงสัญญาณให้เห็นพลังงานตามเวลาและความถี่"),
        ("SST", "Synchrosqueezed Transform; time-frequency transform ที่ reassign พลังงานให้คมขึ้น"),
        ("TFR", "Time-Frequency Representation; ตัวแทนสัญญาณที่มีทั้งแกนเวลาและความถี่"),
        ("CNN", "Convolutional Neural Network; โมเดลที่เรียนรู้ local pattern ด้วย convolution filters"),
        ("GRU", "Gated Recurrent Unit; recurrent model ที่เรียนรู้ dependency ในลำดับ"),
        ("Transformer", "โมเดลที่ใช้ attention จับความสัมพันธ์ระยะไกลใน sequence"),
        ("Encoder", "ส่วนของโมเดลที่เปลี่ยน input ให้เป็น feature representation"),
        ("Embedding", "เวกเตอร์ตัวแทนข้อมูลใน latent space"),
        ("Contrastive learning", "การฝึกให้ representation ที่ควรเหมือนอยู่ใกล้กันและที่ต่างอยู่ห่างกัน"),
        ("Pretraining", "การฝึก encoder ก่อนงาน classification หลัก"),
        ("Fine-tuning", "การปรับน้ำหนักที่ pretrain แล้วให้เหมาะกับ task หลัก"),
        ("Baseline", "โมเดลหรือวิธีง่ายที่ใช้เป็นจุดอ้างอิง"),
        ("Ablation study", "การตัดองค์ประกอบของระบบออกทีละส่วนเพื่อดูว่าส่วนใดช่วยจริง"),
        ("Subject-wise split", "การแบ่งข้อมูลโดยไม่ให้ subject เดียวกันอยู่หลายชุด"),
        ("Data leakage", "ข้อมูลจาก test หรือ validation รั่วเข้าไปช่วย training/model selection"),
        ("Generalization", "ความสามารถของโมเดลในการทำงานกับข้อมูลหรือ subject ที่ไม่เคยเห็น"),
        ("Class imbalance", "จำนวนตัวอย่างแต่ละ class ไม่เท่ากัน"),
        ("Macro-F1", "ค่าเฉลี่ย F1 ของทุก class โดยให้น้ำหนักเท่ากัน"),
        ("Cohen's kappa", "ตัววัด agreement ที่หัก agreement ที่เกิดโดยบังเอิญ"),
        ("Cross-dataset evaluation", "ทดสอบโมเดลบน dataset ที่ต่างจาก dataset ตอน train"),
    ]
    add_table(doc, ["Term", "คำอธิบาย"], glossary, [2500, 6860], font_size=9.7)


def add_references(doc):
    add_heading(doc, "9. แหล่งข้อมูลและงานวิจัยอ้างอิง", 1)
    add_body(doc, "ลิงก์ทั้งหมดถูกรวมไว้ในไฟล์ research_links.md ของโครงงาน โดยรายการสำคัญมีดังนี้")
    refs = [
        ("Sleep-EDF Expanded — PhysioNet", "https://physionet.org/content/sleep-edfx/1.0.0/"),
        ("Research paper หลัก: SST + CNN + contrastive learning + GRU", "https://www.nature.com/articles/s41598-026-62832-5"),
        ("Rhythm representation and contrastive learning", "https://www.sciencedirect.com/science/article/pii/S1746809425011346"),
        ("MultiScaleSleepNet", "https://www.mdpi.com/1424-8220/25/20/6328"),
        ("SleepFocalNet", "https://link.springer.com/article/10.1007/s10044-025-01475-0"),
        ("MNE-Python documentation", "https://mne.tools/stable/index.html"),
        ("PyTorch documentation", "https://pytorch.org/"),
        ("WFDB Python documentation", "https://wfdb.readthedocs.io/en/latest/"),
    ]
    for name, url in refs:
        p = doc.add_paragraph(style="List Bullet")
        set_paragraph_spacing(p, after=4, line=1.2)
        r = p.add_run(name + ": ")
        set_run_font(r, bold=True, color=NAVY)
        add_hyperlink(p, "เปิดแหล่งข้อมูล", url)

    add_heading(doc, "10. Final takeaway", 1)
    add_body(doc, "แก่นของงานนี้ไม่ใช่แค่การสร้างโมเดลที่คะแนนสูง แต่คือการออกแบบการทดลองที่ยุติธรรมและตอบคำถามวิจัยได้ชัดเจน เราต้องรู้ว่า EEG เพียงหนึ่ง channel มีข้อมูลพอแค่ไหน, SST ช่วยอย่างไร, contrastive learning ช่วยหรือไม่, GRU ช่วยด้านใด และคะแนนที่ได้ยังอยู่เมื่อทดสอบกับ subject ใหม่หรือไม่")
    add_body(doc, "ถ้าทำตามลำดับตั้งแต่ baseline -> SST -> contrastive -> GRU พร้อม subject-wise split และรายงานผลหลายมิติ งานจะมีทั้งความเข้าใจเชิงสัญญาณ, ความเข้าใจเชิงโมเดล และหลักฐานเชิงการทดลองที่น่าเชื่อถือ")
    add_callout(doc, "ประโยคสุดท้าย", "เรากำลังสร้างระบบที่เรียนรู้ sleep architecture จากรูปแบบไฟฟ้าของสมอง ไม่ใช่เพียงจำ label จากข้อมูลเดิม และคุณภาพของการแบ่งข้อมูลมีความสำคัญพอ ๆ กับ architecture ของโมเดล", fill="E8EEF5", accent=NAVY)


def build_markdown():
    text = """# Sleep Stage Classification from Single-Channel EEG

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
"""
    MD_PATH.write_text(text, encoding="utf-8")


def build_docx():
    create_pipeline_image()
    doc = Document()
    configure_document(doc)
    add_cover(doc)
    add_intro_and_map(doc)
    add_foundations(doc)
    add_data(doc)
    add_objectives(doc)
    add_method(doc)
    add_evaluation(doc)
    add_limitations(doc)
    add_plan(doc)
    add_glossary(doc)
    add_references(doc)
    doc.core_properties.title = "Sleep Stage Classification from Single-Channel EEG"
    doc.core_properties.subject = "Thai explanatory research guide"
    doc.core_properties.author = "Codex"
    doc.save(DOCX_PATH)
    build_markdown()


if __name__ == "__main__":
    build_docx()
    print(DOCX_PATH)
    print(MD_PATH)
    print(PIPELINE_PATH)

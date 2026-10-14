"""Export only the research reader; never execute code or publish the dashboard."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image

from build_course import CHAPTERS, ROOT, build

SITE = Path('E:/blp/sleep_stage_reproduction/public-reader-site')
BULK = Path('E:/blp/sleep_stage_reproduction')
NOTICE = ('ฉบับเผยแพร่สาธารณะ: เปลี่ยนเส้นทางไฟล์เฉพาะเครื่องเป็น project/, artifacts/ และ user-home/ '
          'แต่คงตัวเลขและภาพผลการทดลองเดิมไว้ ไฟล์ notebook ที่ดาวน์โหลดเป็นฉบับเผยแพร่ '
          'ต้องมีโค้ดประกอบและข้อมูลวิจัยจึงจะรันเองได้ เว็บไซต์นี้ไม่เชื่อมกับเครื่องผู้วิจัย')
FIGURE_NOTE = ('ข้อควรระวังในการอ่านภาพบท 05: คลื่น EEG/STFT ด้านซ้ายและ SST cache ด้านขวา '
               'เป็นคนละช่วงเวลาในบันทึกเดียวกัน ใช้อธิบายรูปแบบข้อมูล ไม่ใช่ภาพก่อน–หลังของ epoch เดียวกัน '
               'ค่า magnitude ผ่าน normalization แล้ว จึงไม่ใช่กำลังสัญญาณในหน่วยกายภาพ')


def redact_text(value):
    replacements = [(str(ROOT.parent), 'project'), (str(BULK), 'artifacts'),
                    (str(Path.home()), 'user-home')]
    for original, replacement in replacements:
        for variant in (original, original.replace('\\', '/')):
            value = value.replace(variant, replacement)
    value = re.sub(r'/home/[^/\s]+', 'user-home', value)
    return value.replace('published cache manifest on E:', 'published cache manifest in artifacts/')


def public_copy(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [public_copy(item) for item in value]
    if isinstance(value, dict):
        # Binary evidence is kept byte-identical, not passed through text redaction.
        result = {}
        for key, item in value.items():
            public_key = redact_text(key)
            if public_key in result:
                raise ValueError('Redaction would produce duplicate metadata keys')
            result[public_key] = item if key == 'image/png' else public_copy(item)
        return result
    return value


def text_fields(value):
    """Read semantic JSON text, not JSON escapes or base64-encoded images."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, bytes):
        yield value.decode('utf-8', errors='replace')
    elif isinstance(value, list):
        for item in value:
            yield from text_fields(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            if key != 'image/png':
                yield from text_fields(item)


PRIVATE_PATTERN = re.compile(
    r'(?<![a-z])[a-z]:[\\/]|\\\\[^\\\s]+\\|OneDrive|/home/|/root/|/Users/|/mnt/|'
    r'127\.0\.0\.1|localhost|Quant OS|/#sleepstage|/api/|BEGIN .{0,20}PRIVATE KEY|'
    r'Bearer\s+[A-Za-z0-9_.-]{12,}|(?:sk-|ghp_)[A-Za-z0-9_-]{20,}', re.I)


def reject_private(value, relative):
    if any(PRIVATE_PATTERN.search(text) for text in text_fields(value)):
        raise ValueError(f'Private path, endpoint, or credential pattern in {relative}')


class Links(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.elements = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def validate_public(dest):
    dest = Path(dest).resolve()
    expected = {'index.html', 'course.css', 'course.js', 'manifest.json'}
    expected.update('notebooks/' + Path(name).stem + '.json' for name, _, _ in CHAPTERS)
    manifest = json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))
    expected.update(manifest['figure_sha256'])
    files = {p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()}
    if files != expected:
        raise ValueError(f'Unexpected/missing public assets: {files ^ expected}')
    for relative in files:
        path = dest / relative
        if path.is_symlink():
            raise ValueError('Public symlinks are not allowed')
        if path.suffix == '.png':
            with Image.open(path) as picture:
                reject_private(picture.info, relative)
                picture.verify()
        elif path.suffix == '.json':
            reject_private(json.loads(path.read_bytes()), relative)
        else:
            reject_private(path.read_text(encoding='utf-8'), relative)
    page = (dest / 'index.html').read_text(encoding='utf-8')
    elements = Links(page).elements
    ids = {attrs['id'] for _, attrs in elements if 'id' in attrs}
    for tag, attrs in elements:
        if tag in {'iframe', 'form'} or any(k.lower().startswith('on') for k in attrs):
            raise ValueError('Unexpected active content')
        for key in ('href', 'src'):
            value = attrs.get(key, '')
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                if key == 'src' or parsed.scheme != 'https':
                    raise ValueError(f'Unexpected external resource: {value}')
                continue
            if parsed.path:
                target = (dest / unquote(parsed.path)).resolve()
                if not target.is_relative_to(dest) or not target.is_file():
                    raise ValueError(f'Unresolved/out-of-scope link: {value}')
            elif parsed.fragment and parsed.fragment not in ids:
                raise ValueError(f'Unresolved anchor: {value}')
    return {'files': len(files), 'chapters': len(manifest['chapters']),
            'figures': manifest['total_figures'], 'bytes': sum((dest / name).stat().st_size for name in files)}


def build_public(dest=SITE / 'dist'):
    dest = Path(dest)
    # Avoid silently publishing stale files from a previous export.
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Use a fresh empty export directory; existing output is preserved')
    originals = {}
    with tempfile.TemporaryDirectory(prefix='public-course-source-', dir=BULK) as temporary:
        staging = Path(temporary)
        for filename, _, _ in CHAPTERS:
            source = ROOT / 'notebooks' / filename
            original = source.read_bytes()
            originals[filename] = hashlib.sha256(original).hexdigest()
            notebook = public_copy(json.loads(original))
            # Keep only standard kernel metadata, not local execution environment details.
            notebook['metadata'] = {k: v for k, v in notebook.get('metadata', {}).items()
                                    if k in {'kernelspec', 'language_info'}}
            target = staging / filename
            target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            os.utime(target, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns))
        manifest = build(notebooks=staging, dest=dest)
    manifest['schema'] = 'sleep_stage_public_course_export_v1'
    manifest['public_edition'] = True
    manifest['privacy_note'] = NOTICE
    manifest['interpretation_note'] = FIGURE_NOTE
    for chapter in manifest['chapters']:
        chapter['original_source_sha256'] = originals[chapter['source']]
        chapter['public_notebook_sha256'] = chapter['sha256']
    manifest['figure_sha256'] = {p.relative_to(dest).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((dest / 'figures').glob('*.png'))}
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    page = (dest / 'index.html').read_text(encoding='utf-8')
    page = page.replace(' | Quant OS', ' | Public Edition')
    page = page.replace('<a class="back-link" href="/#sleepstage" target="_top">Quant OS ↗</a>', '')
    page = page.replace('QUANT OS / RESEARCH LIBRARY', 'SLEEP STAGE / PUBLIC RESEARCH LIBRARY')
    page = page.replace('ดาวน์โหลด notebook ↗', 'ดาวน์โหลด notebook ฉบับเผยแพร่ ↗')
    page = page.replace('โค้ดต้นฉบับ', 'โค้ด · ฉบับเผยแพร่')
    page = page.replace('SHA-256:', 'SHA-256 ของฉบับเผยแพร่:')
    page = page.replace('เว็บไซต์คัดลอกเซลล์และผลที่บันทึกไว้ ไม่มีการเรียก Python หรือเริ่ม training', NOTICE)
    page = page.replace('<div class="reading-toolbar">', f'<div class="snapshot-note"><strong>เกี่ยวกับฉบับเผยแพร่</strong><p>{NOTICE}</p></div><div class="reading-toolbar">')
    page = page.replace('<article id="chapter-05"', f'<aside class="snapshot-note"><strong>หมายเหตุการตีความภาพ</strong><p>{FIGURE_NOTE}</p></aside><article id="chapter-05"')
    page = page.replace('<meta name="color-scheme"', '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; connect-src \'none\'; frame-src \'none\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'"><meta name="referrer" content="no-referrer"><meta name="color-scheme"')
    (dest / 'index.html').write_text(page, encoding='utf-8')
    return validate_public(dest)


if __name__ == '__main__':
    print(json.dumps(build_public(), ensure_ascii=False))

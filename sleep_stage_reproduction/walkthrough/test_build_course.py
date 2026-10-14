"""Focused read-only export tests; no notebook execution or research artifact writes."""
import base64
import hashlib
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_course import CHAPTERS, ROOT, build, highlight_python, render_output, safe_html


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class CourseExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sleep-course-test-")
        cls.dest = Path(cls.temporary.name)
        cls.manifest = build(dest=cls.dest)
        cls.html = (cls.dest / "index.html").read_text(encoding="utf-8")
        cls.elements = Elements(cls.html).elements

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_six_ordered_chapters(self):
        ids = [a["id"] for t, a in self.elements if t == "article"]
        self.assertEqual(ids, [f"chapter-{i:02}" for i in range(6)])
        self.assertFalse(self.manifest["training_performed"])
        self.assertFalse(self.manifest["notebook_execution_performed"])

    def test_all_cells_and_outputs_exported(self):
        cell_elements = [a for _, a in self.elements if "data-cell-type" in a]
        outputs = [a for _, a in self.elements if "data-output-index" in a]
        self.assertEqual(len(cell_elements), self.manifest["total_cells"])
        self.assertEqual(len(outputs), sum(c["outputs"] for c in self.manifest["chapters"]))
        for record in self.manifest["chapters"]:
            for index in range(record["cells"]):
                self.assertTrue(any(a.get("id") == f'{record["id"]}-cell-{index}' for a in cell_elements))

    def test_notebook_downloads_and_hashes_are_exact(self):
        for record in self.manifest["chapters"]:
            source = ROOT / "notebooks" / record["source"]
            data = source.read_bytes()
            self.assertEqual(record["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(data, (self.dest / "notebooks" / (source.stem + ".json")).read_bytes())

    def test_all_png_outputs_are_byte_identical(self):
        count = 0
        for filename, _, _ in CHAPTERS:
            notebook = json.loads((ROOT / "notebooks" / filename).read_bytes())
            for ci, cell in enumerate(notebook["cells"]):
                for oi, output in enumerate(cell.get("outputs", [])):
                    data = output.get("data", {}).get("image/png")
                    if data:
                        name = f"{Path(filename).stem}-cell{ci:02}-out{oi:02}.png"
                        self.assertEqual((self.dest / "figures" / name).read_bytes(), base64.b64decode("".join(data)))
                        count += 1
        self.assertEqual(count, self.manifest["total_figures"])

    def test_links_assets_and_anchors_resolve(self):
        ids = {a["id"] for _, a in self.elements if "id" in a}
        for _, attrs in self.elements:
            for key in ("href", "src"):
                value = attrs.get(key, "")
                if not value or value.startswith("/") or urlsplit(value).scheme:
                    continue
                parsed = urlsplit(value)
                if parsed.path:
                    self.assertTrue((self.dest / unquote(parsed.path)).is_file(), value)
                if parsed.fragment and not parsed.path:
                    self.assertIn(parsed.fragment, ids)

    def test_figure_accessibility_and_reserved_dimensions(self):
        images = [a for tag, a in self.elements if tag == "img"]
        self.assertEqual(len(images), 12)
        for image in images:
            self.assertTrue(image["alt"])
            self.assertGreater(int(image["width"]), 0)
            self.assertGreater(int(image["height"]), 0)
            self.assertEqual(image["loading"], "lazy")

    def test_no_inline_script_handlers_or_remote_runtime(self):
        for tag, attrs in self.elements:
            self.assertFalse(any(a.lower().startswith("on") for a in attrs))
            if tag == "script":
                self.assertEqual(urlsplit(attrs.get("src", "")).path, "course.js")
        self.assertEqual(len(re.findall(r"<script\b", self.html)), 1)

    def test_html_output_sanitization(self):
        value = safe_html('<script>alert(1)</script><a href="javascript:alert(1)" onclick="bad()">x</a><iframe src="/api/export"></iframe><table><tr><td>ok</td></tr></table>')
        self.assertNotIn("<script", value)
        self.assertNotIn("<iframe", value)
        self.assertNotIn("javascript:", value)
        self.assertNotIn("onclick", value)
        self.assertIn("<td>ok</td>", value)

    def test_stream_output_is_escaped(self):
        value, count = render_output({"output_type": "stream", "text": '<img src=x onerror="bad()">'}, "sample", 0, 0, self.dest, "example")
        self.assertIn("&lt;img", value)
        self.assertNotIn("<img", value)
        self.assertEqual(count, 0)

    def test_errors_visible_and_unknown_mime_fails(self):
        value, _ = render_output({"output_type": "error", "ename": "ValueError", "evalue": "example"}, "sample", 0, 0, self.dest, "example")
        self.assertIn("ValueError: example", value)
        with self.assertRaises(ValueError):
            render_output({"output_type": "display_data", "data": {"application/x-unknown": "sample"}}, "sample", 0, 0, self.dest, "example")

    def test_syntax_highlighting_preserves_every_source_character(self):
        class TextContent(HTMLParser):
            def __init__(self, rendered):
                super().__init__()
                self.parts = []
                self.feed(rendered)

            def handle_data(self, data):
                self.parts.append(data)

        samples = ['', '\n\n  x = 2\r\n', '# ภาษาไทย\nx = "<script>alert(1)</script>"', 'def unfinished(']
        for filename, _, _ in CHAPTERS:
            notebook = json.loads((ROOT / "notebooks" / filename).read_bytes())
            samples.extend("".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code")
        for source in samples:
            self.assertEqual("".join(TextContent(highlight_python(source)).parts), source)

    def test_syntax_roles_and_safe_escaping(self):
        source = 'def greet(name):\n    # note\n    return print("<img onerror=bad()>", name, 42)\ngreet("hello")'
        rendered = highlight_python(source)
        for kind in ['keyword', 'function', 'name', 'comment', 'builtin', 'string', 'number']:
            self.assertIn(f'class="syntax-{kind}"', rendered)
        self.assertNotIn('<img', rendered)
        for tag, attrs in Elements(rendered).elements:
            self.assertEqual(tag, 'span')
            self.assertEqual(list(attrs), ['class'])

    def test_dark_default_and_color_contrast(self):
        self.assertIn('data-theme="dark"', self.html)
        css = (self.dest / 'course.css').read_text(encoding='utf-8')

        def luminance(color):
            channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))

        for selector in [':root', ':root[data-theme="light"]']:
            block = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', css).group(1)
            colors = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-f]{6})', block))
            for name, color in colors.items():
                if not (name.startswith('syntax-') or name in ('text', 'muted', 'accent')):
                    continue
                background = colors['code'] if name.startswith('syntax-') else colors['page']
                light, dark = sorted([luminance(color), luminance(background)], reverse=True)
                self.assertGreaterEqual((light + .05) / (dark + .05), 4.5, f'{selector} {name}')


if __name__ == "__main__":
    unittest.main()

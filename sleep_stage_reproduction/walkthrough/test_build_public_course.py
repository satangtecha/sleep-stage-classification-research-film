"""Public export checks: privacy boundaries, provenance, and unchanged evidence."""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from build_public_course import BULK, CHAPTERS, ROOT, build_public, public_copy, redact_text, reject_private, validate_public


class PublicExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='public-export-test-', dir=BULK)
        cls.dest = Path(cls.temp.name) / 'dist'
        cls.before = {name: (ROOT / 'notebooks' / name).read_bytes() for name, _, _ in CHAPTERS}
        cls.result = build_public(cls.dest)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_public_assets_and_provenance(self):
        self.assertEqual(self.result['files'], 22)
        self.assertEqual(self.result['chapters'], 6)
        manifest = json.loads((self.dest / 'manifest.json').read_bytes())
        for item in manifest['chapters']:
            name = item['source']
            data = (self.dest / 'notebooks' / (Path(name).stem + '.json')).read_bytes()
            self.assertEqual(item['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(item['original_source_sha256'], hashlib.sha256(self.before[name]).hexdigest())
            self.assertEqual((ROOT / 'notebooks' / name).read_bytes(), self.before[name])
        self.assertFalse(manifest['training_performed'])
        self.assertFalse(manifest['notebook_execution_performed'])

    def test_images_and_numerical_evidence_unchanged(self):
        count = 0
        for name, _, _ in CHAPTERS:
            original = json.loads(self.before[name])
            public = json.loads((self.dest / 'notebooks' / (Path(name).stem + '.json')).read_bytes())
            self.assertEqual(len(original['cells']), len(public['cells']))
            for ci, (old, new) in enumerate(zip(original['cells'], public['cells'])):
                self.assertEqual(old.get('execution_count'), new.get('execution_count'))
                self.assertEqual(''.join(new['source']), redact_text(''.join(old['source'])))
                for oi, (a, b) in enumerate(zip(old.get('outputs', []), new.get('outputs', []))):
                    if 'text' in a:
                        self.assertEqual(''.join(b['text']), redact_text(''.join(a['text'])))
                    if 'image/png' in a.get('data', {}):
                        raw = base64.b64decode(''.join(a['data']['image/png']))
                        self.assertEqual(a['data']['image/png'], b['data']['image/png'])
                        self.assertEqual(raw, (self.dest / 'figures' / f'{Path(name).stem}-cell{ci:02}-out{oi:02}.png').read_bytes())
                        count += 1
        self.assertEqual(count, 12)

    def test_redaction_and_disclosures(self):
        self.assertEqual(redact_text(str(ROOT.parent) + '/data'), 'project/data')
        self.assertEqual(redact_text(str(BULK) + '/runs'), 'artifacts/runs')
        self.assertEqual(redact_text('/home/example/.cache'), 'user-home/.cache')
        page = (self.dest / 'index.html').read_text(encoding='utf-8')
        for text in ('ฉบับเผยแพร่', 'คนละช่วงเวลา', 'ไม่ใช่หน้ารันสด', 'connect-src', 'Public Edition'):
            self.assertIn(text, page)
        self.assertNotIn('Quant OS', page)

    def test_fail_closed_stale_or_extra_files(self):
        with self.assertRaises(ValueError):
            build_public(self.dest)
        extra = self.dest / 'private.sqlite'
        extra.write_bytes(b'not for publication')
        try:
            with self.assertRaises(ValueError):
                validate_public(self.dest)
        finally:
            extra.unlink()
        self.assertEqual(validate_public(self.dest)['files'], 22)

    def test_private_paths_in_keys_values_and_image_metadata(self):
        for value in [r'D:\private\secret', r'Z:/Users/name', r'\\server\share\file', '/root/private',
                      {'D:/secret': 1}, {'Description': 'Saved by /Users/name/Desktop/tool'},
                      {'Comment': 'Bearer ' + 'a' * 30}]:
            with self.assertRaises(ValueError):
                reject_private(value, 'test asset')
        self.assertEqual(public_copy({str(ROOT.parent): 1}), {'project': 1})
        reject_private({'text': 'Chunk size: 128', 'image/png': 'ignored-binary-payload'}, 'safe')


if __name__ == '__main__':
    unittest.main()

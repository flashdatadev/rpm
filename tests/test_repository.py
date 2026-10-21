"""Distribution invariants; native integration tests exercise actual RPM/DNF trust."""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_signed_package_ledger(self):
        ledger = json.loads((ROOT / 'manifest.json').read_text())['releases']
        expected = set()
        for release in ledger:
            for arch in ('x86_64', 'aarch64'):
                name = f"flashdata-{release['version']}-{release['release']}.{arch}.rpm"
                expected.add(name)
                self.assertEqual(hashlib.sha256((ROOT / 'packages' / name).read_bytes()).hexdigest(), release['packages'][arch])
                self.assertRegex(release['executables'][arch], r'^[a-f0-9]{64}$')
        self.assertEqual(expected, {p.name for p in (ROOT / 'packages').glob('*.rpm')})

    def test_bilingual_install_and_configuration(self):
        english, chinese = [(ROOT / p).read_text(encoding='utf-8') for p in ('README.md', 'README.zh-CN.md')]
        blocks = lambda t: re.findall(r'```bash\n(.*?)```', t, re.S)
        self.assertEqual(blocks(english), blocks(chinese))
        fingerprint = (ROOT / 'keys/fingerprint.txt').read_text().strip()
        self.assertRegex(fingerprint, r'^[A-F0-9]{40}$')
        self.assertIn(f'expected={fingerprint}', blocks(english)[0])
        config = blocks(english)[0].split("<<'EOF'\n", 1)[1].split('\nEOF', 1)[0] + '\n'
        self.assertEqual(config, (ROOT / 'web/flashdata.repo').read_text())
        self.assertIn('[简体中文](README.zh-CN.md)', english.splitlines()[2])
        for path in ROOT.rglob('*.md'):
            if '.git' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            self.assertIn('https://flashdata.dev', text, str(path))
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if ':' not in target and not target.startswith('#'):
                    self.assertTrue((path.parent / target.split('#')[0]).exists(), (path, target))

    @unittest.skipUnless(shutil.which('createrepo_c'), 'native createrepo_c required')
    def test_index_contents_and_immutable_hash_names(self):
        import gzip
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory(prefix='rpm-metadata-test-') as directory:
            outputs = [pathlib.Path(directory) / name for name in ('first', 'second')]
            for output in outputs:
                subprocess.run([sys.executable, str(ROOT / 'scripts/build_repository.py'), '--output', str(output)], check=True, capture_output=True)
            for arch in ('x86_64', 'aarch64'):
                indexes = []
                for output in outputs:
                    folder = output / 'stable' / arch / 'repodata'
                    entries = {p.name: p.read_bytes() for p in folder.iterdir() if p.name != 'repomd.xml'}
                    indexes.append(entries)
                    primary = next(p for p in folder.iterdir() if p.name.endswith('-primary.xml.gz'))
                    packages = ET.fromstring(gzip.decompress(primary.read_bytes()))
                    ns = {'p': 'http://linux.duke.edu/metadata/common'}
                    self.assertEqual(len(packages), 1)
                    package = packages.find('p:package', ns)
                    self.assertEqual(package.find('p:name', ns).text, 'flashdata')
                    self.assertEqual(package.find('p:version', ns).attrib['rel'], '1')
                    self.assertNotIn('upgradetest', gzip.decompress(primary.read_bytes()).decode())
                    location = package.find('p:location', ns).attrib['href']
                    data = (output / 'stable' / arch / location).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), package.find('p:checksum', ns).text)
                self.assertEqual(indexes[0], indexes[1], 'hash-named indexes must remain byte-identical')


if __name__ == '__main__':
    unittest.main()

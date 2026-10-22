"""Stage a reviewed pending release for bootstrap without changing the sealed ledger."""
import json
import re

from common import ROOT, ARCHES


def main():
    pending = ROOT / 'pending-release.json'
    if not pending.exists():
        return
    candidate = json.loads(pending.read_text())
    ledger = ROOT / 'manifest.json'
    manifest = json.loads(ledger.read_text())
    assert re.fullmatch(r'\d+\.\d+\.\d+', candidate['version'])
    assert re.fullmatch(r'[1-9]\d*', candidate['release'])
    assert re.fullmatch(r'[0-9a-f]{40}', candidate['source_commit'])
    assert isinstance(candidate['source_date_epoch'], int) and candidate['source_date_epoch'] > 0
    assert candidate['packages'] == {}, 'Only unsigned new versions can be staged'
    assert all((r['version'], r['release']) != (candidate['version'], candidate['release']) for r in manifest['releases']), 'Never overwrite a sealed release'
    for kind in ['archives', 'executables']:
        assert set(candidate[kind]) == set(ARCHES)
        assert all(re.fullmatch(r'[a-f0-9]{64}', value) for value in candidate[kind].values())
    manifest['releases'].append(candidate)
    ledger.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Staged pending release ' + candidate['version'] + '-' + candidate['release'])


if __name__ == '__main__':
    main()
